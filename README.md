# RoboMark

<p align="center">
  <img src="docs/images/logo.png" alt="RoboMark Logo" width="200">
</p>

<p align="center">
  <strong>图像数据标注与批量预标注平台</strong><br>
  管理数据集、人工标注、调用自定义视觉推理服务，在同一工作台审核候选框并导出训练数据。
</p>
<p align="center">
  <img src="https://img.shields.io/badge/Vue-3.x-brightgreen" alt="Vue 3">
  <img src="https://img.shields.io/badge/FastAPI-0.100+-blue" alt="FastAPI">
  <img src="https://img.shields.io/badge/MySQL-8.0+-orange" alt="MySQL">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
</p>

## 功能预览

| 预标注任务与批量结果 | 原标注工作台中的预标注审核 |
|:---:|:---:|
| ![预标注任务管理](docs/images/screenshots/preannotation.png) | ![预标注审核工作台](docs/images/screenshots/review.png) |

| 人工标注 | 数据集管理 |
|:---:|:---:|
| ![人工标注工作台](docs/images/screenshots/annotation.png) | ![数据集管理](docs/images/screenshots/datasets.png) |

| 管理仪表盘 | 工作量统计 |
|:---:|:---:|
| ![管理仪表盘](docs/images/screenshots/dashboard.png) | ![工作量统计](docs/images/screenshots/statistics.png) |

全部功能页面及配置弹窗见 [页面截图索引](docs/screenshots.md)。截图使用隔离演示数据，统一以 1680 × 1000 桌面视口拍摄；示例候选框和连接测试服务用于展示交互，不代表真实模型识别精度。

## 功能特性

| 模块 | 已实现能力 |
|------|------------|
| 用户与权限 | JWT 注册 / 登录、管理员与普通用户角色、用户添加 / 禁用 / 删除 / 重置密码 |
| 数据集 | 指定后端图片目录、扫描导入、批量导入、启用 / 停用、进度统计；配置 YOLO、DJI ROCO、RC2026-wulin 导入方式 |
| 类别 | 添加 / 编辑 / 删除、颜色与快捷键、排序、文本批量导入、图片模板、从其他数据集或格式默认类别导入 |
| 人工标注 | 矩形、四点 / 八点构造四边形、移框与调整、删除、缩放 / 平移、画后选择类别、撤销 / 重做、历史图片导航、快捷键帮助与自定义 |
| 推理接口 | vLLM / OpenAI 兼容接口及自定义 HTTP JSON，Endpoint、模型、认证、请求模板、字段映射、坐标转换；跨数据集复用和管理员共享 |
| 连接测试 | 已保存配置与未保存配置均可测试；显示可达性、认证或模型检查结果、HTTP 状态和耗时 |
| 后台预标注 | 数据集 Prompt、抽样验证、全量批次、独立 worker、持久化进度、并发控制、取消、失败重试及租约恢复 |
| 人工审核 | 缩略图批量叠加、按执行 / 审核状态与有无候选框筛选；统一 annotate 工作台编辑、保存草稿、通过、驳回与空结果确认 |
| 导出 | YOLOv5/v7/v8、YOLO Darknet、COCO JSON，训练 / 验证 / 测试比例、可选包含未标注图片、ZIP 下载 |
| 工作量 | 总览、近 30 天每日记录、按数据集 / 日期筛选、用户工作量统计、CSV / JSON 导出 |

预标注候选框经过审核后才追加到正式标注；已有正式框会保留。YOLO / Darknet / COCO 导出读取正式标注，未审核候选与草稿不会进入训练标签。

## 预标注与审核流程

