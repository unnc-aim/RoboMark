# 功能页面截图

截图更新日期：2026-10-11（Asia/Shanghai）。所有截图均来自当前 Vue 页面，视口为 **1680 × 1000**，不含浏览器工具栏。

使用隔离演示数据库及仓库的 `test/`、`demo/` 图片，没有改动业务数据库、真实推理接口或用户审核结果。候选框来自样例框数据；连接测试访问本地 HTTP 演示服务的模型列表，不代表实际 vLLM 模型的识别精度。四点标注和 HTTP JSON 配置展示的是未保存编辑状态。

覆盖全部 12 个独立页面路由，并补充人工 / 审核模式、批量结果区及关键功能弹窗，共 **22 张**。旧的独立审核路由重定向到 annotate，因此不另存旧页面截图。

文件统一位于 `docs/images/screenshots/`；[截图清单](images/screenshots/manifest.json) 记录文件名、入口、展示状态和校验值。[返回 README](../README.md)。

## 页面与状态索引

| 页面 / 状态 | 入口 | 截图 |
|---|---|---|
| 登录 | `/login` | [login.png](images/screenshots/login.png) |
| 注册 | `/register` | [register.png](images/screenshots/register.png) |
| 数据集首页 | `/` | [home.png](images/screenshots/home.png) |
| 使用教程 | `/tutorial` | [tutorial.png](images/screenshots/tutorial.png) |
| 管理仪表盘 | `/admin` | [dashboard.png](images/screenshots/dashboard.png) |
| 数据集管理 | `/admin/datasets` | [datasets.png](images/screenshots/datasets.png) |
| 类别管理 | `/admin/categories/1` | [categories.png](images/screenshots/categories.png) |
| 用户管理 | `/admin/users` | [users.png](images/screenshots/users.png) |
| 工作量统计 | `/admin/statistics` | [statistics.png](images/screenshots/statistics.png) |
| 数据集导出 | `/admin/export` | [export.png](images/screenshots/export.png) |
| 人工标注工作台 | `/annotate/1?source=manual&image=3` | [annotation.png](images/screenshots/annotation.png) |
| 四点标注 | `/annotate/1?source=manual&image=11` | [annotation-points.png](images/screenshots/annotation-points.png) |
| 画后选择类别 | `/annotate/1?source=manual&image=11` | [category-picker.png](images/screenshots/category-picker.png) |
| 标注帮助 | `/annotate/1?source=manual&image=3` | [annotation-help.png](images/screenshots/annotation-help.png) |
| 快捷键设置 | `/annotate/1?source=manual&image=3` | [shortcut-settings.png](images/screenshots/shortcut-settings.png) |
| 预标注任务 | `/datasets/1/preannotation?task=2` | [preannotation.png](images/screenshots/preannotation.png) |
| 批量叠加结果 | `/datasets/1/preannotation?task=2` | [preannotation-results.png](images/screenshots/preannotation-results.png) |
| 预标注审核工作台 | `/annotate/1?source=preannotation&task=2&image=7&review_status=pending` | [review.png](images/screenshots/review.png) |
| 数据集格式配置 | `/admin/datasets` | [dataset-config.png](images/screenshots/dataset-config.png) |
| OpenAI 兼容接口配置 | `/datasets/1/preannotation?task=2` | [inference-profile.png](images/screenshots/inference-profile.png) |
| 自定义 HTTP JSON 接口 | `/datasets/1/preannotation?task=2` | [inference-http-json.png](images/screenshots/inference-http-json.png) |
| 推理接口通断测试 | `/datasets/1/preannotation?task=2` | [connection-test.png](images/screenshots/connection-test.png) |

## 截图浏览

| 登录 | 注册 |
|:---:|:---:|
| ![登录](images/screenshots/login.png) | ![注册](images/screenshots/register.png) |

| 数据集首页 | 使用教程 |
|:---:|:---:|
| ![数据集首页](images/screenshots/home.png) | ![使用教程](images/screenshots/tutorial.png) |

| 管理仪表盘 | 数据集管理 |
|:---:|:---:|
| ![管理仪表盘](images/screenshots/dashboard.png) | ![数据集管理](images/screenshots/datasets.png) |

| 类别管理 | 用户管理 |
|:---:|:---:|
| ![类别管理](images/screenshots/categories.png) | ![用户管理](images/screenshots/users.png) |

| 工作量统计 | 数据集导出 |
|:---:|:---:|
| ![工作量统计](images/screenshots/statistics.png) | ![数据集导出](images/screenshots/export.png) |

| 人工标注工作台 | 四点标注 |
|:---:|:---:|
| ![人工标注工作台](images/screenshots/annotation.png) | ![四点标注](images/screenshots/annotation-points.png) |

| 画后选择类别 | 标注帮助 |
|:---:|:---:|
| ![画后选择类别](images/screenshots/category-picker.png) | ![标注帮助](images/screenshots/annotation-help.png) |

| 快捷键设置 | 预标注任务 |
|:---:|:---:|
| ![快捷键设置](images/screenshots/shortcut-settings.png) | ![预标注任务](images/screenshots/preannotation.png) |

| 批量叠加结果 | 预标注审核工作台 |
|:---:|:---:|
| ![批量叠加结果](images/screenshots/preannotation-results.png) | ![预标注审核工作台](images/screenshots/review.png) |

| 数据集格式配置 | OpenAI 兼容接口配置 |
|:---:|:---:|
| ![数据集格式配置](images/screenshots/dataset-config.png) | ![OpenAI 兼容接口配置](images/screenshots/inference-profile.png) |

| 自定义 HTTP JSON 接口 | 推理接口通断测试 |
|:---:|:---:|
| ![自定义 HTTP JSON 接口](images/screenshots/inference-http-json.png) | ![推理接口通断测试](images/screenshots/connection-test.png) |

## 后续更新

页面或交互改变后，重新拍摄对应入口及相关弹窗，保持视口一致，等待数据和图片加载完成并关闭临时提示。检查截图中没有凭据或个人数据，再同步本索引、README 预览和清单校验值。项目 Logo 与几何测试图片总览不是功能页面截图，继续保留原文件。
