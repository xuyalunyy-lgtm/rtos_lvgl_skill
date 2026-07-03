# C08 启动顺序微分片

> ~800 tokens。完整规则见 `constraint_rtos.md`。

## 典型症状

- 启动后 WDT 复位
- 外设初始化在任务创建之后
- NVS/WiFi 未初始化就使用

## 正确启动顺序

```
1. 外设初始化（GPIO/SPI/I2C）
2. 存储初始化（NVS/Flash）
3. 网络初始化（WiFi/TLS）
4. 队列/信号量创建
5. 任务创建
6. 看门狗注册
```

## 危险模式

```c
// ❌ 任务创建在外设初始化之前
void app_main() {
    xTaskCreate(task_fn, ...);  // 任务可能在外设就绪前运行
    gpio_config(&cfg);          // 太晚！
}
```

## 相关 Checker

- `boot_sequence_checker.py` — 自动检测

## 升级到完整 Shard

需要 WDT 配置、多核启动、Zephyr 初始化顺序细节时 → 加载 `constraint_rtos.md`