1. 在首页或数据集管理进入“预标注与审核”，选择可复用的推理接口。
2. 配置完整 Endpoint、接口格式、模型及坐标规则，用“测试连接”检查服务。
3. 输入 Prompt，例如“标注图片中的所有无人机”，选择当前数据集类别与标注形状，先运行“抽样验证”。
4. 检查抽样结果后，对整个数据集创建全量批次。任务在独立后台 worker 执行，关闭页面不影响运行。
5. 在批量结果中叠加候选框并筛选，点击图片或“工作台审核”进入 annotate。
6. 修改 / 删除候选框、补画漏检目标；保存草稿供继续审核，或显式通过后导入正式标注。

直接打开 `/annotate/:datasetId` 时，默认进入最新全量批次的待审核队列（含草稿）；只有抽样批次时使用最新抽样批次，没有批次时进入人工标注。顶部可切换标注方式、批次、审核状态和候选框筛选。候选框为虚线，正式框为只读实线，并可分别开关图层。

**审核模式中，保存与通过是两个操作。** `Ctrl / ⌘ + S` 只保存草稿；“审核通过并下一张”或 `Ctrl / ⌘ + Enter` 才追加正式标注。上一张 / 下一张会保存实际修改的草稿，但不会自动通过。切换方式、批次、筛选、刷新或离开页面时，会保护未保存修改。

合法空结果需要人工确认；失败结果不能当作“没有目标”。无新增候选时保留已有正式框。审核采用修订版本检查与来源记录，重复通过不会重复导入；已审核候选只读，后续正式框修改切换人工标注。

接口配置保存在 MySQL 的 `preannotation_profiles`，支持多数据集复用；可选 `PREANNOTATION_DEFAULT_PROFILE` 在 `.env` 中管理共享默认接口。详细请求模板、结果 Schema、坐标转换、凭据存储、故障恢复和 API 见 [预标注与审核文档](docs/preannotation.md)。

## 技术栈与结构

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3、Vite 7、Element Plus、Pinia、Vue Router |
| 后端 | Python 3.10+、FastAPI、PyMySQL、原生 SQL |
| 数据库 | MySQL 8.0+，utf8mb4 |
| 认证 | JWT（python-jose）、bcrypt |
| 后台任务 | 独立 Python worker，MySQL 任务队列与租约 |

```text
RoboMark/
├── frontend/src/
│   ├── views/                 # 首页、标注工作台、预标注与管理页面
│   ├── components/            # 画布、缩略图、数据集 / 推理配置弹窗
│   ├── stores/                # 用户、人工标注、审核与快捷键状态
│   ├── router/                # 路由与权限
│   └── utils/                 # 统一 API 实例
├── backend/
│   ├── app/
│   │   ├── core/              # 数据库、配置、认证
│   │   ├── routers/           # REST API
│   │   ├── schemas/           # 请求、候选框与结果验证
│   │   ├── services/          # 推理、连接探测、转换与导出
│   │   ├── migrate.py         # 可重复执行的数据库升级
│   │   └── preannotation_worker.py
│   ├── tests/                 # 转换与隔离数据库工作流测试
│   └── scripts/               # 几何测试图片生成
├── database/                  # 初始化与历史迁移 SQL
├── demo/                      # 机器人演示图片
├── test/                      # 13 张几何测试图片与预期框
├── docs/                      # 预标注文档、截图索引与本地截图
├── sslly-nginx/                # Nginx 部署配置
├── dev.sh                     # API、worker、前端启停
└── CLAUDE.md                  # 开发规范
```

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 20.19+ 或 22.12+（Vite 7 要求）
- MySQL 8.0+
- 前端开发建议使用 pnpm；`dev.sh` 会使用 npm 安装和启动前端

数据集目录必须能被后端读取；API 和 worker 使用同一个数据库，并可读取同一份图片文件。视觉推理服务由用户自行部署，平台不内置 vLLM 模型或 GPU 服务。

### 一键启动

```bash
# 新安装：创建数据库及完整表结构
mysql -u root -p < database/init.sql

cp backend/.env.example backend/.env
# 编辑 backend/.env，设置 DATABASE_URL

./dev.sh
```

