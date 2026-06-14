# Skill 迭代日志（自我迭代记录）

Agent 或维护者在 [self_iterate.md](../workflows/self_iterate.md) 闭环结束时追加条目。**最新在上。**

## 条目模板

```markdown
### YYYY-MM-DD — 简短标题

- **来源：** 用户反馈 / SDK 升级 / CI / 量产 / 架构 review
- **平台：** esp32 | stm32 | jl | bk | 通用
- **变更：** `path/to/file` — 一句话
- **验证：** self-test ✅ / sync_lite ✅
- **版本：** x.y.z
```

---

### 2026-06-16 — v2.19.0 Skill 通用化（平台/产品分层）

- **来源：** 用户要求 skill 通用化（除芯片特性外全部审查）
- **平台：** 通用 + JL/ESP32/BK 平台节补 C10
- **变更：** C10/voice prompt/example 抽象化；secrets/crash/l2_project/SKILL/git_commit 去产品绑定
- **验证：** skill_iterate --check --sync ✅
- **版本：** 2.19.0

### 2026-06-16 — v2.18.0 C10 语音 ASR / uplink 共享引擎

- **来源：** 日志诊断（唤醒叮后 ASR 空、第二轮 mic peak 塌陷）+ prompt_tone / VSM 修复闭环
- **平台：** 通用（BK AVDK 多 port 为参考实现）
- **变更：** C10.1–C10.6；`voice_asr_uplink.txt`；`good_voice_prompt_uplink.c`；`bk.md` prompt 节；debug/l2 路由
- **验证：** self-test ✅ / sync_lite ✅ / skill_iterate --check ✅
- **版本：** 2.18.0

### 2026-06-16 — v2.17.0 bk_printer vc_start 竞态与 crash 日志反哺

- **来源：** 日志诊断 + vc_start / voicechat 生命周期修复（bk_printer BK7258）
- **平台：** bk
- **变更：** `platforms/bk.md` WSS 竞态/littlefs emoji/SARADC；`crash_log_decode.txt` BK HardFault；`debug_crash.md` 症状路由
- **验证：** self-test / sync_lite（待 CI）
- **版本：** 2.17.0

### 2026-06-16 — v2.16.0 bk_printer 审查反哺 C6.5 产品层裁剪

- **来源：** 架构 review + 裁剪落地（bk_printer BK7258 AI 打印机）
- **平台：** bk
- **变更：** C6.5；`l2_project_review.md` Step 4b；`platforms/bk.md` 打印机实测；`secrets_kconfig` 单工程布局；`sdk_trim_prune` 产品层章节
- **验证：** self-test / sync_lite（待 CI）
- **版本：** 2.16.0

### 2026-06-16 — v2.15.1 Git 提交说明规范

- **来源：** 用户反馈（多仓 commit message 风格统一）
- **平台：** 通用
- **变更：** `references/git_commit_style.md`、`templates/git-commit-message.md`；联动 core_rules / SKILL / cursor-rule
- **验证：** sync_lite ✅
- **版本：** 2.15.1

### 2026-06-16 — v2.15.0 C9 密钥审查 + 工程审查 workflow

- **来源：** 用户工程审查闭环（AIAlarmClock）
- **平台：** bk / 通用
- **变更：** `secret_scan_checker.py`；`l2_project_review.md`；C9 约束；`run_review --scan-secrets`
- **验证：** self-test ✅ / secret fixtures ✅
- **版本：** 2.15.0

### 2026-06-16 — v2.14.0 AIAlarmClock review 反哺 BK 平台与 checker

- **来源：** 架构 review（AIAlarmClock BK7258 带屏 AI 闹钟）
- **平台：** bk
- **变更：** `platforms/bk.md` AI 产品实测模式；`cjson_leak_checker.py` `!json` 早 return；`lvgl_thread_checker.py` lvgl_ui/lcd 白名单
- **验证：** self-test ✅ / validate-examples ✅ / run_review AIAlarmClock ✅
- **版本：** 2.14.0

### 2026-06-15 — v2.13.0 description 优化 + Cursor Rule 模板

- **来源：** 用户反馈（DeepSeek v4 Pro 命中率低）
- **平台：** 通用 / Cursor
- **变更：** description 中英触发词、`cursor-rule.embedded.mdc`、INSTALL 命中率说明
- **验证：** skill_iterate.cmd -Sync ✅
- **版本：** 2.13.0

