# 约束 ID 速查（L2+ · 省 token 版）

完整矩阵（正例/反例/checker）→ [constraint_detail.md](constraint_detail.md)。违规报告仍引用 `C#.#`。

## C1 LVGL
| ID | P | 一句话 |
|----|---|--------|
| C1.1 | 0 | 非 View 禁止 `lv_obj_*` / `lv_label_*` |
| C1.2 | 0 | UI 仅 LVGL 任务或 `lv_async_call` |
| C1.3 | 0 | `lv_async_call` user_data 回调内 free |
| C1.4 | 1 | mutex 须超时，禁 `portMAX_DELAY` |
| C1.5 | 0 | 持 LVGL 锁禁阻塞 Queue/网络 |
| C1.6 | 1 | 双锁顺序：先网络后 LVGL |
| C1.7 | 2 | 高频 UI 须节流 |

## C2 Queue
| ID | P | 一句话 |
|----|---|--------|
| C2.1 | 0 | 禁 `cJSON*` 进 Queue |
| C2.2 | 0 | 禁栈指针进 Queue |
| C2.3 | 0 | heap payload：Model alloc → Presenter free |
| C2.4 | 0 | Queue 满时 Model 仍须 free payload |
| C2.5 | 1 | Send 成功后 Model 禁再碰 payload |
| C2.6 | 2 | 标注谁 alloc / 谁 free |
| C2.7 | 1 | Queue 深度与背压策略须文档化 |
| C2.8 | 0 | 禁 `lv_obj_t*` 进 Queue |

## C3 cJSON
| ID | P | 一句话 |
|----|---|--------|
| C3.1 | 0 | 每 Parse 同函数内 Delete |
| C3.2 | 0 | 多出口 `goto cleanup` |
| C3.3 | 0 | 进 Queue 前 Delete，只传 plain buffer |
| C3.4 | 1 | 循环内 Parse 每次 Delete |
| C3.5 | 1 | malloc 失败路径不泄漏 root |
| C3.6 | 2 | L2+ 跑 cjson_leak_checker |

## C4 ISR/DMA
| ID | P | 一句话 |
|----|---|--------|
| C4.1 | 0 | ISR 仅 `*FromISR` API |
| C4.2 | 0 | ISR 末尾 `portYIELD_FROM_ISR` |
| C4.3 | 0 | ISR 禁 delay/malloc/cJSON/printf |
| C4.4 | 1 | I2S Ping-Pong + 4 字节对齐 |
| C4.5 | 1 | 音频优先级高于 LVGL/WSS |
| C4.6 | 0 | 音频结果经 Queue，禁直改 UI |
| C4.7 | 0 | ISR 禁 mutex |
| C4.8 | 1 | Cache SoC：DMA 后 invalidate/clean |

## C5–C8
| ID | P | 一句话 |
|----|---|--------|
| C5.1 | 1 | 每大模块 `APP_TEST_MODE_*` |
| C6.1 | 0 | 先问卷再 SDK 裁剪 |
| C6.5 | 1 | main/CMakeLists 与 Kconfig/init 链一致，未 init 不得编入 |
| C7.1 | 0 | 缩池/栈前须有基线 |
| C7.5 | 0 | WSS 栈 ≥4096 bytes |
| C7.9 | 1 | 重连指数退避 |
| C8.1 | 0 | Queue/Presenter 先于网络回调 |
| C8.3 | 1 | Presenter 禁 `portMAX_DELAY` 等 Queue |
| C8.6 | 0 | init 禁同步 TLS/大 Parse |

## C9 密钥/凭证
| ID | P | 一句话 |
|----|---|--------|
| C9.1 | 0 | 入库 config 禁非空 SECRET/TOKEN/PASSWORD |
| C9.2 | 0 | Git remote 禁内嵌凭证 |
| C9.3 | 1 | 日志禁打印密码/token |
| C9.4 | 1 | secrets 文件须 gitignore |
| C9.5 | 2 | 构建支持 config.secrets 覆盖 |
| C9.6 | 2 | L2 工程审查须跑 secret_scan |

