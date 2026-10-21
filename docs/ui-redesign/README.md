# RoboMark UI 设计定稿

2026-10-21 · 用户确认定稿

当前版本已由用户确认，作为后续生产 UI 迁移的设计基准。定稿包含 17 个页面与 5 个弹窗 / 状态；保留红框预览作为本轮修改对照。定稿范围与文件校验清单见 [FINALIZED.md](FINALIZED.md)。

## 结论

保留 Vue 3、Vite、Pinia、Vue Router 和 FastAPI / MySQL，前端引入 TypeScript、Tailwind CSS 4、Reka UI / shadcn-vue、Lucide 和 TanStack Vue Query。重点是重建信息架构、视觉系统与业务边界。此次交付已从三个核心页面扩展为 17 页可点击的全站设计原型；生产页面与 API 尚未迁移。

RoboMark 应该是一套围绕图片工作的专业工具：数据集管理与推理任务使用浅色界面；标注与审核使用全屏深色工作台。同一套字体、间距、图标、状态与键盘操作贯穿所有页面。

## 预览

从仓库根目录启动：

```bash
python3 -m http.server 8766 --bind 127.0.0.1
```

- 数据集工作区：<http://127.0.0.1:8766/docs/ui-redesign/#datasets>
- 预标注与审核：<http://127.0.0.1:8766/docs/ui-redesign/#preannotation>
- 审核工作台：<http://127.0.0.1:8766/docs/ui-redesign/#annotate>

`index.html` 也可直接打开；通过 HTTP 预览更方便检查资源加载与交互。此原型用普通 HTML / CSS / JavaScript 实现，不添加生产依赖。所有数据保存在页面内存中，刷新重置，不连接后端、不调用推理服务。

## 第二轮修订 · 红框预览

`gallery.html` 共 22 个画面：17 页完整页面，以及历史 Prompt、推理详情、类别编辑、画后选类、生成后导出预览 5 个独立状态。红框与编号标出本轮修改区域。

| 反馈 | 实现 |
| --- | --- |
| 首页介绍区 | 已移除，直接呈现数据集 |
| 管理概览待办 | 已移除，最近动态纵向占满右栏 |
| 数据集右侧栏与点击 | 移除右栏；整张卡片可点击 / Enter 打开对应数据集详情 |
| 图片与标签目录 | 均提供本机文件夹选择器；浏览器只提供目录名及文件列表，服务器路径仍可手动填写 |
| 图片浏览 | 默认 6 张分页，支持每页 12 张；只生成当前页 DOM，图片使用 `loading=lazy` 与异步解码 |
| 抽样与批次 | 自定义正整数抽样数量；摘要下拉切换批次；恢复批次、Prompt、进度、状态、结果 / 空 / 失败及操作表 |
| 类别 | 按键捕获、多个快捷键、快捷键冲突校验与图片模板导入 |
| 导出预览 | 提交有效配置前保持空状态；修改配置后旧预览失效 |
| 历史 Prompt | 从管理导航移除，在当前数据集的预标注页面以弹窗筛选、明确填入 |
| 推理详情 | 留在当前页面，以弹窗查看请求历史、输入、响应与转换结果 |
| 标注工作台 | 对照线上截图保留完整顶部工具、模式 / 批次 / 队列、对象操作、进度、图层与推理入口；默认画后选类，主动选类或单类别跳过；预加载后续三张 |

本轮还修改了生产代码：下载请求避免 `/api/api/`，保留认证并延迟释放 Blob；导出 ZIP 在共享临时目录保留一小时，可跨进程读取、失败后重试；审核工作台补充后续图片预加载，类别选择规则统一为主动选择或单类别才跳过弹窗。这些代码尚未部署到线上。原型的其他页面依然使用本地演示数据，不代表生产 UI 已迁移。

验证脚本：`scripts/verify-revisions.js`（原型），`scripts/verify-production.js`（Vite 5173 + 全部接口由浏览器模拟）；生产导出后端使用隔离的临时文件与模拟数据库进行回归，不读取业务数据库。