启动脚本准备依赖、执行迁移，并启动 API、独立预标注 worker 与前端。首次需要保存推理凭据时使用的加密密钥由脚本在配置为空时生成。

- 前端：http://localhost:5173
- API：http://localhost:8000
- Swagger：http://localhost:8000/docs
- 默认管理员：`admin / 123456`

已有数据库先配置 `.env`，执行 `./dev.sh migrate`；迁移可重复执行，补齐表和字段，不清空业务数据。

```bash
./dev.sh status     # 查看 API、worker、前端状态
./dev.sh logs       # 查看日志
./dev.sh restart    # 重启
./dev.sh stop       # 停止并清除 JWT 登录状态
./dev.sh worker     # 单独启动 worker
```

前台运行时按 `Ctrl+C` 停止服务。退出脚本轮换 JWT 密钥；推理凭据的加密密钥会保留。

### 手动启动

```bash
# 后端；新安装需先初始化数据库并复制 .env
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m app.migrate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

另开终端启动 worker：

```bash
cd backend
source venv/bin/activate
python -m app.preannotation_worker
```

另开终端启动前端：

```bash
cd frontend
pnpm install
pnpm dev
# 生产构建：pnpm build
```

手动启动时，如需保存 API Key 或自定义请求头，请生成并设置 `PREANNOTATION_ENCRYPTION_KEY`，并让 API 与 worker 共用该密钥：

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

将输出写入 `backend/.env` 并保留备份。完整环境变量模板见 [backend/.env.example](backend/.env.example)。

### 常用环境变量

| 变量 | 用途 |
|------|------|
| `DATABASE_URL` | MySQL 地址；例如 `mysql+pymysql://root:password@localhost:3306/robomark` |
| `SECRET_KEY` | JWT 密钥；生产部署设置固定随机密钥 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 登录有效期，默认 `1440` 分钟 |
| `CORS_ORIGINS` | JSON 数组，默认允许本地 5173 前端 |
| `PREANNOTATION_ENCRYPTION_KEY` | 推理凭据加密密钥，独立于 JWT |
| `PREANNOTATION_DEFAULT_PROFILE` | 可选共享默认接口 JSON，默认 `{}` |
| `PREANNOTATION_WORKER_CONCURRENCY` | worker 并发槽位，默认 `2` |
| `PREANNOTATION_ENDPOINT_CONCURRENCY` | 同一 Endpoint 并发上限，默认 `1` |
| `VITE_API_PROXY_TARGET` | 前端开发代理目标，默认 `http://localhost:8000` |

## 页面与快捷键

| 页面 | 路径 |
|------|------|
| 登录 / 注册 | `/login`、`/register` |
| 首页 / 教程 | `/`、`/tutorial` |
| 统一人工标注与审核工作台 | `/annotate/:datasetId` |
| 数据集预标注任务与批量结果 | `/datasets/:datasetId/preannotation` |
| 管理仪表盘 / 数据集 | `/admin`、`/admin/datasets` |
| 类别 / 用户 | `/admin/categories/:datasetId`、`/admin/users` |
| 工作量 / 导出 | `/admin/statistics`、`/admin/export` |

预标注管理位于原管理布局的主内容区；审核复用 annotate 画布。普通用户可使用预标注管理与审核，用户管理等 `/admin` 功能要求管理员身份。

| 默认快捷键 | 人工标注 | 预标注审核 |
|------------|----------|------------|
| `Ctrl / ⌘ + S` | 保存当前正式标注 | 仅保存审核草稿 |
| `Ctrl / ⌘ + Enter` | — | 审核通过并下一张 |
| `N` | 标记未见 | 无候选框时确认无目标 / 无新增目标 |
| `Ctrl / ⌘ + Z` | 撤销 | 撤销候选修改 |
| `Ctrl / ⌘ + Shift + Z` | 重做 | 重做候选修改 |
| `Delete` / `Backspace` | 删除选中框 / 最后一个点 | 删除选中候选框 / 最后一个点 |
| 滚轮 / 空格拖动 | 缩放 / 平移 | 缩放 / 平移 |
| `V` / `H` | 标注 / 拖动模式 | 标注 / 拖动模式 |
| 类别自定义键 | 选择类别并进入标注模式 | 选择补画类别 |
| `?` | 快捷键帮助 | 审核快捷键帮助 |

