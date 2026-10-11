import pymysql
from pymysql.cursors import DictCursor
from contextlib import contextmanager
from .config import settings
from urllib.parse import urlsplit, unquote

# 解析数据库URL
def parse_database_url(url: str) -> dict:
    """解析数据库连接URL"""
    parsed = urlsplit(url.replace("mysql+pymysql://", "mysql://", 1))
    if parsed.scheme != "mysql" or not parsed.hostname or not parsed.path.strip("/"):
        raise ValueError("DATABASE_URL 必须是有效的 MySQL 连接地址")

    return {
        "host": parsed.hostname,
        "port": parsed.port or 3306,
        "user": unquote(parsed.username or "root"),
        "password": unquote(parsed.password or ""),
        "database": unquote(parsed.path.strip("/")),
        "charset": "utf8mb4",
        "connect_timeout": 5,
        "read_timeout": 30,
        "write_timeout": 30,
        "init_command": "SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED",
        "cursorclass": DictCursor
    }

db_config = parse_database_url(settings.DATABASE_URL)


def get_connection():
    """获取数据库连接"""
    return pymysql.connect(**db_config)


@contextmanager
def get_db():
    """数据库连接上下文管理器"""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_db_dependency():
    """FastAPI 依赖注入"""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
