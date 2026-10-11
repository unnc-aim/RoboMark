# 数据集批量预标注与审核

用户在数据集上输入 Prompt，后台调用自己的 vLLM 或其他 HTTP 推理服务，为创建任务时的全部图片生成候选框。候选框可叠加浏览、筛选、修改、删除和补画；审核通过后追加到正式标注。

## 运行与数据库

要求 MySQL 8.0+、Python 3.10+、Node.js 20.19+ 或 22.12+（当前 Vite 7 的要求）。API 与 worker 必须使用同一个数据库，并能访问数据库中记录的图片文件路径。

新安装：

```bash
mysql -u root -p < database/init.sql
cp backend/.env.example backend/.env
# 编辑 DATABASE_URL
./dev.sh
```

已有数据库升级：

```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
python -m app.migrate
```

迁移会补齐旧的数据集配置、四点标注、图片修订版本和预标注表，可重复执行，不清空已有图片或标注。`init.sql` 已包含新安装所需的全部表。旧的 migration 001 / 002 也已修正为可重复执行；预标注版本与来源列由 Python 迁移器补齐，不能只执行 migration 003 SQL 来替代完整升级。

独立启动：

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
# 在另一个终端使用同一虚拟环境与 .env
python -m app.preannotation_worker
```

`./dev.sh` 默认同时启动 API、worker 和前端。`./dev.sh worker` 单独启动 worker，`./dev.sh migrate` 升级数据库；`status` / `logs` 包含 worker，日志为 `preannotation-worker.log`。停止 worker 保留任务记录，正在处理的图片在租约到期后恢复领取。

## 统一推理配置

接口配置统一保存在 MySQL 的 `preannotation_profiles`，与数据集的导入格式配置 `dataset_configs` 分开。多个数据集可复用同一接口；普通用户管理自己的配置，管理员可以共享配置。任务创建时固定 endpoint、请求格式、坐标规则、类别和 Prompt 的版本。

API Key 和所有自定义请求头值加密保存，客户端仅收到是否存在 Key 和请求头名称。加密密钥独立于 JWT：

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

将生成值保存为 `backend/.env` 的 `PREANNOTATION_ENCRYPTION_KEY` 并保留备份。`dev.sh` 仅在该变量为空时首次生成，退出时轮换 JWT 密钥不会改变它。没有此密钥时仍可保存不含认证的接口，保存凭据会返回明确错误。

### .env 默认接口

可选的 `PREANNOTATION_DEFAULT_PROFILE` 是 JSON 对象，字段与接口配置 API 一致。例如：

```dotenv
PREANNOTATION_DEFAULT_PROFILE={"name":"共享 vLLM","endpoint":"http://gpu-server:8000/v1/chat/completions","interface_type":"openai","model":"your-vision-model","api_key":"","response_path":"choices[0].message.content","annotations_path":"annotations","coordinate_system":"relative_1000","box_format":"xyxy"}
```

设为 `{}` 时仅使用页面保存的配置。配置完整请求地址，不自动拼接 `/v1/chat/completions`。API 启动和迁移命令会将环境默认配置同步为一条共享记录；相同配置不重复创建或增加版本。该记录在页面上只能使用，修改须编辑 `.env` 后重启 API。其他页面配置不被覆盖；删除环境变量不会自动删除已经保存的记录。

凭据在任务执行时使用当前配置的受保护引用。停用普通配置或撤销凭据会影响尚未执行的调用，已生成结果和已保存审核草稿仍保留。

### 可选执行参数

```dotenv
PREANNOTATION_WORKER_CONCURRENCY=2
PREANNOTATION_ENDPOINT_CONCURRENCY=1
PREANNOTATION_MAX_IMAGE_BYTES=20971520
PREANNOTATION_MAX_RESPONSE_BYTES=2097152
```

worker 支持多个并发槽位，同一 endpoint 的配额通过数据库领取锁协调。推理期间不占用数据库连接。图片读取、响应大小、最大候选数量和总请求时间均有上限。

## 请求格式与结果转换

OpenAI 兼容模式发送图片 data URL 与 Prompt，支持 Prompt 约束、`response_format` JSON Schema 或 vLLM `structured_outputs`。使用哪种扩展应与实际服务版本匹配。

通用 HTTP JSON 模式支持 POST / PUT、请求模板、响应提取路径、候选数组路径和字段映射。例如服务请求：

```json
{
  "image": "{{image.data_url}}",
  "prompt": "{{prompt}}",
  "model": "{{model}}",
  "schema": "{{output_schema}}"
}
```

完整占位符保留对象或数组类型。可用变量：`image.data_url`、`image.base64`、`image.mime`、`image.width`、`image.height`、`prompt`、`user_prompt`、`categories`、`output_schema`、`model`。`prompt` 会加入输出约定，`user_prompt` 是用户原文。模板不执行脚本。

假设服务返回：

```json
{"result":{"objects":[{"label":"无人机","bbox_2d":[100,100,300,300]}]}}
```

对应配置：

```json
{
  "response_path": "result",
  "annotations_path": "objects",
  "field_mapping": {"label":"label","bbox":"bbox_2d"},
  "coordinate_system": "relative_1000",
  "box_format": "xyxy"
}
```

字段路径支持嵌套对象和数组位置，例如 `choices[0].message.content`；空响应路径表示使用整个响应，空候选路径支持顶层数组。模型输出 Schema 按候选路径和字段映射生成，最终产物仍转换为平台现有的 `category_id`、`annotation_type`、`x_center`、`y_center`、`width`、`height` 及四点字段。

像素坐标按实际读取的原图尺寸归一化，0–1000 坐标除以 1000。不会猜测模型坐标体系。四点须按边界顺序构成有效凸四边形，外接矩形自动计算。非法类别、非有限坐标、越界、零面积、截断和无法解析的响应使该图片验证失败，不被当作“未发现目标”。

## 用户流程

1. 首页或管理员数据集列表进入“预标注与审核”。
2. 添加 / 选择接口，选择当前数据集类别和矩形 / 四点形状，填写 Prompt。
3. “抽样验证”创建 1–20 张图片的后台任务，与全量使用同一执行管线。
4. “对整个数据集运行”创建新批次，固定当前图片清单；关闭页面后继续执行。
5. 按批次、是否存在当前候选框、执行状态、审核状态筛选。合法空结果、未处理和失败分别展示。
6. 点击图片，在画布中编辑候选框。正式标注显示为只读实线，候选框显示为虚线。支持移动、调整、修改类别、删除、补画和撤销 / 重做。
7. 保存草稿后刷新仍可恢复；通过后追加正式标注并保留来源。可驳回，也可在删除全部候选后确认无目标。
8. 上一张 / 下一张遵循进入时的筛选条件。草稿与正式标注采用修订版本，冲突返回 `409`，要求重新加载核对。

审核过的结果不可在候选草稿中重新编辑，后续正式框修改使用原人工标注页面。空候选审核不会删除已有正式标注。重复审核不会重复导入或重复增加工作量。默认 YOLO / Darknet / COCO 导出只读取正式标注。

## 故障与恢复

- 取消使剩余图片终止，已生成结果仍可审核；迟到响应凭领取 token 和状态被拒绝。
- worker 每 10 秒续租，租约 45 秒；进程退出后领取会在到期后恢复。恢复或重试可能重复调用外部推理服务，数据库结果保持幂等。
- 临时网络错误和可重试 HTTP 状态有限重试，最大尝试次数由配置决定；认证、配置和结构错误需要修正原因。失败重试不清除成功结果或审核结论。
- 新 Prompt / 接口转换规则创建新批次，不覆盖旧批次。每次模型结果与人工草稿分开保留。
- 普通标注保存 API 现在要求 `revision`，来自图片详情的 `annotation_revision`，并保留 `source_preannotation_id`；前端已更新。外部调用者需要同步更新。
- 推理服务必须支持图片输入；纯文本模型即使接口兼容，也不能提供有效图像预标注。

## 验证

纯转换测试：

```bash
cd backend
pip install pytest==8.3.5
python -m pytest tests/test_preannotation_schema.py -q
```

真实数据库集成测试需显式指定可创建 / 删除测试数据库的隔离 MySQL 地址：

```bash
ROBOMARK_TEST_DATABASE_URL='mysql+pymysql://test_user:test_password@127.0.0.1:3306/test_database' \
  python -m pytest tests -q
```

测试仅创建并删除随机命名的 `robomark_test_*` 数据库，不清空连接字符串中已有数据库。测试账户须拥有创建这些测试数据库的权限。工作流测试覆盖真实 HTTP 请求、独立 worker 新进程恢复、取消、重试、配额、编辑审核冲突、普通保存来源和导出隔离。

本次验收使用隔离 MySQL 9.3 与可控 HTTP mock，以及 Playwright 浏览器操作。真实 vLLM / GPU 服务未提供，真实模型识别精度、四点定位质量和推理延迟未验证；这些需用用户配置的服务与代表性图片试运行评估。
