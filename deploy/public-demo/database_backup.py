"""Back up only the configured demo database; credentials stay out of argv."""
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from dotenv import load_dotenv
load_dotenv('/root/robomark/shared/backend.env')
from app.core.database import db_config

output = Path(sys.argv[1])
output.parent.mkdir(parents=True, exist_ok=True)
env = {**os.environ, 'MYSQL_PWD': db_config['password']}
with output.open('xb') as handle:
    output.chmod(0o600)
    subprocess.run(['mysqldump', '--single-transaction', '--no-tablespaces', '--set-gtid-purged=OFF',
                    '--host', db_config['host'], '--port', str(db_config['port']),
                    '--user', db_config['user'], db_config['database']],
                   stdout=handle, env=env, check=True)
print('Database backup saved:', output)
