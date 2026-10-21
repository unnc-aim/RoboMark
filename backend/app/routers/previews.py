"""Read-only preview endpoints, also served by the optional standalone sidecar."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from app.core import get_db_dependency
from app.services.image_preview import PreviewWidth, preview_response

router = APIRouter(prefix="/api", tags=["图片预览"])
_backend_root = Path(__file__).resolve().parents[2]


@router.get("/images/{image_id}/preview")
async def get_image_preview(
    image_id: int,
    request: Request,
    width: PreviewWidth = PreviewWidth.MEDIUM,
    conn=Depends(get_db_dependency),
):
    """公开内网图片的压缩预览，与原图接口访问规则一致。"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT file_path FROM images WHERE id = %s", (image_id,))
        image = cursor.fetchone()
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")
    return await run_in_threadpool(preview_response, image["file_path"], width, request)


@router.get("/categories/{category_id}/template-image/preview")
async def get_template_preview(
    category_id: int,
    request: Request,
    width: PreviewWidth = PreviewWidth.MEDIUM,
    conn=Depends(get_db_dependency),
):
    with conn.cursor() as cursor:
        cursor.execute("SELECT template_image_path FROM categories WHERE id = %s", (category_id,))
        category = cursor.fetchone()
    if not category or not category.get("template_image_path"):
        raise HTTPException(status_code=404, detail="模板图片不存在")
    path = _backend_root / category["template_image_path"].lstrip("/")
    return await run_in_threadpool(preview_response, str(path), width, request)
