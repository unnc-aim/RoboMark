# jproot 公开演示部署

演示地址：https://robomark.lijie.space 。部署分支：`codex/public-demo`。

## 当前结构

- `/opt/robomark/app`：当前代码和 `frontend/dist`；更新脚本将其转换为版本目录的符号链接。
- `/opt/robomark/venv`：Python 运行环境，使用 `python -m pip` 安装依赖。
- `/opt/robomark/data/datasets`：压缩后的 QDU 40 张照片、13 张几何图形及源标签清单。
- `/opt/robomark/shared/backend.env`：数据库连接、固定 JWT 密钥、凭据加密密钥和 CORS。
- `/opt/robomark/shared/deployment-secrets.json`：仅 root 可读的站内管理员凭据。
- `/opt/robomark/backups`：数据库快照。
- MySQL：使用已有服务中的 `robomark_demo` 数据库和同名专用账号。

应用对外仅监听 **HTTP 12345**，统一提供前端、图片及 `/api`。API 的 `18000` 只监听 `127.0.0.1`。域名入口、宝塔 Nginx、证书、443 和防火墙由站点所有者管理；本目录的更新脚本不会修改或重载它们。

`nginx.conf` 是独立的应用网关配置，只监听 12345，使用服务器已有 Nginx 二进制，但通过独立 systemd 服务运行。

CORS 为 `https://robomark.lijie.space`。同源访问无需配置额外 CORS。

## 体验账号与数据

公开体验可使用 `demo` 普通账号或 `admin` 管理员账号，当前两者密码均由维护者设为 `RoboMark2026!`。普通账号可查看图片、正式标注、预标注结果、推理记录，并修改标注或审核草稿；数据集／类别管理、导出和管理仪表盘沿用管理员权限。管理员账号也计划公开，因此已移除保存的 GLM 推理接口并清空当前数据库中的接口凭据；历史结果和执行记录保留。

QDU 的 55 个正式标注对象来自 `rmcv/armor` 的 `qdu_damo` 源标签，来源登记为模型自动标注，不声称人工真值；排除源标签中的 ignore 区域。几何图形的 40 个正式标注来自生成时的精确坐标，保留一张空白对照。GLM-5.3-Flash 的预标注独立生成，不将源标签输入模型。

QDU 原分辨率 1440×1080 保留，JPEG quality=80；选中照片约 21.3 MB → 7.8 MB。13 张几何图形转为无损 WebP，约 177 KB → 51 KB。源数据许可及来源登记保存在数据目录中。

公开网关禁止注册、新建／修改推理接口、连接探测、新建任务和重试，防止公众消耗模型额度。已有预标注展示与标注审核保持可用。普通账号共享数据，操作会互相影响。停止 worker 不会抹掉预标注和推理记录。

## 更新部署

在本机仓库中执行，确保改动已经提交，且部署前没有预标注任务正在运行：

```bash
git switch codex/public-demo
git pull --ff-only
# 如需合入主线：git merge origin/main
# 处理冲突并检查 App.vue，保留演示分支不显示备案号的修改。
./deploy/public-demo/update.sh jproot
```

脚本会检查工作区、安装锁定的前端依赖、执行类型检查和构建、只打包已提交代码与构建产物，再通过 SSH 上传。服务器先备份演示数据库、安装 Python 依赖、执行幂等迁移，然后切换版本并重启 `robomark-api`。保留数据库、数据图片、密钥及用户维护的宝塔配置。健康检查失败时回退代码；数据库迁移与依赖安装不会自动逆转，必要时使用备份恢复。

更新需要本机 Git、pnpm、SSH、scp、tar，以及可登录的 `jproot`。服务器无需安装 Node.js。不要使用 `dev.sh` 更新生产服务，也不要重新运行 `seed.py`。

## 状态与日志

```bash
ssh jproot 'systemctl status robomark-api robomark-web --no-pager'
ssh jproot 'journalctl -u robomark-api -n 100 --no-pager'
ssh jproot 'curl -f http://127.0.0.1:12345/api/health'
```

需要维护任务时，先完成现有任务再停止 worker；公开演示平时关闭 worker，不启用开机自启：

```bash
ssh jproot 'systemctl start robomark-worker'
ssh jproot 'journalctl -u robomark-worker -f'
ssh jproot 'systemctl stop robomark-worker'
```

`systemctl restart robomark-api robomark-web` 只重启应用服务，不重载宝塔 Nginx。

## 备份与回退

```bash
ssh jproot '/opt/robomark/venv/bin/python /opt/robomark/app/deploy/public-demo/database_backup.py /opt/robomark/backups/manual-$(date +%Y%m%d-%H%M%S).sql'
ssh jproot 'readlink -f /opt/robomark/app; readlink -f /opt/robomark/previous'
```

更新后可将 `/opt/robomark/previous` 指向的目录重新链接为 `app`，再重启 API。仅回退代码不会撤销已经执行的数据库迁移；遇到不兼容迁移时，应在停服后从对应数据库备份恢复。不会自动每天重置演示数据；公开前的初始快照由维护者决定何时恢复。
