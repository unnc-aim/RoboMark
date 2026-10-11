"""所有预标注配置统一存入 MySQL；.env 可提供一个受环境管理的共享默认配置。"""
import json
from app.core.config import settings
from app.core.database import get_db
from app.schemas.preannotation import ProfileInput
from app.services.preannotation_inference import validate_profile, encrypt_credentials, decrypt_credentials, json_value


def sync_environment_profile():
    if not settings.PREANNOTATION_DEFAULT_PROFILE:
        return None
    data = ProfileInput.model_validate({"name": "环境默认接口", **settings.PREANNOTATION_DEFAULT_PROFILE, "is_shared": True})
    validate_profile(data)
    config = data.model_dump(exclude={"api_key", "headers", "clear_credentials", "is_shared", "name"})
    credentials = {"api_key": data.api_key or "", "headers": data.headers}
    if not credentials["api_key"] and not credentials["headers"]:
        credentials = {}
    with get_db() as conn, conn.cursor() as c:
        # 同一环境默认配置只有一行；更新不影响其他用户手动创建的配置。
        c.execute("""INSERT INTO preannotation_profiles (environment_key,name,config,is_shared)
                     VALUES ('default',%s,%s,TRUE) ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)""", (data.name, json.dumps(config)))
        profile_id = c.lastrowid
        c.execute("SELECT * FROM preannotation_profiles WHERE id=%s FOR UPDATE", (profile_id,))
        old = c.fetchone()
        old_credentials = decrypt_credentials(old["credentials"])
        changes = json_value(old["config"]) != config or old_credentials != credentials or old["name"] != data.name or not old["is_active"]
        if changes:
            ciphertext = encrypt_credentials(credentials) if credentials else None
            c.execute("UPDATE preannotation_profiles SET name=%s,config=%s,credentials=%s,is_shared=TRUE,is_active=TRUE,version=version+1 WHERE id=%s",
                      (data.name, json.dumps(config), ciphertext, profile_id))
        return profile_id
