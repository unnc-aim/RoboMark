# 4656e22 前端生产 UI 迁移

2026-10-21。以 `docs/ui-redesign/FINALIZED.md` 的设计定稿为基准，覆盖 17 个页面及历史 Prompt、推理详情、类别编辑、画后选类与导出完成状态。原型文件和定稿校验清单保持原样。

## 组件与运行时

- Element Plus 及其图标依赖已移除。所有交互控件、表单、弹窗、确认、选择器、表格、分页、目录选择、折叠内容和链接通过项目内的 Reka UI 组件库实现。业务页面只保留语义排版、图片、SVG 和业务 Canvas。
- 共享组件与使用边界见 `src/shared/ui/README.md`。`pnpm check:ui` 阻止业务层重新使用原生交互控件或旧组件库。
- 引入 TypeScript、Tailwind CSS 4、Lucide、TanStack Vue Query。保留现有 Pinia 编辑会话、Axios 鉴权和 Canvas 交互。新增数据集端点类型、查询键、请求取消与缓存失效，登录/登出清空查询缓存。
- 浅色工作空间与深色工作台共享设计 tokens；备案和署名放在正常文档流中，不覆盖画布。
- 登录／注册页左侧仅展示卡牌轮播，使用 Embla 的自动播放、拖动、键盘及手动切换。32 张完整卡面统一收录在 `src/assets/aim-cards/`，WebP 总体积约 2.87 MiB，首屏只挂载当前与相邻图片，指示点最多显示 7 个。

## 页面映射

| 功能 | 生产入口 |
| --- | --- |
| 标注首页 / 管理概览 | `/` / `/admin` |
| 数据集工作区 | `/admin/datasets` |
| 数据集详情 / 图片分页 | `/datasets/:datasetId` |
| 预标注与审核 | `/datasets/:datasetId/preannotation` |
| 人工标注 / 预标注审核工作台 | `/annotate/:datasetId?source=manual` / `?source=preannotation` |
| 类别与模板 | `/admin/categories/:datasetId` |
| 成员 / 统计 / 导出 | `/admin/users` / `/admin/statistics` / `/admin/export` |
| 推理接口 | `/profiles` |
| 数据集设置 | `/datasets/:datasetId/settings` |
| 工作空间设置 | `/settings` |
| 教程 / 登录 / 注册 | `/tutorial` / `/login` / `/register` |

旧审核路由继续重定向到统一工作台；旧推理记录直达链接保留。新的推理详情入口在当前页面打开弹窗，不丢失批次和筛选上下文。

## 业务保留与边界

- 数据集卡片通过真实图片端点获取封面；详情和推理结果默认只渲染 6 张，可切换每页 12 张。无数据时显示空状态。
- 目录选择提供目录名和文件列表；服务器路径可手动编辑。浏览器不提供本机绝对路径，也不把目录选择误当作上传。
- 预标注保留后台任务、批次、执行/审核筛选、取消、重试、Token / TPS、历史 Prompt 的搜索、明确填入与撤销，以及请求历史与响应转换记录。
- 自定义正整数抽样接入真实 API，移除后端旧的 20 张上限，并增加 schema 回归。
- 保留矩形、四点、八点交线绘制、拖动、缩放、撤销/重做、类别模板、画后选类、主动选类和单类别跳过选择规则。提取的几何函数与快捷键解析独立于 UI。
- 保存草稿不审核通过；通过携带修订版本，在后端成功后才切图。冲突保留本地编辑。离页确认区分放弃修改与 Escape 取消导航。
- 工作台预加载后续 3 张，显示缩略图队列、图层与对象面板；移动端通过工具按钮展开对象与图层。
- 导出预览在提交有效配置前保持空状态；修改配置清空旧结果。下载保留认证、避免重复 `/api` 前缀并延迟释放 Blob。
- 多个类别快捷键以逗号分隔，兼容现有 `shortcut_key` 字段；按现有数据库限制保留总长度 10 字符，并校验别名之间的冲突。未执行数据库结构变更。
- 工作空间名称与说明是当前浏览器的显示偏好。后端没有团队配置/存储配额接口，因此页面明确说明本机保存，不展示虚构存储数字。
- 教程图片复用定稿的 MVM3D MIT 素材，许可证放在 `public/design/MVM3D-LICENSE.txt`。账号页使用用户提供的 AIM 五周年纪念卡牌，来源记录在 `src/assets/aim-cards/README.md`。标注画布保持原图颜色。

## 复现验证

机器检查（Node.js 22.18+；本次使用 Node.js 24）：

```bash
cd frontend
pnpm install
pnpm check
```

隔离浏览器验收：在一个终端启动 `pnpm --dir frontend dev --host 127.0.0.1`，再从仓库根目录运行：

```bash
playwright-cli --session robomark-migration open http://127.0.0.1:5173/login
playwright-cli --session robomark-migration run-code --filename=frontend/scripts/verify-ui-migration.js
```

脚本独立模拟所有 `/api/` 请求，不连接业务数据库或推理服务。验证覆盖数据集、设置、接口、成员权限、注册登录、导出、历史 Prompt、推理详情、矩形/四点/八点画布、草稿/审核与异常恢复，并在 1600×1100、768×1024、390×844 下逐页检查溢出、破图和空页。截图写入被 Git 忽略的 `output/playwright/migration/`。

后端抽样 schema 与原导出下载回归：

```bash
backend/venv/bin/python -m pytest backend/tests/test_preannotation_schema.py backend/tests/test_export_download.py -q
```

本次只完成代码迁移与本地隔离验收，未部署线上，也未执行真实推理、业务标注写入或生产数据库操作。

## 本次验收结果

- `pnpm check` 通过：组件边界检查、Vue TypeScript 检查、6 项前端单元回归和生产构建。
- 独立浏览器完整脚本通过：58 项交互检查、17 页 × 3 种尺寸共 51 次渲染检查，另补充 6 次账号页布局复查；457 次隔离模拟请求，无未预期请求、JavaScript 异常或 Vue 警告。
- 后端 schema 与导出下载共 22 项回归通过，仅有既有依赖弃用提示。
- 共享主 JS 约 376.54 kB（gzip 124.18 kB），共享 CSS 约 38.84 kB（gzip 8.57 kB），构建未再出现超过 500 kB 的 chunk 警告。
- 本地详细报告：`output/playwright/migration-report.json`；桌面、平板和手机截图：`output/playwright/migration/`。

## 后续调整验收

- 32 张完整卡面逐张浏览与循环切换检查通过；登录／注册页在桌面、平板和手机共 6 次布局检查通过，无异常或警告。
- 侧栏 Logo 的 hover 范围已将下方布局留白排除在外，人工验收确认效果正常。
