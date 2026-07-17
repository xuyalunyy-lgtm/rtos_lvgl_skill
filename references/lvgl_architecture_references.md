# LVGL 开源项目架构参考

本页归纳开源项目的架构思路，供页面规划和工程评审时参考。它不是代码模板：应保留目标工程既有的任务模型、驱动接口、LVGL 版本和许可证要求。

检索日期：2026-07-17。

## 重点：大型项目的页面规划与跳转框架

页面规划的目标不是列出一组截图，而是预先定义：谁拥有当前页、哪些入口可中断当前流程、返回应回到哪里，以及页面销毁时哪些状态必须保留。以下两种框架应优先参考。

### InfiniTime：单一路由器 + 返回页栈 + 转场方向栈

参考：[DisplayApp 源码](https://github.com/InfiniTimeOrg/InfiniTime/blob/main/src/displayapp/DisplayApp.cpp) 与 [InfiniTime 仓库](https://github.com/InfiniTimeOrg/InfiniTime)。

InfiniTime 将显示系统收敛到 `DisplayApp`：它创建独立显示任务和消息队列，持有唯一 `currentScreen`，并用 `returnAppStack` 保存返回页、用 `appStackDirections` 保存进入方向。页面不能直接接管系统跳转；触摸、按键、通知、定时器和蓝牙事件先成为消息，再由这个路由器决定跳转、反向动画与回退。

实际的顶层页面树可概括为：

```text
Clock（根页）
├── Launcher / 应用列表 ──→ 用户应用、设置及其子页
├── Notifications / 通知中心
├── QuickSettings / 快捷设置
└── 系统中断入口
    ├── NotificationsPreview
    ├── Timer / Alarm
    ├── FirmwareUpdate
    └── PassKey
```

其跳转规则有几个关键点：

- 从根页的手势进入启动器、通知或快捷设置；页面可优先消费自己的触摸事件，未消费才交给全局手势。
- 普通前进使用 `LoadNewScreen`：仅在目标不是当前页时，将当前页和进入方向压栈，再替换当前页面对象。
- 返回时同时弹出页面与方向，并将动画反向；长按等全局动作直接回到 Clock 并清空两个栈。
- 通知、计时器、闹钟、配对与升级等异步事件属于“中断路由”：按优先级跳到专用页，而非伪装成用户主动导航。
- 页面对象替换前会释放旧 `currentScreen`，因此页面私有定时器、订阅和 LVGL 对象必须跟随页面生命周期清理。

适合：手表、仪表和设备控制台这类有明确根页、硬件手势、异步告警与多级设置的产品。

### Meshtastic device-ui：应用壳 + 视图工厂 + 领域分区

参考：[Meshtastic device-ui](https://github.com/meshtastic/device-ui)。

Meshtastic 的 device-ui 是跨 ESP32、nRF52、RP2040、Linux 等环境的实际 UI 库。其公开架构计划明确采用 View hierarchy / View factory / Controller / Model，并用包式线程安全接口连接控制器与模型。相比“每页直接读串口或全局状态”，它更适合消息、地图、节点、配置等复杂信息并存的设备。

从项目已实现的页面能力可提炼出如下页面树：

```text
Boot
└── Home（全局状态栏：电池、连接、时间等）
    ├── Nodes ──→ Node details ──→ Position / Telemetry
    ├── Channels ──→ Chat ──→ Virtual keyboard
    ├── Map（瓦片加载、平移、缩放、节点位置）
    └── Settings
        ├── 基础设置：亮度、语言、校准、超时、地图等
        └── 高级设置：General / Radio / Module
```

应借鉴的不是某个具体控件，而是四个规划约束：

- **应用壳常驻，业务视图替换**：状态栏、显示休眠和输入控制属于壳层；节点、聊天、地图和设置作为可替换内容区。
- **按领域分区，而非按控件分文件**：`Nodes`、`Chat`、`Map`、`Settings` 各自管理子路由和业务状态，根路由只负责模块间跳转。
- **由视图工厂集中创建**：路由解析后由工厂决定页面类型和依赖，避免在任意回调中散落 `lv_obj_create` 或跨页全局指针。
- **数据经 Controller/Model 边界进入**：通信包、地图数据和持久化配置先更新模型，再在 UI 线程刷新对应视图；页面不直接处理底层协议。

适合：节点列表、聊天记录、地图、表单设置等信息密度高、跨平台且需要扩展模块的产品。

### 可直接复用的页面规划表

为每个路由先填写下表，再开始实现。它结合了 InfiniTime 的显式返回栈与 Meshtastic 的模块边界。

| 路由 | 父路由 / 返回目标 | 创建方式 | 允许入口 | 退出与资源策略 | 异步中断策略 |
| --- | --- | --- | --- | --- | --- |
| `home` | 根页 | 常驻壳 | 启动、全局返回 | 保留状态栏；替换内容区 | 可接收高优先级告警 |
| `nodes` | `home` | 视图工厂 | Home 快捷入口 | 离开时停止列表刷新 | 新节点仅更新角标，不抢页 |
| `node_detail` | `nodes` | 按节点 ID 创建 | 列表选择 | 释放详情订阅与图表缓存 | 节点删除则返回 `nodes` |
| `settings/*` | `settings` | 懒创建子页 | 设置列表 | 提交或撤销草稿状态 | OTA/配对可升级为专用页 |
| `alarm` | 中断路由 | 独占页面 | 定时器/系统事件 | 消警后按策略回原页或 Home | 抢占当前路由并记录恢复点 |

推荐把该表中的内容映射到 `lvgl_page_plan.json`：页面 `state` 记录输入和草稿状态，`navigation` 记录目标与 guard，资源策略记录创建/隐藏/销毁的责任。对“返回原页”以外的场景，增加明确的 `resume_target` 或 `fallback_target`，不要依赖页面地址或隐式全局变量。

页面规划模板 1.1 已将这些责任固化为可校验字段：

- 顶层 `navigation` 声明路由器 owner、根页、显式返回栈与中断恢复策略。
- 每页的 `parent`、`lifecycle.create_policy`、`lifecycle.exit_policy` 和 `fallback_target` 明确页面树与资源释放。
- 每个跳转的 `kind`、`stack_action` 和 `direction` 区分前进、返回、恢复、中断和回根；中断页还需要优先级与恢复目标。
- 校验器会检查 UI owner 一致性、未知目标、不可达页面、无退出路由、错误的 back 父级、复入压栈和非法中断恢复。

已有 1.0 规划文件仍可校验；新建多页工程应使用 1.1 模板。

使用 `python tools/lvgl_navigation_report.py lvgl_page_plan.json --output lvgl_navigation_review.md` 可生成 Markdown 审计报告。报告将页面树、页面生命周期、所有跳转边和中断路径集中到一页，并附上校验诊断，适合作为评审或提交附件。

### 路由器应承担的职责

无论使用 C 还是 C++，集中路由器至少应负责：

1. 校验目标路由和 guard，决定是压栈、替换、回根还是拒绝跳转。
2. 保存进入方向，使返回动画与进入动画相反。
3. 为告警、来电、升级、配对等系统事件设定中断优先级和恢复策略。
4. 在销毁旧页前撤销订阅、定时器和页面私有资源；在创建新页后绑定其 Presenter/Model。
5. 仅在 UI owner 中执行 LVGL 创建、删除和屏幕切换；其它任务只投递“导航意图”或状态事件。

不要让每个页面自行维护返回栈，也不要让后台任务直接 `lv_scr_load`。这两种做法在页面较少时看似快捷，但会在异步告警、长按回根、深层设置和页面析构时产生不可预测的返回路径。

## 1. LVGL：库、移植与产品 UI 分离

参考：[lvgl/lvgl](https://github.com/lvgl/lvgl) 与 [官方集成文档](https://lvgl.io/docs/open/integration/overview)。

LVGL 仓库将核心 `src`、可选 `examples`/`demos`、测试和不同环境支持放在清晰边界内；集成配置则通过 `lv_conf.h`、Kconfig 或编译定义注入。这提示产品工程应把 LVGL 当作依赖与运行时，而不是把页面、面板驱动和业务状态混在 LVGL 目录中。

```text
业务状态 / Presenter
        ↓
页面、组件与导航
        ↓
LVGL 适配层（tick、display、input）
        ↓
面板、触摸、DMA 与板级 HAL
```

建议的目录责任：

- `app/ui/pages`：页面和可复用组件；只表达 UI 行为。
- `app/ui/navigation`：路由、页面切换和返回策略。
- `platform/ui_port`：`lv_tick`、显示 flush、输入设备注册等 LVGL 适配。
- `platform/display`：面板、总线、DMA、缓存维护和 TE 同步。

适合：所有 LVGL 产品工程，尤其是需要更换面板、触摸或 LVGL 版本的项目。

注意：LVGL 仓库本身是库工程，不提供完整产品的页面路由模型；不要把其源码目录直接当作应用目录规范。

## 2. InfiniTime：设备抽象、系统任务与显示应用分层

参考：[InfiniTime 仓库](https://github.com/InfiniTimeOrg/InfiniTime) 与其 [开发者架构说明](https://docs.infinitime.io/en/latest/developer-documentation/index.html)。

InfiniTime 将硬件相关低层、面向电池/文件系统/运动等能力的控制器、FreeRTOS 系统层，以及基于 LVGL 的可见应用层分开；系统层通过任务和消息队列串联。这是多页面设备 UI 最值得借鉴的边界：UI 不是直接拥有硬件，后台任务也不直接拥有 LVGL 对象。

```text
驱动与 SDK → 能力控制器 → 后台任务 / 消息 → UI owner 任务 → 页面
```

可迁移做法：

- 为电量、连接、传感器、存储等建立稳定的能力接口，页面只订阅状态或调用高层命令。
- 让一个 UI owner 统一执行 LVGL 调用；后台任务仅投递事件或更新 Presenter 状态。
- 页面进入时注册需要的更新源，退出时撤销订阅、停止定时器并释放页面私有资源。
- 将高频数据做节流和合并后再投递，避免每次采样都触发整页失效。

适合：FreeRTOS 或类似多任务系统中的仪表、手表、家电和控制面板。

注意：其具体 C++、nRF 和 LVGL 版本属于项目实现细节；应迁移职责划分，不应复制 API 或任务优先级。

## 3. EEZ Framework：生成式页面与原生业务边界

参考：[eez-framework](https://github.com/eez-open/eez-framework)、[模板与示例集合](https://github.com/eez-open/eez-framework-projects) 和 [EEZ Studio FAQ](https://github.com/eez-open/studio/wiki/FAQ)。

EEZ 的项目模板覆盖 SDL、STM32、ESP32 等运行环境。其 Flow 模式将页面切换、控件属性和变量联动放进 UI 流程，生成的 UI 源通常位于 `src/ui`；设备侧的 C/C++ 通过原生变量和动作承担硬件与业务逻辑，并在 LVGL 初始化后执行 UI 初始化和周期性 UI 调度。

```text
设计器 / Flow → 生成的 UI 层 → 原生动作与变量接口 → 领域服务 / 驱动
```

可迁移做法：

- 即使不使用 EEZ，也将页面结构与业务命令隔离：页面发出意图，Presenter/动作层调用领域服务。
- 生成文件与手写扩展分目录；生成物、工具版本和配置都进入版本控制。
- 把设备 I/O、阻塞操作和错误恢复保留在原生业务层，避免隐藏在页面事件里。

适合：设计师参与度高、页面状态机较多，或希望用可视化工具维护 UI 流程的产品。

注意：引入生成器会增加构建与版本管理成本。若项目页面少且状态简单，手写页面加清晰导航通常更轻量。

## 4. ESP-BOX：BSP、HMI 框架与产品应用三层

参考：[Espressif ESP-BOX 技术架构](https://github.com/espressif/esp-box/blob/master/docs/technical_architecture.md)。

ESP-BOX 将系统层、解决方案框架层和应用层拆分。其 ESP-HMI 框架通过统一显示/触摸驱动接口适配不同屏幕，并将 UI 模板作为上层可组合资产。对于同一产品要支持多块屏、多种交互或多个 SKU 的情况，这种“板级能力不泄漏到页面”的分层比按单个页面堆叠驱动判断更稳健。

```text
ESP-IDF / RTOS / BSP
        ↓
显示、触摸、音频等 HMI 能力框架
        ↓
产品场景、页面与业务编排
```

可迁移做法：

- 用稳定的显示和输入能力接口隔离屏幕控制器、总线与触摸芯片差异。
- 将页面模板、主题和业务场景置于应用层；应用层不得依赖特定 GPIO、SPI 或面板时序。
- 产品变体通过板级配置、资源包或能力开关收敛，不在每个页面散布 `#if`。

适合：ESP32-S3 或其他需要多屏适配、语音/音频/联网能力并存的 HMI 产品。

注意：ESP-BOX 的组件和 ESP-IDF 依赖是特定生态实现；跨平台项目应保留三层边界，而不是引入其全部组件。

## 5. OV-Watch 与 esp32-c3-mini：仿真、硬件适配与资源上限

参考：[No-Chicken/OV-Watch](https://github.com/No-Chicken/OV-Watch) 与 [fbiego/esp32-c3-mini](https://github.com/fbiego/esp32-c3-mini)。

OV-Watch 将 Windows LVGL 仿真工程与设备工程并存，并以硬件数据访问中间层减少 UI 在仿真和实机间的差异；其页面切换使用明确的返回栈。esp32-c3-mini 则将板级 `hal`、应用 `src`、支持库、脚本与测试拆开，支持原生 SDL 构建，同时面对多种分辨率、可选表盘和受限 Flash/SRAM 的部署约束。

```text
页面 / 导航 ──→ 硬件数据访问接口 ──→ 实机 HAL
      │                    └──────→ 模拟数据源（本机 SDL）
      └──→ 页面返回栈、资源预算与构建目标矩阵
```

可迁移做法：

- 为页面提供可替换的数据访问接口，使同一 UI 能跑在本机模拟器与设备上。
- 将页面路由封装成显式导航栈，定义根页、回退与异常回退，避免回退逻辑散落在按键回调。
- 让原生仿真构建成为快速验证入口；仍需在设备上复测触摸、DMA flush、功耗和内存峰值。
- 对可安装主题、表盘和图片包设置 Flash/SRAM 分区与缓存上限，低内存目标按需裁剪资源。

适合：小团队需要缩短 UI 调试周期，或同一 UI 同时支持多块圆屏/方屏硬件的项目。

注意：模拟器不能证明真实帧率、DMA 同步或低功耗行为；这些工程的具体页面栈和资源格式仅适合作为设计参考。

## 6. 组合后的推荐落地模型

对多页嵌入式产品，可组合上述三种思路：以 LVGL 的移植边界隔离硬件，以 InfiniTime 的 UI owner 和事件边界隔离并发，以 EEZ 的“页面与业务动作分离”隔离复杂交互。

```text
领域任务 / 驱动
       │  事件、快照、命令结果
       ▼
Presenter / 状态聚合
       ▼
唯一 UI owner ──→ 页面、组件、导航 ──→ 资源缓存
       ▼
LVGL port ──→ flush / input ──→ 显示 HAL、DMA、面板
```

页面规划时，至少明确以下内容：

- 每个页面的状态来源、刷新频率和动态区域；高频状态应合并更新。
- 页面创建、隐藏、销毁时的订阅、定时器和资源缓存责任。
- 哪个任务是唯一 UI owner，以及后台事件进入 UI 的队列或 Presenter 边界。
- 页面导航的 guard、返回路径和异常状态，避免页面间隐式共享可变对象。
- flush、DMA 和 cache 维护属于显示适配层，页面不得等待或操作其底层细节。

将这些结论写入 [页面规划模板](../templates/lvgl_page_plan.json)，再按 [LVGL 页面工作流](../workflows/l3_lvgl_page.md) 校验和实现。

## 7. 模型选型速览

| 项目特征 | 优先借鉴 | 关键决策 |
| --- | --- | --- |
| 单屏、页面少 | LVGL 分层 | 保持页面、适配层和驱动层分离。 |
| 多任务、传感器或联网状态多 | InfiniTime | 单一 UI owner，后台以事件或状态快照进入 UI。 |
| 设计器主导、状态流复杂 | EEZ Framework | 固化生成物与手写业务边界。 |
| 多屏或多 SKU | ESP-BOX | 以 HMI 能力接口隔离 BSP 差异。 |
| 需要高频迭代与多板验证 | OV-Watch / esp32-c3-mini | 本机模拟器加实机性能与资源复测。 |