保存、未见、撤销、重做与帮助键可在工作台“快捷键”中自定义。

## 导出与测试数据

YOLO 框使用归一化的 `class_id x_center y_center width height`。导出界面可以选择格式和训练 / 验证 / 测试比例，下载 ZIP：

| 格式 | 主要产物 |
|------|----------|
| Ultralytics YOLO | `data.yaml`、`images/{train,val,test}`、`labels/{train,val,test}` |
| Darknet | `classes.names`、`dataset.data`、各分割的路径清单、图片与标签 |
| COCO | `annotations/instances_*.json`、各分割图片目录 |

[test/](test/) 提供 13 张包含矩形、圆形、小目标、重叠、边缘、低对比度和空白对照的 PNG。[expected_shapes.json](test/expected_shapes.json) 给出预期框，供人工核对，不会自动写入正式标注。详情见 [测试图片说明](test/README.md)。

```bash
cd backend
pip install pytest==8.3.5
python -m pytest tests/test_preannotation_schema.py -q
```

工作流集成测试需显式设置 `ROBOMARK_TEST_DATABASE_URL`，账户要能创建 / 删除隔离测试库。测试创建随机命名的数据库，不清空指定业务库；完整命令与覆盖范围见 [验证说明](docs/preannotation.md#验证)。

## 部署

前端执行 `pnpm build` 后，将 `frontend/dist/` 交给 Nginx；配置 SPA 路由回退及 `/api` 代理：

```nginx
server {
    listen 80;
    server_name your-domain.com;
    root /var/www/robomark/dist;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

通过进程管理器分别运行 API 与 `python -m app.preannotation_worker`，配置相同的数据库、凭据密钥和图片存储。仓库提供 [sslly-nginx](sslly-nginx/) 的 Nginx 配置；API、MySQL 与 worker 的容器化部署需要自行补齐镜像与挂载配置。

## API 与开发

启动 API 后访问 http://localhost:8000/docs。主要入口：

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/api/auth/login`、`/api/auth/register` | 登录、注册 |
| GET / POST | `/api/datasets` | 数据集列表、创建 |
| POST | `/api/datasets/{id}/scan` | 扫描图片 |
| POST | `/api/images/{id}/save` | 带图片修订版本保存正式标注 |
| GET / POST | `/api/preannotation/profiles` | 列出 / 创建推理配置 |
| POST | `/api/preannotation/profiles/{id}/test` | 测试已保存配置 |
| POST | `/api/datasets/{id}/preannotation-tasks` | 创建抽样 / 全量后台批次 |
| PUT | `/api/preannotation/tasks/{task}/images/{image}/draft` | 保存审核草稿 |
| POST | `/api/preannotation/tasks/{task}/images/{image}/review` | 通过 / 驳回 / 空结果确认 |
| POST | `/api/export` | 导出训练数据 |
| GET | `/api/admin/statistics/overview` | 管理统计 |

开发规范见 [CLAUDE.md](CLAUDE.md)。每个功能或修复及时提交，提交信息使用 `feat:` / `fix:` / `docs:` / `refactor:` 加简洁中文说明，不添加 coauthor。

后续计划包括标注框复制 / 粘贴、键盘微调、自动保存、任务分派、协作反馈、视频与分割标注。目前预标注审核由用户完成，未提供自动质量审核。

## License

MIT License。感谢 [Vue](https://vuejs.org/)、[FastAPI](https://fastapi.tiangolo.com/)、[Element Plus](https://element-plus.org/) 与 [Ultralytics](https://docs.ultralytics.com/)。
