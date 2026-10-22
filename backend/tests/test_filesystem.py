"""Directory browser tests use temporary paths and never access the business database."""
import errno
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import get_current_admin, get_current_user, settings
from app.routers.filesystem import router
import app.routers.filesystem as filesystem


@pytest.fixture
def browser(tmp_path, monkeypatch):
    root = tmp_path / "data"
    root.mkdir()
    for name in ["images", "labels", ".hidden", "中文 空格", "Empty"]:
        (root / name).mkdir()
    (root / "readme.txt").write_text("not a directory")
    (root / "images" / "nested").mkdir()
    monkeypatch.setattr(settings, "FILE_BROWSER_ROOTS", [str(root)])
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_admin] = lambda: {"id": 1, "is_admin": True}
    with TestClient(app) as client:
        yield client, root, app


def browse(client, **params):
    return client.get("/api/admin/filesystem/directories", params=params)


def test_only_directories_sorted_and_no_files_or_hidden_by_default(browser):
    client, root, _ = browser
    data = browse(client).json()
    assert data["path"] == str(root)
    assert data["parent_path"] is None
    assert [row["name"] for row in data["entries"]] == ["Empty", "images", "labels", "中文 空格"]
    assert data["total"] == 4
    assert data["breadcrumbs"] == [{"name": "data", "path": str(root)}]
    assert (root / "readme.txt").read_text() == "not a directory"


def test_navigation_breadcrumbs_and_empty_folders(browser):
    client, root, _ = browser
    data = browse(client, path=str(root / "images" / "nested")).json()
    assert data["parent_path"] == str(root / "images")
    assert [row["name"] for row in data["breadcrumbs"]] == ["data", "images", "nested"]
    assert data["entries"] == []
    assert data["total"] == 0


def test_filter_hidden_pagination_and_unicode(browser):
    client, root, _ = browser
    assert [row["name"] for row in browse(client, search="IMAg").json()["entries"]] == ["images"]
    assert [row["name"] for row in browse(client, search="中文").json()["entries"]] == ["中文 空格"]
    assert ".hidden" in [row["name"] for row in browse(client, show_hidden=True).json()["entries"]]
    data = browse(client, limit=2, offset=2).json()
    assert data["total"] == 4
    assert [row["name"] for row in data["entries"]] == ["labels", "中文 空格"]
    assert browse(client, offset=999).json()["entries"] == []


@pytest.mark.parametrize("relative,code", [("missing", 404), ("readme.txt", 400)])
def test_missing_and_file_paths_have_clear_errors(browser, relative, code):
    client, root, _ = browser
    response = browse(client, path=str(root / relative))
    assert response.status_code == code
    assert response.json()["detail"]


@pytest.mark.parametrize("params", [{"path": "relative/path"}, {"path": "\x00"}, {"limit": 0}, {"limit": 501}, {"offset": -1}])
def test_invalid_input(browser, params):
    client, _, _ = browser
    assert browse(client, **params).status_code in (400, 422)


def test_path_traversal_prefix_collision_and_symlink_escape_are_rejected(browser):
    client, root, _ = browser
    outside = root.parent / "data-private"
    outside.mkdir()
    (outside / "secret-folder").mkdir()
    (root / "escape").symlink_to(outside, target_is_directory=True)
    (root / "broken").symlink_to(root / "missing", target_is_directory=True)
    (root / "inside").symlink_to(root / "images", target_is_directory=True)
    for path in [outside, root / "..", root / "escape", root / "escape" / "secret-folder"]:
        assert browse(client, path=str(path)).status_code == 403
    rows = browse(client).json()["entries"]
    assert not {"escape", "broken"} & {row["name"] for row in rows}
    assert next(row for row in rows if row["name"] == "inside")["path"] == str(root / "images")
    assert browse(client, path=str(root / "images" / ".." / "labels")).json()["path"] == str(root / "labels")


def test_multiple_roots_and_no_parent_above_scope(browser, monkeypatch):
    client, root, _ = browser
    other = root.parent / "other"
    other.mkdir()
    monkeypatch.setattr(settings, "FILE_BROWSER_ROOTS", [str(root), str(other)])
    data = browse(client, path=str(other)).json()
    assert len(data["roots"]) == 2
    assert data["parent_path"] is None
    assert browse(client, path=str(other.parent)).status_code == 403


def test_configured_symlink_root_alias_resolves_to_canonical_server_path(browser, monkeypatch):
    client, root, _ = browser
    alias = root.parent / "alias"
    alias.symlink_to(root, target_is_directory=True)
    monkeypatch.setattr(settings, "FILE_BROWSER_ROOTS", [str(alias)])
    response = browse(client, path=str(alias / "images"))
    assert response.status_code == 200
    assert response.json()["path"] == str(root / "images")


def test_default_scope_can_browse_an_absolute_server_path(browser, monkeypatch):
    client, root, _ = browser
    monkeypatch.setattr(settings, "FILE_BROWSER_ROOTS", [])
    data = browse(client, path=str(root)).json()
    assert data["path"] == str(root)
    assert data["parent_path"] == str(root.parent)


def test_permission_failures_are_403_not_empty_success(browser, monkeypatch):
    client, root, _ = browser
    def denied(_):
        raise PermissionError(errno.EACCES, "denied")
    monkeypatch.setattr(filesystem.os, "scandir", denied)
    response = browse(client, path=str(root))
    assert response.status_code == 403
    assert "权限" in response.json()["detail"]


def test_bad_root_configuration_is_explicit(browser, monkeypatch):
    client, root, _ = browser
    monkeypatch.setattr(settings, "FILE_BROWSER_ROOTS", [str(root / "missing")])
    assert browse(client).status_code == 503


def test_admin_only_and_no_mutating_routes(browser):
    client, root, app = browser
    app.dependency_overrides.pop(get_current_admin)
    assert browse(client).status_code == 401
    app.dependency_overrides[get_current_user] = lambda: {"id": 2, "is_admin": False}
    assert browse(client).status_code == 403
    app.dependency_overrides[get_current_user] = lambda: {"id": 1, "is_admin": True}
    assert browse(client).status_code == 200
    for method in ["post", "put", "delete", "patch"]:
        assert getattr(client, method)("/api/admin/filesystem/directories").status_code == 405
    assert sorted(row.name for row in root.iterdir()) == [".hidden", "Empty", "images", "labels", "readme.txt", "中文 空格"]
