"""声明式 HTTP 适配、凭据保护及模型结果转换；不执行用户代码。"""
import base64
import json
import math
import mimetypes
import re
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError
from cryptography.fernet import Fernet, InvalidToken
from PIL import Image
from app.core.config import settings
from app.schemas.preannotation import Annotation, ProfileInput, POINT_FIELDS, GEOMETRY_FIELDS


class InferenceError(Exception):
    def __init__(self, code, message, retryable=False, raw_response=None):
        super().__init__(message)
        self.code, self.retryable, self.raw_response = code, retryable, raw_response


def json_value(value):
    return json.loads(value) if isinstance(value, (str, bytes)) else value


def cipher():
    if not settings.PREANNOTATION_ENCRYPTION_KEY:
        raise ValueError("请配置独立的 PREANNOTATION_ENCRYPTION_KEY 后保存接口凭据")
    try:
        return Fernet(settings.PREANNOTATION_ENCRYPTION_KEY.encode())
    except (ValueError, TypeError) as exc:
        raise ValueError("PREANNOTATION_ENCRYPTION_KEY 必须是有效的 Fernet 密钥") from exc


def encrypt_credentials(value):
    return cipher().encrypt(json.dumps(value).encode()).decode() if value else None


def decrypt_credentials(value):
    if not value:
        return {}
    try:
        return json.loads(cipher().decrypt(value.encode()))
    except (InvalidToken, ValueError) as exc:
        raise InferenceError("credentials", "接口凭据无法解密，请重新保存凭据") from exc


def extract(value, path):
    if not path:
        return value
    if not re.fullmatch(r"[A-Za-z_][\w-]*(?:\[\d+\])*(?:\.[A-Za-z_][\w-]*(?:\[\d+\])*)*", path):
        raise ValueError(f"不支持的字段路径：{path}")
    for part in path.split("."):
        key = part.split("[")[0]
        value = value[key]
        for index in re.findall(r"\[(\d+)\]", part):
            value = value[int(index)]
    return value


