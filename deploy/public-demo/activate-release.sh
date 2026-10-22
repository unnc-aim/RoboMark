#!/usr/bin/env bash
set -euo pipefail
release_id="${1:?release id required}"
[[ "$release_id" =~ ^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{7,40}$ ]] || exit 2
base=/opt/robomark
exec 9>"$base/run/update.lock"
flock -n 9 || { echo '另一项部署正在进行中。' >&2; exit 1; }
if systemctl is-active --quiet robomark-worker; then
    echo '预标注 worker 正在运行；请等任务完成并停止 worker 后更新。' >&2
    exit 1
fi
release_path="$base/releases/$release_id"
mkdir "$release_path"
tar -xzf "$release_path.tar.gz" -C "$release_path"
ln -s "$base/data/uploads" "$release_path/backend/uploads"
cd "$release_path/backend"
backup_path="$base/backups/before-$release_id.sql"
umask 077
# Read database credentials directly from application settings, not process arguments.
"$base/venv/bin/python" "$release_path/deploy/public-demo/database_backup.py" "$backup_path"
"$base/venv/bin/python" -m pip install -q -r requirements.txt
"$base/venv/bin/python" "$release_path/deploy/public-demo/run_with_env.py" "$base/venv/bin/python" -m app.migrate
if [[ -L "$base/app" ]]; then
    old_release="$(readlink -f "$base/app")"
else
    old_release="$base/releases/initial-$(date -u +%Y%m%dT%H%M%SZ)"
    systemctl stop robomark-api
    mv "$base/app" "$old_release"
fi
rollback() {
    ln -sfn "$old_release" "$base/app.rollback"
    mv -Tf "$base/app.rollback" "$base/app"
    systemctl restart robomark-api
    echo '健康检查失败，代码已回退；数据库备份保留，迁移不会自动逆转。' >&2
}
ln -sfn "$old_release" "$base/previous"
ln -sfn "$release_path" "$base/app.next"
mv -Tf "$base/app.next" "$base/app"
if ! systemctl restart robomark-api; then rollback; exit 1; fi
healthy=0
for attempt in {1..20}; do
    if curl --fail --silent http://127.0.0.1:18000/api/health >/dev/null; then healthy=1; break; fi
    sleep 1
done
if [[ "$healthy" != 1 ]]; then rollback; exit 1; fi
curl --fail --silent http://127.0.0.1:12345/api/health
printf '\n当前版本：%s\n备份：%s\n' "$release_id" "$backup_path"
# Deliberately leave the user's BaoTa Nginx, SSL, firewall, DB data and worker untouched.
