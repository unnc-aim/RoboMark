-- 每次领取单独保留请求、响应及转换记录，手动重试不清空历史。
CREATE TABLE IF NOT EXISTS preannotation_attempts (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_image_id INT NOT NULL,
    sequence_number INT NOT NULL,
    claim_token CHAR(36) NOT NULL UNIQUE,
    status ENUM('running','succeeded','failed','cancelled','interrupted') NOT NULL DEFAULT 'running',
    trace JSON NOT NULL,
    error_code VARCHAR(50) NULL,
    error_message TEXT NULL,
    started_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    finished_at DATETIME(6) NULL,
    FOREIGN KEY (task_image_id) REFERENCES preannotation_task_images(id) ON DELETE CASCADE,
    UNIQUE KEY uk_pre_attempt_sequence (task_image_id, sequence_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
