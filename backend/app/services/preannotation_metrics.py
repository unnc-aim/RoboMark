"""轻量用量统计。Token 只读取服务 usage，不从模型正文或总 Token 猜测。"""
import json
import math
from datetime import datetime


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        result = float(value)
    except (ValueError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _tokens(value):
    number = _number(value)
    if number is None or number < 0 or number > 2**53-1 or not number.is_integer():
        return None
    return int(number)


def _usage(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, RecursionError):
            return {}
    return value if isinstance(value, dict) else {}


def inference_metrics(usage=None, elapsed_ms=None, request_at=None, response_at=None):
    usage = _usage(usage)
    input_tokens = _tokens(usage.get('prompt_tokens'))
    output_tokens = _tokens(usage.get('completion_tokens'))
    if input_tokens is None:
        input_tokens = _tokens(usage.get('input_tokens'))
    if output_tokens is None:
        output_tokens = _tokens(usage.get('output_tokens'))
    elapsed = _number(elapsed_ms)
    source = 'http' if elapsed is not None and elapsed > 0 else None
    if source is None:
        elapsed = None
        if isinstance(request_at, str) and isinstance(response_at, str):
            try:
                duration = (datetime.fromisoformat(response_at.replace('Z','+00:00'))
                            - datetime.fromisoformat(request_at.replace('Z','+00:00'))).total_seconds()*1000
                if duration > 0:
                    elapsed, source = duration, 'trace'
            except (ValueError, TypeError, OverflowError):
                pass
    rate = output_tokens*1000/elapsed if output_tokens is not None and elapsed else None
    return {'input_tokens':input_tokens,'output_tokens':output_tokens,
            'tps':round(rate,2) if rate is not None and math.isfinite(rate) else None,
            'elapsed_ms':elapsed,'duration_source':source}


def attach_inference_metrics(c, rows):
    """一次批量查询本页最近成功尝试，仅提取小字段，不拉取原始正文或逐图查询。"""
    if not rows:
        return
    ids = [r['task_image_id'] for r in rows]
    marks = ','.join(['%s']*len(ids))
    c.execute(f"""SELECT a.task_image_id,
                 JSON_EXTRACT(a.trace,'$.parsed.data.usage') AS reported_usage,
                 JSON_EXTRACT(a.trace,'$.response.data.elapsed_ms') AS http_elapsed_ms,
                 JSON_UNQUOTE(JSON_EXTRACT(a.trace,'$.request.at')) AS request_at,
                 JSON_UNQUOTE(JSON_EXTRACT(a.trace,'$.response.at')) AS response_at
                 FROM preannotation_attempts a JOIN (
                   SELECT task_image_id,MAX(id) AS id FROM preannotation_attempts
                   WHERE task_image_id IN ({marks}) AND status='succeeded' GROUP BY task_image_id
                 ) latest ON a.id=latest.id""", ids)
    latest = {r['task_image_id']:r for r in c.fetchall()}
    for row in rows:
        legacy = row.pop('legacy_usage',None)
        attempt = latest.get(row['task_image_id'],{})
        usage = attempt.get('reported_usage')
        metrics = inference_metrics(usage,attempt.get('http_elapsed_ms'),attempt.get('request_at'),attempt.get('response_at'))
        # 老批次的 raw_response 有 usage 时可补 Token；没有耗时就不生成 TPS。
        old = inference_metrics(legacy)
        for name in ('input_tokens','output_tokens'):
            if metrics[name] is None:
                metrics[name] = old[name]
        if metrics['tps'] is None and metrics['output_tokens'] is not None and metrics['elapsed_ms']:
            rate = metrics['output_tokens']*1000/metrics['elapsed_ms']
            metrics['tps'] = round(rate,2) if math.isfinite(rate) else None
        row['inference_metrics'] = metrics
