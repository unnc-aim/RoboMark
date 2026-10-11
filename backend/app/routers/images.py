from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date
import os
import json
from app.core import get_db_dependency, get_current_user
from app.schemas.preannotation import Annotation
from app.services.preannotation_store import require_dataset, categories_for_image, validate_categories, insert_annotation, finish_image

router = APIRouter(prefix="/api/images", tags=["图片标注"])


class AnnotationCreate(Annotation):
    pass


class AnnotationResponse(BaseModel):
    id: int
    image_id: int
    category_id: int
    annotation_type: Optional[str] = 'bbox'
    x_center: float
    y_center: float
    width: float
    height: float
    p1_x: Optional[float] = None
    p1_y: Optional[float] = None
    p2_x: Optional[float] = None
    p2_y: Optional[float] = None
    p3_x: Optional[float] = None
    p3_y: Optional[float] = None
    p4_x: Optional[float] = None
    p4_y: Optional[float] = None
    created_at: datetime


class ImageResponse(BaseModel):
    id: int
    dataset_id: int
    filename: str
    width: Optional[int]
    height: Optional[int]
    status: str
    annotations: List[AnnotationResponse] = []


class SaveAnnotationsRequest(BaseModel):
    annotations: List[AnnotationCreate]
    skip: bool = False
    revision: int


