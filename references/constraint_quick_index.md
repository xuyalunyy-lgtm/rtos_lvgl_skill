# Constraint Quick Index

> Lightweight constraint index. Lists C1-C48 names, applicable scenarios, and corresponding detail shards.
> See corresponding shard files for complete rules.

## Constraint Shard Mapping

| 分片文件 | 包含约束 | 场景 |
|---|---|---|
| `constraint_review.md` | C1-C4, C11-C16 | 代码审查、ISR、队列、cJSON、编码规范 |
| `constraint_memory.md` | C7, C28, C36 | 内存分配、DMA、拷贝预算 |
| `constraint_rtos.md` | C8, C15, C17, C29-C35, C43-C44 | 启动、优先级、IPC、模块契约、拓扑、锁、临界区 |
| `constraint_platform.md` | C18-C21, C23, C42, C45, C46 | GPIO、NVS、网络、低功耗、显示、板级资源、传感器、蓝牙协议 |
| `constraint_media.md` | C25-C27 | A/V 管线、编解码、时钟漂移 |
| `constraint_ota.md` | C9, C22, C24 | 密钥、OTA 安全、外设关闭 |
| `constraint_recover.md` | C37-C41 | 背压、故障隔离、配置矩阵、复现、回归 |

## C1-C46 快速查找

| ID | 名称 | 场景 | 分片 |
|---|---|---|---|
| C1 | LVGL 线程安全 | UI 跨线程、flush 阻塞 | review |
| C2 | 队列 Payload 所有权 | 队列发送后访问、栈指针入队 | review |
| C3 | cJSON 生命周期 | Parse/Delete 配对、泄漏 | review |
| C4 | ISR/DMA 安全 | ISR 中阻塞、printf、malloc | review |
| C5 | 测试宏 | APP_TEST_MODE 边界 | review |
| C6 | SDK 裁剪 | 需求驱动裁剪 | review |
| C7 | 内存分配 | 堆/栈/池分层、PSRAM | memory |
| C8 | 启动顺序/WDT | 初始化顺序、看门狗 | rtos |
| C9 | 密钥/凭证 | config.secrets、git 凭证 | ota |
| C10 | 语音 ASR/Uplink | 共享引擎、AEC settle | media |
| C11 | 编码规范 | 函数长度、命名 | review |
| C12 | 错误处理 | 返回值检查、goto cleanup | review |
| C13 | 状态机 | switch-default、枚举 | review |
| C14 | 日志规范 | ISR 日志、脱敏、限频 | review |
| C15 | 优先级/通信 | 二进制信号量替代互斥锁 | rtos |
| C16 | 定时器管理 | Timer callback 阻塞 | review |
| C17 | 多核 IPC | 跨核数据竞争 | rtos |
| C18 | 外设驱动 | GPIO 方向、I2C 地址 | platform |
| C19 | Flash/NVS | commit 返回值、磨损均衡 | platform |
| C20 | 网络韧性 | 重连退避、超时 | platform |
| C21 | 低功耗 | 深睡眠状态保存 | platform |
| C22 | OTA 安全 | 签名验证、回滚 | ota |
| C23 | 显示驱动 | LCD 初始化、帧缓冲 | platform |
| C24 | 外设关闭 | 异常退出收尾、DMA 等待 | ota |
| C25 | A/V 管线 | 音视频同步、背压 | media |
| C26 | 编解码格式 | sample rate、channels | media |
| C27 | 时钟漂移 | PTS、jitter buffer | media |
| C28 | DMA/Cache | cache clean/invalidate | memory |
| C29 | 模块契约 | I/P/O 接口、错误码、高内聚低耦合、模块边界 | rtos |
| C30 | 任务拓扑 | 生产-消费链路 | rtos |
| C31 | 超时预算 | 有限等待、避免永久阻塞 | rtos |
| C32 | 可观测性 | 状态字段、遥测 | rtos |
| C33 | 生命周期 | init/deinit 对称 | rtos |
| C34 | 热路径禁令 | 热路径禁 malloc/printf/锁 | rtos |
| C35 | 关键路径预算 | 关键路径时间预算 | rtos |
| C36 | 拷贝预算 | 减少 memcpy | memory |
| C37 | 背压降级 | 队列满策略 | recover |
| C38 | 故障隔离 | 自动恢复、circuit breaker | recover |
| C39 | 配置矩阵 | ifdef 矩阵 | recover |
| C40 | 一键复现 | 最小复现命令 | recover |
| C41 | 回归样本 | good/bad fixture | recover |
| C42 | 板级资源 | GPIO/外设 owner | platform |
| C43 | 锁预算 | 有限等锁、持锁禁阻塞 | rtos |
| C44 | 临界区预算 | 短临界区、禁重活 | rtos |
| C45 | 传感器集成 | WHO_AM_I、data-ready | platform |
| C46 | 蓝牙协议核对 | BLE 状态机、GATT、配对安全与 MTU | platform |
| C47 | 工具层日志卫生 | MCP 输出、日志脱敏、凭据保护 | toolchain |
| C48 | AI 生成代码审查 | 幻觉 API、错误处理、注释卫生 | review |

## Checker Status Dashboard

`python tools/constraint_dashboard.py` emits the versioned, machine-readable
coverage table. Status is `automatic` (one or more registered checkers),
`manual` (process/document verification), or `missing` (no current control).
The registry is the source of truth; its schema/migration metadata prevents a
rule update from silently changing an existing checker contract.

## 加载规则

1. 先选 workflow
2. 再选平台
3. 根据 workflow 声明的约束分片加载对应 detail 文件
4. 不需要的分片不加载
