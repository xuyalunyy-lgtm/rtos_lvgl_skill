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

## 症状 → ID（Crash 用）
| 症状 | ID |
|------|-----|
| 跨线程 LVGL | C1.1 |
| 野指针/Queue | C2.1–C2.3 |
| cJSON 泄漏 | C3.1 |
| ISR 卡死 | C4.1–C4.3 |
| STACK OVERFLOW WSS | C7.5, C4.5 |
| WDT | C8.3–C8.6, C1.5 |
| heap 下降 | C3.*, C7.2 |
| 明文密钥入库 | C9.1, C9.2 |

Prompt 深细节按需 1–3 个 → [skill_structure.md](skill_structure.md) 场景表。
