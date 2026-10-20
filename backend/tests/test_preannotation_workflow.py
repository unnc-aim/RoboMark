"""使用隔离的真实 MySQL 验证队列、故障恢复和审核事务。
运行时显式设置 ROBOMARK_TEST_DATABASE_URL；绝不清空业务数据库。
"""
import asyncio
import json
import os
import threading
import subprocess
import sys
from urllib.parse import urlsplit
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
    assert system['client'].get(f"/api/preannotation/profiles/{p['id']}").json()['has_api_key']
    job = task(system, profile=p, sample_size=2)
    response = system["client"].put(f"/api/preannotation/profiles/{p['id']}", json={"name":"changed","endpoint":"http://127.0.0.1:9998/other"})
    assert response.status_code == 200
    claim = claim_image()
    assert claim["config"]["endpoint"] == p["endpoint"]
    assert job["total_images"] == 2
    system["user"]["id"] = 999
    system["user"]["is_admin"] = False
    assert system['client'].get(f"/api/preannotation/profiles/{p['id']}").status_code == 403
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
            claim = claim_image()
            # 新进程从 MySQL 中恢复过期领取，证明队列不依赖内存或 API 进程。
            with database.get_db() as conn, conn.cursor() as c:
                c.execute('UPDATE preannotation_task_images SET lease_until=DATE_SUB(NOW(6),INTERVAL 1 SECOND) WHERE id=%s', (claim['item']['id'],))
            env = dict(os.environ)
            address = urlsplit(os.environ['ROBOMARK_TEST_DATABASE_URL'])
            env['DATABASE_URL'] = address._replace(path='/'+database.db_config['database']).geturl()
            process = subprocess.run([sys.executable,'-m','app.preannotation_worker','--once'], cwd=Path(__file__).resolve().parents[1],env=env,capture_output=True,text=True,timeout=20)
            assert process.returncode == 0, process.stderr
            assert not save_result(claim,[box(system)],'late from previous process')
            state = detail(system,job,claim['item']['image_id'])
            assert state['task_image']['execution_status'] == 'succeeded', state
            assert len(state['candidates']) == 1
            history=trace(system,job,claim['item']['image_id'])
            assert history['total']==2
            assert history['attempts'][0]['status']=='interrupted'
            assert set(history['attempts'][-1]['trace'])=={'request','response_headers','response','parsed','normalized'}
            assert 'test-token' not in json.dumps(history)
            assert 'base64,' not in json.dumps(history)
    finally:
        server.shutdown();server.server_close();thread.join()


def test_environment_config_sync_is_idempotent_and_managed(system, monkeypatch):
    from app.core.config import settings
    from app.services.preannotation_config import sync_environment_profile
    monkeypatch.setattr(settings, 'PREANNOTATION_DEFAULT_PROFILE', {
        'endpoint':'http://127.0.0.1:8001/v1/chat/completions', 'model':'vision-model', 'api_key':'env-secret'})
    pid = sync_environment_profile()
    assert sync_environment_profile() == pid
    with database.get_db() as conn, conn.cursor() as c:
        c.execute('SELECT version,credentials FROM preannotation_profiles WHERE id=%s', (pid,))
        row = c.fetchone()
        assert row['version'] == 2
        assert 'env-secret' not in row['credentials']
    response = system['client'].put(f'/api/preannotation/profiles/{pid}',json={'name':'changed','endpoint':'http://localhost/x'})
    assert response.status_code == 409
    monkeypatch.setattr(settings, 'PREANNOTATION_DEFAULT_PROFILE', {
        'endpoint':'http://127.0.0.1:8001/v1/chat/completions', 'model':'changed-model', 'api_key':'env-secret'})
    assert sync_environment_profile() == pid
    with database.get_db() as conn, conn.cursor() as c:
        c.execute('SELECT version,config FROM preannotation_profiles WHERE id=%s', (pid,))
        row = c.fetchone()
        assert row['version'] == 3 and json.loads(row['config'])['model'] == 'changed-model'


def test_existing_database_upgrade_preserves_annotations(system):
    from app.services.preannotation_store import insert_annotation
    with database.get_db() as conn, conn.cursor() as c:
        annotation_id = insert_annotation(c,system['images'][0],box(system),1)
        for table in ('preannotations','preannotation_attempts','preannotation_task_images','preannotation_tasks','preannotation_profiles','dataset_configs'):
            c.execute(f'DROP TABLE {table}')
        c.execute('ALTER TABLE images DROP COLUMN annotation_revision')
        c.execute('ALTER TABLE annotations DROP INDEX uk_annotation_source, DROP COLUMN source_preannotation_id, DROP COLUMN annotation_type')
        for i in range(1,5):
            for axis in ('x','y'):c.execute(f'ALTER TABLE annotations DROP COLUMN p{i}_{axis}')
        c.execute('ALTER TABLE categories DROP COLUMN template_image_path')
    migrate();migrate()
    with database.get_db() as conn, conn.cursor() as c:
        c.execute('SELECT id,x_center,annotation_type FROM annotations WHERE id=%s',(annotation_id,))
        row = c.fetchone()
        assert row['id'] == annotation_id and row['x_center'] == .5 and row['annotation_type'] == 'bbox'


