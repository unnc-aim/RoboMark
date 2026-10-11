"""数据集预标注配置、后台任务、图片筛选及事务化审核 API。"""
import hashlib
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from app.core import get_db_dependency, get_current_user
from app.schemas.preannotation import ProfileInput, ProfileTestInput, TaskInput, DraftInput, ReviewInput, Annotation
from app.services.preannotation_inference import validate_profile, encrypt_credentials, decrypt_credentials, json_value
from app.services.preannotation_probe import probe_connection
from app.services.preannotation_store import (
    require_dataset, require_task, require_operator, task_detail, reconcile_task,
    categories_for_image, validate_categories, insert_annotation, finish_image, candidate_rows,
)

router = APIRouter(prefix="/api", tags=["预标注"])


def public_profile(row):
    config = json_value(row["config"])
    # 请求头也可能含认证信息，任何请求头值均不返回客户端。
    credentials = decrypt_credentials(row["credentials"])
    return {**{k: v for k, v in row.items() if k not in ("config", "credentials")}, **config,
            "has_api_key": bool(credentials.get("api_key")),
            "headers": {key: "[已保存]" for key in credentials.get("headers", {})}}


def get_profile(c, profile_id, user, write=False, lock=False):
    c.execute("SELECT * FROM preannotation_profiles WHERE id=%s AND is_active=TRUE" + (" FOR UPDATE" if lock else ""), (profile_id,))
    row = c.fetchone()
    if not row:
        raise HTTPException(404, "接口配置不存在或已停用")
    if row["owner_id"] != user["id"] and not user["is_admin"] and (write or not row["is_shared"]):
        raise HTTPException(403, "无权操作该接口配置")
    if write and row.get("environment_key"):
        raise HTTPException(409, "此配置由 .env 管理，请修改 PREANNOTATION_DEFAULT_PROFILE 并重启服务")
    return row


def profile_material(data, previous=None):
    try:
        validate_profile(data)
        old = decrypt_credentials(previous["credentials"]) if previous else {}
        headers = {}
        for key, value in data.headers.items():
            if value == "[已保存]":
                if key not in old.get("headers", {}):
                    raise ValueError("保存的请求头不存在，请重新输入")
                value = old["headers"][key]
            headers[key] = value
        credentials = {} if data.clear_credentials else {"headers": headers, "api_key": old.get("api_key", "") if data.api_key is None else data.api_key}
        config = data.model_dump(exclude={"api_key", "headers", "clear_credentials", "is_shared", "name"})
        return config, credentials
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


def profile_values(data, user, previous=None):
    if data.is_shared and not user["is_admin"]:
        raise HTTPException(403, "仅管理员可共享接口配置")
    config, credentials = profile_material(data, previous)
    try:
        encrypted = encrypt_credentials(credentials) if credentials.get("api_key") or credentials.get("headers") else None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return json.dumps(config), encrypted


@router.get("/preannotation/profiles")
def list_profiles(conn=Depends(get_db_dependency), user=Depends(get_current_user)):
    with conn.cursor() as c:
        sql = "SELECT * FROM preannotation_profiles WHERE is_active=TRUE"
        args = []
        if not user["is_admin"]:
            sql += " AND (owner_id=%s OR is_shared=TRUE)"
            args.append(user["id"])
        c.execute(sql + " ORDER BY id DESC", args)
        return [public_profile(row) for row in c.fetchall()]


@router.post("/preannotation/profiles", status_code=201)
def create_profile(data: ProfileInput, conn=Depends(get_db_dependency), user=Depends(get_current_user)):
    config, credentials = profile_values(data, user)
    with conn.cursor() as c:
        c.execute("INSERT INTO preannotation_profiles (owner_id,name,config,credentials,is_shared) VALUES (%s,%s,%s,%s,%s)",
                  (user["id"], data.name, config, credentials, data.is_shared))
        c.execute("SELECT * FROM preannotation_profiles WHERE id=%s", (c.lastrowid,))
        return public_profile(c.fetchone())


@router.get("/preannotation/profiles/{profile_id}")
def read_profile(profile_id: int, conn=Depends(get_db_dependency), user=Depends(get_current_user)):
    with conn.cursor() as c:
        return public_profile(get_profile(c, profile_id, user))


