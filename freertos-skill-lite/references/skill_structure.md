# Skill 缁撴瀯鎬昏锛堢淮鎶?/ L2+ 鎸夐渶鍔犺浇锛?
Agent 缁存姢 skill 鎴栦笉纭畾銆岃璇诲摢涓枃浠躲€嶆椂璇诲彇鏈枃浠躲€?*L1 姒傚康闂瓟涓嶅繀鍔犺浇銆?*

## 鍥涘眰鍔犺浇妯″瀷

```
L0 鎺у埗骞抽潰   SKILL.md              鎰忓浘璺敱 路 閾佸緥绱㈠紩 路 rules锛堢姝㈣啫鑳€锛?L1 缂栨帓       workflows/*.md        閫夊畾 1 涓?workflow锛屾寜 Step 椤哄簭鎵ц
L2 鎬荤翰       references/           core_rules 路 constraint_index 路 鏈枃浠?L3 鍦烘櫙       prompts/*.txt         workflow 鎸囧畾 1鈥? 涓紝绂佹鍏ㄥ姞杞?     骞冲彴     platforms/*.md        workflow Step 1 鍔犺浇 1 涓?L4 鍙墽琛?    examples/ 路 tools/    瀹屾暣鐗?L2+锛汱ite 鏃犳灞?```

**閾佸緥锛?* 姣忓眰鍙悜涓嬪姞杞斤紝绂佹璺冲眰鎶?12 涓?prompt 濉炶繘 context銆?
---

## 鐩綍鑱岃矗

| 璺緞 | 鑱岃矗 | 璋佺淮鎶?| Lite |
|------|------|--------|------|
| `SKILL.md` | 鎺у埗骞抽潰锛?100 琛岋級 | 浜哄伐 | 鑷姩鐢熸垚 |
| `agents/openai.yaml` | Codex/OpenAI UI 鍏冩暟鎹?| 浜哄伐 | 鍚屾 |
| `workflows/` | 姝ラ缂栨帓銆佽緭鍑烘ā鏉?| 浜哄伐 | 鍚屾 + patch |
| `references/` | 鎬荤翰銆佺害鏉熺煩闃点€佺粨鏋勩€佹棩蹇?| 浜哄伐 | 鍚屾 |
| `references/constraint_index.md` | C#.# 閫熸煡锛圠2 榛樿锛岀渷 token锛?| 浜哄伐 | 鍚屾 |
| `references/git_commit_style.md` | 澶氫粨 Git 鎻愪氦璇存槑瑙勮寖 | 浜哄伐 | 鍚屾 |
| `references/claude_code.md` | Claude Code 鎳掑姞杞芥寚鍗?| 浜哄伐 | 鍚屾 |
| `prompts/` | 鍦烘櫙涓撻摼锛堟繁缁嗚妭锛?| 浜哄伐 | 鍚屾 |
| `platforms/` | 鑺墖/SDK 浜嬪疄 | 浜哄伐 | 鍚屾 |
| `examples/` | good/bad 鑼冧緥銆乣app_mvp.h` | 浜哄伐 + checker | **鏃?* |
| `tools/` | checker銆乧odegen銆乫ixtures銆乣checker_registry.py` | 浜哄伐 + CI | **鏃?* |
| `scripts/` | sync銆乮terate銆乮nstall | 浜哄伐 | 閮ㄥ垎澶嶅埗 |
| `freertos-skill-lite/` | Lite 鍒嗗彂鍖?| **sync 鐢熸垚** | 鈥?|

