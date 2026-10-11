-- 由 python -m app.migrate 执行；图片版本与正式框来源列由迁移器幂等补齐。
CREATE TABLE IF NOT EXISTS preannotation_profiles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    owner_id INT NULL,
    environment_key VARCHAR(100) NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    config JSON NOT NULL,
    credentials TEXT NULL,
    is_shared BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS preannotation_tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_id INT NOT NULL,
    profile_id INT NOT NULL,
    created_by INT NULL,
    prompt TEXT NOT NULL,
    annotation_type ENUM('bbox','parallelogram') NOT NULL,
    config_snapshot JSON NOT NULL,
    categories_snapshot JSON NOT NULL,
    endpoint_key CHAR(64) NOT NULL,
    is_sample BOOLEAN DEFAULT FALSE,
    status ENUM('queued','running','cancelling','cancelled','completed','completed_with_errors','failed') NOT NULL DEFAULT 'queued',
    total_images INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE,
    FOREIGN KEY (profile_id) REFERENCES preannotation_profiles(id),
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_pre_tasks_dataset (dataset_id, id),
    INDEX idx_pre_tasks_status (status),
    INDEX idx_pre_tasks_endpoint (endpoint_key, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS preannotation_task_images (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_id INT NOT NULL,
    image_id INT NOT NULL,
    execution_status ENUM('queued','running','succeeded','failed','cancelled') NOT NULL DEFAULT 'queued',
    review_status ENUM('unreviewed','draft','approved','rejected') NOT NULL DEFAULT 'unreviewed',
    attempts INT NOT NULL DEFAULT 0,
    claim_token CHAR(36) NULL,
    lease_until DATETIME(6) NULL,
    retry_at DATETIME(6) NULL,
    error_code VARCHAR(50) NULL,
    error_message TEXT NULL,
    raw_response MEDIUMTEXT NULL,
    original_count INT NOT NULL DEFAULT 0,
    revision INT NOT NULL DEFAULT 0,
    reviewed_by INT NULL,
    reviewed_at DATETIME NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES preannotation_tasks(id) ON DELETE CASCADE,
    FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE,
    FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL,
    UNIQUE KEY uk_pre_task_image (task_id, image_id),
    INDEX idx_pre_execution (task_id, execution_status, retry_at, lease_until),
    INDEX idx_pre_review (task_id, review_status, image_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS preannotations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_image_id INT NOT NULL,
    original_geometry JSON NULL,
    geometry JSON NOT NULL,
    is_deleted BOOLEAN DEFAULT FALSE,
    is_manual BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (task_image_id) REFERENCES preannotation_task_images(id) ON DELETE CASCADE,
    INDEX idx_pre_candidates (task_image_id, is_deleted)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
