"""Small, cached display images. Annotation and inference keep using the originals."""

from hashlib import sha256
from enum import IntEnum
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import Lock

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse, Response
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings


class PreviewWidth(IntEnum):
    SMALL = 320
    MEDIUM = 640
    LARGE = 1280


_locks = [Lock() for _ in range(32)]
_default_cache = Path(__file__).resolve().parents[2] / "uploads" / "image_previews"


def preview_response(source: str, width: PreviewWidth, request: Request):
    """Run in a worker thread: decoding/encoding must not block the event loop."""
    width = int(width)
    path = Path(source).resolve()
    try:
        stat = path.stat()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="图片文件不存在")
    # Include source identity + revision so replacing a template/file invalidates it.
    key = sha256(f"v1:{path}:{stat.st_mtime_ns}:{stat.st_ctime_ns}:{stat.st_size}:{width}".encode()).hexdigest()
    headers = {"ETag": f'"{key}"', "Cache-Control": "public, max-age=0, must-revalidate"}
    tags = request.headers.get("if-none-match", "").split(",")
    if any(tag.strip().removeprefix("W/") in (headers["ETag"], "*") for tag in tags):
        return Response(status_code=304, headers=headers)

    cache = Path(settings.IMAGE_PREVIEW_CACHE_DIR) if settings.IMAGE_PREVIEW_CACHE_DIR else _default_cache
    destination = cache / key[:2] / f"{key}.webp"
    with _locks[int(key[:2], 16) % len(_locks)]:
        if not destination.exists():
            temporary = None
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                with Image.open(path) as original:
                    # JPEG draft decoding avoids a full-size decode when supported.
                    original.draft("RGB", (width, width))
                    image = ImageOps.exif_transpose(original)
                    image.thumbnail((width, width), Image.Resampling.LANCZOS)
                    image = image.convert("RGBA" if "A" in image.getbands() or "transparency" in image.info else "RGB")
                    with NamedTemporaryFile(dir=destination.parent, suffix=".tmp", delete=False) as output:
                        temporary = Path(output.name)
                        image.save(output, format="WEBP", quality=72, method=4)
                # Readers and other workers only ever see a complete image.
                temporary.replace(destination)
            except FileNotFoundError:
                raise HTTPException(status_code=404, detail="图片文件不存在")
            except (UnidentifiedImageError, Image.DecompressionBombError):
                raise HTTPException(status_code=415, detail="图片格式无效或尺寸过大，无法生成预览")
            except OSError:
                raise HTTPException(status_code=503, detail="图片预览暂时不可用，请稍后重试")
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)

    return FileResponse(destination, media_type="image/webp", headers=headers)
