# Workflow: Bug 诊断 / Crash 日志

**触发：** HardFault、Guru Meditation、死机 dump、栈溢出、WDT、界面 frozen、WSS 握手 fail。

<thinking>
1. 先日志后改代码
2. 提取 PC/LR/Backtrace → addr2line
3. 对照反例与 scene prompt
</thinking>

## Step 1 — 日志解读

读取 [crash_log_decode.txt](../prompts/crash_log_decode.txt) + 对应 `platforms/xxx.md` Crash/addr2line 节。

## Step 2 — 症状路由

| 症状 | 下一步 |
|------|--------|
| STACK OVERFLOW / WssTask | [mbedtls_wss_memory.txt](../prompts/mbedtls_wss_memory.txt) + stack_calculator |
| LoadProhibited + network/UI | 完整版 `examples/bad_lvgl_cross_thread.c` |
| 界面 frozen | [deadlock_lock_order.txt](../prompts/deadlock_lock_order.txt) |
| I2S 卡顿 | 完整版 `examples/bad_isr_blocking.c` |
| cJSON / heap 降 | cjson_leak_checker |
| TLS 握手 fail | SNTP、证书、cipher → mbedtls_wss_memory |

## Step 3 — 验证（完整版）

对相关源文件：

```bash
python tools/run_review.py --dir ./src --platform xxx
```

## Step 4 — 输出

```markdown
## 结论
## 日志提取（PC/LR/Backtrace）
## 定位（addr2line / 反例对照）
## 修复（MVP 合规）
## 验证
```
