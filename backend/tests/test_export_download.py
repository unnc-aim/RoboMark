"""Export/download regressions, with no database or production files."""
import os
import time
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core import get_current_admin, get_db_dependency
from app.routers import export


class ExportCursor:
    def __init__(self, image):
        self.image = image
        self.query = ''

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, query, params):
        self.query = query

    def fetchone(self):
        return {'id': 7, 'name': 'demo'}

    def fetchall(self):
        if 'FROM categories' in self.query:
            return [{'id': 1, 'name': '机器人'}]
        if 'FROM images' in self.query:
            return [{'id': 1, 'file_path': str(self.image), 'filename': 'demo.jpg', 'width': 640, 'height': 480}]
        return [{'category_id': 1, 'x_center': .5, 'y_center': .5, 'width': .2, 'height': .3}]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(export, 'EXPORT_ROOT', tmp_path / 'exports')
    image = tmp_path / 'demo.jpg'
    image.write_bytes(b'test image bytes')
    class Connection:
        def cursor(self):
            return ExportCursor(image)
    application = FastAPI()
    application.include_router(export.router)
    application.dependency_overrides[get_db_dependency] = lambda: Connection()
    application.dependency_overrides[get_current_admin] = lambda: {'id': 1, 'is_admin': True}
    with TestClient(application) as instance:
        yield instance


@pytest.mark.parametrize('format,expected', [('yolov8', 'data.yaml'), ('darknet', 'dataset.data'), ('coco', 'annotations/instances_test.json')])
def test_export_download_can_retry(client, format, expected):
    created = client.post('/api/export', json={'dataset_id': 7, 'format': format, 'output_name': '训练数据'})
    assert created.status_code == 200, created.text
    url = created.json()['download_url']
    first = client.get(url)
    assert first.status_code == 200
    assert first.headers['content-type'] == 'application/zip'
    with ZipFile(BytesIO(first.content)) as archive:
        assert '训练数据/' + expected in archive.namelist()
    # A second request/worker resolves the artifact from disk, without a memory registry.
    assert client.get(url).content == first.content


def test_expired_export_returns_actionable_error(client):
    result = client.post('/api/export', json={'dataset_id': 7}).json()
    directory = export.EXPORT_ROOT / result['download_url'].rsplit('/', 1)[1]
    old = time.time() - export.EXPORT_TTL_SECONDS - 1
    os.utime(directory, (old, old))
    response = client.get(result['download_url'])
    assert response.status_code == 404
    assert '过期' in response.json()['detail']
    assert not directory.exists()


@pytest.mark.parametrize('name', ['../escape', '/tmp/escape', '..', 'a\\b'])
def test_output_name_cannot_escape_export_directory(client, name):
    assert client.post('/api/export', json={'dataset_id': 7, 'output_name': name}).status_code == 422


def test_download_rejects_unknown_task(client):
    assert client.get('/api/export/download/unknown').status_code == 404
