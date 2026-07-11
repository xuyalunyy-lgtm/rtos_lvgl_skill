# 多页面 MVP UI 生成计划

## 目标与默认决策

将当前单页 `ui/manifest.json` 升级为应用级输入：整理好设计图、切图、字体、页面状态和交互关系后，`generate_ui` 一次生成可编译的多页面 MVP。

已确定：

- 导航：栈式导航，支持 `push`、`replace`、`back`；默认最大深度 8。
- Model：生成接口 + 内存 Mock，不耦合网络、NVS 或具体 SDK。
- 平台基线：LVGL v9 + FreeRTOS；所有 LVGL 修改仅在 UI 线程或 `lv_async_call` 回调中执行。
- 输出：先写入 `artifacts/ui_app/<app_id>/`，验证通过后才允许通过现有 `apply_patch` 进入业务工程。
- 现有 Manifest v1 单页链保持兼容；多页模式要求 Manifest v2。

## Manifest v2 合同

顶层字段固定为：

```json
{
  "schema_version": "2.0",
  "app": {
    "id": "affirmation_app",
    "entry_page": "home",
    "navigation": { "mode": "stack", "max_depth": 8 }
  },
  "display": { "width": 480, "height": 800, "color_format": "RGB565" },
  "shared": { "assets": {}, "fonts": {} },
  "models": [],
  "pages": [],
  "routes": []
}
```

页面字段：

- `id`：全局唯一 snake_case，作为路由和 C 标识符基础。
- `design`：默认状态设计图；不得作为运行时资产。
- `state_designs`：每个可视状态到设计图的映射；所有声明状态必须具备基线。
- `template`：已支持模板名或 `auto`；低置信分析不得静默降级。
- `assets`、`fonts`：优先页面配置，未提供则继承 `shared`。
- `states`：默认含 `default`；例如 `["default","favorited","loading","error"]`。
- `events`：仅声明节点事件与动作。

路由字段：

```json
{
  "id": "home_to_detail",
  "from": "home",
  "event": "detail_button.clicked",
  "to": "detail",
  "mode": "push"
}
```

只支持三种路由模式：`push`、`replace`、`back`。`back` 不填写 `to`，由 Router 恢复上一页。

事件动作只支持：

- `route`：引用一个 `routes[].id`。
- `model_set`：给 bool、int32、string 字段赋值。
- `model_toggle`：切换 bool 字段。
- `set_state`：切换当前页面声明的状态。

Model 字段仅支持 `bool`、`int32`、`string`；字符串必须声明 `max_length` 和 `default`。首版不生成网络、存储、定时任务或业务协议。

字体继续遵守现有策略：设备工程使用 LVGL `.c` 字库；需要 native 视觉验收的字体必须提供同一字体的 `preview_bin`，缺失即拒绝 native render。

## 生成架构

`generate_ui` 增加应用模式：传入 `manifest_path` 或检测到 Manifest v2 时进入 `app_mvp` 编排；不增加第七个 MCP 工具。

生成目录固定为：

```text
artifacts/ui_app/<app_id>/
├─ app/
│  ├─ ui_app.c/.h
│  ├─ ui_router.c/.h
│  └─ ui_app_manifest_resolved.json
├─ pages/<page_id>/
│  ├─ ui_<page_id>.c/.h
│  ├─ ui_spec.json
│  └─ per-state render/compare evidence
├─ presenters/presenter_<page_id>.c/.h
├─ models/model_<name>.c/.h
├─ assets/、fonts/、ui_app_sources.cmake
└─ app_evidence.json
```

实现职责：

- `ui_app`：初始化 Model、Router、入口页；提供 `ui_app_start(parent)`、`ui_app_deinit()`、`ui_app_post_event(...)`。
- `ui_router`：维护页面栈；`push` 隐藏旧页并创建目标页，`back` 销毁当前页并恢复旧页，`replace` 销毁旧页后创建目标页。
- Page：只负责 LVGL 对象创建、销毁、页面状态渲染和数据展示。
- Presenter：绑定节点事件；只调用 Router 或 Model，不保存页面对象所有权。
- Model Mock：保存默认数据；提供 `init/get/set/reset`。外部线程只能通过 `ui_app_post_event` 投递完整拷贝 payload，最终经 `lv_async_call` 回到 UI 上下文。
- 资源：跨页资产和字体去重；设计图永不进入运行时资产包。

