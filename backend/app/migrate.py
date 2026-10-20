"""幂等升级已有数据库。先按 database/init.sql 创建基础数据库，再运行此命令。"""
from pathlib import Path
from app.core.database import get_db


def add_column(cursor, table, name, definition):
    cursor.execute("SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=%s AND column_name=%s", (table, name))
    if not cursor.fetchone():
        cursor.execute(f"ALTER TABLE `{table}` ADD COLUMN `{name}` {definition}")


def migrate():
    with get_db() as conn, conn.cursor() as c:
        c.execute("SELECT GET_LOCK(CONCAT(DATABASE(), ':robomark-migrate'), 30) AS acquired")
        if not c.fetchone()["acquired"]:
            raise RuntimeError("数据库迁移锁被占用")
        try:
            c.execute("""CREATE TABLE IF NOT EXISTS dataset_configs (
                id INT AUTO_INCREMENT PRIMARY KEY, dataset_id INT NOT NULL UNIQUE,
                format_type ENUM('yolo','dji_roco','rc2026_wulin') DEFAULT 'yolo',
                annotation_path VARCHAR(500), source_width INT DEFAULT 1920, source_height INT DEFAULT 1080,
                auto_import_annotations BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY(dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
            c.execute("ALTER TABLE dataset_configs MODIFY format_type ENUM('yolo','dji_roco','rc2026_wulin') DEFAULT 'yolo'")
            add_column(c, "categories", "template_image_path", "VARCHAR(500) NULL")
            add_column(c, "annotations", "annotation_type", "ENUM('bbox','parallelogram') DEFAULT 'bbox'")
            for i in range(1, 5):
                for axis in ("x", "y"):
                    add_column(c, "annotations", f"p{i}_{axis}", "FLOAT NULL")
            add_column(c, "images", "annotation_revision", "INT NOT NULL DEFAULT 0")
            add_column(c, "annotations", "source_preannotation_id", "INT NULL")
            c.execute("SELECT 1 FROM information_schema.statistics WHERE table_schema=DATABASE() AND table_name='annotations' AND index_name='uk_annotation_source'")
            if not c.fetchone():
                c.execute("ALTER TABLE annotations ADD UNIQUE KEY uk_annotation_source (source_preannotation_id)")
            sql = (Path(__file__).resolve().parents[2] / "database/migration_003_preannotation.sql").read_text()
            # 项目根目录位于 backend 的上一层
            for statement in sql.split(";"):
                if statement.strip():
                    c.execute(statement)
            add_column(c, "preannotation_profiles", "environment_key", "VARCHAR(100) NULL UNIQUE")
            sql = (Path(__file__).resolve().parents[2] / "database/migration_004_preannotation_attempts.sql").read_text()
            for statement in sql.split(";"):
                if statement.strip():
                    c.execute(statement)
        finally:
            c.execute("SELECT RELEASE_LOCK(CONCAT(DATABASE(), ':robomark-migrate'))")
    print("数据库已升级：数据集配置、预标注任务、审核版本与标注来源")
    from app.services.preannotation_config import sync_environment_profile
    sync_environment_profile()


if __name__ == "__main__":
    migrate()
