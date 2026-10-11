"""原生 SQL 存储与事务辅助。调用者负责提交 / 回滚。"""
import json
from datetime import date
from fastapi import HTTPException
from app.schemas.preannotation import Annotation, GEOMETRY_FIELDS
from app.services.preannotation_inference import json_value


def require_dataset(c, dataset_id, user):
    c.execute("SELECT * FROM datasets WHERE id=%s", (dataset_id,))
    dataset = c.fetchone()
    if not dataset:
        raise HTTPException(404, "数据集不存在")
    if not dataset["is_active"] and not user["is_admin"]:
        raise HTTPException(403, "无权访问该数据集")
    return dataset


def require_task(c, task_id, user, lock=False):
    c.execute("SELECT * FROM preannotation_tasks WHERE id=%s" + (" FOR UPDATE" if lock else ""), (task_id,))
    task = c.fetchone()
    if not task:
        raise HTTPException(404, "预标注任务不存在")
    require_dataset(c, task["dataset_id"], user)
    return task


def require_operator(task, user):
    if task["created_by"] != user["id"] and not user["is_admin"]:
        raise HTTPException(403, "仅任务创建者或管理员可取消或重试任务")


def task_detail(c, task):
    c.execute("""SELECT execution_status, COUNT(*) AS n FROM preannotation_task_images
                 WHERE task_id=%s GROUP BY execution_status""", (task["id"],))
    counts = {r["execution_status"]: r["n"] for r in c.fetchall()}
    c.execute("""SELECT SUM(execution_status='succeeded' AND original_count>0) AS with_results,
                 SUM(execution_status='succeeded' AND original_count=0) AS empty_results,
                 SUM(review_status='approved') AS approved, SUM(review_status='rejected') AS rejected
                 FROM preannotation_task_images WHERE task_id=%s""", (task["id"],))
    aggregate = {k: int(v or 0) for k, v in c.fetchone().items()}
    c.execute("SELECT image_id,error_code,error_message FROM preannotation_task_images WHERE task_id=%s AND execution_status='failed' ORDER BY image_id LIMIT 20", (task["id"],))
    errors = c.fetchall()
    return {**{k: v for k, v in task.items() if k not in ("config_snapshot", "endpoint_key")},
            "categories_snapshot": json_value(task["categories_snapshot"]), "counts": counts,
            "processed_images": sum(counts.get(k, 0) for k in ("succeeded", "failed", "cancelled")),
            **aggregate, "errors": errors}


def reconcile_task(c, task_id):
    c.execute("SELECT status FROM preannotation_tasks WHERE id=%s FOR UPDATE", (task_id,))
    task = c.fetchone()
    if not task:
        return
    c.execute("SELECT execution_status,COUNT(*) AS n FROM preannotation_task_images WHERE task_id=%s GROUP BY execution_status", (task_id,))
    counts = {r["execution_status"]: r["n"] for r in c.fetchall()}
    pending = counts.get("queued", 0) + counts.get("running", 0)
    if task["status"] in ("cancelling", "cancelled"):
        status = "cancelling" if pending else "cancelled"
    elif pending:
        status = "running" if counts.get("running", 0) or counts.get("succeeded", 0) or counts.get("failed", 0) else "queued"
    elif counts.get("failed", 0):
        status = "completed_with_errors" if counts.get("succeeded", 0) else "failed"
    else:
        status = "completed"
    c.execute("UPDATE preannotation_tasks SET status=%s WHERE id=%s", (status, task_id))


def categories_for_image(c, image):
    c.execute("SELECT id FROM categories WHERE dataset_id=%s", (image["dataset_id"],))
    return {row["id"] for row in c.fetchall()}


def validate_categories(annotations, category_ids):
    for ann in annotations:
        if ann.category_id not in category_ids:
            raise HTTPException(422, "标注类别不属于当前数据集或已被删除")


def insert_annotation(c, image_id, ann, user_id, source_id=None):
    data = ann.model_dump() if isinstance(ann, Annotation) else ann
    columns = ["image_id", *GEOMETRY_FIELDS, "created_by", "source_preannotation_id"]
    values = [image_id, *[data.get(key) for key in GEOMETRY_FIELDS], user_id, source_id]
    c.execute(f"INSERT INTO annotations ({','.join(columns)}) VALUES ({','.join(['%s'] * len(columns))})", values)
    return c.lastrowid


def finish_image(c, image, status, user_id, new_annotations=0):
    """图片行必须已锁定；状态转移和计数在同一事务内。"""
    delta = int(status == "labeled") - int(image["status"] == "labeled")
    if status == "pending":
        c.execute("UPDATE images SET status='pending',assigned_to=NULL,assigned_at=NULL,labeled_by=NULL,labeled_at=NULL,annotation_revision=annotation_revision+1 WHERE id=%s", (image["id"],))
    else:
        c.execute("UPDATE images SET status=%s,labeled_by=%s,labeled_at=NOW(),assigned_to=NULL,assigned_at=NULL,annotation_revision=annotation_revision+1 WHERE id=%s", (status, user_id, image["id"]))
    if delta:
        c.execute("UPDATE datasets SET labeled_images=GREATEST(0,labeled_images+%s) WHERE id=%s", (delta, image["dataset_id"]))
    first_completion = int(status in ("labeled", "skipped") and image["status"] not in ("labeled", "skipped"))
    if first_completion or new_annotations:
        c.execute("""INSERT INTO work_statistics (user_id,dataset_id,date,images_labeled,annotations_created)
                     VALUES (%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE
                     images_labeled=images_labeled+VALUES(images_labeled),
                     annotations_created=annotations_created+VALUES(annotations_created)""",
                  (user_id, image["dataset_id"], date.today(), first_completion, new_annotations))


def candidate_rows(c, item_id, include_deleted=True):
    c.execute("SELECT * FROM preannotations WHERE task_image_id=%s" + ("" if include_deleted else " AND is_deleted=FALSE") + " ORDER BY id", (item_id,))
    return [{**json_value(r["geometry"]), "id": r["id"], "is_deleted": bool(r["is_deleted"]),
             "is_manual": bool(r["is_manual"]), "original_geometry": json_value(r["original_geometry"])} for r in c.fetchall()]
