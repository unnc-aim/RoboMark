"""每次领取的持久执行记录；图片仅保留引用，不复制 Base64 或接口凭据。"""
import json
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from app.core.database import get_db

SENSITIVE = re.compile(r'^(?:authorization|.*api[-_]?key|(?:access|refresh|auth)[-_]?token|token|secret|password|cookie|set-cookie|credentials?|auth)$', re.I)


def sanitize(value, credentials=None, image_base64=None):
    credentials = credentials or {}
    secrets = [credentials.get('api_key'), *credentials.get('headers', {}).values()]

    def clean(obj):
        if isinstance(obj, dict):
            return {k: '[已隐藏]' if SENSITIVE.search(k) else clean(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [clean(v) for v in obj]
        if isinstance(obj, str):
            obj = re.sub(r'data:image/[^;\s]+;base64,[A-Za-z0-9+/=]+', '[图片内容，见原图]', obj)
            if image_base64:
                obj = obj.replace(image_base64, '[图片 Base64，见原图]')
            for secret in secrets:
                if secret:
                    obj = obj.replace(secret, '[已隐藏]')
            return obj
        return obj
    return clean(value)


def safe_endpoint(endpoint):
    parts = urlsplit(endpoint)
    return urlunsplit((parts.scheme, parts.netloc, parts.path,
                       urlencode([(key, '[已隐藏]') for key, _ in parse_qsl(parts.query)]), ''))


def start_attempt(c, item_id, token):
    c.execute('SELECT COALESCE(MAX(sequence_number),0)+1 AS n FROM preannotation_attempts WHERE task_image_id=%s', (item_id,))
    seq = c.fetchone()['n']
    c.execute("INSERT INTO preannotation_attempts (task_image_id,sequence_number,claim_token,trace) VALUES (%s,%s,%s,%s)",
              (item_id, seq, token, '{}'))


def record_event(claim, stage, data):
    if stage not in ('request', 'response_headers', 'response', 'parsed', 'normalized'):
        raise ValueError('未知推理阶段')
    event = {'at': datetime.now(timezone.utc).isoformat(), 'data': data}
    with get_db() as conn, conn.cursor() as c:
        # 与领取、取消、提交结果保持相同锁顺序，避免记录阶段与取消互锁。
        c.execute('SELECT id FROM preannotation_tasks WHERE id=%s FOR UPDATE', (claim['task']['id'],))
        c.execute("""UPDATE preannotation_attempts a JOIN preannotation_task_images ti ON ti.id=a.task_image_id
                     SET a.trace=JSON_SET(a.trace,%s,CAST(%s AS JSON))
                     WHERE a.claim_token=%s AND a.status='running' AND ti.claim_token=%s
                     AND ti.execution_status='running' AND ti.lease_until>NOW(6)""",
                  ('$.'+stage, json.dumps(event, ensure_ascii=False), claim['token'], claim['token']))


def finish_attempt(c, token, status, code=None, message=None):
    c.execute("""UPDATE preannotation_attempts SET status=%s,error_code=%s,error_message=%s,finished_at=NOW(6)
                 WHERE claim_token=%s AND status='running'""", (status, code, message, token))


def archive_legacy_attempt(c, item):
    """重试旧图片前只保存已有错误/响应，不能伪造其实际请求和耗时。"""
    if not item['error_code'] and not item['raw_response']:
        return
    c.execute('SELECT id FROM preannotation_attempts WHERE task_image_id=%s LIMIT 1', (item['id'],))
    if c.fetchone():
        return
    trace = {'legacy': True}
    if item['raw_response']:
        trace['response'] = {'data': {'raw': item['raw_response']}}
    c.execute("""INSERT INTO preannotation_attempts
                 (task_image_id,sequence_number,claim_token,status,trace,error_code,error_message,finished_at)
                 VALUES (%s,%s,%s,'failed',%s,%s,%s,NOW(6))""",
              (item['id'],max(1,item['attempts']),str(uuid.uuid4()),json.dumps(trace),item['error_code'],item['error_message']))
