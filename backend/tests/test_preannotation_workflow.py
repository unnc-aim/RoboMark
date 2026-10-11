"""使用隔离的真实 MySQL 验证队列、故障恢复和审核事务。
运行时显式设置 ROBOMARK_TEST_DATABASE_URL；绝不清空业务数据库。
"""
import asyncio
import json
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pymysql
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from app.core import database
from app.core.security import get_current_user
from app.main import app
from app.migrate import migrate
from app.preannotation_worker import claim_image, save_result, execute_claim, heartbeat
from app.services.preannotation_inference import InferenceError

pytestmark = pytest.mark.skipif(not os.getenv("ROBOMARK_TEST_DATABASE_URL"), reason="需要显式隔离 MySQL 测试地址")


@pytest.fixture
def system(tmp_path):
    original = dict(database.db_config)
    name = "robomark_test_" + uuid.uuid4().hex[:12]
    admin = pymysql.connect(**original)
    try:
        with admin.cursor() as c:
            c.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4")
        admin.commit()
        database.db_config["database"] = name
        with database.get_db() as conn, conn.cursor() as c:
            sql = (Path(__file__).resolve().parents[2] / "database/init.sql").read_text()
            sql = sql.replace("robomark DEFAULT", name+" DEFAULT").replace("USE robomark;", "USE "+name+";")
            for statement in sql.split(";"):
                if statement.strip():
                    c.execute(statement)
        migrate()
        migrate()
        image_path = tmp_path / "drone.png"
        Image.new("RGB", (320, 240), "white").save(image_path)
        with database.get_db() as conn, conn.cursor() as c:
            c.execute("INSERT INTO datasets (name,image_path,total_images) VALUES ('test',%s,3)", (str(tmp_path),))
            dataset = c.lastrowid
            c.execute("INSERT INTO categories (dataset_id,name) VALUES (%s,'无人机')", (dataset,))
            category = c.lastrowid
            c.executemany("INSERT INTO images (dataset_id,filename,file_path,width,height) VALUES (%s,%s,%s,320,240)",
                          [(dataset, f"drone_{i}.png", str(image_path)) for i in range(3)])
            c.execute("SELECT id FROM images WHERE dataset_id=%s ORDER BY id", (dataset,))
            images = [r["id"] for r in c.fetchall()]
        user = {"id":1,"is_admin":True,"is_active":True,"username":"admin"}
        app.dependency_overrides[get_current_user] = lambda: user
        with TestClient(app) as client:
            yield {"client":client,"dataset":dataset,"category":category,"images":images,"user":user}
    finally:
        app.dependency_overrides.clear()
        database.db_config.clear()
        database.db_config.update(original)
        with admin.cursor() as c:
            c.execute(f"DROP DATABASE IF EXISTS `{name}`")
        admin.close()