### 2026-06-15 — v2.12.0 Claude Code 省 token 适配

- **来源：** 用户反馈（Claude Code 适配、保能力省 token）
- **平台：** 通用
- **变更：** `constraint_index.md`、`claude_code.md`、`templates/`、`install_claude_code.*`、workflow/L2 懒加载
- **验证：** skill_iterate.cmd -Sync ✅
- **版本：** 2.12.0

### 2026-06-15 — v2.11.0 自主实施模式

- **来源：** 用户反馈（AI 应自主改代码至编译通过，无需逐步确认）
- **平台：** 通用
- **变更：** `core_rules.md` 自主实施模式、`SKILL.md` rules、`l3_new_module.md`、`debug_crash.md`、`skill_lite_body.md`
- **验证：** self-test ✅ / validate-examples ✅ / skill_iterate.cmd -Sync ✅
- **版本：** 2.11.0

### 2026-06-15 — v2.10.0 启动顺序 / WDT / DMA Cache

- **来源：** 架构 review（嵌入式量产常见 init/WDT/DMA cache 踩坑）
- **平台：** 通用
- **变更：** C8.1–C8.6、`boot_wdt_lifecycle.txt`、C4.8、`good_boot_sequence.c`、workflows/examples
- **验证：** self-test ✅ / validate-examples ✅ / skill_iterate.cmd -Sync ✅
- **版本：** 2.10.0

### 2026-06-15 — v2.9.0 通用内存分配约束 C7

- **来源：** 用户反馈（内存优化途径需沉淀为 Skill 约束）
- **平台：** 通用
- **变更：** `prompts/memory_alloc_optimize.txt`、`constraint_detail.md` C7.1–C7.9、`core_rules.md`、`SKILL.md` 2.9.0、workflows、Lite checklist
- **验证：** self-test ✅ / validate-examples ✅ / skill_iterate.cmd -Sync ✅
- **版本：** 2.9.0

### 2026-06-15 — v2.8.0 Skill 四层结构与控制平面瘦身

- **来源：** 用户反馈（主要结构方面）
- **平台：** 通用
- **变更：** `references/skill_structure.md`、`workflows/README.md`、`SKILL.md`、`skill_lite_body.md`、`README.md`、`self_iterate.md`、`.gitignore`
- **验证：** self-test ✅ / validate-examples ✅ / skill_iterate.cmd -Sync ✅
- **版本：** 2.8.0

### 2026-06-15 — v2.7.0 细粒度约束矩阵 C#.#

- **来源：** 用户反馈（约束需更细节）
- **平台：** 通用
- **变更：** `references/constraint_detail.md`、`core_rules.md`、`SKILL.md`、`l2_code_review.md`、`debug_crash.md`、`run_review.py --validate-examples`、`examples/README.md`、`lite_manual_checklist.md`
- **验证：** self-test ✅ / validate-examples ✅ / skill_iterate.ps1 -Sync ✅
- **版本：** 2.7.0

### 2026-06-15 — v2.6.0 安装硬化与症状子路由

- **来源：** 用户反馈（安装带入本地 SDK 目录）+ 架构 review
- **平台：** 通用 / bk
- **变更：** `install_skill.ps1/sh`、`debug_crash.md`、`l3_new_module.md`、`platforms/bk.md`、`INSTALL.md`
- **验证：** skill_iterate --check（CI）
- **版本：** 2.6.0

### 2026-06-15 — v2.5.0 铁律 #2 与验证闭环可执行化

- **来源：** 架构 review / 用户反馈
- **平台：** 通用
- **变更：** `queue_ownership_checker.py`、`--validate-examples`、CI 扩展、`bad_queue_stack_pointer.c`、`good_wss_reconnect.c`
- **验证：** self-test ✅ / validate-examples ✅ / skill_iterate ✅
- **版本：** 2.5.0

### 2026-06-15 — v2.4.0 自我迭代机制

- **来源：** 架构 review
- **平台：** 通用
- **变更：** 新增 `workflows/self_iterate.md`、`scripts/skill_iterate.py`、`CHANGELOG.md`、本日志
- **验证：** self-test + skill_iterate + sync_lite
- **版本：** 2.4.0
