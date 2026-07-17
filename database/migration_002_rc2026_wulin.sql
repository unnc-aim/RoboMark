-- Migration 002: RC2026-wulin 格式支持
-- 添加平行四边形标注、类别模板图片、新格式类型

USE robomark;

-- 1. dataset_configs 表增加 rc2026_wulin 枚举值
ALTER TABLE dataset_configs
  MODIFY COLUMN format_type ENUM('yolo', 'dji_roco', 'rc2026_wulin') DEFAULT 'yolo'
  COMMENT '数据集格式类型';

-- 2. categories 表增加模板图片路径
ALTER TABLE categories
  ADD COLUMN template_image_path VARCHAR(500) DEFAULT NULL COMMENT '模板图片路径'
  AFTER sort_order;

-- 3. annotations 表增加平行四边形支持
ALTER TABLE annotations
  ADD COLUMN annotation_type ENUM('bbox', 'parallelogram') DEFAULT 'bbox' COMMENT '标注类型'
  AFTER category_id,
  ADD COLUMN p1_x FLOAT DEFAULT NULL COMMENT '平行四边形顶点1 x (0-1)' AFTER height,
  ADD COLUMN p1_y FLOAT DEFAULT NULL COMMENT '平行四边形顶点1 y (0-1)' AFTER p1_x,
  ADD COLUMN p2_x FLOAT DEFAULT NULL COMMENT '平行四边形顶点2 x (0-1)' AFTER p1_y,
  ADD COLUMN p2_y FLOAT DEFAULT NULL COMMENT '平行四边形顶点2 y (0-1)' AFTER p2_x,
  ADD COLUMN p3_x FLOAT DEFAULT NULL COMMENT '平行四边形顶点3 x (0-1)' AFTER p2_y,
  ADD COLUMN p3_y FLOAT DEFAULT NULL COMMENT '平行四边形顶点3 y (0-1)' AFTER p3_x,
  ADD COLUMN p4_x FLOAT DEFAULT NULL COMMENT '平行四边形顶点4 x (0-1)' AFTER p3_y,
  ADD COLUMN p4_y FLOAT DEFAULT NULL COMMENT '平行四边形顶点4 y (0-1)' AFTER p4_x;
