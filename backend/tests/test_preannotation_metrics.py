import pytest
from app.services.preannotation_metrics import inference_metrics


def test_usage_tokens_and_tps_are_per_request_not_total_usage():
    result=inference_metrics({'prompt_tokens':1280,'completion_tokens':256,'total_tokens':1536},2000)
    assert result=={'input_tokens':1280,'output_tokens':256,'tps':128.0,'elapsed_ms':2000.0,'duration_source':'http'}


def test_response_style_aliases_and_zero_usage_are_preserved():
    result=inference_metrics('{"input_tokens":"10","output_tokens":0}',1000)
    assert result['input_tokens']==10 and result['output_tokens']==0 and result['tps']==0
    zero=inference_metrics({'prompt_tokens':0,'completion_tokens':0},1000)
    assert zero['input_tokens']==zero['output_tokens']==zero['tps']==0


@pytest.mark.parametrize('bad',[True,-1,1.5,float('nan'),float('inf'),{},[],2**53])
def test_invalid_token_counts_are_unknown_not_fabricated(bad):
    result=inference_metrics({'prompt_tokens':bad,'completion_tokens':bad},1000)
    assert result['input_tokens'] is None and result['output_tokens'] is None and result['tps'] is None


def test_no_usage_never_infers_breakdown_from_total_or_model_text():
    for usage in [None,'not-json',{'total_tokens':100},{'choices':[{'message':{'content':'{"usage":{"prompt_tokens":10,"completion_tokens":20}}'}}]}]:
        result=inference_metrics(usage,1000)
        assert result['input_tokens'] is None and result['output_tokens'] is None


def test_old_trace_timing_is_explicitly_an_estimate_and_http_timing_has_priority():
    result=inference_metrics({'completion_tokens':100},request_at='2026-10-20T00:00:00Z',response_at='2026-10-20T08:00:05+08:00')
    assert result['elapsed_ms']==5000 and result['tps']==20 and result['duration_source']=='trace'
    result=inference_metrics({'completion_tokens':100},1000,'bad','bad')
    assert result['tps']==100 and result['duration_source']=='http'


@pytest.mark.parametrize('elapsed',[0,-1,False,float('nan'),float('inf'),None])
def test_missing_or_invalid_timing_cannot_produce_tps(elapsed):
    result=inference_metrics({'prompt_tokens':10,'completion_tokens':20},elapsed)
    assert result['input_tokens']==10 and result['output_tokens']==20
    assert result['elapsed_ms'] is None and result['tps'] is None
