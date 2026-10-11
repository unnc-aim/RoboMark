-- RoboMark 数据库初始化脚本
-- MySQL 8.0+

CREATE DATABASE IF NOT EXISTS robomark DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE robomark;

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_email (email)
) ENGINE=InnoDB;

-- 数据集表
CREATE TABLE IF NOT EXISTS datasets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    image_path VARCHAR(500) NOT NULL COMMENT '图片目录路径',
    label_path VARCHAR(500) COMMENT '标签目录路径',
    total_images INT DEFAULT 0,
    labeled_images INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_name (name)
) ENGINE=InnoDB;

-- 类别表
CREATE TABLE IF NOT EXISTS categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_id INT NOT NULL,
    name VARCHAR(50) NOT NULL,
    shortcut_key VARCHAR(10) COMMENT '快捷键',
    color VARCHAR(20) DEFAULT '#FF0000',
    sort_order INT DEFAULT 0,
    template_image_path VARCHAR(500) DEFAULT NULL COMMENT '模板图片路径',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE,
    INDEX idx_dataset (dataset_id),
    UNIQUE KEY uk_dataset_name (dataset_id, name)
) ENGINE=InnoDB;

-- 图片表
CREATE TABLE IF NOT EXISTS images (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_id INT NOT NULL,
    filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    width INT,
    height INT,
    status ENUM('pending', 'assigned', 'labeled', 'skipped') DEFAULT 'pending',
    annotation_revision INT NOT NULL DEFAULT 0,
    assigned_to INT,
    assigned_at TIMESTAMP NULL,
    labeled_by INT,
    labeled_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE,
    FOREIGN KEY (assigned_to) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (labeled_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_dataset (dataset_id),
    INDEX idx_status (status),
    INDEX idx_assigned (assigned_to),
    UNIQUE KEY uk_dataset_filename (dataset_id, filename)
) ENGINE=InnoDB;

-- 标注表
CREATE TABLE IF NOT EXISTS annotations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    image_id INT NOT NULL,
    category_id INT NOT NULL,
    annotation_type ENUM('bbox', 'parallelogram') DEFAULT 'bbox' COMMENT '标注类型',
    x_center FLOAT NOT NULL COMMENT 'YOLO格式 x中心点 (0-1)',
    y_center FLOAT NOT NULL COMMENT 'YOLO格式 y中心点 (0-1)',
    width FLOAT NOT NULL COMMENT 'YOLO格式 宽度 (0-1)',
    height FLOAT NOT NULL COMMENT 'YOLO格式 高度 (0-1)',
    p1_x FLOAT DEFAULT NULL COMMENT '平行四边形顶点1 x (0-1)',
    p1_y FLOAT DEFAULT NULL COMMENT '平行四边形顶点1 y (0-1)',
    p2_x FLOAT DEFAULT NULL COMMENT '平行四边形顶点2 x (0-1)',
    p2_y FLOAT DEFAULT NULL COMMENT '平行四边形顶点2 y (0-1)',
    p3_x FLOAT DEFAULT NULL COMMENT '平行四边形顶点3 x (0-1)',
    p3_y FLOAT DEFAULT NULL COMMENT '平行四边形顶点3 y (0-1)',
    p4_x FLOAT DEFAULT NULL COMMENT '平行四边形顶点4 x (0-1)',
    p4_y FLOAT DEFAULT NULL COMMENT '平行四边形顶点4 y (0-1)',
    source_preannotation_id INT NULL,
    UNIQUE KEY uk_annotation_source (source_preannotation_id),
    created_by INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_image (image_id),
    INDEX idx_category (category_id)
) ENGINE=InnoDB;

-- 标注历史表 (用于撤销/重做)
CREATE TABLE IF NOT EXISTS annotation_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    image_id INT NOT NULL,
    user_id INT NOT NULL,
    action ENUM('create', 'update', 'delete') NOT NULL,
    annotation_data JSON NOT NULL COMMENT '标注数据快照',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_image_user (image_id, user_id)
) ENGINE=InnoDB;

-- 工作量统计表
CREATE TABLE IF NOT EXISTS work_statistics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    dataset_id INT NOT NULL,
    date DATE NOT NULL,
    images_labeled INT DEFAULT 0,
    annotations_created INT DEFAULT 0,
    time_spent INT DEFAULT 0 COMMENT '花费时间(秒)',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE,
    UNIQUE KEY uk_user_dataset_date (user_id, dataset_id, date),
    INDEX idx_date (date)
) ENGINE=InnoDB;

-- 插入默认管理员账户
-- 密码: 123456 (bcrypt哈希)
INSERT INTO users (username, email, hashed_password, is_admin, is_active)
VALUES ('admin', 'admin@robomark.local', '$2b$12$tXRiGDRzF8unBqUSRnIYMuf1AXkH5HEouLpAapns4fY7UngSVbBwW', TRUE, TRUE)
ON DUPLICATE KEY UPDATE username = username;

-- 新安装包含全部表；已有数据库使用 python -m app.migrate。
CREATE TABLE IF NOT EXISTS dataset_configs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dataset_id INT NOT NULL UNIQUE,
    format_type ENUM('yolo','dji_roco','rc2026_wulin') DEFAULT 'yolo',
    annotation_path VARCHAR(500),
    source_width INT DEFAULT 1920,
    source_height INT DEFAULT 1080,
    auto_import_annotations BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (dataset_id) REFERENCES datasets(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
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