@router.post("/preannotation/profiles/test")
async def test_draft_profile(data: ProfileTestInput, conn=Depends(get_db_dependency), user=Depends(get_current_user)):
    previous = None
    if data.existing_profile_id:
        with conn.cursor() as c:
            previous = get_profile(c, data.existing_profile_id, user)
        # 不能将共享配置的隐藏凭据发送到一个被其他用户改写的测试地址。
        if previous['owner_id'] != user['id'] and not user['is_admin']:
            raise HTTPException(403, "共享配置请使用已保存接口的测试按钮")
    config, credentials = profile_material(data.profile, previous)
    return await probe_connection(config, credentials)


@router.post("/preannotation/profiles/{profile_id}/test")
async def test_saved_profile(profile_id: int, conn=Depends(get_db_dependency), user=Depends(get_current_user)):
    with conn.cursor() as c:
        profile = get_profile(c, profile_id, user)
    return await probe_connection(json_value(profile['config']), decrypt_credentials(profile['credentials']))


@router.put("/preannotation/profiles/{profile_id}")
def update_profile(profile_id: int, data: ProfileInput, conn=Depends(get_db_dependency), user=Depends(get_current_user)):
    with conn.cursor() as c:
        previous = get_profile(c, profile_id, user, write=True, lock=True)
        config, credentials = profile_values(data, user, previous)
        c.execute("UPDATE preannotation_profiles SET name=%s,config=%s,credentials=%s,is_shared=%s,version=version+1 WHERE id=%s",
                  (data.name, config, credentials, data.is_shared, profile_id))
        return public_profile(get_profile(c, profile_id, user))


@router.delete("/preannotation/profiles/{profile_id}")
def delete_profile(profile_id: int, conn=Depends(get_db_dependency), user=Depends(get_current_user)):
    with conn.cursor() as c:
        get_profile(c, profile_id, user, write=True, lock=True)
        c.execute("UPDATE preannotation_profiles SET is_active=FALSE,credentials=NULL WHERE id=%s", (profile_id,))
    return {"message": "配置已停用；未完成的调用将报告配置不可用"}


