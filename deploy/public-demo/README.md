# jproot 公开演示部署

地址：https://robomark.lijie.space 。服务器部署根目录为 `/root/robomark`（jproot 的 `~/robomark`），源码通过 Git 同步 `codex/public-demo` 分支。

## 目录与服务

| 位置 | 用途 |
| --- | --- |
| `/root/robomark/app` | Git checkout，origin 为 `https://github.com/unnc-aim/RoboMark.git` |
| `/root/robomark/frontend` | 当前前端构建目录的符号链接 |
| `/root/robomark/builds` | 服务器构建的前端版本，保留旧资源供已打开的页面使用 |
| `/root/robomark/venv` | Python 虚拟环境 |
| `/root/robomark/toolchain/node` | Node.js 24 LTS |
| `/root/robomark/toolchain/pnpm` | pnpm 10 |
| `/root/robomark/data/datasets` | 数据集图片、标签及来源清单 |
| `/root/robomark/data/uploads` | 上传文件，链接到 `app/backend/uploads` |
| `/root/robomark/shared/backend.env` | 数据库、JWT、推理凭据加密密钥和缓存路径 |
| `/root/robomark/shared/deployment-secrets.json` | 仅 root 可读的演示账号凭据 |
| `/root/robomark/backups` | 数据库、迁移前配置和服务文件备份 |

MySQL 继续使用已有 `robomark_demo` 数据库。`robomark-api` 和 `robomark-web` 由 systemd 管理，继续以 `robomark` 用户运行。`/root` 仅给该账号增加穿越权限（ACL），不开放目录列表；服务采用 `ProtectHome=read-only` 和 `ProtectSystem=strict`，仅 data/run 可写。worker 公开演示时保持停止。

应用网关仍只监听 HTTP 12345，API 为 `127.0.0.1:18000`。域名入口、宝塔 Nginx、443、证书与防火墙保持原配置。应用网关使用 `/www/server/nginx/sbin/nginx`，配置为 `app/deploy/public-demo/nginx.conf`，通过独立 `robomark-web` 服务运行。

## Git 更新

本机只需执行：

```bash
./deploy/public-demo/update.sh jproot
```

或直接在服务器执行：

```bash
cd ~/robomark/app
bash deploy/public-demo/update-server.sh
```

服务端脚本检查 Git 工作区干净、分支正确且 worker 停止，备份数据库，然后 `git pull --ff-only origin codex/public-demo`。随后在服务器安装锁定依赖、执行前端检查与构建、运行幂等数据库迁移，切换前端链接并重启 API/应用网关，最后检查健康状态。源码和前端产物均由服务器处理，不使用 SCP 或上传源码压缩包。

不要用 `dev.sh` 更新生产服务，也不要重新运行 `seed.py`。如果上游分支经过 rebase，`--ff-only` 会拒绝更新，需要维护者先明确处理分叉，不会自动覆盖本地修改。`DEPLOYED_REVISION` 写入服务器 `.git/info/exclude`，环境文件、上传和构建缓存沿用 `.gitignore`。

失败时回退 Git 提交和前端链接；数据库迁移及 Python 依赖安装不会自动逆转，必要时使用更新前备份。上一版本记录在 `previous-revision` 和 `previous-frontend`。不要在部署 checkout 中保存未提交业务改动。

## 一次性路径迁移

从 `/opt/robomark` 迁移时，先备份数据库、环境和 systemd 配置，复制数据与虚拟环境，设置账号权限，使用 Git clone 创建 app，再构建前端。停服期间用 `relocate_paths.py --old /opt/robomark --new /root/robomark` 在一个事务内更新数据集、图片和相关配置的绝对路径，同时更新环境文件中的缓存路径。

验收通过后将原部署保存在新根目录下的 `legacy-opt-backup-*`，`/opt/robomark` 只保留兼容软链接，实际文件与运行服务均使用新位置。迁移工具可交换 old/new 参数反向迁移；有效图片与目录目标必须存在，重复执行不会再次修改路径。

## 检查与备份

```bash
ssh jproot 'git -C ~/robomark/app status --short; git -C ~/robomark/app log -1 --oneline'
ssh jproot 'systemctl status robomark-api robomark-web --no-pager'
ssh jproot 'curl -f http://127.0.0.1:12345/api/health'
ssh jproot 'journalctl -u robomark-api -n 100 --no-pager'
ssh jproot '~/robomark/venv/bin/python ~/robomark/app/deploy/public-demo/database_backup.py ~/robomark/backups/manual-$(date +%Y%m%d-%H%M%S).sql'
```

## 演示数据与限制

演示账号 `demo` 和 `admin` 的公开密码由维护者设为 `RoboMark2026!`。现有 QDU 40 张图片、13 张几何图形和历史推理/审核记录保留。QDU 的 55 个正式对象来自源标签，几何图形的 40 个对象来自精确生成坐标，不声称人工真值。

公开网关仍禁止注册、创建/修改推理接口、连接探测、新建或重试推理任务；已移除保存的推理凭据。已有结果、图片浏览与标注审核保持可用。账号共享业务数据，不自动重置；维护者需要运行推理时再手动启动 worker，完成后停止。
