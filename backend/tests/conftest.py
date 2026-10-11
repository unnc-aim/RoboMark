import os
import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if os.getenv("ROBOMARK_TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["ROBOMARK_TEST_DATABASE_URL"]
# 仅测试凭据；不依赖真实 JWT / 推理密钥。
os.environ["PREANNOTATION_ENCRYPTION_KEY"] = base64.urlsafe_b64encode(b"0"*32).decode()
