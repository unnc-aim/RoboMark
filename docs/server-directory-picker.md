# 服务器目录选择器

“选择目录”读取运行 RoboMark API 的服务器文件系统，确认后回填绝对路径。已用于新建数据集的图片/标签目录、批量导入根目录，以及数据集设置中的图片、标签和 DJI ROCO 标注来源目录。也可手动填写路径；新建标签目录等既有行为保留。

支持上一级、面包屑、路径跳转、当前层名称筛选、隐藏目录开关和分页。空目录可以选择；取消（包括加载过程中取消）不改变原字段。加载失败时同时显示通知和弹窗内错误，并禁止确认失败路径。目录浏览不上传、创建、修改或删除服务器文件。

## 组件选择

调研了 [VueFinder](https://github.com/n1crack/vuefinder) 4.7.6（MIT）、[Syncfusion Vue FileManager](https://github.com/syncfusion/ej2-vue-ui-components) 和项目已安装的 [Reka UI](https://github.com/unovue/reka-ui) 2.11.0（MIT）。VueFinder 适合完整文件管理，但包含上传、编辑器、裁剪及多种语言编辑支持；Syncfusion 有独立许可条件。本需求仅选择服务器目录，采用已有 Reka UI Dialog、Listbox 的焦点管理和键盘导航，配合 FastAPI 只读接口，不新增前端依赖。

UI 组件为 `frontend/src/shared/ui/DirectoryList.vue`；请求与弹窗状态由 `frontend/src/components/DirectoryPicker.vue` 管理，统一沿用已有 API 认证与失败通知。

## 浏览范围

默认 `FILE_BROWSER_ROOTS=[]`，管理员可从服务器文件系统根目录浏览。可在 `backend/.env` 中配置一个或多个数据根目录：

```dotenv
FILE_BROWSER_ROOTS=["/data/datasets","/mnt/shared"]
```

重启 API 生效。配置后的根目录显示在选择器中；上级导航不会越过根目录，符号链接解析后的路径也必须位于允许范围内。仅管理员可以请求接口；操作系统读取权限仍生效。此配置约束目录浏览接口，数据集路径的手动输入仍沿用原有创建/更新接口校验。

## API

`GET /api/admin/filesystem/directories`（Bearer 认证、管理员权限）

| 参数 | 含义 |
| --- | --- |
| `path` | 服务器绝对目录路径；省略时打开首个浏览根目录 |
| `search` | 仅筛选当前目录的子目录名，不递归搜索 |
| `show_hidden` | 是否显示以 `.` 开头的目录，默认 `false` |
| `offset` / `limit` | 分页，默认 `0` / `100`，单页最多 `500` 项 |

返回规范化的 `path`、`parent_path`、`roots`、`breadcrumbs`、`entries`、`total`、`offset`、`limit`。仅列目录，不返回文件内容。不存在返回 404，不是目录/路径无效返回 400，无读取权限或超出范围返回 403，无效根目录配置返回 503。

## 验证

```bash
backend/venv/bin/python -m pytest backend/tests/test_filesystem.py -q
pnpm --dir frontend check
```

浏览器验收使用临时目录和隔离接口，不连接业务数据库。先运行前端 Vite 服务（5173），再在 `backend/` 启动目录测试服务：

```bash
venv/bin/python -m uvicorn scripts.preview_directory_picker:app --host 127.0.0.1 --port 8002
```

从仓库根目录执行：

```bash
playwright-cli -s=directory-picker open http://127.0.0.1:5173/login
playwright-cli -s=directory-picker run-code --filename frontend/scripts/verify-directory-picker.js
```

该测试服务只用于本地验收，能浏览的范围只有启动时创建的临时目录，退出时清理。测试覆盖键盘操作、完整路径回填、取消、隐藏目录、中文筛选、分页、404/403、通知操作、请求取消、批量导入、设置入口和手机布局。
