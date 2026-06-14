# Lite 版 L2 人工审查清单（替代 tools/）

Code Review 或 L3 校验时逐条核对。违规项引用 `C#.#`（完整矩阵见完整版 `references/constraint_detail.md`）。完成后输出：**「Lite 人工审查已完成」**。

## C1 — LVGL 线程安全

- [ ] C1.1 非 View 文件无 `lv_obj_*` / `lv_label_*`
- [ ] C1.2 跨任务刷新用 `lv_async_call` 或 mutex
- [ ] C1.3 `lv_async_call` user_data 在回调内 free
- [ ] C1.5 无持 LVGL 锁等 Queue / 网络

## C2 — Queue 所有权

- [ ] C2.1 无 `cJSON*` 进 Queue
- [ ] C2.2 无栈指针进 Queue
- [ ] C2.3 Presenter 统一 `vPortFree(payload)`
- [ ] C2.4 Queue 满时 Model 释放 payload
- [ ] C2.7 Queue 深度与背压已说明

## C3 — cJSON

- [ ] C3.1 每个 `cJSON_Parse` 有唯一 `cleanup:` 且 `cJSON_Delete`
- [ ] C3.2 多出口用 `goto cleanup`
- [ ] C3.3 进 Queue 前已 Delete，只传 plain buffer

## C4 — ISR

- [ ] C4.1 HAL_*Callback 内无阻塞 API，仅用 `*FromISR`
- [ ] C4.2 有 `portYIELD_FROM_ISR`
- [ ] C4.7 ISR 无 mutex

## C5 — 测试宏

- [ ] C5.1 每大模块有 `APP_TEST_MODE_*` 宏

## C7 — 内存分配优化

- [ ] C7.1 缩池/缩栈前有基线或标注「未实测」
- [ ] C7.2 先修泄漏(C2/C3)再缩池，顺序正确
- [ ] C7.3 无大 buffer / JSON 树压栈
- [ ] C7.5 WSS 栈 ≥ 4096 bytes（TLS 建议 6144–8192）
- [ ] C7.6 缩 LwIP/TLS/LVGL 池后有 WiFi+WSS 冒烟说明
- [ ] C7.9 重连指数退避，无 tight loop 握手

## C8 — 启动 / WDT

- [ ] C8.1 Queue + Presenter 先于网络回调注册
- [ ] C8.2 WiFi IP → SNTP → TLS 顺序
- [ ] C8.3 Presenter 无 portMAX_DELAY 等 Queue
- [ ] C8.5 重连幂等，无重复 xTaskCreate 同模块

## 堆栈 / WSS / MVP

- [ ] 相对优先级表已输出（见 [core_rules.md](core_rules.md)）
- [ ] WSS 任务栈 ≥ 4096 bytes（含 TLS 取 6144–8192）
- [ ] Model 不碰 UI；View 不碰网络/音频寄存器
- [ ] SNTP 先于 TLS；重连指数退避