def profile(system, **updates):
    payload = {"name":"mock","endpoint":"http://127.0.0.1:9999/v1/chat/completions", **updates}
    response = system["client"].post("/api/preannotation/profiles", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def task(system, **updates):
    config = updates.pop("profile", None) or profile(system)
    response = system["client"].post(f"/api/datasets/{system['dataset']}/preannotation-tasks",
                                    json={"profile_id":config["id"],"prompt":"标注无人机","category_ids":[system["category"]],**updates})
    assert response.status_code == 202, response.text
    return response.json()


def box(system):
    return {"category_id":system["category"],"annotation_type":"bbox","x_center":.5,"y_center":.5,"width":.2,"height":.2}


def succeed(system, count=1):
    claim = claim_image()
    assert claim
    assert save_result(claim, [box(system)]*count, '{"mock":true}')
    return claim


def detail(system, job, image):
    response = system["client"].get(f"/api/preannotation/tasks/{job['id']}/images/{image}")
    assert response.status_code == 200, response.text
    return response.json()


def test_profile_secrets_permissions_and_task_snapshots(system):
    p = profile(system, api_key="do-not-return", headers={"X-Token":"private-header"})
    assert p["headers"] == {"X-Token":"[已保存]"}
    assert "do-not-return" not in json.dumps(p)
    job = task(system, profile=p, sample_size=2)
    response = system["client"].put(f"/api/preannotation/profiles/{p['id']}", json={"name":"changed","endpoint":"http://127.0.0.1:9998/other"})
    assert response.status_code == 200
    claim = claim_image()
    assert claim["config"]["endpoint"] == p["endpoint"]
    assert job["total_images"] == 2
    system["user"]["id"] = 999
    system["user"]["is_admin"] = False
    assert system["client"].put(f"/api/preannotation/profiles/{p['id']}", json={"name":"x","endpoint":"http://localhost/x"}).status_code == 403
    assert system["client"].post(f"/api/preannotation/tasks/{job['id']}/cancel").status_code == 403


def test_queue_idempotency_empty_failure_and_filters(system):
    job = task(system)
    first = succeed(system)
    assert not save_result(first, [box(system)], "duplicate")
    second = succeed(system, 0)
    third = claim_image()
    save_result(third, error=InferenceError("validation","bad schema"))
    status = system["client"].get(f"/api/preannotation/tasks/{job['id']}").json()
    assert status["status"] == "completed_with_errors"
    assert status["processed_images"] == 3
    assert status["with_results"] == 1 and status["empty_results"] == 1
    response = system["client"].get(f"/api/datasets/{system['dataset']}/images", params={"task_id":job["id"],"has_candidates":"true"})
    assert response.json()["total"] == 1
    response = system["client"].get(f"/api/datasets/{system['dataset']}/images", params={"task_id":job["id"],"execution_status":"succeeded","has_candidates":"false"})
    assert response.json()["total"] == 1
    assert detail(system,job,second["item"]["image_id"])["task_image"]["execution_status"] == "succeeded"
    retried = system["client"].post(f"/api/preannotation/tasks/{job['id']}/retry-failed")
    assert retried.status_code == 200
    assert claim_image()["item"]["image_id"] == third["item"]["image_id"]


def test_cancel_and_lease_recovery_reject_late_results(system):
    job = task(system)
    old = claim_image()
    with database.get_db() as conn, conn.cursor() as c:
        c.execute("UPDATE preannotation_task_images SET lease_until=DATE_SUB(NOW(6),INTERVAL 1 SECOND) WHERE id=%s", (old["item"]["id"],))
    recovered = claim_image()
    assert recovered["item"]["id"] == old["item"]["id"]
    assert recovered["token"] != old["token"]
    assert not save_result(old, [box(system)], "stale")
    assert heartbeat(recovered["item"]["id"], recovered["token"])
    response = system["client"].post(f"/api/preannotation/tasks/{job['id']}/cancel")
    assert response.json()["status"] == "cancelled"
    assert not save_result(recovered, [box(system)], "late")
    assert claim_image() is None


def test_edit_delete_draft_review_merge_and_duplicate_approval(system):
    job = task(system, sample_size=1)
    claim = succeed(system, 2)
    image_id = claim["item"]["image_id"]
    state = detail(system, job, image_id)
    assert not state["annotations"]
    first, second = state["candidates"]
    first["x_center"] = .6
    second["is_deleted"] = True
    payload = {"revision":state["task_image"]["revision"],"annotations":[first,second]}
    url = f"/api/preannotation/tasks/{job['id']}/images/{image_id}"
    response = system["client"].put(url+"/draft", json=payload)
    assert response.status_code == 200, response.text
    assert system["client"].put(url+"/draft", json=payload).status_code == 409
    saved = detail(system, job, image_id)
    assert saved["candidates"][0]["x_center"] == .6
    assert saved["candidates"][1]["is_deleted"]
    with database.get_db() as conn, conn.cursor() as c:
        # 模拟已有人工框；审核不得覆盖它。
        from app.services.preannotation_store import insert_annotation
        insert_annotation(c, image_id, box(system), 1)
    approval = {"revision":saved["task_image"]["revision"],"image_revision":saved["image"]["annotation_revision"],"action":"approve"}
    response = system["client"].post(url+"/review", json=approval)
    assert response.status_code == 200, response.text
    assert len(response.json()["annotations"]) == 2
    assert system["client"].post(url+"/review", json=approval).status_code == 200
    assert len(detail(system, job, image_id)["annotations"]) == 2
    with database.get_db() as conn, conn.cursor() as c:
        c.execute("SELECT images_labeled,annotations_created FROM work_statistics WHERE dataset_id=%s", (system["dataset"],))
        assert c.fetchone() == {"images_labeled":1,"annotations_created":1}


def test_formal_revision_conflict_and_source_preserved_by_normal_save(system):
    job = task(system, sample_size=1)
    claim = succeed(system)
    image_id = claim["item"]["image_id"]
    state = detail(system, job, image_id)
    url = f"/api/preannotation/tasks/{job['id']}/images/{image_id}"
    body = {"revision":state["task_image"]["revision"],"image_revision":999,"action":"approve"}
    assert system["client"].post(url+"/review",json=body).status_code == 409
    body["image_revision"] = state["image"]["annotation_revision"]
    state = system["client"].post(url+"/review",json=body).json()
    manual = {"annotations":state["annotations"],"revision":state["image"]["annotation_revision"]}
    response = system["client"].post(f"/api/images/{image_id}/save", json=manual)
    assert response.status_code == 200, response.text
    assert system["client"].post(f"/api/images/{image_id}/save",json=manual).status_code == 409
    assert detail(system,job,image_id)["annotations"][0]["source_preannotation_id"]


def test_empty_review_and_new_batch_do_not_overwrite_existing(system):
    job = task(system,sample_size=1)
    claim = succeed(system,0)
    image_id = claim["item"]["image_id"]
    state = detail(system,job,image_id)
    url = f"/api/preannotation/tasks/{job['id']}/images/{image_id}"
    response = system["client"].post(url+"/review",json={"revision":state["task_image"]["revision"],"image_revision":0,"action":"empty"})
    assert response.status_code == 200
    assert response.json()["image"]["status"] == "skipped"
    next_job = task(system,sample_size=1)
    succeed(system)
    assert detail(system,job,image_id)["task_image"]["review_status"] == "approved"
    assert detail(system,next_job,image_id)["task_image"]["review_status"] == "unreviewed"


def test_real_http_adapters_use_same_background_pipeline(system):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if self.path == '/generic':
                assert body["image"].startswith("data:image/")
                assert isinstance(body["schema"],dict)
                response = {"result":{"objects":[{"label":"无人机","bounds":[100,100,300,300]}]}}
            else:
                assert body["messages"][1]["content"][1]["image_url"]["url"].startswith("data:image/")
                assert self.headers['Authorization'] == 'Bearer test-token'
                response = {"choices":[{"finish_reason":"stop","message":{"content":json.dumps({"annotations":[box(system)]})}}]}
            data = json.dumps(response).encode()
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(data)
    server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread = threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        base = f'http://127.0.0.1:{server.server_port}'
        for config in [{"endpoint":base+'/openai',"api_key":"test-token"},
                       {"endpoint":base+'/generic',"interface_type":"http_json","response_path":"result",
                        "annotations_path":"objects","coordinate_system":"relative_1000","box_format":"xyxy",
                        "field_mapping":{"bbox":"bounds","label":"label"},
                        "request_template":{"image":"{{image.data_url}}","prompt":"{{prompt}}","schema":"{{output_schema}}"}}]:
            job = task(system,profile=profile(system,**config),sample_size=1)
            claim = claim_image();asyncio.run(execute_claim(claim))
            state = detail(system,job,claim['item']['image_id'])
            assert state['task_image']['execution_status'] == 'succeeded', state
            assert len(state['candidates']) == 1
    finally:
        server.shutdown();server.server_close();thread.join()
