"""Relocate persisted filesystem paths in one transaction; safe to repeat or reverse."""
import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv

APP = Path(__file__).resolve().parents[2]
BASE = APP.parent
sys.path.insert(0, str(APP / 'backend'))
load_dotenv(BASE / 'shared/backend.env', override=True)
from app.core import get_db

FIELDS = [('datasets', 'image_path'), ('datasets', 'label_path'),
          ('images', 'file_path'), ('dataset_configs', 'annotation_path'),
          ('categories', 'template_image_path')]


def relocate(conn, old: str, new: str):
    old, new = old.rstrip('/'), new.rstrip('/')
    if not old or not new or not Path(old).is_absolute() or not Path(new).is_absolute() or old == new:
        raise ValueError('old/new must be different absolute directory prefixes')
    result = {}
    with conn.cursor() as cursor:
        for table, column in FIELDS:
            cursor.execute(f'SELECT id,`{column}` AS path FROM `{table}` WHERE `{column}` LIKE %s', (old + '/%',))
            rows = [row for row in cursor.fetchall() if row['path'].startswith(old + '/')]
            for row in rows:
                target = new + row['path'][len(old):]
                if (table, column) in [('images', 'file_path'), ('datasets', 'image_path')] and not Path(target).exists():
                    raise FileNotFoundError(f'Migration target is missing: {target}')
                cursor.execute(f'UPDATE `{table}` SET `{column}`=%s WHERE id=%s AND `{column}`=%s',
                               (target, row['id'], row['path']))
                if cursor.rowcount != 1:
                    raise RuntimeError('A path changed concurrently; transaction will be rolled back')
            result[table + '.' + column] = len(rows)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old', required=True)
    parser.add_argument('--new', required=True)
    args = parser.parse_args()
    with get_db() as conn:
        result = relocate(conn, args.old, args.new)
    print('Path relocation committed:', result)