**鍒嗗彂杈圭晫锛?* 婧愮爜浠撲繚鐣欐牴鐩綍 `README.md`銆乣INSTALL.md`銆乣CHANGELOG.md`銆乣.github/`銆乣.vscode/`銆佸巻鍙叉棩蹇楀拰 Lite 浜х墿锛汣ursor/Claude/Codex 瀹夎鑴氭湰榛樿鎺掗櫎杩欎簺缁存姢璧勪骇锛屽彧瀹夎杩愯鏃堕渶瑕佺殑 skill 鏂囦欢锛屽苟淇濈暀 `workflows/README.md`銆乣examples/README.md` 绛夎繍琛屾椂绱㈠紩銆?
---

## Workflow 鈫?蹇呰 / 鎸夐渶鍔犺浇

| Workflow | L2 蹇呰 | L3 鎸夐渶锛?鈥?锛?| L4 瀹屾暣鐗?|
|----------|---------|----------------|-----------|
| L1 鏃?| 鈥?| 鈥?| 鈥?|
| [l2_code_review](../workflows/l2_code_review.md) | core_rules + **constraint_index** | 瀚岀枒鍦烘櫙 prompt | run_review + 鍗曟枃浠?example |
| [l2_architecture_review](../workflows/l2_architecture_review.md) | core_rules + constraint_index | 架构评审场景 prompt | run_review + 项目分层输出 |
| [debug_crash](../workflows/debug_crash.md) | constraint_detail 鐥囩姸琛?| 鐥囩姸瀵瑰簲 prompt | run_review + 鍙嶄緥 |
| [l3_sdk_trim](../workflows/l3_sdk_trim.md) | core_rules | sdk_trim_prune | 鈥?|
| [l3_new_module](../workflows/l3_new_module.md) | core_rules | 妯″潡琛?prompt | mvp_codegen / good_* |
| [hw_sw_cocodebug](../workflows/hw_sw_cocodebug.md) | core_rules锛圕8 鍒濆鍖栭『搴忥級 | 骞冲彴寮曡剼澶嶇敤 | 鈥?|
| [l3_bring_up](../workflows/l3_bring_up.md) | core_rules + hw_sw_cocodebug IO 琛?| boot_wdt_lifecycle + audio_dma_pingpong | run_review + good_boot_sequence |
| [l2_memory_analysis](../workflows/l2_memory_analysis.md) | core_rules + constraint_index | memory_alloc_optimize + cjson_safe_parse | run_review + stack_calculator |
| [l3_lvgl_page](../workflows/l3_lvgl_page.md) | core_rules锛圕1 绾跨▼瀹夊叏锛?| lvgl_thread_safety | 鈥?|
| [self_iterate](../workflows/self_iterate.md) | **鏈枃浠?* + iteration_log | 鍙楀奖鍝嶅眰 prompt | skill_iterate |

鐢ㄦ埛瑕佹眰 **git commit / 鎻愪氦** 鈫?璇?[git_commit_style.md](git_commit_style.md)锛堟棤闇€鍗曠嫭 workflow锛?
Workflow 绱㈠紩 鈫?[workflows/README.md](../workflows/README.md)

---

## 鍦烘櫙 Prompt 鐩綍锛圕 鍩?鈫?鏂囦欢锛?
| C 鍩?| 鍦烘櫙 | 鏂囦欢 |
|------|------|------|
| C1 | LVGL 绾跨▼ / v8v9 | [lvgl_thread_safety.txt](../prompts/lvgl_thread_safety.txt) 路 [lvgl_v8_v9_diff.txt](../prompts/lvgl_v8_v9_diff.txt) |
| C29 | 软件架构设计 | [software_architecture_design.txt](../prompts/software_architecture_design.txt) |
| C2 | Queue / 鎵€鏈夋潈 / 姝婚攣 | [memory_ownership.txt](../prompts/memory_ownership.txt) 路 [queue_event_bus.txt](../prompts/queue_event_bus.txt) 路 [deadlock_lock_order.txt](../prompts/deadlock_lock_order.txt) |
| C3 | cJSON | [cjson_safe_parse.txt](../prompts/cjson_safe_parse.txt) |
| C4 | 闊抽 DMA / ISR | [audio_dma_pingpong.txt](../prompts/audio_dma_pingpong.txt) |
| C5 | 娴嬭瘯瀹?| [test_mode_macro.txt](../prompts/test_mode_macro.txt) |
| C6 | SDK 瑁佸壀 | [sdk_trim_prune.txt](../prompts/sdk_trim_prune.txt) |
| C7 | 鍐呭瓨鍒嗛厤浼樺寲 | [memory_alloc_optimize.txt](../prompts/memory_alloc_optimize.txt) |
| C8 | 鍚姩 / WDT / 闃诲 | [boot_wdt_lifecycle.txt](../prompts/boot_wdt_lifecycle.txt) |
| C9 | 瀵嗛挜 / 鍑瘉 | [secrets_kconfig.txt](../prompts/secrets_kconfig.txt) |
| C10 | 璇煶 / ASR / Uplink | [voice_asr_uplink.txt](../prompts/voice_asr_uplink.txt) |
| C11 | 缂栫爜瑙勮寖 | [coding_style.txt](../prompts/coding_style.txt) |
| C12 | 閿欒澶勭悊 | [error_handling.txt](../prompts/error_handling.txt) |
| C13 | 鐘舵€佹満 | [state_machine_patterns.txt](../prompts/state_machine_patterns.txt) |
| C14 | 鏃ュ織瑙勮寖 | [logging_debug.txt](../prompts/logging_debug.txt) |
| C15 | 浼樺厛绾т笌閫氫俊 | [inter_task_communication.txt](../prompts/inter_task_communication.txt) |
| C16 | 瀹氭椂鍣ㄧ鐞?| [timer_management.txt](../prompts/timer_management.txt) |
| C17 | 澶氭牳 IPC | [multi_core_ipc.txt](../prompts/multi_core_ipc.txt) |
| 缃戠粶 | WSS / mbedTLS / 鏍?| [mbedtls_wss_memory.txt](../prompts/mbedtls_wss_memory.txt) |
| Crash | 鏃ュ織瑙ｈ | [crash_log_decode.txt](../prompts/crash_log_decode.txt) |
| 鍚屾 | FreeRTOS 鍘熻 | [freertos_sync_primitives.txt](../prompts/freertos_sync_primitives.txt) |
| C18 | 澶栬椹卞姩瀹夊叏 | [peripheral_driver_safety.txt](../prompts/peripheral_driver_safety.txt) |
| C19 | Flash/NVS 瀹夊叏 | [flash_nvs_safety.txt](../prompts/flash_nvs_safety.txt) |
| C20 | 缃戠粶闊ф€?| [network_resilience.txt](../prompts/network_resilience.txt) |
| C21 | 浣庡姛鑰楃鐞?| [low_power_management.txt](../prompts/low_power_management.txt) |
| C23 | 鏄剧ず椹卞姩 | [lcd_display_driver.txt](../prompts/lcd_display_driver.txt) |
| C24 | 澶栬鍏抽棴瀹夊叏 | [peripheral_shutdown_safety.txt](../prompts/peripheral_shutdown_safety.txt) |
| C25 | 闊宠棰戠绾?/ A/V Sync | [av_pipeline_sync.txt](../prompts/av_pipeline_sync.txt) |
| C26 | 缂栬В鐮?/ 濯掍綋鏍煎紡涓€鑷存€?| [av_codec_format.txt](../prompts/av_codec_format.txt) |
| C27 | 鏃堕挓婕傜Щ / Jitter Buffer | [av_clock_jitter.txt](../prompts/av_clock_jitter.txt) |
| C28 | DMA/cache/闆舵嫹璐?buffer 鐢熷懡鍛ㄦ湡 | [av_dma_buffer_lifecycle.txt](../prompts/av_dma_buffer_lifecycle.txt) |

绾︽潫 ID 缁嗗垯 鈫?[constraint_detail.md](constraint_detail.md) 路 L2 閫熸煡 鈫?[constraint_index.md](constraint_index.md) 路 **鐭ヨ瘑鍥捐氨** 鈫?[constraint_graph.md](constraint_graph.md)

> C1鈥揅28锛?7 涓害鏉熷煙锛?49 鏉¤鍒欍€?
---

## Claude Code锛堢渷 token锛?
瀹夎 鈫?[claude_code.md](claude_code.md) 路 椤圭洰妯℃澘 鈫?[templates/CLAUDE.embedded.md](../templates/CLAUDE.embedded.md)

| 鍘熷垯 | 璇存槑 |
|------|------|
| 鎳掑姞杞?| 浠?workflow 鎸囧畾鏂囦欢锛涚 Glob prompts/ |
| L2 榛樿 | `constraint_index.md` 鏇夸唬 detail 鍏ㄦ枃 |
| Lite 浼樺厛 | `lite_manual_checklist.md` + `constraint_index.md` 鎵嬪伐鏍稿 |
| 椤圭洰绱㈠紩 | 鍥轰欢浠?`CLAUDE.md` <500 token + `.claudeignore` |

## Cursor 鍛戒腑鐜囷紙DeepSeek 绛夛級

鍥轰欢浠?Rule 妯℃澘 鈫?[templates/cursor-rule.embedded.mdc](../templates/cursor-rule.embedded.mdc) 路 璇存槑 鈫?[INSTALL.md](../INSTALL.md)

| 鍘熷垯 | 璇存槑 |
|------|------|
| description | 涓枃 + `Use when` 瑙﹀彂璇嶏紙SKILL frontmatter锛?|
| 椤圭洰 Rule | `globs: **/*.{c,h}` 缂栬緫 C 鏃跺己鍒?Read skill |
| 鏄惧紡鐐瑰悕 | `@freertos-embedded-architect` |

## 浜у搧绾?Profile锛坄product_profiles/`锛?
| 骞冲彴 | 鏂囦欢 | 蹇呴€夌害鏉?| 鐗规€?|
|------|------|----------|------|
| ESP32 | `esp32.json` | C1-C4,C7-C9,C11-C12,C14-C15,C23,C25-C28 | WiFi+BLE+LVGL+I2S+Camera, 鍙屾牳, PSRAM |
| STM32 | `stm32.json` | C2-C4,C7-C9,C11-C12,C14-C15,C23 | LVGL+I2S+TLS, 鍗曟牳 Cortex-M |
| JL | `jl.json` | C1-C4,C6-C15,C23,C25-C28 | WiFi+BLE+LVGL+I2S+璇煶/瑙嗛, 鍙屾牳 RISC-V |
| BK | `bk.json` | C1-C4,C6-C15,C17,C23,C25-C28 | WiFi+BLE+LVGL+AVDK闊抽+璇煶/瑙嗛, 鍙屾牳 IPC |

Lite 鐢ㄦ硶锛氭寜涓婅〃浜哄伐璇嗗埆骞冲彴鑳藉姏锛涢渶瑕佽嚜鍔?profile 鏃跺洖鍒板畬鏁寸増婧愮爜浠撹繍琛屽伐鍏枫€?
Agent 鍦?L3 寮€濮嬪墠**鎺ㄨ崘**鍔犺浇浜у搧 profile锛氳嚜鍔ㄨ幏鍙栧繀閫夌害鏉熴€佹爤寤鸿銆佸父瑙佸潙鐐广€?
## 宸ュ叿鐩綍锛圠ite 路 浜哄伐鏇夸唬锛?
Lite 鍖呬笉鎼哄甫 `tools/`銆乣examples/`銆乣scripts/`銆傞渶瑕佽嚜鍔?checker銆佸畨瑁呮垨鍚屾鍛戒护鏃讹紝鍥炲埌瀹屾暣鐗堟簮鐮佷粨鎵ц锛汱ite 鍐呮寜涓嬭〃浜哄伐鏇夸唬銆?
| 鐢ㄩ€?| Lite 鍋氭硶 |
|------|-----------|
| L2 瀹℃煡 | [l2_code_review_lite.md](../workflows/l2_code_review_lite.md) + [lite_manual_checklist.md](lite_manual_checklist.md) |
| C1-C28 绾︽潫鏍稿 | [core_rules.md](core_rules.md) + [constraint_index.md](constraint_index.md) + 瀵瑰簲 prompt 鎵嬪伐妫€鏌?|
| 姝?鍙嶄緥鍙傝€?| 鍥炲埌瀹屾暣鐗?`examples/README.md` 涓庡搴?example 鏂囦欢 |
| Skill 缁存姢鍚屾 | 鍥炲埌瀹屾暣鐗堟簮鐮佷粨鎵ц鍚屾涓庢牎楠岃剼鏈?|

---

## 缁存姢锛氭敼鍝竴灞?
```
鏀归搧寰?绾︽潫 ID     鈫?core_rules.md + constraint_detail.md (+ 蹇呰鏃?prompt 涓€鍙?
鏀瑰満鏅繁缁嗚妭       鈫?prompts/xxx.txt锛堟鏌?workflow 寮曠敤锛?鏀规楠?杈撳嚭鏍煎紡    鈫?workflows/xxx.md锛堟鏌?SKILL 璺敱琛級
鏀瑰钩鍙颁簨瀹?        鈫?platforms/xxx.md
鏀硅寖渚?checker     鈫?tools/checker_registry.py + examples/ + tools/fixtures/锛堣窇 validate-examples锛?鏀规帶鍒跺钩闈?        鈫?SKILL.md锛堜繚鎸?<100 琛岋級+ skill_lite_body.md + agents/openai.yaml 鈫?sync
鏀?Skill 缁撴瀯璇存槑  鈫?鏈枃浠?+ workflows/README.md + README.md
```

**绂佹锛?* 鎷嗗涓?skill锛涙湭闂嵎鎵?SDK 鍒犻櫎娓呭崟锛涙墜鏀?`freertos-skill-lite/` 姝ｆ枃銆?
---

## 瀹屾暣鐗?vs Lite 缁撴瀯宸?
| 灞?| 瀹屾暣鐗?| Lite |
|----|--------|------|
| L0 | SKILL.md | sync 鐢熸垚 |
| L1 | 鍏ㄩ儴 workflow | l2 鐢?lite 瀛?workflow |
| L2鈥揕3 | 鍚屽乏 | 鍚屽乏锛堟棤 examples 閾炬帴锛?|
| L4 | examples + tools | 鐢?lite_manual_checklist 鏇夸唬 |
