"""One-time demo dataset import; run locally on the target before opening access.

Credentials are read from root-only runtime files, never from source control.
Existing nonempty datasets are deliberately not overwritten.
"""
import json
import re
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path('/root/robomark')
sys.path.insert(0, str(ROOT / 'app/backend'))
load_dotenv(ROOT / 'shared/backend.env')
from app.core.database import get_db
from app.core.security import get_password_hash
from app.schemas.preannotation import Annotation, ProfileInput, TaskInput
from app.services.preannotation_store import insert_annotation
from app.routers.preannotation import create_profile, create_task

secrets = json.loads((ROOT / 'shared/deployment-secrets.json').read_text())
with get_db() as conn, conn.cursor() as c:
    c.execute('SHOW TABLES LIKE %s', ('datasets',))
    if c.fetchone():
        c.execute('SELECT COUNT(*) AS n FROM datasets')
        if c.fetchone()['n']:
            raise SystemExit('Refusing to overwrite existing datasets')
    sql = (ROOT / 'app/database/init.sql').read_text()
    for part in re.sub(r'--[^\n]*', '', sql).split(';'):
        statement = part.strip()
        if not statement or statement.upper().startswith(('CREATE DATABASE', 'USE ')):
            continue
        c.execute(statement)
    c.execute('UPDATE users SET hashed_password=%s WHERE username=%s',
              (get_password_hash(secrets['admin_password']), 'admin'))
    c.execute('INSERT INTO users (username,hashed_password,is_admin,is_active) VALUES (%s,%s,FALSE,TRUE)',
              ('demo', get_password_hash(secrets['demo_password'])))
    c.execute('SELECT id,username,is_admin,is_active FROM users WHERE username=%s', ('admin',))
    admin = c.fetchone()
    datasets = []
    for folder, names in [('qdu', ['AM02小装甲', 'AM12 大装甲']), ('shapes', ['rectangle', 'circle'])]:
        directory = ROOT / 'data/datasets' / folder
        manifest = json.loads((directory / 'manifest.json').read_text())
        c.execute('INSERT INTO datasets (name,description,image_path,total_images,labeled_images) VALUES (%s,%s,%s,%s,%s)',
                  (manifest['name'], manifest['description'], str(directory / 'images'), len(manifest['images']), len(manifest['images'])))
        dataset_id = c.lastrowid
        category_ids = {}
        for index, name in enumerate(names):
            c.execute('INSERT INTO categories (dataset_id,name,color,shortcut_key,sort_order) VALUES (%s,%s,%s,%s,%s)',
                      (dataset_id, name, ['#2563eb', '#e45353'][index], str(index + 1), index))
            category_ids[name] = c.lastrowid
        c.execute('INSERT INTO dataset_configs (dataset_id,format_type,auto_import_annotations) VALUES (%s,%s,FALSE)', (dataset_id, 'yolo'))
        count = 0
        for image in manifest['images']:
            path = directory / 'images' / image['filename']
            assert path.is_file()
            c.execute("INSERT INTO images (dataset_id,filename,file_path,width,height,status,labeled_by,labeled_at,annotation_revision) VALUES (%s,%s,%s,%s,%s,'labeled',%s,NOW(),1)",
                      (dataset_id, image['filename'], str(path), image['width'], image['height'], admin['id']))
            image_id = c.lastrowid
            for source in image['annotations']:
                geometry = {k:v for k,v in source.items() if k not in ('category_name', 'bbox_xyxy')}
                geometry['category_id'] = category_ids[source['category_name']]
                annotation = Annotation.model_validate(geometry)
                insert_annotation(c, image_id, annotation.model_dump(), admin['id'])
                count += 1
        datasets.append((folder, dataset_id, list(category_ids.values())))
        print(folder, 'images', len(manifest['images']), 'formal annotations', count, flush=True)
    c.execute('INSERT INTO work_statistics (user_id,dataset_id,date,images_labeled,annotations_created) SELECT %s,d.id,CURRENT_DATE,COUNT(DISTINCT i.id),COUNT(a.id) FROM datasets d JOIN images i ON i.dataset_id=d.id LEFT JOIN annotations a ON a.image_id=i.id GROUP BY d.id', (admin['id'],))

# The only external connection profile is administrator-owned and shared read-only.
connection = json.loads((ROOT / 'shared/inference.json').read_text())
with get_db() as conn:
    profile = create_profile(ProfileInput(name='GLM-5.3-Flash', endpoint=connection['url']+'/v1/chat/completions',
        model='glm-5.3-flash', api_key=connection['key'], is_shared=True,
        coordinate_system='relative_1000', box_format='xyxy', max_attempts=3), conn=conn, user=admin)
    # Use existing task APIs to preserve the platform's real queue, traces and metrics.
    for folder, dataset_id, categories in datasets:
        prompt = ('标注图片中所有 RoboMaster 机器人装甲板。只框装甲板本体（两根灯条与中间数字板），不要框整个机器人。AM02小装甲对应小装甲板，AM12 大装甲对应大装甲板。矩形框应紧贴完整装甲板边界。'
                  if folder == 'qdu' else
                  '标注图片中的所有矩形和圆形。使用紧贴完整目标边界的外接矩形，包含空心轮廓。遮挡物体按完整图形边界标注。忽略文字、背景，没有图形时返回空数组。')
        task = create_task(dataset_id, TaskInput(profile_id=profile['id'], prompt=prompt,
                          annotation_type='bbox', category_ids=categories), conn=conn, user=admin)
        print(folder, 'full preannotation task', task['id'], flush=True)
print('Seed completed')
