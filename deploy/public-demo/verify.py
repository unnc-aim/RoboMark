"""Read-only deployment checks, plus a temporary export to verify source labels."""
import io
import json
import zipfile
from pathlib import Path
import httpx
from PIL import Image

secrets = json.loads(Path('/opt/robomark/shared/deployment-secrets.json').read_text())
with httpx.Client(base_url='http://127.0.0.1:12345', timeout=60, trust_env=False) as c:
    assert c.get('/api/health').json()['status'] == 'healthy'
    login = c.post('/api/auth/login', data={'username':'demo','password':secrets['demo_password']})
    login.raise_for_status()
    c.headers['Authorization'] = 'Bearer ' + login.json()['access_token']
    datasets = c.get('/api/datasets').json()
    assert len(datasets) == 2 and sum(d['total_images'] for d in datasets) == 53
    for d in datasets:
        rows = c.get(f"/api/datasets/{d['id']}/images", params={'page_size':100}).json()
        assert rows['total'] == d['total_images']
        first = rows['items'][0] if 'items' in rows else rows['images'][0]
        image = c.get(f"/api/images/{first['id']}/file")
        image.raise_for_status()
        with Image.open(io.BytesIO(image.content)) as decoded:
            assert decoded.size == (first['width'], first['height'])
        detail = c.get(f"/api/images/{first['id']}").json()
        assert detail['annotations']
        print(d['name'], 'images', d['total_images'], 'first-image labels', len(detail['annotations']))
    for path in ['/api/auth/register', '/api/preannotation/profiles', '/api/preannotation/profiles/test',
                 '/api/datasets/1/preannotation-tasks', '/api/preannotation/tasks/1/retry-failed']:
        assert c.post(path, json={}).status_code == 403, path
    for origin, expected in [('https://robomark.lijie.space',200),('https://example.invalid',400)]:
        preflight = c.options('/api/auth/login', headers={'Origin':origin,'Access-Control-Request-Method':'POST'})
        assert preflight.status_code == expected, (origin, preflight.status_code)
    admin = c.post('/api/auth/login', data={'username':'admin','password':secrets['admin_password']})
    admin.raise_for_status()
    c.headers['Authorization'] = 'Bearer ' + admin.json()['access_token']
    export = c.post('/api/export', json={'dataset_id':2,'format':'coco','train_ratio':1,'val_ratio':0,'test_ratio':0})
    export.raise_for_status()
    payload = export.json()
    assert payload['total_images'] == 13 and payload['total_annotations'] == 40
    archive = c.get(payload['download_url'])
    archive.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(archive.content)) as z:
        assert z.testzip() is None
        annotations = next(n for n in z.namelist() if n.endswith('instances_train.json'))
        coco = json.loads(z.read(annotations))
        assert len(coco['images']) == 13 and len(coco['annotations']) == 40
    print('Login, datasets, compressed files, source labels, proxy restrictions, CORS and COCO export: PASS')
