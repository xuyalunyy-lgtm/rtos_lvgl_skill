# Zephyr Quick Reference

> Lightweight Zephyr platform quick reference. Full version see `zephyr.md`.

## Key Differences

- **静态定义**：所有原语用宏定义（`K_THREAD_DEFINE`, `K_MSGQ_DEFINE`, `K_SEM_DEFINE`）
- **Device Tree**：硬件描述在 `.dts`/`.overlay`，用 `DEVICE_DT_GET()` 获取设备
- **Kconfig**：配置在 `prj.conf`，用 `CONFIG_XXX` 条件编译
- **Workqueue**：类似 FreeRTOS timer task，用 `K_WORK_DEFINE` + `k_work_submit`
- **MCUboot**：OTA 用 `boot_request_upgrade()` + `boot_set_confirmed()`

## 常用 API 对照

| 操作 | Zephyr API |
|---|---|
| 任务创建 | `k_thread_create(&thread, stack, sz, entry, p1, p2, p3, prio, opts, delay)` |
| 队列 | `K_MSGQ_DEFINE(q, sz, len, align)` / `k_msgq_put()` / `k_msgq_get()` |
| 信号量 | `K_SEM_DEFINE(sem, init, limit)` / `k_sem_take()` / `k_sem_give()` |
| 互斥锁 | `K_MUTEX_DEFINE(m)` / `k_mutex_lock()` / `k_mutex_unlock()` |
| 延时 | `k_msleep(ms)` |
| 堆分配 | `k_malloc(sz)` / `k_free(p)` |
| 日志 | `LOG_INF("fmt", ...)` / `LOG_WRN(...)` / `LOG_ERR(...)` |
| WiFi | `net_mgmt(NET_REQUEST_WIFI_CONNECT, ...)` |
| OTA | `boot_request_upgrade(buf, size)` / `boot_set_confirmed()` |

## 高频踩坑

1. **动态创建原语** → Zephyr 推荐静态定义，动态创建需特殊 API
2. **ISR 中调用阻塞 API** → 用 `k_sem_give()`（ISR-safe），不用 `k_msleep()`
3. **Workqueue 任务饥饿** → workqueue 共享线程，长任务会阻塞其他 work
4. **MCUboot 未 confirmed** → 重启后自动回滚
5. **Device Tree 配置错误** → 用 `DEVICE_DT_GET()` 检查设备是否就绪

## Crash 定位

```bash
# addr2line
arm-zephyr-eabi-addr2line -pfiaC -e build/zephyr/zephyr.elf 0x080xxxxx
```
