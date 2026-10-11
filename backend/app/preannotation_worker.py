"""独立持久任务 worker：python -m app.preannotation_worker。"""
import asyncio
import json
import logging
import signal
import uuid
from concurrent.futures import ThreadPoolExecutor

from app.core.config import settings
from app.core.database import get_db, get_connection
from app.services.preannotation_inference import infer, decrypt_credentials, json_value, InferenceError
from app.services.preannotation_store import reconcile_task

logger = logging.getLogger("preannotation-worker")


def claim_image():
    """短暂命名锁串行化领取和端点配额计数，推理期间不持有锁或连接。"""
    conn = get_connection()
    acquired = False
    try:
        with conn.cursor() as c:
            c.execute("SELECT GET_LOCK(CONCAT(DATABASE(), ':preannotation-claim'),0) AS acquired")
            acquired = bool(c.fetchone()["acquired"])
            if not acquired:
                return None
            c.execute("SELECT * FROM preannotation_tasks WHERE status IN ('queued','running','cancelling') ORDER BY id LIMIT 100 FOR UPDATE SKIP LOCKED")
            tasks = c.fetchall()
            for task in tasks:
                config = json_value(task["config_snapshot"])
                # 失去租约的结果必须更换领取 token，防止旧 worker 写回。
                c.execute("""UPDATE preannotation_task_images SET execution_status=
                             IF(attempts >= %s,'failed','queued'),claim_token=NULL,lease_until=NULL,
                             error_code='lease_expired',error_message='worker 租约到期，已恢复或达到重试上限'
                             WHERE task_id=%s AND execution_status='running' AND lease_until<NOW(6)""",
                          (config["max_attempts"], task["id"]))
                if task["status"] == "cancelling":
                    c.execute("UPDATE preannotation_task_images SET execution_status='cancelled',claim_token=NULL,lease_until=NULL WHERE task_id=%s AND execution_status='queued'", (task["id"],))
                    reconcile_task(c, task["id"])
                    continue
                c.execute("""SELECT COUNT(*) AS n FROM preannotation_task_images ti
                             JOIN preannotation_tasks t ON t.id=ti.task_id
                             WHERE t.endpoint_key=%s AND ti.execution_status='running' AND ti.lease_until>=NOW(6)""", (task["endpoint_key"],))
                if c.fetchone()["n"] >= max(1, settings.PREANNOTATION_ENDPOINT_CONCURRENCY):
                    reconcile_task(c, task["id"])
                    continue
                c.execute("""SELECT * FROM preannotation_task_images WHERE task_id=%s AND execution_status='queued'
                             AND (retry_at IS NULL OR retry_at<=NOW(6)) ORDER BY image_id LIMIT 1 FOR UPDATE SKIP LOCKED""", (task["id"],))
                item = c.fetchone()
                if not item:
                    reconcile_task(c, task["id"])
                    continue
                token = str(uuid.uuid4())
                c.execute("UPDATE preannotation_task_images SET execution_status='running',attempts=attempts+1,claim_token=%s,lease_until=DATE_ADD(NOW(6),INTERVAL 45 SECOND),error_code=NULL,error_message=NULL WHERE id=%s", (token, item["id"]))
                c.execute("UPDATE preannotation_tasks SET status='running' WHERE id=%s", (task["id"],))
                c.execute("SELECT file_path FROM images WHERE id=%s", (item["image_id"],))
                image = c.fetchone()
                c.execute("SELECT credentials,is_active FROM preannotation_profiles WHERE id=%s", (task["profile_id"],))
                profile = c.fetchone()
                conn.commit()
                return {"task": task, "item": {**item, "attempts": item["attempts"]+1}, "config": config,
                        "token": token, "image": image, "profile": profile}
            conn.commit()
            return None
    except Exception:
        conn.rollback()
        raise
    finally:
        if acquired:
            with conn.cursor() as c:
                c.execute("SELECT RELEASE_LOCK(CONCAT(DATABASE(), ':preannotation-claim'))")
        conn.close()


def heartbeat(item_id, token):
    with get_db() as conn, conn.cursor() as c:
        c.execute("UPDATE preannotation_task_images SET lease_until=DATE_ADD(NOW(6),INTERVAL 45 SECOND) WHERE id=%s AND claim_token=%s AND execution_status='running'", (item_id, token))
        return bool(c.rowcount)


