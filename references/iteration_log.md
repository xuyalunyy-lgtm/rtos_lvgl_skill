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

### 2026-06-16 — v2.28.0 软硬联调 workflow + L3 安全围栏 + Token 优化

- **来源：** Skill 审查优化建议
- **平台：** 通用
- **变更：** `workflows/hw_sw_cocodebug.md`（IO 口收集→平台核对→board_io.h 生成→反复核对）；`core_rules.md` L3 安全围栏（编译重试上限/改动范围锁定/不可触碰清单/回滚点）；`constraint_index.md` 症状表精简为单行引用；SKILL.md 触发词+路由新增软硬联调
- **验证：** self-test 待 CI
- **版本：** 2.28.0

### 2026-06-16 — v2.23.0 新增 C17 多核 IPC + bk.md TOC

- **来源：** Skill 审查优化建议
- **平台：** 通用 + BK
- **变更：** `prompts/multi_core_ipc.txt`（C17.1–C17.3）；`platforms/bk.md` 加 15 节目录导航；SKILL.md / skill_structure.md / constraint_index.md / Lite 联动更新
- **验证：** self-test ✅ / check_links ✅
- **版本：** 2.23.0

### 2026-06-16 — v2.22.1 一致性修复（Lite checklist / README / 症状表）

- **来源：** Skill 回归审查
- **平台：** 通用
- **变更：** `lite_manual_checklist.md` 补齐 C9–C16；`README.md` 更新描述与范例；`constraint_detail.md` 症状表扩展 C12/C14/C16；`examples/README.md` 去"规划中"
- **验证：** self-test ✅ / check_links ✅
- **版本：** 2.22.1

### 2026-06-16 — v2.22.0 C11-C16 约束矩阵 + 新 checker + 反例

- **来源：** Skill 审查优化建议（P0+P1 补缺）
- **平台：** 通用
- **变更：** `constraint_detail.md` 补充 C11–C16 完整矩阵；`return_check_checker.py`（C12）；`logging_checker.py`（C14）；`bad_unchecked_return.c` + `bad_isr_printf.c` 反例；`l2_code_review.md` / `examples/README.md` / `skill_structure.md` 联动；`run_review.py` 串联新 checker
- **验证：** self-test ✅ / validate-examples ✅ / check_links ✅
- **版本：** 2.22.0

### 2026-06-16 — v2.21.0 新增 C11–C16 开发规范体系

- **来源：** Skill 审查优化建议（嵌入式 RTOS 全生命周期规范）
- **平台：** 通用
- **变更：** 新增 C11 编码规范 / C12 错误处理 / C13 状态机 / C14 日志规范 / C15 优先级与通信 / C16 定时器管理；6 个 prompt；constraint_index / core_rules / SKILL.md / skill_structure 全面联动
- **验证：** self-test ✅ / validate-examples ✅ / check_links ✅
- **版本：** 2.21.0

### 2026-06-16 — v2.20.0 C10 checker + 链接检查 + 覆盖扩展

- **来源：** Skill 审查优化建议
- **平台：** 通用
- **变更：** `voice_sequence_checker.py`；`check_links.py`；`bad_prompt_no_detach.c`；validate-examples 扩展至 C8/C10；Lite 补齐 C9/C10；症状表去重；description 精简
- **验证：** self-test ✅ / validate-examples ✅ / check_links ✅
- **版本：** 2.20.0

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

> v2.4.0 – v2.15.1 的历史条目已归档至 [iteration_log_archive_2026Q2.md](iteration_log_archive_2026Q2.md)。
