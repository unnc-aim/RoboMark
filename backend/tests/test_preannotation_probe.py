import asyncio
import json

import httpx
import pytest
from app.services.preannotation_probe import probe_connection

CONFIG = {'endpoint':'http://localhost:8001/v1/chat/completions','interface_type':'openai','model':'vision-model'}
CREDENTIALS = {'api_key':'secret-key','headers':{'X-Token':'secret-header'}}


def probe(handler, config=None, **kwargs):
    return asyncio.run(probe_connection(config or CONFIG, CREDENTIALS, transport=httpx.MockTransport(handler), **kwargs))


def test_openai_probe_verifies_models_and_credentials_without_inference():
    requests=[]
    def handler(request):
        requests.append(request)
        assert request.headers['Authorization']=='Bearer secret-key'
        assert request.headers['X-Token']=='secret-header'
        return httpx.Response(200,json={'data':[{'id':'vision-model'}]})
    result=probe(handler)
    assert result['ok'] and result['reachable'] and result['authentication_verified'] and result['model_available']
    assert result['models']==['vision-model'] and result['latency_ms']>=0
    assert [(r.method,r.url.path) for r in requests]==[('GET','/v1/models')]


@pytest.mark.parametrize('status',[401,403])
def test_authentication_error_distinguished_from_network_failure(status):
    result=probe(lambda request:httpx.Response(status,text='private service response secret-key'))
    assert result['reachable'] and not result['ok']
    assert result['status']=='authentication_failed' and result['http_status']==status
    assert 'secret-key' not in json.dumps(result)


def test_unsupported_models_route_falls_back_to_non_generating_probe():
    methods=[]
    def handler(request):
        methods.append((request.method,request.url.path))
        return httpx.Response(404 if request.method=='GET' else 405)
    result=probe(handler)
    assert result['status']=='reachable' and result['reachable']
    assert not result['authentication_verified'] and not result['ok']
    assert methods==[('GET','/v1/models'),('HEAD','/v1/chat/completions')]


def test_generic_interface_probe_checks_reachability_only():
    def handler(request):
        assert request.method=='HEAD' and request.url.path=='/custom'
        return httpx.Response(200)
    result=probe(handler,{'endpoint':'http://localhost:8001/custom','interface_type':'http_json'})
    assert result['reachable'] and result['status']=='reachable' and not result['authentication_verified']


@pytest.mark.parametrize('response,expected',[
    (httpx.Response(200,json={'data':[{'id':'other-model'}]}),'model_not_found'),
    (httpx.Response(200,json={'data':[]}),'no_models'),
    (httpx.Response(200,text='<html>frontend</html>'),'unexpected_response'),
    (httpx.Response(500),'http_error'),
    (httpx.Response(302,headers={'Location':'http://other-server/'}),'redirect'),
])
def test_wrong_model_format_and_service_errors(response,expected):
    result=probe(lambda request:response)
    assert result['status']==expected and result['reachable'] and not result['ok']


def test_network_failure_is_safe_to_display():
    def handler(request):
        raise httpx.ConnectError('sensitive-url?token=secret-key',request=request)
    result=probe(handler)
    assert result['status']=='network_error' and not result['reachable']
    assert 'secret-key' not in json.dumps(result)


def test_probe_has_total_time_limit():
    async def handler(request):
        await asyncio.sleep(.1)
        return httpx.Response(200,json={'data':[]})
    result=probe(handler,timeout_seconds=.01)
    assert result['status']=='timeout' and not result['reachable']


def test_model_list_does_not_echo_credentials():
    result=probe(lambda request:httpx.Response(200,json={'data':[{'id':'secret-key'},{'id':'secret-header'}]}))
    assert 'secret-key' not in json.dumps(result) and 'secret-header' not in json.dumps(result)
