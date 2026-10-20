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

### 测试连接

预标注页面的接口选择区域，以及添加 / 编辑接口弹窗，均提供“测试连接”。弹窗可以在保存前测试当前输入，留空名称也能测试；已有 Key 留空会使用已保存的凭据。测试不创建配置或推理任务，也不发送图片。

OpenAI 兼容地址以 `/chat/completions` 结尾时，先使用同一认证访问对应的 `/models`，核对模型名并显示可用模型。模型列表路由不支持时，以及通用 HTTP JSON 接口，使用 HEAD 轻量探测；这类结果只表示服务可达，认证、请求格式与图像推理仍需抽样验证。

界面显示结果、HTTP 状态和耗时，区分网络 / TLS 错误、超时、认证失败、模型不存在与服务异常。整个探测最多 10 秒。第三方服务返回 401 不会清除平台登录状态；接口编辑后旧测试结果会清除。共享配置的隐藏凭据只能针对保存的地址测试，避免被其他用户转发到改写的地址。

API：`POST /api/preannotation/profiles/{id}/test` 测试保存的配置；`POST /api/preannotation/profiles/test` 使用 `{ "profile": { ... }, "existing_profile_id": null }` 测试未保存配置。

### 可选执行参数

```dotenv
PREANNOTATION_WORKER_CONCURRENCY=2
PREANNOTATION_ENDPOINT_CONCURRENCY=1
PREANNOTATION_MAX_IMAGE_BYTES=20971520
PREANNOTATION_MAX_RESPONSE_BYTES=2097152
```

worker 支持多个并发槽位，同一 endpoint 的配额通过数据库领取锁协调。等待模型时不持有数据库连接，各阶段用短事务保存执行记录。图片与响应大小、最大候选数量仍有上限；单图推理不设总耗时和响应读取时限。`timeout_seconds` 只控制连接与发送阶段，旧配置和旧批次快照中的该字段也采用这一含义。连接池等待上限为 30 秒。

### 每张图片的推理记录与失败重试

图片卡片的“推理详情”和审核工作台的“完整推理记录”打开同一对话式详情页，仍位于原管理布局的主内容区。失败或未完成的图片点击缩略图也进入详情，成功图片点击缩略图继续进入审核工作台。

左侧按每次尝试展示历史与状态；中间依次展示用户输入、实际请求体、响应、提取的模型输出与平台转换校验；右侧预览原图或该次候选结果。请求记录包含完整系统约束、Prompt、模型参数、输出 Schema、字段映射和坐标规则；响应记录包含 HTTP 状态、请求标识、原始正文、服务返回的 `reasoning_content` 和用量（服务提供时）。图片 Base64 用原图引用替代，认证字段与凭据值隐藏。页面以文本呈现返回内容，不执行模型输出。

每次领取持久化到 `preannotation_attempts`，独立保存阶段时间、结果、错误与耗时。后台处理中每 4 秒刷新一次已记录的阶段；这是执行阶段记录，不是模型 Token 流。未返回的推理说明不补写。新建后台任务会记录完整链路；旧任务只能显示已有 Prompt / 配置快照和原始响应，无法补还原未记录的请求。重试旧失败图片前，会先保留已有错误 / 响应快照，未知耗时不会伪造。

- 单图“重试此图”重新排队当前失败图片；等待自动退避重试的图片也可立即重试。
- 批次“重试失败”同时重新排队失败和等待自动重试的未审核图片，返回实际排队数量。
- 手动重试重置本轮尝试配额，历史记录序号持续递增；成功结果和人工审核草稿不被清空。运行中的图片不可重复提交，已取消批次需创建新批次。
- 仅任务创建者或管理员可以重试 / 取消；详情读取遵循当前数据集访问权限。
- 平台不再主动以整图时限中断慢模型，仍可手动取消任务。上游推理服务或网关返回的超时 / 错误会保留为该次失败记录。

页面提供“推理对话示例”入口，URL 带 `demo=1`，可查看成功、失败 / 重试、等待响应与旧任务状态；页面明确标注 Mock，不调用推理服务或写入数据库。示例使用仓库几何图片，输出和推理说明均为样例。

API：`GET /api/preannotation/tasks/{task}/images/{image}/trace` 分页读取记录（默认最近 5 条，支持 `before_id` 加载更早记录）；`POST /api/preannotation/tasks/{task}/images/{image}/retry` 重试单图。原批次 `retry-failed` 接口返回 `retried_images`。升级时执行 `python -m app.migrate`，迁移器会创建 migration 004 的记录表；随后重启 API 与 worker。仅执行 migration 003 不足以启用记录功能。

### 图片卡片的 Token 与 TPS

成功图片的候选框数量旁展示“输入 Token / 输出 Token · TPS”。用量读取服务顶层 `usage` 的 `prompt_tokens` / `completion_tokens`，也兼容 `input_tokens` / `output_tokens`。只使用这张图片最近一次成功请求的数据，不累计失败重试的消耗，也不会从生成文本长度或 `total_tokens` 猜测输入 / 输出数量。

