# C09 密钥/凭证微分片

> ~800 tokens。完整规则见 `constraint_ota.md`。

## 典型症状

- config.secrets 提交到 git
- WiFi 密码硬编码
- API key 明文打印

## 危险模式

```c
// ❌ 硬编码密钥
#define WIFI_PASSWORD "my_secret_password"
#define API_KEY "sk-1234567890"

// ❌ 日志打印密钥
ESP_LOGI(TAG, "Password: %s", password);
```

## 修复规则

1. 密钥放 Kconfig，不放源码
2. .gitignore 排除 config.secrets
3. 日志脱敏：密码/token/key 用 *** 替代
4. git remote 扫描嵌入凭证

## 相关 Checker

- `secret_scan_checker.py` — 自动检测
- `log_desensitize_checker.py` — 日志脱敏

## 升级到完整 Shard

需要 secure boot 密钥管理、Flash 加密、OTA 签名密钥细节时 → 加载 `constraint_ota.md`