def render_template(value, context):
    if isinstance(value, dict):
        return {k: render_template(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [render_template(v, context) for v in value]
    if not isinstance(value, str):
        return value
    token = re.fullmatch(r"\{\{([\w.]+)\}\}", value)
    if token:
        return extract(context, token[1])

    def replace(match):
        result = extract(context, match[1])
        return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
    return re.sub(r"\{\{([\w.]+)\}\}", replace, value)


def validate_profile(profile: ProfileInput):
    endpoint = urlsplit(profile.endpoint)
    if endpoint.scheme not in ("http", "https") or not endpoint.hostname or endpoint.username or endpoint.password or endpoint.fragment:
        raise ValueError("endpoint 必须是无内嵌凭据的 HTTP(S) 地址")
    _ = endpoint.port
    if profile.interface_type == "http_json" and not profile.request_template:
        raise ValueError("通用 HTTP JSON 接口需要请求模板")
    for path in [profile.response_path, profile.annotations_path, *profile.field_mapping.values()]:
        if path:
            # 验证语法，不要求字段存在
            if not re.fullmatch(r"[A-Za-z_][\w-]*(?:\[\d+\])*(?:\.[A-Za-z_][\w-]*(?:\[\d+\])*)*", path):
                raise ValueError(f"不支持的字段路径：{path}")
    allowed = {*GEOMETRY_FIELDS, "label", "bbox", "points"}
    if set(profile.field_mapping) - allowed:
        raise ValueError("字段映射含未知标注字段")
    for key, value in profile.headers.items():
        if not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", key) or '\r' in value or '\n' in value:
            raise ValueError("请求头格式不合法")
        if key.lower() in ("host", "content-length", "transfer-encoding", "connection"):
            raise ValueError("不能覆盖 HTTP 传输控制头")
    if len(json.dumps(profile.request_template)) > 65536:
        raise ValueError("请求模板过大")


def output_schema(config, categories, shape):
    props = {"category_id": {"type": "integer", "enum": [c["id"] for c in categories]},
             "annotation_type": {"type": "string", "enum": [shape]}}
    fields = ["category_id", "annotation_type"]
    if shape == "parallelogram":
        fields += POINT_FIELDS
    elif config.get("box_format") == "xyxy":
        fields += ["bbox"]
        props["bbox"] = {"type": "array", "items": {"type": "number"}, "minItems": 4, "maxItems": 4}
    else:
        fields += ["x_center", "y_center", "width", "height"]
    for name in fields:
        if name not in props:
            props[name] = {"type": "number"}
    return {"type": "object", "properties": {"annotations": {"type": "array", "maxItems": 500,
            "items": {"type": "object", "properties": props, "required": fields, "additionalProperties": False}}},
            "required": ["annotations"], "additionalProperties": False}


def normalize_output(output, config, categories, shape, width, height):
    if isinstance(output, str):
        text = output.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        output = json.loads(text)
    rows = output if isinstance(output, list) else extract(output, config.get("annotations_path", "annotations"))
    if not isinstance(rows, list) or len(rows) > 500:
        raise ValueError("标注结果必须是最多 500 个对象的数组")
    mapping = config.get("field_mapping", {})
    ids = {c["id"] for c in categories}
    labels = {c["name"]: c["id"] for c in categories}
    coordinate = config.get("coordinate_system", "normalized")
    sx, sy = (width, height) if coordinate == "pixels" else ((1000, 1000) if coordinate == "relative_1000" else (1, 1))
    if not sx or not sy:
        raise ValueError("像素坐标转换需要有效图片尺寸")
    results = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"第 {index + 1} 个标注不是对象")
        data = dict(row)
        for key, path in mapping.items():
            data[key] = extract(row, path)
        category = data.get("category_id")
        if category is None:
            category = labels.get(data.get("label"))
        if isinstance(category, bool) or category not in ids:
            raise ValueError(f"第 {index + 1} 个标注类别不属于任务的类别集合")
        if data.get("annotation_type", shape) != shape:
            raise ValueError(f"第 {index + 1} 个标注形状与任务不符")
        ann = {"category_id": category, "annotation_type": shape}

        def coordinate_value(value, divisor):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError("坐标必须是有限数字")
            return value / divisor

        if shape == "parallelogram":
            points = data.get("points")
            for i in range(1, 5):
                for axis, divisor, pos in (("x", sx, 0), ("y", sy, 1)):
                    value = points[i-1][pos] if points is not None else data[f"p{i}_{axis}"]
                    ann[f"p{i}_{axis}"] = coordinate_value(value, divisor)
            xs, ys = [ann[f"p{i}_x"] for i in range(1, 5)], [ann[f"p{i}_y"] for i in range(1, 5)]
            ann.update(x_center=(min(xs)+max(xs))/2, y_center=(min(ys)+max(ys))/2,
                       width=max(xs)-min(xs), height=max(ys)-min(ys))
        elif config.get("box_format", "center") == "xyxy":
            box = data["bbox"]
            if len(box) != 4:
                raise ValueError("bbox 必须有四个坐标")
            x1, y1, x2, y2 = [coordinate_value(v, d) for v, d in zip(box, (sx, sy, sx, sy))]
            ann.update(x_center=(x1+x2)/2, y_center=(y1+y2)/2, width=x2-x1, height=y2-y1)
        else:
            for key, divisor in (("x_center", sx), ("y_center", sy), ("width", sx), ("height", sy)):
                ann[key] = coordinate_value(data[key], divisor)
        results.append(Annotation.model_validate(ann).model_dump(exclude={"source_preannotation_id"}))
    return results


async def infer(config, credentials, image_path, prompt, categories, shape):
    path = Path(image_path)
    try:
        if path.stat().st_size > settings.PREANNOTATION_MAX_IMAGE_BYTES:
            raise InferenceError("image_size", "图片文件超过预标注大小限制")
        with Image.open(path) as image:
            width, height = image.size
        data = path.read_bytes()
        if len(data) > settings.PREANNOTATION_MAX_IMAGE_BYTES:
            raise InferenceError("image_size", "图片文件超过预标注大小限制")
    except (OSError, Image.DecompressionBombError) as exc:
        raise InferenceError("image", "图片不存在或不能解码") from exc
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    encoded = base64.b64encode(data).decode()
    schema = output_schema(config, categories, shape)
    contract = (f"只返回符合以下 JSON Schema 的 JSON，不使用 Markdown。类别必须来自提供的集合。"
                f"坐标体系：{config['coordinate_system']}，矩形格式：{config['box_format']}。"
                f"四点按边界顺序排列。没有目标时返回 {{\"annotations\":[]}}。\n"
                f"类别：{json.dumps(categories, ensure_ascii=False)}\nSchema：{json.dumps(schema, ensure_ascii=False)}")
    context = {"image": {"data_url": f"data:{mime};base64,{encoded}", "base64": encoded,
                         "mime": mime, "width": width, "height": height},
               "prompt": prompt + "\n" + contract, "user_prompt": prompt, "categories": categories,
               "output_schema": schema, "model": config.get("model", "")}
    if config["interface_type"] == "openai":
        body = {"model": config.get("model", ""), "temperature": 0, "max_tokens": 8192,
                "messages": [{"role": "system", "content": contract},
                             {"role": "user", "content": [{"type": "text", "text": prompt},
                              {"type": "image_url", "image_url": {"url": context["image"]["data_url"]}}]}]}
        if config.get("structured_output") == "response_format":
            body["response_format"] = {"type": "json_schema", "json_schema": {"name": "annotations", "schema": schema}}
        elif config.get("structured_output") == "vllm":
            body["structured_outputs"] = {"json": schema}
    else:
        body = render_template(config["request_template"], context)
    headers = {"Content-Type": "application/json", **credentials.get("headers", {})}
    if credentials.get("api_key") and not any(key.lower() == "authorization" for key in headers):
        headers["Authorization"] = "Bearer " + credentials["api_key"]
    raw = None
    try:
        # 总耗时同时由 worker 的 wait_for 限制，单独设置连接 / 读取超时。
        async with httpx.AsyncClient(timeout=config["timeout_seconds"], follow_redirects=False, trust_env=False) as client:
            async with client.stream(config.get("http_method", "POST"), config["endpoint"], json=body, headers=headers) as response:
                if response.status_code >= 300:
                    raise InferenceError("http", f"推理服务返回 HTTP {response.status_code}",
                                         response.status_code in (408, 429, 500, 502, 503, 504))
                chunks, size = [], 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > settings.PREANNOTATION_MAX_RESPONSE_BYTES:
                        raise InferenceError("response_size", "推理响应超过大小限制")
                    chunks.append(chunk)
        raw = b"".join(chunks).decode("utf-8")
        response_data = json.loads(raw)
        if config["interface_type"] == "openai" and response_data.get("choices", [{}])[0].get("finish_reason") == "length":
            raise ValueError("模型输出被截断")
        output = extract(response_data, config.get("response_path", ""))
        annotations = normalize_output(output, config, categories, shape, width, height)
        return annotations, redact(raw, credentials)
    except httpx.HTTPError as exc:
        raise InferenceError("network", "推理请求超时或网络不可用", True) from exc
    except ValidationError as exc:
        issue = exc.errors(include_url=False)[0]
        field = '.'.join(str(part) for part in issue['loc']) or '几何'
        raise InferenceError("validation", f"模型候选框的 {field} 不合法，请检查坐标范围、面积与顶点顺序", raw_response=redact(raw, credentials)) from exc
    except json.JSONDecodeError as exc:
        raise InferenceError("validation", "模型响应不是有效 JSON，请检查接口输出格式", raw_response=redact(raw, credentials)) from exc
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise InferenceError("validation", f"模型结果验证失败：{str(exc)[:1000]}", raw_response=redact(raw, credentials)) from exc


def redact(text, credentials):
    if text is None:
        return None
    for value in [credentials.get("api_key"), *credentials.get("headers", {}).values()]:
        if value:
            text = text.replace(value, "[已隐藏]")
    return text
