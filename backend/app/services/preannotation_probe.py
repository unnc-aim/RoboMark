"""轻量连接探测，不提交图片或创建推理任务。"""
import asyncio
import json
import time
from urllib.parse import urlsplit, urlunsplit

import httpx
from app.services.preannotation_inference import redact


def probe_headers(credentials):
    headers = {"Accept": "application/json", **credentials.get("headers", {})}
    if credentials.get("api_key") and not any(k.lower() == "authorization" for k in headers):
        headers["Authorization"] = "Bearer " + credentials["api_key"]
    return headers


async def probe_connection(config, credentials, *, transport=None, timeout_seconds=10):
    started = time.perf_counter()
    endpoint = config["endpoint"]
    parsed = urlsplit(endpoint)
    models_url = None
    if config.get("interface_type") == "openai" and parsed.path.rstrip('/').endswith('/chat/completions'):
        path = parsed.path.rstrip('/')[:-len('/chat/completions')] + '/models'
        models_url = urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, ''))

    def result(status, message, *, ok=False, reachable=False, http_status=None, auth=False, model=None, models=None):
        return {"ok": ok, "reachable": reachable, "status": status, "message": message,
                "http_status": http_status, "authentication_verified": auth,
                "model_available": model, "models": [redact(name, credentials) for name in (models or [])],
                "latency_ms": round((time.perf_counter() - started) * 1000)}

    async def request():
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=False, trust_env=False, transport=transport) as client:
            urls = [("GET", models_url)] if models_url else []
            urls.append(("HEAD", endpoint))
            for method, url in urls:
                async with client.stream(method, url, headers=probe_headers(credentials)) as response:
                    status = response.status_code
                    if status in (401, 403):
                        return result("authentication_failed", f"服务可达，但认证失败（HTTP {status}），请检查 API Key 或请求头。", reachable=True, http_status=status)
                    if method == 'GET' and status in (404, 405, 501):
                        continue
                    if method == 'GET' and 200 <= status < 300:
                        chunks, size = [], 0
                        async for chunk in response.aiter_bytes():
                            size += len(chunk)
                            if size > 65536:
                                return result("unexpected_response", "服务可达，但模型列表响应过大，无法确认接口格式。", reachable=True, http_status=status)
                            chunks.append(chunk)
                        try:
                            data = json.loads(b''.join(chunks))
                            rows = data['data']
                            if not isinstance(rows, list) or any(not isinstance(row, dict) or not isinstance(row.get('id'), str) for row in rows):
                                raise ValueError('Invalid model list')
                            models = [row['id'] for row in rows]
                        except (ValueError, KeyError, TypeError):
                            return result("unexpected_response", "服务可达，但返回的不是兼容的模型列表，请检查 API 地址。", reachable=True, http_status=status)
                        selected = config.get('model', '')
                        if not models:
                            return result("no_models", "认证通过，但服务尚未提供可用模型。", reachable=True, http_status=status, auth=True)
                        if selected and selected not in models:
                            return result("model_not_found", "认证通过，但配置的模型不在服务模型列表中。", reachable=True, http_status=status, auth=True, model=False, models=models[:30])
                        return result("ready", "连接成功，认证及模型列表验证通过。" if selected else "连接成功，认证及模型列表验证通过；请选择服务中的模型名。",
                                      ok=True, reachable=True, http_status=status, auth=True, model=True if selected else None, models=models[:30])
                    if method == 'HEAD' and (200 <= status < 300 or status in (400, 405, 422)):
                        return result("reachable", "服务可达；该接口的认证、请求格式与图像推理需通过抽样验证。", reachable=True, http_status=status)
                    if status == 404:
                        return result("not_found", "服务可达，但接口路径不存在（HTTP 404）。", reachable=True, http_status=status)
                    if 300 <= status < 400:
                        return result("redirect", "服务返回重定向，请填写最终的 API 地址。", reachable=True, http_status=status)
                    return result("http_error", f"服务已响应，但返回 HTTP {status}，请检查服务状态。", reachable=True, http_status=status)

    try:
        return await asyncio.wait_for(request(), timeout=timeout_seconds)
    except (asyncio.TimeoutError, httpx.TimeoutException):
        return result("timeout", "连接测试超时，请检查地址、端口及服务状态。")
    except httpx.HTTPError:
        # 不回传异常正文，避免 URL / 请求头中的认证信息泄露。
        return result("network_error", "无法连接服务，请检查网络、地址、端口或 TLS 证书。")
