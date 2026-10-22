#!/usr/bin/env bash
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
if [[ "$(git branch --show-current)" != "codex/public-demo" ]]; then
    echo '请先切换到 codex/public-demo 分支。' >&2
    exit 1
fi
if [[ -n "$(git status --porcelain)" ]]; then
    echo '请先提交或暂存处理工作区改动，再部署。' >&2
    exit 1
fi
target_host="${1:-jproot}"
revision="$(git rev-parse --short=12 HEAD)"
release_id="$(date -u +%Y%m%dT%H%M%SZ)-${revision}"
staging_dir="$(mktemp -d)"
trap 'rm -rf "$staging_dir"' EXIT
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend typecheck
pnpm --dir frontend build
mkdir -p "$staging_dir/source"
git archive HEAD | tar -x -C "$staging_dir/source"
mkdir -p "$staging_dir/source/frontend/dist"
cp -R frontend/dist/. "$staging_dir/source/frontend/dist/"
printf '%s\n' "$revision" > "$staging_dir/source/DEPLOYED_REVISION"
tar -czf "$staging_dir/$release_id.tar.gz" -C "$staging_dir/source" .
ssh "$target_host" 'mkdir -p /opt/robomark/releases'
scp "$staging_dir/$release_id.tar.gz" "$target_host:/opt/robomark/releases/"
# Execute the new release's activation script, rather than an older deployed copy.
scp deploy/public-demo/activate-release.sh "$target_host:/opt/robomark/releases/activate-release.sh"
ssh "$target_host" bash /opt/robomark/releases/activate-release.sh "$release_id"
echo "部署完成：$release_id"
