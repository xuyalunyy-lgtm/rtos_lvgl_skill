# C22 OTA 安全微分片

> ~1000 tokens。完整规则见 `constraint_ota.md`。

## 典型症状

- OTA 升级后自动回滚
- 固件签名验证失败
- 分区表不一致

## 危险模式

```c
// ❌ OTA 后未标记有效
esp_ota_end(ota_handle);
esp_ota_set_boot_partition(partition);
// 缺少 esp_ota_mark_app_valid_cancel_rollback()！
// → 重启后自动回滚
```

## OTA 完整流程

```
1. esp_ota_begin()
2. esp_ota_write() × N
3. esp_ota_end()
4. esp_image_verify()  ← 签名验证
5. esp_ota_set_boot_partition()
6. 重启
7. esp_ota_mark_app_valid_cancel_rollback()  ← 首次启动必须调用
```

## 相关 Checker

- `ota_safety_checker.py` — 自动检测

## 升级到完整 Shard

需要 secure boot 配置、分区表细节、差分升级、断电恢复时 → 加载 `constraint_ota.md`