def test_retry_limits_endpoint_quota_and_filtered_navigation(system):
    first = task(system)
    task(system)
    claim = claim_image()
    assert claim_image() is None  # 同一 endpoint 的全局并发配额
    save_result(claim,error=InferenceError('network','temporary',True))
    with database.get_db() as conn, conn.cursor() as c:
        c.execute('UPDATE preannotation_task_images SET retry_at=NULL,attempts=2 WHERE id=%s',(claim['item']['id'],))
    claim = claim_image()
    assert claim['item']['attempts'] == 3
    save_result(claim,error=InferenceError('network','temporary',True))
    succeed(system,0)
    succeeded = succeed(system)
    response = system['client'].get(f"/api/datasets/{system['dataset']}/images",params={
        'task_id':first['id'],'has_candidates':'true','after_id':system['images'][0],'page_size':1})
    assert response.status_code == 200
    assert response.json()['items'][0]['id'] == succeeded['item']['image_id']
    response = system['client'].get(f"/api/datasets/{system['dataset']}/images",params={
        'task_id':first['id'],'execution_status':'succeeded','before_id':succeeded['item']['image_id'],'page_size':1})
    assert response.json()['items'][0]['id'] == system['images'][1]


def test_export_only_includes_formal_annotations(system):
    from app.services.preannotation_store import insert_annotation, finish_image
    image_id = system['images'][0]
    with database.get_db() as conn, conn.cursor() as c:
        c.execute('SELECT * FROM images WHERE id=%s FOR UPDATE',(image_id,))
        image = c.fetchone()
        insert_annotation(c,image_id,box(system),1)
        finish_image(c,image,'labeled',1,1)
    job = task(system,sample_size=1)
    succeed(system)
    def export():
        response = system['client'].post('/api/export',json={'dataset_id':system['dataset']})
        assert response.status_code == 200,response.text
        downloaded = system['client'].get(response.json()['download_url'])
        assert downloaded.status_code == 200
        return response.json(),downloaded.content
    before,_ = export()
    assert before['total_annotations'] == 1
    state = detail(system,job,image_id)
    reviewed = system['client'].post(f"/api/preannotation/tasks/{job['id']}/images/{image_id}/review",json={
        'revision':state['task_image']['revision'],'image_revision':state['image']['annotation_revision'],'action':'approve'})
    assert reviewed.status_code == 200
    after,data = export()
    assert after['total_annotations'] == 2
    import io,zipfile
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        labels = [n for n in z.namelist() if '/labels/' in n and n.endswith('.txt')]
        assert len(labels) == 1 and len(z.read(labels[0]).decode().strip().splitlines()) == 2


def test_saved_and_draft_connection_tests_preserve_credentials_and_permissions(system,monkeypatch):
    calls=[]
    async def fake_probe(config,credentials):
        calls.append((config,credentials))
        return {'ok':True,'reachable':True,'status':'ready','message':'连接成功','latency_ms':1}
    monkeypatch.setattr('app.routers.preannotation.probe_connection',fake_probe)
    p=profile(system,api_key='saved-key',headers={'X-Token':'saved-header'},is_shared=True)
    response=system['client'].post(f"/api/preannotation/profiles/{p['id']}/test")
    assert response.status_code==200 and response.json()['ok']
    assert calls[-1][1]=={'api_key':'saved-key','headers':{'X-Token':'saved-header'}}
    draft={'profile':{'name':'draft','endpoint':p['endpoint'],'api_key':None,'headers':{'X-Token':'[已保存]'}},'existing_profile_id':p['id']}
    response=system['client'].post('/api/preannotation/profiles/test',json=draft)
    assert response.status_code==200 and calls[-1][1]=={'api_key':'saved-key','headers':{'X-Token':'saved-header'}}
    with database.get_db() as conn,conn.cursor() as c:
        c.execute('SELECT version FROM preannotation_profiles WHERE id=%s',(p['id'],))
        assert c.fetchone()['version']==1
    system['user'].update(id=999,is_admin=False)
    assert system['client'].post(f"/api/preannotation/profiles/{p['id']}/test").status_code==200
    draft['profile']['endpoint']='http://different-server/capture'
    n=len(calls)
    assert system['client'].post('/api/preannotation/profiles/test',json=draft).status_code==403
    assert len(calls)==n


