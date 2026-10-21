"""Optional preview-only process: no migrations, workers, or startup DB writes.

Run from backend/: uvicorn app.preview_app:app --host 127.0.0.1 --port 8001
Keep the existing API and inference workers running during a sidecar rollout.
"""

from fastapi import FastAPI

from app.routers.previews import router

app = FastAPI(title="RoboMark 图片预览", docs_url=None, redoc_url=None)
app.include_router(router)


@app.get("/api/preview/health")
def health():
    return {"status": "healthy"}
