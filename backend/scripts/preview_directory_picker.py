"""Local UI-test fixtures, never the production application or business database.

From backend/: venv/bin/python -m uvicorn scripts.preview_directory_picker:app --host 127.0.0.1 --port 8002
"""
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core import get_current_admin, settings
from app.routers.filesystem import router


@asynccontextmanager
async def lifespan(app):
    with TemporaryDirectory(prefix="robomark-directory-e2e-") as temporary:
        root = Path(temporary).resolve()
        for name in ["Alpha/images", "Alpha/labels", "Big", "Empty", "Denied", ".hidden", "中文 目录"]:
            (root / name).mkdir(parents=True, exist_ok=True)
        for index in range(205):
            (root / "Big" / f"folder-{index:03}").mkdir()
        (root / "notes.txt").write_text("Not included in the directory browser")
        settings.FILE_BROWSER_ROOTS = [str(root)]
        yield


app = FastAPI(title="目录选择器本地验收", lifespan=lifespan)
app.include_router(router)
# This local-only app can enumerate only its temporary fixture directories.
app.dependency_overrides[get_current_admin] = lambda: {"id": 1, "is_admin": True}


@app.middleware("http")
async def denied_fixture(request: Request, call_next):
    if request.query_params.get("path", "").endswith("/Denied"):
        return JSONResponse({"detail": "服务账号没有读取此服务器目录的权限"}, status_code=403)
    return await call_next(request)
