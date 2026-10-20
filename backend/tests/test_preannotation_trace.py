import asyncio
import json
import hashlib
import httpx
from PIL import Image
from app.schemas.preannotation import ProfileInput
from app.services.preannotation_inference import infer, InferenceError
from app.services.preannotation_trace import sanitize, safe_endpoint


def test_trace_redacts_auth_and_images_but_preserves_model_parameters():
    encoded='aGVsbG93b3JsZA=='
    source={'max_tokens':8192,'api_key':'unknown-secret','body':{'image':'data:image/png;base64,'+encoded},
            'prompt':'secret-token in a prompt','access_token':'new-secret','plain_image':encoded}
    result=sanitize(source,{'api_key':'secret-token'},encoded)
    text=json.dumps(result)
    assert result['max_tokens']==8192
    assert 'secret-token' not in text and 'unknown-secret' not in text and 'new-secret' not in text
    assert encoded not in text
    assert 'key=abc' not in safe_endpoint('http://localhost/predict?key=abc')
    nested = sanitize({'content':'{"client_secret":"hidden-secret","X-Token":"hidden-token","max_tokens":8192}'})
    assert 'hidden-secret' not in nested['content'] and 'hidden-token' not in nested['content']
    assert json.loads(nested['content'])['max_tokens']==8192
    assert '[非有限数值' in sanitize({'bad':float('nan')})['bad']


def test_actual_request_response_and_provider_reasoning_are_recorded(tmp_path,monkeypatch):
    path=tmp_path/'image.png';Image.new('RGB',(20,20),'white').save(path)
    events=[];timeouts=[]
    box={'category_id':1,'x_center':.5,'y_center':.5,'width':.5,'height':.5}
    async def handler(request):
        body=json.loads(request.content)
        assert body['messages'][1]['content'][1]['image_url']['url'].startswith('data:image/png;base64,')
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'annotations':[box]}),'reasoning_content':'服务实际返回的说明'}}], 'usage':{'completion_tokens':20}})
    client=httpx.AsyncClient
    def factory(**kwargs):
        timeouts.append(kwargs['timeout'])
        return client(**kwargs,transport=httpx.MockTransport(handler))
    monkeypatch.setattr('app.services.preannotation_inference.httpx.AsyncClient',factory)
    async def emit(stage,data):events.append((stage,data))
    config=ProfileInput(name='trace',endpoint='http://localhost/v1/chat/completions').model_dump()
    result,_=asyncio.run(infer(config,{'api_key':'private-key'},str(path),'识别目标',[{'id':1,'name':'目标'}],'bbox',on_event=emit))
    assert len(result)==1
    assert [e[0] for e in events]==['request','response_headers','response','parsed','normalized']
    assert timeouts[0].read is None and timeouts[0].connect==120
    assert events[0][1]['body']['max_tokens']==8192
    assert events[0][1]['image']['sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
    assert events[0][1]['headers']['Authorization']=='[已隐藏]'
    assert 'base64,' not in json.dumps(events)
    assert events[3][1]['reasoning_content']=='服务实际返回的说明'
    assert events[2][1]['elapsed_ms'] > 0
    assert events[-1][1]['count']==1


def test_http_error_body_is_retained_for_diagnostics(tmp_path,monkeypatch):
    path=tmp_path/'image.png';Image.new('RGB',(20,20)).save(path)
    events=[]
    client=httpx.AsyncClient
    monkeypatch.setattr('app.services.preannotation_inference.httpx.AsyncClient',lambda **kw:client(**kw,transport=httpx.MockTransport(lambda req:httpx.Response(503,json={'error':'busy','api_key':'must-hide'}))))
    async def emit(stage,data):events.append((stage,data))
    config=ProfileInput(name='trace',endpoint='http://localhost/v1/chat/completions').model_dump()
    try:
        asyncio.run(infer(config,{},str(path),'识别目标',[{'id':1,'name':'目标'}],'bbox',on_event=emit))
        assert False,'503 must fail'
    except InferenceError as error:
        assert error.retryable and error.code=='http'
        assert 'busy' in error.raw_response and 'must-hide' not in error.raw_response
    assert events[-1][0]=='response' and events[-1][1]['http_status']==503