所有页面必须生成 `create/destroy/show/hide/set_state` 生命周期函数。Router 失败、栈溢出、未知 route、未知 state、未知 model 字段均返回明确错误码，不能静默忽略。

## 生成与验证流程

1. 解析 Manifest v2，先做路径、ID、字体、资源、状态、事件、路由图验证。
2. 为每页执行现有"设计分析 → UI Spec → C/H → 结构验证"链路。
3. 汇总共享资产、字体、页面工厂、Presenter、Model、Router 和 CMake 源文件清单。
4. 生成每页每个状态的 native scene 与 render evidence。
5. 生成三页面 MVP 集成夹具：`home → detail → settings`，覆盖 `push`、`back`、`replace`、Model toggle。
6. 仅当所有页面和路由通过时，将 `app_evidence.json.status` 标为 `verified`；否则保留产物但拒绝 replace 模式应用。

低置信节点、缺失切图、未支持效果必须记录为 `manual_required`，并使应用状态为 `needs_manual_work`，不能计入"80% 完成"。

## 验收点

### Manifest 与代码

- Manifest v2 验证通过；页面 ID、route ID、model 名、节点 ID 均唯一。
- 入口页存在；所有 route 的来源、事件节点、目标页、模式合法。
- 每个声明状态都存在设计基线；每张输入切图均出现在 `cutout_audit.json`。
- 所有生成 C/H、字体 C 源、资源构建清单通过编译门。
- Router 生命周期测试证明：连续 `push/back/replace` 后页面栈、活动页面、对象数量正确，无残留页面。

### 线程与 MVP 行为

- Presenter 不直接被后台线程调用 LVGL API。
- 所有跨线程更新经 `ui_app_post_event` 和 `lv_async_call`；payload 拷贝后不再引用调用者内存。
- Model Mock 的 bool、int32、string 更新能驱动对应页面刷新。
- 收藏切换、页面跳转、返回、错误态切换均有独立行为测试。

### 原生渲染真实性

- 每个页面、每个声明状态产生 `render.png`、对象树、资源加载报告、字体加载报告。
- 有文字且声明字体时，`font_load_report.json` 必须列出全部 `font_id`；缺失 `.bin` 直接失败。
- 图像请求数与成功加载数相等；不允许使用设计基线图作为运行时背景。
- 对象树节点数大于 1，且文本/图片节点与 Spec 一致；空白页、缺资源、未知 opcode 均失败。
- MVP 视觉阈值：最终整数总分 ≥ 9000、全图 SSIM ≥ 0.90、像素变化率 ≤ 10%；文字、主交互区、状态栏三类重点区域 SSIM 均 ≥ 0.90。最多评估 3 个候选轮次，只交付严格单调链中的最高分版本；任何门槛未达标必须标记 `manual_required`，不可标记 `verified`。

## 实施批次

1. ✅ **Manifest v2 与 Validator** (`693d49e`)：兼容读取 v1 单页；v2 开启 app 模式；补路由、事件、Model、状态与资源校验。45 tests.
2. ✅ **App 代码生成器** (`e642768`)：生成 Page Factory、Router、Presenter、Model Mock、统一 CMake 清单。38 tests.
3. ✅ **应用级验证器** (`b5c49ae`)：实现路由图、生命周期、线程边界、资源去重、手工待办门禁。28 tests.
4. **三页 MVP 夹具与 CI**：编译生成代码，模拟点击与导航，执行 native 渲染和视觉回归。
5. **接入真实 UI 包**：按同一 Manifest 填入页面后，由我只负责审查 `app_evidence.json`、render 结果、CI 和回归差异。

假设：首版只覆盖已支持模板和标准 LVGL 控件；复杂动画、平台模糊、网络协议、存储策略和自定义组件保留为明确的人工集成项。