@router.get("/next/{dataset_id}")
async def get_next_image(
    dataset_id: int,
    conn = Depends(get_db_dependency),
    current_user = Depends(get_current_user)
):
    """获取下一张待标注图片"""
    with conn.cursor() as cursor:
        # 检查数据集
        cursor.execute("SELECT id FROM datasets WHERE id = %s AND is_active = TRUE", (dataset_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="数据集不存在或未激活")

        # 优先返回当前用户已分配但未完成的图片
        cursor.execute(
            "SELECT * FROM images WHERE dataset_id = %s AND assigned_to = %s AND status = 'assigned'",
            (dataset_id, current_user['id'])
        )
        image = cursor.fetchone()

        if not image:
            # 获取一张新的待标注图片
            cursor.execute(
                "SELECT * FROM images WHERE dataset_id = %s AND status = 'pending' LIMIT 1",
                (dataset_id,)
            )
            image = cursor.fetchone()

            if image:
                # 分配给当前用户
                cursor.execute(
                    "UPDATE images SET assigned_to = %s, assigned_at = NOW(), status = 'assigned' WHERE id = %s",
                    (current_user['id'], image['id'])
                )
                image['status'] = 'assigned'
                image['assigned_to'] = current_user['id']

        if not image:
            return None

        # 获取标注
        cursor.execute("SELECT * FROM annotations WHERE image_id = %s", (image['id'],))
        annotations = cursor.fetchall()

    return {
        **image,
        "annotations": annotations
    }


@router.get("/next/{dataset_id}/batch")
async def get_next_images_batch(
    dataset_id: int,
    count: int = 20,
    conn = Depends(get_db_dependency),
    current_user = Depends(get_current_user)
):
    """批量获取待标注图片（用于预加载）"""
    if count > 50:
        count = 50  # 限制最大数量

    with conn.cursor() as cursor:
        # 检查数据集
        cursor.execute("SELECT id FROM datasets WHERE id = %s AND is_active = TRUE", (dataset_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="数据集不存在或未激活")

        # 获取当前用户已分配的图片
        cursor.execute(
            "SELECT * FROM images WHERE dataset_id = %s AND assigned_to = %s AND status = 'assigned'",
            (dataset_id, current_user['id'])
        )
        assigned_images = cursor.fetchall()

        # 获取待标注图片
        remaining = count - len(assigned_images)
        pending_images = []
        if remaining > 0:
            cursor.execute(
                "SELECT * FROM images WHERE dataset_id = %s AND status = 'pending' ORDER BY RAND() LIMIT %s",
                (dataset_id, remaining)
            )
            pending_images = cursor.fetchall()

            # 分配给当前用户
            for image in pending_images:
                cursor.execute(
                    "UPDATE images SET assigned_to = %s, assigned_at = NOW(), status = 'assigned' WHERE id = %s",
                    (current_user['id'], image['id'])
                )
                image['status'] = 'assigned'
                image['assigned_to'] = current_user['id']

        all_images = list(assigned_images) + list(pending_images)

        # 获取每张图片的标注
        result = []
        for image in all_images:
            cursor.execute("SELECT * FROM annotations WHERE image_id = %s", (image['id'],))
            annotations = cursor.fetchall()
            result.append({
                **image,
                "annotations": annotations
            })

    return result


@router.get("/{image_id}")
async def get_image(
    image_id: int,
    conn = Depends(get_db_dependency),
    current_user = Depends(get_current_user)
):
    """获取图片详情和标注"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM images WHERE id = %s", (image_id,))
        image = cursor.fetchone()

        if not image:
            raise HTTPException(status_code=404, detail="图片不存在")

        cursor.execute("SELECT * FROM annotations WHERE image_id = %s", (image_id,))
        annotations = cursor.fetchall()

    return {
        **image,
        "annotations": annotations
    }


@router.get("/{image_id}/file")
async def get_image_file(
    image_id: int,
    conn = Depends(get_db_dependency)
):
    """获取图片文件（内网使用，无需认证）"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT file_path FROM images WHERE id = %s", (image_id,))
        image = cursor.fetchone()

    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")

    if not os.path.exists(image['file_path']):
        raise HTTPException(status_code=404, detail="图片文件不存在")

    return FileResponse(image['file_path'])


@router.post("/{image_id}/annotations")
async def create_annotation(
    image_id: int,
    annotation_data: AnnotationCreate,
    conn = Depends(get_db_dependency),
    current_user = Depends(get_current_user)
):
    """创建标注"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM images WHERE id = %s FOR UPDATE", (image_id,))
        image = cursor.fetchone()
        if not image:
            raise HTTPException(status_code=404, detail="图片不存在")

        require_dataset(cursor, image['dataset_id'], current_user)
        # 验证类别
        cursor.execute(
            "SELECT id FROM categories WHERE id = %s AND dataset_id = %s",
            (annotation_data.category_id, image['dataset_id'])
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=400, detail="无效的类别")

        cursor.execute(
            """INSERT INTO annotations (image_id, category_id, annotation_type, x_center, y_center, width, height,
               p1_x, p1_y, p2_x, p2_y, p3_x, p3_y, p4_x, p4_y, created_by)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (image_id, annotation_data.category_id, annotation_data.annotation_type,
             annotation_data.x_center, annotation_data.y_center,
             annotation_data.width, annotation_data.height,
             annotation_data.p1_x, annotation_data.p1_y,
             annotation_data.p2_x, annotation_data.p2_y,
             annotation_data.p3_x, annotation_data.p3_y,
             annotation_data.p4_x, annotation_data.p4_y,
             current_user['id'])
        )
        annotation_id = cursor.lastrowid
        cursor.execute("UPDATE images SET annotation_revision=annotation_revision+1 WHERE id=%s", (image_id,))

        # 记录历史
        history_data = {
            "category_id": annotation_data.category_id,
            "annotation_type": annotation_data.annotation_type,
            "x_center": annotation_data.x_center,
            "y_center": annotation_data.y_center,
            "width": annotation_data.width,
            "height": annotation_data.height
        }
        if annotation_data.annotation_type == 'parallelogram':
            history_data.update({
                "p1_x": annotation_data.p1_x, "p1_y": annotation_data.p1_y,
                "p2_x": annotation_data.p2_x, "p2_y": annotation_data.p2_y,
                "p3_x": annotation_data.p3_x, "p3_y": annotation_data.p3_y,
                "p4_x": annotation_data.p4_x, "p4_y": annotation_data.p4_y,
            })
        cursor.execute(
            "INSERT INTO annotation_history (image_id, user_id, action, annotation_data) VALUES (%s, %s, %s, %s)",
            (image_id, current_user['id'], 'create', json.dumps(history_data))
        )

        cursor.execute("SELECT * FROM annotations WHERE id = %s", (annotation_id,))
        annotation = cursor.fetchone()

    return annotation