@router.post("/datasets/{dataset_id}/preannotation-tasks", status_code=202)
def create_task(dataset_id: int, data: TaskInput, conn=Depends(get_db_dependency), user=Depends(get_current_user)):
    with conn.cursor() as c:
        require_dataset(c, dataset_id, user)
        profile = get_profile(c, data.profile_id, user)
        config = json_value(profile["config"])
        c.execute("SELECT id,name,color FROM categories WHERE dataset_id=%s ORDER BY sort_order,id", (dataset_id,))
        categories = [row for row in c.fetchall() if row["id"] in set(data.category_ids)]
        if len(categories) != len(set(data.category_ids)):
            raise HTTPException(422, "选择的类别不属于该数据集或已被删除")
        config["profile_version"] = profile["version"]
        endpoint_key = hashlib.sha256(config["endpoint"].encode()).hexdigest()
        c.execute("""INSERT INTO preannotation_tasks (dataset_id,profile_id,created_by,prompt,annotation_type,
                     config_snapshot,categories_snapshot,endpoint_key,is_sample)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                  (dataset_id, profile["id"], user["id"], data.prompt.strip(), data.annotation_type,
                   json.dumps(config), json.dumps(categories), endpoint_key, data.sample_size is not None))
        task_id = c.lastrowid
        sql = "INSERT INTO preannotation_task_images (task_id,image_id) SELECT %s,id FROM images WHERE dataset_id=%s ORDER BY id"
        args = [task_id, dataset_id]
        if data.sample_size:
            sql += " LIMIT %s"
            args.append(data.sample_size)
        c.execute(sql, args)
        total = c.rowcount
        if not total:
            raise HTTPException(422, "数据集中没有图片，请先扫描导入")
        c.execute("UPDATE preannotation_tasks SET total_images=%s WHERE id=%s", (total, task_id))
        return task_detail(c, require_task(c, task_id, user))


@router.get("/datasets/{dataset_id}/preannotation-tasks")
def list_tasks(dataset_id: int, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
               conn=Depends(get_db_dependency), user=Depends(get_current_user)):
    with conn.cursor() as c:
        require_dataset(c, dataset_id, user)
        c.execute("SELECT COUNT(*) AS n FROM preannotation_tasks WHERE dataset_id=%s", (dataset_id,))
        total = c.fetchone()["n"]
        c.execute("SELECT * FROM preannotation_tasks WHERE dataset_id=%s ORDER BY id DESC LIMIT %s OFFSET %s", (dataset_id, page_size, (page-1)*page_size))
        tasks = c.fetchall()
        return {"total": total, "items": [task_detail(c, task) for task in tasks]}


@router.get("/preannotation/tasks/{task_id}")
def get_task(task_id: int, conn=Depends(get_db_dependency), user=Depends(get_current_user)):
    with conn.cursor() as c:
        return task_detail(c, require_task(c, task_id, user))


@router.post("/preannotation/tasks/{task_id}/cancel")
def cancel_task(task_id: int, conn=Depends(get_db_dependency), user=Depends(get_current_user)):
    with conn.cursor() as c:
        task = require_task(c, task_id, user, lock=True)
        require_operator(task, user)
        if task["status"] not in ("queued", "running", "cancelling"):
            return task_detail(c, task)
        c.execute("UPDATE preannotation_tasks SET status='cancelling' WHERE id=%s", (task_id,))
        # 直接使所有领取 token 失效；worker 写结果前再次检查。
        c.execute("UPDATE preannotation_task_images SET execution_status='cancelled',claim_token=NULL,lease_until=NULL WHERE task_id=%s AND execution_status IN ('queued','running')", (task_id,))
        reconcile_task(c, task_id)
        return task_detail(c, require_task(c, task_id, user))


@router.post("/preannotation/tasks/{task_id}/retry-failed")
def retry_failed(task_id: int, conn=Depends(get_db_dependency), user=Depends(get_current_user)):
    with conn.cursor() as c:
        task = require_task(c, task_id, user, lock=True)
        require_operator(task, user)
        if task["status"] in ("cancelled", "cancelling"):
            raise HTTPException(409, "取消的任务不能重试，请创建新批次")
        c.execute("UPDATE preannotation_task_images SET execution_status='queued',attempts=0,error_code=NULL,error_message=NULL,retry_at=NULL,claim_token=NULL,lease_until=NULL WHERE task_id=%s AND execution_status='failed' AND review_status='unreviewed'", (task_id,))
        reconcile_task(c, task_id)
        return task_detail(c, require_task(c, task_id, user))


@router.get("/datasets/{dataset_id}/images")
def list_images(dataset_id: int, task_id: int | None = None, has_candidates: bool | None = None,
                execution_status: str | None = None, review_status: str | None = None,
                after_id: int | None = Query(None, ge=1), before_id: int | None = Query(None, ge=1),
                page: int = Query(1, ge=1), page_size: int = Query(24, ge=1, le=100),
                conn=Depends(get_db_dependency), user=Depends(get_current_user)):
    with conn.cursor() as c:
        require_dataset(c, dataset_id, user)
        if task_id is None:
            if has_candidates is not None or execution_status or review_status:
                raise HTTPException(422, "预标注筛选必须选择任务批次")
            c.execute("SELECT COUNT(*) AS n FROM images WHERE dataset_id=%s", (dataset_id,))
            total = c.fetchone()["n"]
            c.execute("SELECT id,filename,width,height,status,annotation_revision FROM images WHERE dataset_id=%s ORDER BY id LIMIT %s OFFSET %s", (dataset_id, page_size, (page-1)*page_size))
            return {"total": total, "items": c.fetchall()}
        task = require_task(c, task_id, user)
        if task["dataset_id"] != dataset_id:
            raise HTTPException(422, "任务不属于该数据集")
        if execution_status and execution_status not in ("queued", "running", "succeeded", "failed", "cancelled"):
            raise HTTPException(422, "执行状态不合法")
        if review_status and review_status not in ("pending", "unreviewed", "draft", "approved", "rejected"):
            raise HTTPException(422, "审核状态不合法")
        clauses, args = ["i.dataset_id=%s", "ti.task_id=%s"], [dataset_id, task_id]
        if has_candidates is not None:
            clauses.append("EXISTS(SELECT 1 FROM preannotations p WHERE p.task_image_id=ti.id AND p.is_deleted=FALSE)" if has_candidates else "NOT EXISTS(SELECT 1 FROM preannotations p WHERE p.task_image_id=ti.id AND p.is_deleted=FALSE)")
        for name, value in (("execution_status", execution_status), ("review_status", review_status)):
            if value:
                if name == 'review_status' and value == 'pending':
                    clauses.append("ti.review_status IN ('unreviewed','draft')")
                    continue
                clauses.append(f"ti.{name}=%s")
                args.append(value)
        if after_id is not None and before_id is not None:
            raise HTTPException(422, "前后导航条件不能同时指定")
        if after_id is not None:
            clauses.append("i.id>%s")
            args.append(after_id)
        if before_id is not None:
            clauses.append("i.id<%s")
            args.append(before_id)
        joins = " FROM images i JOIN preannotation_task_images ti ON ti.image_id=i.id WHERE " + " AND ".join(clauses)
        c.execute("SELECT COUNT(*) AS n" + joins, args)
        total = c.fetchone()["n"]
        ordering = " ORDER BY i.id DESC" if before_id is not None else " ORDER BY i.id"
        c.execute("SELECT i.id,i.filename,i.width,i.height,i.status,i.annotation_revision,ti.id AS task_image_id,ti.execution_status,ti.review_status,ti.original_count,ti.error_code,ti.error_message,ti.revision" + joins + ordering + " LIMIT %s OFFSET %s", [*args, page_size, (page-1)*page_size])
        rows = c.fetchall()
        # 一次查询所有本页候选，避免缩略图列表的 N+1 查询。
        candidates = {}
        if rows:
            c.execute("SELECT id,task_image_id,geometry FROM preannotations WHERE is_deleted=FALSE AND task_image_id IN (" + ",".join(["%s"]*len(rows)) + ") ORDER BY id", [r["task_image_id"] for r in rows])
            for row in c.fetchall():
                candidates.setdefault(row["task_image_id"], []).append({**json_value(row["geometry"]), "id": row["id"]})
        for row in rows:
            row["candidates"] = candidates.get(row["task_image_id"], [])
        return {"total": total, "items": rows}


def lock_review(c, task_id, image_id, user):
    task = require_task(c, task_id, user)
    c.execute("SELECT * FROM images WHERE id=%s AND dataset_id=%s FOR UPDATE", (image_id, task["dataset_id"]))
    image = c.fetchone()
    if not image:
        raise HTTPException(404, "图片不存在")
    c.execute("SELECT * FROM preannotation_task_images WHERE task_id=%s AND image_id=%s FOR UPDATE", (task_id, image_id))
    item = c.fetchone()
    if not item:
        raise HTTPException(404, "图片不在该任务中")
    if item["execution_status"] != "succeeded":
        raise HTTPException(409, "该图片尚未产生通过验证的结果")
    return task, image, item


def image_detail(c, task_id, image_id, user):
    task = require_task(c, task_id, user)
    c.execute("SELECT * FROM images WHERE id=%s AND dataset_id=%s", (image_id, task["dataset_id"]))
    image = c.fetchone()
    c.execute("SELECT * FROM preannotation_task_images WHERE task_id=%s AND image_id=%s", (task_id, image_id))
    item = c.fetchone()
    if not image or not item:
        raise HTTPException(404, "图片不在该任务中")
    c.execute("SELECT * FROM annotations WHERE image_id=%s ORDER BY id", (image_id,))
    annotations = c.fetchall()
    return {"image": {k: v for k, v in image.items() if k != "file_path"},
            "task_image": {k: v for k, v in item.items() if k not in ("claim_token", "lease_until")},
            "annotations": annotations, "candidates": candidate_rows(c, item["id"])}


@router.get("/preannotation/tasks/{task_id}/images/{image_id}")
def get_task_image(task_id: int, image_id: int, conn=Depends(get_db_dependency), user=Depends(get_current_user)):
    with conn.cursor() as c:
        return image_detail(c, task_id, image_id, user)


@router.put("/preannotation/tasks/{task_id}/images/{image_id}/draft")
def save_draft(task_id: int, image_id: int, data: DraftInput, conn=Depends(get_db_dependency), user=Depends(get_current_user)):
    with conn.cursor() as c:
        _, image, item = lock_review(c, task_id, image_id, user)
        if item["review_status"] in ("approved", "rejected"):
            raise HTTPException(409, "该结果已审核，正式标注请在标注页面修改")
        if item["revision"] != data.revision:
            raise HTTPException(409, "审核草稿已被其他操作修改，请重新加载")
        validate_categories([ann for ann in data.annotations if not ann.is_deleted], categories_for_image(c, image))
        c.execute("SELECT id FROM preannotations WHERE task_image_id=%s", (item["id"],))
        existing = {r["id"] for r in c.fetchall()}
        supplied = [ann.id for ann in data.annotations if ann.id]
        if len(set(supplied)) != len(supplied) or set(supplied) - existing:
            raise HTTPException(422, "草稿候选 ID 重复或不属于本图片")
        c.execute("UPDATE preannotations SET is_deleted=TRUE WHERE task_image_id=%s", (item["id"],))
        for ann in data.annotations:
            geometry = json.dumps(ann.model_dump(exclude={"id", "is_deleted", "source_preannotation_id"}))
            if ann.id:
                c.execute("UPDATE preannotations SET geometry=%s,is_deleted=%s WHERE id=%s AND task_image_id=%s", (geometry, ann.is_deleted, ann.id, item["id"]))
            else:
                c.execute("INSERT INTO preannotations (task_image_id,geometry,is_deleted,is_manual) VALUES (%s,%s,%s,TRUE)", (item["id"], geometry, ann.is_deleted))
        c.execute("UPDATE preannotation_task_images SET revision=revision+1,review_status='draft' WHERE id=%s", (item["id"],))
        return image_detail(c, task_id, image_id, user)


@router.post("/preannotation/tasks/{task_id}/images/{image_id}/review")
def review_image(task_id: int, image_id: int, data: ReviewInput, conn=Depends(get_db_dependency), user=Depends(get_current_user)):
    with conn.cursor() as c:
        _, image, item = lock_review(c, task_id, image_id, user)
        target = "rejected" if data.action == "reject" else "approved"
        if item["review_status"] in ("approved", "rejected"):
            if item["review_status"] == target:
                return image_detail(c, task_id, image_id, user)
            raise HTTPException(409, "结果已审核，不能改为另一结论")
        if item["revision"] != data.revision:
            raise HTTPException(409, "审核草稿已改变，请重新加载")
        if data.action != "reject":
            if image["annotation_revision"] != data.image_revision:
                raise HTTPException(409, "正式标注已改变，请重新加载并核对后审核")
            rows = candidate_rows(c, item["id"], include_deleted=False)
            if data.action == "empty" and rows:
                raise HTTPException(422, "确认无目标前请删除全部候选框")
            annotations = [Annotation.model_validate(row) for row in rows]
            validate_categories(annotations, categories_for_image(c, image))
            for row, ann in zip(rows, annotations):
                insert_annotation(c, image_id, ann, user["id"], row["id"])
            c.execute("SELECT COUNT(*) AS n FROM annotations WHERE image_id=%s", (image_id,))
            total = c.fetchone()["n"]
            finish_image(c, image, "labeled" if total else "skipped", user["id"], len(rows))
            c.execute("INSERT INTO annotation_history (image_id,user_id,action,annotation_data) VALUES (%s,%s,'create',%s)",
                      (image_id, user["id"], json.dumps({"task_id": task_id, "review": data.action, "candidate_ids": [r["id"] for r in rows]})))
        c.execute("UPDATE preannotation_task_images SET review_status=%s,reviewed_by=%s,reviewed_at=NOW(),revision=revision+1 WHERE id=%s", (target, user["id"], item["id"]))
        return image_detail(c, task_id, image_id, user)
