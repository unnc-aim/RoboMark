-- 可重复执行的 RC2026 升级；也可使用 python -m app.migrate
USE robomark;
ALTER TABLE dataset_configs MODIFY format_type ENUM('yolo','dji_roco','rc2026_wulin') DEFAULT 'yolo';

SET @ddl = IF(EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='categories' AND column_name='template_image_path'), 'SELECT 1', 'ALTER TABLE categories ADD COLUMN template_image_path VARCHAR(500) NULL');
PREPARE migration_stmt FROM @ddl;
EXECUTE migration_stmt;
DEALLOCATE PREPARE migration_stmt;

SET @ddl = IF(EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='annotations' AND column_name='annotation_type'), 'SELECT 1', 'ALTER TABLE annotations ADD COLUMN annotation_type ENUM(''bbox'',''parallelogram'') DEFAULT ''bbox''');
PREPARE migration_stmt FROM @ddl;
EXECUTE migration_stmt;
DEALLOCATE PREPARE migration_stmt;

SET @ddl = IF(EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='annotations' AND column_name='p1_x'), 'SELECT 1', 'ALTER TABLE annotations ADD COLUMN p1_x FLOAT NULL');
PREPARE migration_stmt FROM @ddl;
EXECUTE migration_stmt;
DEALLOCATE PREPARE migration_stmt;

SET @ddl = IF(EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='annotations' AND column_name='p1_y'), 'SELECT 1', 'ALTER TABLE annotations ADD COLUMN p1_y FLOAT NULL');
PREPARE migration_stmt FROM @ddl;
EXECUTE migration_stmt;
DEALLOCATE PREPARE migration_stmt;

SET @ddl = IF(EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='annotations' AND column_name='p2_x'), 'SELECT 1', 'ALTER TABLE annotations ADD COLUMN p2_x FLOAT NULL');
PREPARE migration_stmt FROM @ddl;
EXECUTE migration_stmt;
DEALLOCATE PREPARE migration_stmt;

SET @ddl = IF(EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='annotations' AND column_name='p2_y'), 'SELECT 1', 'ALTER TABLE annotations ADD COLUMN p2_y FLOAT NULL');
PREPARE migration_stmt FROM @ddl;
EXECUTE migration_stmt;
DEALLOCATE PREPARE migration_stmt;

SET @ddl = IF(EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='annotations' AND column_name='p3_x'), 'SELECT 1', 'ALTER TABLE annotations ADD COLUMN p3_x FLOAT NULL');
PREPARE migration_stmt FROM @ddl;
EXECUTE migration_stmt;
DEALLOCATE PREPARE migration_stmt;

SET @ddl = IF(EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='annotations' AND column_name='p3_y'), 'SELECT 1', 'ALTER TABLE annotations ADD COLUMN p3_y FLOAT NULL');
PREPARE migration_stmt FROM @ddl;
EXECUTE migration_stmt;
DEALLOCATE PREPARE migration_stmt;

SET @ddl = IF(EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='annotations' AND column_name='p4_x'), 'SELECT 1', 'ALTER TABLE annotations ADD COLUMN p4_x FLOAT NULL');
PREPARE migration_stmt FROM @ddl;
EXECUTE migration_stmt;
DEALLOCATE PREPARE migration_stmt;

SET @ddl = IF(EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name='annotations' AND column_name='p4_y'), 'SELECT 1', 'ALTER TABLE annotations ADD COLUMN p4_y FLOAT NULL');
PREPARE migration_stmt FROM @ddl;
EXECUTE migration_stmt;
DEALLOCATE PREPARE migration_stmt;