def test_new_draft_connection_test_does_not_save_profile(system,monkeypatch):
    async def fake_probe(config,credentials):
        return {'ok':False,'reachable':True,'status':'authentication_failed','message':'认证失败','latency_ms':1}
    monkeypatch.setattr('app.routers.preannotation.probe_connection',fake_probe)
    response=system['client'].post('/api/preannotation/profiles/test',json={'profile':{'name':'temporary','endpoint':'http://localhost:8001/v1/chat/completions'}})
    assert response.status_code==200 and response.json()['status']=='authentication_failed'
    with database.get_db() as conn,conn.cursor() as c:
        c.execute('SELECT COUNT(*) AS n FROM preannotation_profiles')
        assert c.fetchone()['n']==0


def test_pending_review_queue_includes_drafts_but_excludes_final_reviews(system):
    job=task(system)
    for _ in range(3):succeed(system)
    with database.get_db() as conn,conn.cursor() as c:
        c.execute("UPDATE preannotation_task_images SET review_status='draft' WHERE task_id=%s AND image_id=%s",(job['id'],system['images'][1]))
        c.execute("UPDATE preannotation_task_images SET review_status='approved' WHERE task_id=%s AND image_id=%s",(job['id'],system['images'][2]))
    response=system['client'].get(f"/api/datasets/{system['dataset']}/images",params={
        'task_id':job['id'],'review_status':'pending','execution_status':'succeeded'})
    assert response.status_code==200
    assert [row['id'] for row in response.json()['items']]==system['images'][:2]


def test_slow_model_has_no_per_image_deadline(system, monkeypatch):
    """超过旧配置时长仍能完成，且租约任务随请求收尾。"""
    job = task(system, sample_size=1)
    claim = claim_image()
    claim['config']['timeout_seconds'] = .01

    async def slow_infer(*args, **kwargs):
        await asyncio.sleep(.08)
        return [box(system)], '{"slow":true}'

    monkeypatch.setattr('app.preannotation_worker.infer', slow_infer)
    asyncio.run(execute_claim(claim))
    assert detail(system, job, claim['item']['image_id'])['task_image']['execution_status'] == 'succeeded'


def trace(system, job, image_id, **params):
    response=system['client'].get(f"/api/preannotation/tasks/{job['id']}/images/{image_id}/trace",params=params)
    assert response.status_code==200,response.text
    return response.json()


def test_per_image_retry_preserves_attempt_history_and_protects_success(system):
    job=task(system,sample_size=1)
    first=claim_image();image_id=first['item']['image_id']
    save_result(first,error=InferenceError('validation','响应格式错误'))
    assert trace(system,job,image_id)['can_retry']
    url=f"/api/preannotation/tasks/{job['id']}/images/{image_id}/retry"
    assert system['client'].post(url).status_code==200
    assert system['client'].post(url).status_code==409
    second=claim_image();save_result(second,[box(system)],'success')
    history=trace(system,job,image_id)
    assert [(a['sequence_number'],a['status']) for a in history['attempts']]==[(1,'failed'),(2,'succeeded')]
    assert history['attempts'][0]['error_message']=='响应格式错误'
    assert not history['can_retry']
    assert system['client'].post(url).status_code==409
    assert len(detail(system,job,image_id)['candidates'])==1


def test_waiting_automatic_retry_can_be_started_immediately(system):
    job=task(system,sample_size=1)
    claim=claim_image();image_id=claim['item']['image_id']
    save_result(claim,error=InferenceError('network','连接失败',True))
    state=trace(system,job,image_id)
    assert state['task_image']['execution_status']=='queued' and state['can_retry']
    assert system['client'].get(f"/api/preannotation/tasks/{job['id']}").json()['retryable_images']==1
    assert system['client'].post(f"/api/preannotation/tasks/{job['id']}/retry-failed").json()['retried_images']==1
    assert claim_image()['item']['image_id']==image_id
    assert trace(system,job,image_id)['total']==2


def test_attempt_pagination_and_legacy_fallback(system):
    job=task(system,sample_size=1);image_id=system['images'][0]
    for _ in range(6):
        claim=claim_image();save_result(claim,error=InferenceError('validation','bad output'))
        system['client'].post(f"/api/preannotation/tasks/{job['id']}/images/{image_id}/retry")
    latest=trace(system,job,image_id,page_size=2)
    assert [a['sequence_number'] for a in latest['attempts']]==[5,6]
    older=trace(system,job,image_id,before_id=latest['attempts'][0]['id'],page_size=2)
    assert [a['sequence_number'] for a in older['attempts']]==[3,4]
    with database.get_db() as conn,conn.cursor() as c:
        c.execute('DELETE FROM preannotation_attempts WHERE task_image_id=%s',(claim['item']['id'],))
        c.execute('UPDATE preannotation_task_images SET raw_response=%s WHERE id=%s',('{"legacy":true}',claim['item']['id']))
    legacy=trace(system,job,image_id)
    assert legacy['total']==0 and legacy['legacy_response']=='{"legacy":true}'