新请求记录从 HTTP 请求开始到响应正文接收完成的单调计时，`TPS = 输出 Token ÷ 请求耗时（秒）`，包含连接、排队与首 Token 等待，不表示模型纯解码速度。已有完整阶段记录但没有 HTTP 计时的，使用请求至响应阶段的时间差估算，提示中明确标注“估算”。更旧的结果可从已有原始响应中读取 Token，但没有耗时就显示 `— TPS`；服务未返回用量时也显示 `—`，合法零值保留为 `0`。

图片列表 API 返回 `inference_metrics`：`input_tokens`、`output_tokens`、`tps`、`elapsed_ms` 与 `duration_source`（`http` / `trace` / `null`）。一页只增加一次批量查询，提取用量和计时小字段，不把完整推理链或原始响应发到缩略图列表。此功能无需新增数据库迁移。

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
6. 点击图片或批次的“工作台审核”，进入原 annotate 工作台编辑候选框。正式标注显示为只读实线，候选框显示为虚线。支持移动、调整、修改类别、删除、补画和撤销 / 重做。
7. 保存草稿后刷新仍可恢复；通过后追加正式标注并保留来源。可驳回，也可在删除全部候选后确认无目标。
8. 上一张 / 下一张遵循进入时的筛选条件。草稿与正式标注采用修订版本，冲突返回 `409`，要求重新加载核对。

审核过的结果不可在候选草稿中重新编辑，后续正式框修改使用原人工标注页面。空候选审核不会删除已有正式标注。重复审核不会重复导入或重复增加工作量。默认 YOLO / Darknet / COCO 导出只读取正式标注。

### 标注工作台的审核交互

直接打开 `/annotate/:datasetId` 时，优先进入最新全量批次的待审核队列，包含尚未编辑的结果和审核草稿；只有抽样批次时使用最新抽样批次，没有批次时进入人工标注。待审核队列处理完毕后显示完成提示，不会自动选择另一个批次。运行中的后台任务可以随时打开工作台检查已产出的结果，暂时无结果时可稍后刷新。

工作台顶部可切换“预标注审核 / 人工标注”、批次、审核状态和是否存在候选框。当前图片显示审核状态、未保存提示和筛选队列总数。右侧显示批次审核进度，并允许独立开关候选框和正式标注图层；左侧候选列表可定位框、修改类别和删除。已审核图片的候选记录只读，通过的框显示在正式标注图层。

审核操作有明确的保存边界：

- `Ctrl / ⌘ + S`（或自定义保存键）仅保存审核草稿，继续停留当前图片。
- “审核通过并下一张”或 `Ctrl / ⌘ + Enter` 才会将当前有效候选框追加到正式标注，然后进入筛选队列的下一张。
- “确认无目标”要求没有候选框；有已有正式框时显示“无新增目标”，保留正式框。
- “驳回”需要明确确认，保留已有正式标注。
- 上一张 / 下一张会保存实际修改的草稿，不隐式通过；未修改或撤销回原状态时不会写草稿。
- 切换模式、批次、筛选、刷新当前结果或离开页面时，有修改会提供“保存并切换 / 放弃修改”，关闭提示则留在当前图片。刷新浏览器也会提示未保存修改。

切换到人工标注会加载当前图片的正式框，延续原人工标注保存流程。预标注任务管理和批量叠加浏览继续位于原管理布局的主内容区，具体审核复用 annotate 的画布、类别和快捷键。旧的独立审核链接会重定向到 annotate，保留批次、图片和筛选上下文。

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

连接测试补充验收：38 项测试通过；Playwright 在 1440×1000 与 390×844 视口验证未保存配置的成功、401 及连接拒绝，保存配置按钮使用浏览器 mock 响应验收。没有改动用户的真实推理配置，也没有用连接测试宣称图像识别质量已验证。

统一工作台补充验收：39 项后端测试通过；Playwright 完成 21 项流程断言，覆盖默认全量批次、改类别、移框、补画、删除与撤销、空结果筛选、仅保存草稿、通过后切图、空结果确认、正式框保留、审核后只读、人工模式切换和旧链接重定向。审核写入使用浏览器内存 mock，没有通过验收去审核用户现有结果。1680×1000 和 1280×800 布局已查看截图，浏览器无运行时错误。

逐图推理记录补充验收（2026-10-20）：48 项后端测试通过，覆盖慢响应不受整图计时器中断、真实 HTTP 请求分阶段记录、原始错误响应、凭据与图片内容脱敏、单图 / 批次重试、历史游标、旧错误归档、租约恢复和权限。Playwright 完成 25 项流程断言，覆盖 Mock 四状态、历史查看、实际旧任务读取、审核页往返、单图 / 卡片 / 批次重试、刷新失败保留记录和示例隔离；审核与重试写入使用浏览器 mock，未改动现有结果。1680、1280 和 390 像素宽度已检查布局。真实推理网关的超时策略仍由上游服务决定。

Token / TPS 补充验收（2026-10-20）：67 项后端测试通过，包含合法零值、两组用量字段名、非法用量、缺少计时、旧阶段耗时估算、最近成功尝试及旧原始响应回退；前端构建通过。Playwright 的 11 项断言覆盖真实旧结果的用量展示、千位格式、TPS 提示、零值 / 缺失值区分、桌面 / 笔记本 / 手机布局和无推理写入。指标展示使用 mock 用量与计时，不重跑用户推理。
