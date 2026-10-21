"""Preview transport tests use an in-memory DB stub, never the real database."""

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from starlette.requests import Request

from app.core import get_db_dependency
from app.core.config import settings
from app.preview_app import app
from app.services.image_preview import preview_response
import app.routers.previews as previews


class Connection:
    def __init__(self, image, template):
        self.image, self.template = image, template

    def cursor(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def execute(self, sql, params):
        assert sql.startswith("SELECT "), "Preview endpoints must never write to the DB"
        self.row = None if params[0] != 1 else (
            {"file_path": str(self.image)} if "FROM images" in sql
            else {"template_image_path": self.template}
        )

    def fetchone(self):
        return self.row


@pytest.fixture
def preview_client(tmp_path, monkeypatch):
    original = tmp_path / "original.jpg"
    Image.effect_noise((2400, 1600), 80).convert("RGB").save(original, quality=96)
    templates = tmp_path / "uploads" / "category_templates"
    templates.mkdir(parents=True)
    template = templates / "example.png"
    Image.new("RGBA", (1000, 600), (255, 0, 0, 100)).save(template)
    monkeypatch.setattr(settings, "IMAGE_PREVIEW_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(previews, "_backend_root", tmp_path)
    conn = Connection(original, "uploads/category_templates/example.png")
    app.dependency_overrides[get_db_dependency] = lambda: conn
    with TestClient(app) as client:
        yield client, original, template, tmp_path / "cache"
    app.dependency_overrides.clear()


def test_preview_reduces_transfer_preserves_original_and_reuses_cache(preview_client):
    client, original, _, cache = preview_client
    before = original.read_bytes()
    response = client.get("/api/images/1/preview?width=640")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"
    with Image.open(BytesIO(response.content)) as preview:
        assert preview.size == (640, 427)
    assert len(response.content) < len(before) / 10
    assert original.read_bytes() == before
    cached = next(cache.rglob("*.webp"))
    modified = cached.stat().st_mtime_ns
    assert client.get("/api/images/1/preview?width=640").content == response.content
    assert cached.stat().st_mtime_ns == modified
    not_modified = client.get("/api/images/1/preview?width=640", headers={"If-None-Match": response.headers["etag"]})
    assert not_modified.status_code == 304 and not not_modified.content
    Image.new("RGB", (900, 600), "blue").save(original)
    changed = client.get("/api/images/1/preview?width=640", headers={"If-None-Match": response.headers["etag"]})
    assert changed.status_code == 200 and changed.headers["etag"] != response.headers["etag"]


@pytest.mark.parametrize("width", [320, 640, 1280])
def test_supported_sizes_template_transparency_and_portrait_bounds(preview_client, width):
    client, original, _, _ = preview_client
    response = client.get(f"/api/categories/1/template-image/preview?width={width}")
    assert response.status_code == 200
    with Image.open(BytesIO(response.content)) as image:
        assert image.mode == "RGBA" and image.width == min(width, 1000)
    Image.new("RGB", (300, 1800), "green").save(original)
    with Image.open(BytesIO(client.get(f"/api/images/1/preview?width={width}").content)) as image:
        assert image.height == width and image.width <= width


def test_invalid_sizes_missing_and_corrupt_files(preview_client):
    client, original, _, _ = preview_client
    assert client.get("/api/images/1/preview?width=641").status_code == 422
    assert client.get("/api/images/2/preview").status_code == 404
    assert client.get("/api/categories/2/template-image/preview").status_code == 404
    original.write_bytes(b"not an image")
    assert client.get("/api/images/1/preview").status_code == 415
    original.unlink()
    assert client.get("/api/images/1/preview").status_code == 404


def test_concurrent_first_requests_only_publish_complete_images(preview_client):
    _, original, _, cache = preview_client
    def generate(_):
        request = Request({"type": "http", "headers": []})
        response = preview_response(str(original), 640, request)
        with Image.open(response.path) as image:
            image.load()
            assert image.size == (640, 427)
        return Path(response.path)
    with ThreadPoolExecutor(max_workers=8) as executor:
        paths = list(executor.map(generate, range(8)))
    assert len(set(paths)) == 1
    assert len(list(cache.rglob("*.webp"))) == 1
    assert not list(cache.rglob("*.tmp"))


def test_sidecar_has_no_startup_writes_or_original_routes():
    assert not app.router.on_startup
    paths = {route.path for route in app.routes}
    assert "/api/images/{image_id}/file" not in paths
    assert "/api/preview/health" in paths
