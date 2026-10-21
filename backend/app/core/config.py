from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "RoboMark"
    DEBUG: bool = True

    # 数据库配置
    DATABASE_URL: str = "mysql+pymysql://root:password@localhost:3306/robomark"

    # JWT配置
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24小时

    # CORS配置
    CORS_ORIGINS: list = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # 文件上传配置
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_IMAGE_EXTENSIONS: list = [".jpg", ".jpeg", ".png", ".bmp", ".webp"]
    # 默认为 backend/uploads/image_previews；可放在独立缓存盘，可安全清理。
    IMAGE_PREVIEW_CACHE_DIR: str = ""

    # 独立于 JWT 密钥（dev.sh 会轮换 SECRET_KEY），保护推理接口凭据
    PREANNOTATION_ENCRYPTION_KEY: str = ""
    PREANNOTATION_WORKER_CONCURRENCY: int = 2
    PREANNOTATION_ENDPOINT_CONCURRENCY: int = 1
    PREANNOTATION_MAX_IMAGE_BYTES: int = 20 * 1024 * 1024
    PREANNOTATION_MAX_RESPONSE_BYTES: int = 2 * 1024 * 1024
    # 可选 JSON 默认配置；字段与 ProfileInput 一致，启动时同步到统一配置表
    PREANNOTATION_DEFAULT_PROFILE: dict = {}

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()
