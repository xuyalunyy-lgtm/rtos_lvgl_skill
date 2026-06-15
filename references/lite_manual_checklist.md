# Lite 版 L2 人工审查清单（替代 tools/）

Code Review 或 L3 校验时逐条核对。完成后输出：**「Lite 人工审查已完成」**。

## 堆栈设计

- [ ] 相对优先级表已输出（见 [core_rules.md](core_rules.md)）
- [ ] WSS 任务栈 ≥ 4096 bytes（含 TLS 取 6144–8192）
- [ ] 计划用 `uxTaskGetStackHighWaterMark` 实测

## cJSON 防泄漏

- [ ] 每个 `cJSON_Parse` 有唯一 `cleanup:` 且 `cJSON_Delete`
- [ ] 循环内 Parse 每次迭代都 Delete
- [ ] Queue 只传 plain buffer，不传 `cJSON*`
- [ ] Queue 满时 Model 释放 payload

## LVGL 线程安全

- [ ] 非 View 文件无 `lv_obj_*` / `lv_label_*`
- [ ] 跨任务刷新用 `lv_async_call` 或 mutex

## ISR 安全

- [ ] HAL_*Callback / IRQHandler 内无 `vTaskDelay`、`portMAX_DELAY`
- [ ] 仅用 `*FromISR` + `portYIELD_FROM_ISR`

## MVP 分层

- [ ] Model 不碰 UI；View 不碰网络/音频寄存器
- [ ] Presenter 释放 Queue payload
- [ ] Queue 深度与背压已说明
- [ ] 每大模块有 `APP_TEST_MODE_*` 宏

## Queue / 死锁

- [ ] Queue 只传 heap plain buffer，不传 cJSON* / 栈指针（铁律 #2 → `queue_ownership_checker.py`）
- [ ] SNTP 先于 TLS；重连指数退避
- [ ] 无持 LVGL 锁等 Queue / 网络