## 全站截图总览

直接打开 [gallery.html](gallery.html)，或访问 <http://127.0.0.1:8766/docs/ui-redesign/gallery.html>。

- 单个 HTML 内嵌全部 17 页桌面截图与 5 个弹窗 / 状态，无需额外资源即可离线查看。
- 支持按页面 / 路由搜索、业务分组、单双列切换、放大与原始尺寸查看。
- 放大后可用左右方向键翻页，Esc 关闭。
- 每页提供交互原型链接；这些链接需要保留同目录的原型文件，或运行本地 HTTP 服务。

### 页面覆盖

| 原型入口 | 对应生产页面 / 功能 |
| --- | --- |
| `#home` | `/` 标注首页 |
| `#dashboard` | `/admin` 管理概览 |
| `#datasets` | `/admin/datasets` 数据集工作区 |
| `#dataset-detail` | 新增数据集详情 / 图片浏览 |
| `#preannotation` | `/datasets/:id/preannotation` |
| 预标注 → 推理详情 | 当前页面的单图记录弹窗 |
| `#annotate` | `/annotate/:id?source=preannotation` 审核模式；原审核重定向复用此页面 |
| `#manual` | `/annotate/:id` 人工模式 |
| `#categories` | `/admin/categories/:id` |
| `#members` | `/admin/users` |
| `#statistics` | `/admin/statistics` |
| `#export` | `/admin/export` |
| `#profiles` | 推理接口配置，原弹窗提升为页面 |
| 预标注 → 历史记录 | 当前数据集的历史 Prompt 弹窗 |
| `#settings` | 数据集配置，原弹窗提升为页面 |
| `#workspace-settings` | 新增工作空间设置 |
| `#tutorial` | `/tutorial` |
| `#login` / `#register` | `/login` / `/register` |

页面使用代表性示例数据，不模拟完整的多数据集权限、身份认证或后台任务。账号页无需真实凭据，导出仅生成配置清单，不生成训练数据。

### 文件与重建

- `mock.js` / `mock.css`：原有三页交互与视觉系统。
- `pages.js` / `pages.css`：全站页面注册表、共用布局与新增页面。
- `screenshots/full-site/`：17 页及 5 个状态的最新桌面截图与页面清单；旧 `screenshots/*.png` 保留为最初设计参考。
- `scripts/capture-pages.js`：Playwright CLI `run-code --filename` 批量渲染脚本；从仓库根目录执行，需本地 8766 服务。
- `scripts/verify-revisions.js`：主要交互烟雾检查。
- `scripts/build-gallery.py`：从截图与 `pages.json` 重建单文件预览，执行 `python3 docs/ui-redesign/scripts/build-gallery.py`。

截图中的所有数字与记录为设计样例。截图脚本会返回页面清单、三种尺寸的检查结果和异常列表；当前原始结果保存在 `output/playwright/ui-redesign-full/`（不入 Git）。

## 原有三个核心页面

| 页面 | 布局与意图 | 原型中可以操作 |
| --- | --- | --- |
| 数据集工作区 | 统一工作空间导航；图片封面与标注进度；右侧继续审核与近期动态 | 搜索、状态筛选、网格 / 列表切换、新建本地演示数据集、进入预标注与审核 |
| 预标注与审核 | 左侧配置接口 / Prompt / 类别，右侧批次摘要与结果图像；失败与待审核结果明确区分 | 状态筛选、候选框图层、历史 Prompt 填充、推理记录、点击样例图进入对应图片 |
| 审核工作台 | 轻量顶部上下文、左侧工具、中央大图、右侧对象属性、底部图像队列与审核动作 | 选中候选框、编辑坐标、缩放、显隐图层、草稿、通过并下一张、驳回、快捷键与图片导航 |