@router.delete("/annotations/{annotation_id}")
async def delete_annotation(
    annotation_id: int,
    conn = Depends(get_db_dependency),
    current_user = Depends(get_current_user)
):
    """删除标注"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM annotations WHERE id = %s", (annotation_id,))
        annotation = cursor.fetchone()
        if not annotation:
            raise HTTPException(status_code=404, detail="标注不存在")

        cursor.execute("SELECT * FROM images WHERE id=%s FOR UPDATE", (annotation['image_id'],))
        image = cursor.fetchone()
        require_dataset(cursor, image['dataset_id'], current_user)
        cursor.execute("SELECT * FROM annotations WHERE id=%s", (annotation_id,))
        annotation = cursor.fetchone()
        if not annotation:
            raise HTTPException(409, "标注已改变，请重新加载")
        # 记录历史
        cursor.execute(
            "INSERT INTO annotation_history (image_id, user_id, action, annotation_data) VALUES (%s, %s, %s, %s)",
            (annotation['image_id'], current_user['id'], 'delete', json.dumps({
                "annotation_id": annotation_id,
                "category_id": annotation['category_id'],
                "x_center": annotation['x_center'],
                "y_center": annotation['y_center'],
                "width": annotation['width'],
                "height": annotation['height']
            }))
        )

        cursor.execute("DELETE FROM annotations WHERE id = %s", (annotation_id,))
        cursor.execute("UPDATE images SET annotation_revision=annotation_revision+1 WHERE id=%s", (annotation['image_id'],))

    return {"message": "删除成功"}


@router.post("/{image_id}/save")
async def save_annotations(
    image_id: int,
    data: SaveAnnotationsRequest,
    conn = Depends(get_db_dependency),
    current_user = Depends(get_current_user)
):
    """保存图片的所有标注并完成"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM images WHERE id=%s FOR UPDATE", (image_id,))
        image = cursor.fetchone()
        if not image:
            raise HTTPException(404, "图片不存在")
        require_dataset(cursor, image['dataset_id'], current_user)
        if image['annotation_revision'] != data.revision:
            raise HTTPException(409, "图片标注已被其他操作修改，请重新加载后保存")
        validate_categories(data.annotations, categories_for_image(cursor, image))
        cursor.execute("SELECT source_preannotation_id FROM annotations WHERE image_id=%s", (image_id,))
        previous = cursor.fetchall()
        sources = {row['source_preannotation_id'] for row in previous if row['source_preannotation_id']}
        submitted = [ann.source_preannotation_id for ann in data.annotations if ann.source_preannotation_id]
        if len(set(submitted)) != len(submitted) or set(submitted) - sources:
            raise HTTPException(422, "标注来源重复或不属于该图片")
        cursor.execute("DELETE FROM annotations WHERE image_id=%s", (image_id,))
        if not data.skip:
            for ann in data.annotations:
                insert_annotation(cursor, image_id, ann, current_user['id'], ann.source_preannotation_id)
        count = 0 if data.skip else len(data.annotations)
        status = 'skipped' if data.skip else ('labeled' if count else 'pending')
        finish_image(cursor, image, status, current_user['id'], max(0, count-len(previous)))
        cursor.execute("INSERT INTO annotation_history (image_id,user_id,action,annotation_data) VALUES (%s,%s,'update',%s)",
                       (image_id, current_user['id'], json.dumps({'annotations': [a.model_dump() for a in data.annotations], 'skip': data.skip})))
    return {"message": "保存成功", "status": status, "annotation_revision": data.revision+1}


@router.get("/{image_id}/history")
async def get_annotation_history(
    image_id: int,
    conn = Depends(get_db_dependency),
    current_user = Depends(get_current_user)
):
    """获取标注历史 (用于撤销)"""
    with conn.cursor() as cursor:
        cursor.execute(
            """SELECT id, action, annotation_data, created_at FROM annotation_history
               WHERE image_id = %s AND user_id = %s ORDER BY created_at DESC LIMIT 50""",
            (image_id, current_user['id'])
        )
        history = cursor.fetchall()

    return [
        {
            "id": h['id'],
            "action": h['action'],
            "data": json.loads(h['annotation_data']) if isinstance(h['annotation_data'], str) else h['annotation_data'],
            "created_at": h['created_at']
        }
        for h in history
    ]


@router.get("/dataset/{dataset_id}/progress")
async def get_dataset_progress(
    dataset_id: int,
    conn = Depends(get_db_dependency),
    current_user = Depends(get_current_user)
):
    """获取数据集标注进度"""
    with conn.cursor() as cursor:
        cursor.execute("SELECT id FROM datasets WHERE id = %s", (dataset_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="数据集不存在")

        cursor.execute("SELECT COUNT(*) as count FROM images WHERE dataset_id = %s", (dataset_id,))
        total = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM images WHERE dataset_id = %s AND status = 'labeled'", (dataset_id,))
        labeled = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM images WHERE dataset_id = %s AND status = 'skipped'", (dataset_id,))
        skipped = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM images WHERE dataset_id = %s AND status = 'pending'", (dataset_id,))
        pending = cursor.fetchone()['count']

    # 进度计算：已标注 + 未见 = 已处理
    processed = labeled + skipped
    return {
        "total": total,
        "labeled": labeled,
        "skipped": skipped,
        "pending": pending,
        "progress": round(processed / total * 100, 2) if total > 0 else 0
    }
