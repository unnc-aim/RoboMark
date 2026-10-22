#!/usr/bin/env bash
set -euo pipefail
base="${ROBOMARK_HOME:-/root/robomark}"
app="$base/app"
export PATH="$base/toolchain/node/bin:$base/toolchain/pnpm/bin:$PATH"
exec 9>"$base/run/update.lock"
flock -n 9 || { echo '另一项部署正在进行中。' >&2; exit 1; }
[[ "$(git -C "$app" branch --show-current)" = codex/public-demo ]] || { echo '服务器必须检出 codex/public-demo。' >&2; exit 1; }
[[ -z "$(git -C "$app" status --porcelain)" ]] || { echo '服务器源码有未提交修改，请先处理。' >&2; exit 1; }
if systemctl is-active --quiet robomark-worker; then
    echo '请先完成预标注任务并停止 worker。' >&2
    exit 1
fi
old_revision="$(git -C "$app" rev-parse HEAD)"
old_frontend="$(readlink -f "$base/frontend")"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="$base/backups/before-git-$stamp.sql"
umask 077
cd "$app/backend"
"$base/venv/bin/python" "$app/deploy/public-demo/database_backup.py" "$backup"
rollback() {
    trap - ERR
    set +e
    git -C "$app" reset --hard "$old_revision"
    ln -sfn "$old_frontend" "$base/frontend.rollback"
    mv -Tf "$base/frontend.rollback" "$base/frontend"
    for unit in robomark-api robomark-web robomark-worker; do
        install -m 644 "$app/deploy/public-demo/$unit.service" "/etc/systemd/system/$unit.service"
    done
    systemctl daemon-reload
    systemctl restart robomark-api robomark-web
    echo "更新失败，代码与静态页面已回退。数据库备份：$backup；迁移和依赖不会自动回退。" >&2
    exit 1
}
trap rollback ERR
umask 022
install -d -m 755 "$base/builds"
git -C "$app" pull --ff-only origin codex/public-demo
revision="$(git -C "$app" rev-parse HEAD)"
build="$base/builds/$stamp-${revision:0:12}"
pnpm --dir "$app/frontend" install --frozen-lockfile
pnpm --dir "$app/frontend" run check:ui
pnpm --dir "$app/frontend" run typecheck
pnpm --dir "$app/frontend" run test
pnpm --dir "$app/frontend" exec vite build --outDir "$build"
# Keep immutable assets referenced by browser tabs opened before this update.
if [[ -d "$old_frontend/assets" ]]; then cp -an "$old_frontend/assets/." "$build/assets/"; fi
chmod -R a+rX "$build"
"$base/venv/bin/python" -m pip install -q -r requirements.txt
"$base/venv/bin/python" "$app/deploy/public-demo/run_with_env.py" "$base/venv/bin/python" -m app.migrate
for unit in robomark-api robomark-web robomark-worker; do
    install -m 644 "$app/deploy/public-demo/$unit.service" "/etc/systemd/system/$unit.service"
done
systemctl daemon-reload
/www/server/nginx/sbin/nginx -p "$base/run/" -c "$app/deploy/public-demo/nginx.conf" -t
ln -sfn "$build" "$base/frontend.next"
mv -Tf "$base/frontend.next" "$base/frontend"
systemctl restart robomark-api robomark-web
healthy=0
for attempt in {1..30}; do
    if curl --fail --silent --max-time 3 http://127.0.0.1:12345/api/health >/dev/null; then healthy=1; break; fi
    sleep 1
done
[[ "$healthy" = 1 ]]
printf '%s\n' "$old_revision" > "$base/previous-revision"
printf '%s\n' "$old_frontend" > "$base/previous-frontend"
printf '%s\n' "$revision" > "$app/DEPLOYED_REVISION"
trap - ERR
printf 'Git 更新完成：%s\n前端：%s\n备份：%s\n' "$revision" "$build" "$backup"