原先仅显示说明的管理入口已扩展为完整页面。浅色管理界面、深色工作台、字体与设计 tokens 延续原版，不新增生产依赖。新建 / 编辑类别、成员、接口配置、搜索、Prompt 复用、导出比例校验、教程切换与账号流程均为本地演示。原型支持矩形、四点与八点构造、画后选类、移动、角点调整、撤销 / 重做与缩放平移；生产迁移仍应复用已有画布与 API。手机支持导航、推理配置、结果查看与工作台控件；精细绘制以桌面为主。

原型中的用户、活动、存储、批次、数量、耗时、Token、TPS、候选框与置信度均为示例，不代表真实业务状态或识别质量。

## 为什么选择这套栈

| 选择 | 作用与取舍 |
| --- | --- |
| Vue 3 + TypeScript + Vite | 复用现有路由、状态、画布与 API；为候选框、修订版本、批次状态和导出类型补齐约束。本系统是登录后的交互工作台，目前没有 SSR / SEO 需求。 |
| Tailwind CSS 4 + CSS 自定义属性 | 用统一颜色、间距、字号、圆角、状态与明暗主题约束全站，防止每个页面独立积累 CSS。画布布局和几何样式仍使用清晰的语义 CSS。 |
| Reka UI + shadcn-vue | Reka 提供无样式的可访问交互基础；shadcn-vue 用来选取并维护项目内组件，不整包复制。Dialog、Select、Tabs、Popover、Tooltip、Command 等统一外观与键盘操作。 |
| Lucide Vue | 统一图标笔画、尺寸和语义，不再在工具栏混用 emoji 与不同图标风格。此 mock 的 SVG 为原型内自包含绘制，正式版使用 Lucide。 |
| TanStack Vue Query | 处理服务端数据缓存、查询失效、后台批次轮询、筛选与分页；不再在页面内复制大量 loading / error / fetching 状态。对于创建批次、通过审核等有副作用请求，不自动重试。 |
| Pinia | 保留会话、工作空间偏好与跨组件的画布编辑会话。服务端记录以 Query 为数据源，避免 Query / Pinia 各保存一份。 |
| 现有 Canvas 2D + TypeScript 领域层 | 当前已支持矩形、四点 / 八点、拖动、缩放、只读正式框、撤销 / 重做。先抽出坐标变换、命中检测与编辑命令，保留行为；有性能或维护证据后再考虑 Konva / WebGL。 |
| 现有 Axios API 实例 | 保留鉴权与错误拦截，补类型与取消请求；没有同时更换传输库的必要。 |

React + Next.js 需要重写现有交互和 Vue 组件，对当前需求收益有限。继续用 Element Plus 默认主题只能局部改善外观，难以形成这套画布优先的工具体验。新 UI 使用独立设计系统，迁移期间旧页面可保留 Element Plus，避免一次性替换所有业务。

当前生产构建成功，但共享 JS 约 1.22 MB、CSS 约 350 kB（构建报告的未压缩产物大小），存在大 chunk 警告。迁移时检查图标全局注册、组件全量导入与路由依赖，按页面加载；根据实际 bundle 分析决定拆分方式。

## 前端边界

```text
frontend/src/
  app/                    # 应用启动、路由、权限、providers
  layouts/
    WorkspaceLayout.vue   # 管理 / 数据集 / 推理任务
    EditorLayout.vue      # 全屏人工标注与审核
  features/
    datasets/             # 列表、导入、类别、数据集设置
    preannotation/        # 接口、Prompt、批次、结果、执行记录
    annotation/
      domain/             # geometry、commands、history、revision
      canvas/             # Canvas 2D 渲染与指针输入
      composables/        # 编辑会话、审核队列、快捷键
      components/         # 工具栏、对象面板、图层、filmstrip
    exports/
    statistics/
    users/
  shared/
    ui/                   # Button、Dialog、Select、EmptyState 等
    api/                  # Axios 实例、端点类型、query keys
    styles/               # tokens、主题、排版与基础样式
    lib/
```

依赖方向：页面编排 → feature 组件 / composable → domain / API → shared。几何与审核规则不依赖 UI 组件库。每个 feature 拥有自己的查询、表单、组件和类型，避免全部堆入全局 store 或巨大 views。