def save_result(claim, annotations=None, raw=None, error=None):
    task, item = claim["task"], claim["item"]
    with get_db() as conn, conn.cursor() as c:
        c.execute("SELECT status FROM preannotation_tasks WHERE id=%s FOR UPDATE", (task["id"],))
        current_task = c.fetchone()
        if not current_task:
            return False
        c.execute("SELECT * FROM preannotation_task_images WHERE id=%s FOR UPDATE", (item["id"],))
        current = c.fetchone()
        if not current or current["claim_token"] != claim["token"] or current["execution_status"] != "running":
            return False
        if current_task["status"] in ("cancelled", "cancelling"):
            c.execute("UPDATE preannotation_task_images SET execution_status='cancelled',claim_token=NULL,lease_until=NULL WHERE id=%s", (item["id"],))
        elif error:
            retry = error.retryable and current["attempts"] < claim["config"]["max_attempts"]
            c.execute("""UPDATE preannotation_task_images SET execution_status=%s,error_code=%s,error_message=%s,
                         raw_response=%s,claim_token=NULL,lease_until=NULL,retry_at=DATE_ADD(NOW(6),INTERVAL %s SECOND)
                         WHERE id=%s""", ("queued" if retry else "failed", error.code, str(error)[:2000],
                                          error.raw_response, min(60, 2 ** current["attempts"]), item["id"]))
        else:
            # 校验最新类别；任务快照对应类别被删除时不落入成功状态。
            c.execute("SELECT id FROM categories WHERE dataset_id=%s", (task["dataset_id"],))
            ids = {r["id"] for r in c.fetchall()}
            if any(ann["category_id"] not in ids for ann in annotations):
                c.execute("UPDATE preannotation_task_images SET execution_status='failed',error_code='category_deleted',error_message='模型结果使用的类别已被删除',raw_response=%s,claim_token=NULL,lease_until=NULL WHERE id=%s", (raw, item["id"]))
            else:
                if annotations:
                    c.executemany("INSERT INTO preannotations (task_image_id,original_geometry,geometry) VALUES (%s,%s,%s)",
                                  [(item["id"], json.dumps(ann), json.dumps(ann)) for ann in annotations])
                c.execute("UPDATE preannotation_task_images SET execution_status='succeeded',original_count=%s,raw_response=%s,claim_token=NULL,lease_until=NULL,retry_at=NULL,revision=revision+1 WHERE id=%s", (len(annotations), raw, item["id"]))
        reconcile_task(c, task["id"])
        return True


async def keep_lease(claim, inference_task):
    while not inference_task.done():
        await asyncio.sleep(10)
        if inference_task.done():
            return
        active = await asyncio.to_thread(heartbeat, claim["item"]["id"], claim["token"])
        if not active:
            inference_task.cancel()
            return


async def execute_claim(claim):
    lease_task = None
    try:
        profile = claim["profile"]
        if not profile or not profile["is_active"]:
            raise InferenceError("profile", "接口配置已停用")
        if not claim["image"]:
            raise InferenceError("image", "图片已被删除")
        credentials = decrypt_credentials(profile["credentials"])
        task = claim["task"]
        request = asyncio.create_task(infer(claim["config"], credentials, claim["image"]["file_path"],
                                            task["prompt"], json_value(task["categories_snapshot"]), task["annotation_type"]))
        lease_task = asyncio.create_task(keep_lease(claim, request))
        try:
            annotations, raw = await asyncio.wait_for(request, timeout=claim["config"]["timeout_seconds"])
        except TimeoutError as exc:
            raise InferenceError("timeout", "推理总耗时超过限制", True) from exc
        await asyncio.to_thread(save_result, claim, annotations, raw)
    except asyncio.CancelledError:
        # 租约被取消 / 收回，旧领取 token 不得写回。
        return
    except InferenceError as exc:
        await asyncio.to_thread(save_result, claim, error=exc)
    except Exception:
        logger.exception("执行任务图片失败 task=%s image=%s", claim["task"]["id"], claim["item"]["image_id"])
        await asyncio.to_thread(save_result, claim, error=InferenceError("internal", "worker 执行异常，请查看服务端日志", True))
    finally:
        if lease_task:
            lease_task.cancel()
            await asyncio.gather(lease_task, return_exceptions=True)


async def run_worker(once=False):
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    slots = max(1, min(16, settings.PREANNOTATION_WORKER_CONCURRENCY))
    loop.set_default_executor(ThreadPoolExecutor(max_workers=max(4, slots*2)))
    active = set()
    logger.info("worker 启动 concurrency=%s", slots)
    try:
        while not stop.is_set():
            active = {task for task in active if not task.done()}
            claim = await asyncio.to_thread(claim_image) if len(active) < slots else None
            if claim:
                task = asyncio.create_task(execute_claim(claim))
                active.add(task)
                if once:
                    await task
                    return
                continue
            if once:
                return
            try:
                await asyncio.wait_for(stop.wait(), timeout=1)
            except TimeoutError:
                pass
    finally:
        for task in active:
            task.cancel()
        await asyncio.gather(*active, return_exceptions=True)
        logger.info("worker 已停止；未完成的领取将在租约到期后恢复")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="执行一张图片后退出（诊断 / 测试）")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(run_worker(args.once))