## C10 语音/ASR/Uplink
| ID | P | 一句话 |
|----|---|--------|
| C10.1 | 0 | prompt/TTS 结束须 detach 播放路径 |
| C10.2 | 0 | 开 uplink 前 AEC settle + mic ready |
| C10.3 | 1 | 先 peak/uplink 区分无 PCM vs ASR 空 |
| C10.4 | 1 | prompt 完成后再 start uplink |
| C10.5 | 1 | session generation 防 stale 回调 |
| C10.6 | 2 | playback slot/handle 勿 hardcode |

## C11 编码规范
| ID | P | 一句话 |
|----|---|--------|
| C11.1 | 2 | 文件名 `模块_功能.c/h`，禁止中文/空格 |
| C11.2 | 2 | 函数名 `模块_动作_对象()`，≤30 字符 |
| C11.3 | 2 | 宏全大写 `MODULE_FEATURE_VALUE` |
| C11.4 | 2 | 结构体名 `模块_xxx_t` |
| C11.5 | 1 | 单函数 ≤80 行，超限须拆分 |
| C11.6 | 2 | 每个 .c/.h 须有模块说明文件头注释 |

## C12 错误处理
| ID | P | 一句话 |
|----|---|--------|
| C12.1 | 0 | FreeRTOS API 返回值必须检查 |
| C12.2 | 0 | malloc 失败须有 fallback，禁止 NULL 解引用 |
| C12.3 | 1 | 统一错误码枚举，禁 magic number 返回 |
| C12.4 | 0 | 多资源函数用 goto cleanup 统一释放 |
| C12.5 | 1 | configASSERT 仅用于不可恢复错误 |

## C13 状态机
| ID | P | 一句话 |
|----|---|--------|
| C13.1 | 1 | 长生命周期任务须有显式 enum state |
| C13.2 | 2 | >5 状态须有转换表注释 |
| C13.3 | 1 | switch-default 处理非法状态（log + reset） |
| C13.4 | 2 | 需断电恢复的状态持久化到 NVS/Flash |

## C14 日志规范
| ID | P | 一句话 |
|----|---|--------|
| C14.1 | 1 | 分级日志 + TAG，禁止裸 printf |
| C14.2 | 2 | 日志级别可 Kconfig 配置 |
| C14.3 | 0 | ISR/DMA/LVGL timer 内禁止日志 |
| C14.4 | 1 | 日志禁止打印密码/token 明文 |
| C14.5 | 1 | HardFault handler 须采集 PC/LR/寄存器 |

## C15 任务优先级与通信
| ID | P | 一句话 |
|----|---|--------|
| C15.1 | 1 | 相邻任务优先级差 ≥2 |
| C15.2 | 1 | 共享资源用 mutex（优先级继承），禁 binary semaphore |
| C15.3 | 2 | 禁止运行时 vTaskPrioritySet（需文档说明） |

## C16 定时器管理
| ID | P | 一句话 |
|----|---|--------|
| C16.1 | 0 | 软件定时器回调禁止阻塞（daemon 共享） |
| C16.2 | 1 | 动态创建 timer 须有 stop + delete 路径 |
| C16.3 | 2 | 周期 pdTRUE / 单次 pdFALSE 须区分 |

## C17 多核 IPC
| ID | P | 一句话 |
|----|---|--------|
| C17.1 | 0 | 跨核通信禁止直接共享全局变量（须 IPC/mailbox） |
| C17.2 | 0 | 不同 FreeRTOS 实例间禁 xQueueSend（须平台 IPC API） |
| C17.3 | 1 | 核间同步用硬件信号量，禁跨核 mutex |

## 症状 → ID（Crash 用）

完整症状→约束 ID 表 → [constraint_detail.md](constraint_detail.md) 末尾。

Prompt 深细节按需 1–3 个 → [skill_structure.md](skill_structure.md) 场景表。