画布编辑、草稿持久化、审核通过是不同命令：

- 编辑只改变本地会话与 dirty 状态。
- 保存草稿只提交候选修改，成功后更新当前修订版本，不计为通过。
- 通过必须显式触发，携带修订版本；等待后端成功后再更新队列并切换下一张。冲突保留本地修改并要求重新加载 / 解决。
- 原有正式框保持只读图层；失败任务不能当成合法空结果。
- 保留离页保护、空结果确认、批次选择、执行 / 审核状态筛选、无候选框过滤、幂等导入和来源追踪。
- 后台任务先沿用现有 REST 轮询；页面不可见时降频，完成后停止。无需为 UI 重构先引入 WebSocket 或更换任务基础设施。

## 视觉系统

| 项目 | 设计值 |
| --- | --- |
| 浅色底 / 主面 | `#f7f8fa` / `#ffffff` |
| 主文字 / 次文字 | `#20232c` / `#747b89` |
| 主操作 | `#3a61ed`；蓝色仅强调当前导航、选中状态与主操作 |
| 成功 / 待审核 | 绿 / 琥珀，状态同时显示文字 |
| 深色画布 / 面板 | `#15191f` / `#1d222b` |
| 字体 | DM Sans + Noto Sans SC，离线回退系统字体；正式版评估自托管字集与加载体积 |
| 尺度 | 页面标题 26–29 px；主体与操作 12–14 px；紧凑指标 10–11 px，正式开发继续做可读性验证 |
| 间距 / 圆角 | 基于 4 px；页面区块 24–32 px；控件约 6–8 px，内容面板约 10–12 px |

原型截图中的图像使用 CSS 亮度提升，便于评审低光场景的框与对象。原始文件未改动。正式标注默认保持图像原色；若提供亮度增强，必须是用户可切换的查看选项，不能改变源图或导出像素。

备案与署名信息应放在非覆盖的页面底部；工作台不得使用固定覆盖层遮挡画布或审核操作。具体上线时保留现有备案信息。

## 迁移顺序

1. 建立 tokens、基础 UI 组件、两种布局、TypeScript 与 typed API；旧路由继续可用。
2. 迁移数据集列表与详情，建立加载、空、权限不足、异常和导入中等状态。
3. 迁移推理配置、历史 Prompt、批次与批量结果、单图执行记录。
4. 抽离画布领域逻辑并接入新工作台；针对修订冲突、草稿、通过、空结果、取消 / 重试、快捷键做重点回归。
5. 迁移类别、导出、统计、用户与登录，清理旧 Element Plus 依赖和重复样式。

全站迁移的定义包含所有现有页面与异常状态，不能只美化这三个页面。该交付阶段只用于确认产品结构与视觉方向。

## 素材来源

机器人样例来自 [DRL-CASIA/MVM3D](https://github.com/DRL-CASIA/MVM3D)，作者仓库用于多视角机器人检测研究。仅下载了 `sample_datasets/imgs/left/` 下的 `1024.jpg`、`1655.jpg`、`3591.jpg`、`3757.jpg`、`4186.jpg`、`549.jpg`，文件放在本目录 `assets/`；保留仓库 [MIT License](assets/MVM3D-LICENSE.txt)，Copyright © 2021 ZichengDuan。原型页脚与图片替代文字也注明来源。它们是公开参考样例，不是项目团队采集的数据。

几何图像使用仓库现有 `test/shapes_06_mixed_colors.png`。原型中的图片仅用于 UI 设计预览；正式产品使用用户导入的数据集。

曾尝试使用内置 imagegen 生成机器人场景，但服务返回 503，未产生可用图片。最终交付不含 AI 生成图片。

## 验证

验证结果与屏幕尺寸记录见 [VALIDATION.md](VALIDATION.md)。截图输出位于仓库 `output/playwright/ui-redesign/`（被现有 Git 规则忽略），交付用桌面截图另外保存在本目录 `screenshots/`。