def test_trace_permissions_cancel_and_late_record_protection(system):
    from app.services.preannotation_trace import record_event
    from app.core.security import get_current_user
    job=task(system,sample_size=1);claim=claim_image();image_id=claim['item']['image_id']
    record_event(claim,'request',{'body':{'model':'test'}})
    app.dependency_overrides[get_current_user]=lambda:{'id':99,'is_admin':False,'is_active':True}
    assert system['client'].post(f"/api/preannotation/tasks/{job['id']}/images/{image_id}/retry").status_code==403
    app.dependency_overrides[get_current_user]=lambda:system['user']
    assert system['client'].post(f"/api/preannotation/tasks/{job['id']}/cancel").status_code==200
    record_event(claim,'response',{'raw':'late response'})
    state=trace(system,job,image_id)
    assert state['attempts'][0]['status']=='cancelled'
    assert 'response' not in state['attempts'][0]['trace']
    assert system['client'].get(f"/api/preannotation/tasks/{job['id']}/images/99999/trace").status_code==404
    with database.get_db() as conn,conn.cursor() as c:
        c.execute('UPDATE datasets SET is_active=FALSE WHERE id=%s',(system['dataset'],))
    app.dependency_overrides[get_current_user]=lambda:{'id':99,'is_admin':False,'is_active':True}
    assert system['client'].get(f"/api/preannotation/tasks/{job['id']}/images/{image_id}/trace").status_code==403


def test_retry_archives_available_legacy_error_without_inventing_request(system):
    job=task(system,sample_size=1);image_id=system['images'][0]
    with database.get_db() as conn,conn.cursor() as c:
        c.execute("UPDATE preannotation_task_images SET execution_status='failed',attempts=3,error_code='timeout',error_message='旧版本整图超时' WHERE task_id=%s",(job['id'],))
    assert system['client'].post(f"/api/preannotation/tasks/{job['id']}/images/{image_id}/retry").status_code==200
    claim_image();history=trace(system,job,image_id)
    assert history['total']==2
    old=history['attempts'][0]
    assert old['trace']=={'legacy':True} and old['elapsed_ms'] is None
    assert old['error_message']=='旧版本整图超时'
    assert history['attempts'][1]['sequence_number']==4


def test_image_cards_use_latest_success_usage_and_lightweight_legacy_fallback(system):
    from app.services.preannotation_trace import record_event
    job=task(system)
    failed=claim_image()
    record_event(failed,'parsed',{'usage':{'prompt_tokens':9999,'completion_tokens':9999}})
    save_result(failed,error=InferenceError('validation','bad'))
    assert system['client'].post(f"/api/preannotation/tasks/{job['id']}/images/{failed['item']['image_id']}/retry").status_code==200
    success=claim_image()
    record_event(success,'request',{'body':{'model':'test'}})
    record_event(success,'response',{'elapsed_ms':2000})
    record_event(success,'parsed',{'usage':{'prompt_tokens':1280,'completion_tokens':256}})
    save_result(success,[box(system)],json.dumps({'usage':{'prompt_tokens':1280,'completion_tokens':256}}))
    legacy=claim_image()
    save_result(legacy,[],json.dumps({'usage':{'input_tokens':0,'output_tokens':12}}))
    with database.get_db() as conn,conn.cursor() as c:
        c.execute('DELETE FROM preannotation_attempts WHERE task_image_id=%s',(legacy['item']['id'],))
    unknown=claim_image();save_result(unknown,[box(system)],'invalid JSON in a legacy record')
    response=system['client'].get(f"/api/datasets/{system['dataset']}/images",params={'task_id':job['id']})
    assert response.status_code==200,response.text
    rows={row['id']:row for row in response.json()['items']}
    metrics=rows[success['item']['image_id']]['inference_metrics']
    assert metrics['input_tokens']==1280 and metrics['output_tokens']==256 and metrics['tps']==128
    old=rows[legacy['item']['image_id']]['inference_metrics']
    assert old['input_tokens']==0 and old['output_tokens']==12 and old['tps'] is None
    assert rows[unknown['item']['image_id']]['inference_metrics']['input_tokens'] is None
    assert 'legacy_usage' not in response.text and 'raw_response' not in response.text
