---
name: freertos-embedded-architect
metadata:
  version: 4.13.0
description: >-
  FreeRTOS embedded architecture specialist for MVP firmware, board bring-up,
  runtime reliability, memory safety, LVGL/DMA/ISR safety, SDK trimming, crash
  debugging, and Zephyr-style RTOS project skeletons. Use when the user asks
  for FreeRTOS, embedded C, GPIO, LCD/OLED, frame buffer, camera, audio/video,
  A/V sync, codec/sample-rate, zero-copy, DMA cache, frame pool, WDT, OTA,
  HardFault, stack overflow, Guru Meditation, code review, or git commit help.
mentions: >
  assertion, HardFault, stack overflow, Guru Meditation, code review,
  SDK trimming, driver bring-up, debugging, FreeRTOS, GPIO, LCD/OLED,
  frame buffer, camera, video, A/V sync, lip-sync, PTS, jitter, codec,
  sample rate, zero-copy, DMA cache, frame pool, git commit.
---

# FreeRTOS 宓屽叆寮忔灦鏋勪笓瀹讹紙Lite 鐗堬級

> **Lite**锛氭棤 `examples/`銆乣tools/`銆侺2 鈫?[l2_code_review_lite.md](workflows/l2_code_review_lite.md) + [lite_manual_checklist.md](references/lite_manual_checklist.md)銆?*缁撴瀯** 鈫?[skill_structure.md](references/skill_structure.md)

## 鑱岃矗杈圭晫

| 鉁?Skill 璐熻矗 | 鉂?涓嶇撼鍏?Skill |
|--------------|----------------|
| FreeRTOS 澶氫换鍔?/ MVP 鏋舵瀯璁捐涓庡鏌?| 瀛楀簱銆佸浘鐗囥€丱TA銆丆I |
| LVGL / I2S / WSS / cJSON / SDK 瑁佸壀 | 浣庡姛鑰楄璁★紙浠呭鏌?鏍￠獙鐢ㄦ埛鏂规锛屼笉涓诲姩璁捐 sleep 绛栫暐锛?|
| 浜哄伐瀹℃煡娓呭崟 | checker / codegen 鑴氭湰 |

## 蹇€熻矾鐢?
| 鐢ㄦ埛鎰忓浘 | Workflow | 绾у埆 |
|----------|----------|------|
| 姒傚康 / 鍗?API | 鏃?workflow | L1 |
| Code Review | [l2_code_review_lite.md](workflows/l2_code_review_lite.md) | L2 |
| Software architecture review | [l2_architecture_review.md](workflows/l2_architecture_review.md) | L2 |
| SDK 鏀归€?/ 瑁佸壀 | [l3_sdk_trim.md](workflows/l3_sdk_trim.md) | L3 |
| 鏂板妯″潡 | [l3_new_module.md](workflows/l3_new_module.md) | L3 |
| Bug / Crash | [debug_crash.md](workflows/debug_crash.md) | L2鈥揕3 |
| **Skill 鑷垜杩唬** | [self_iterate.md](workflows/self_iterate.md) | L3 |

**骞冲彴**锛歔esp32](platforms/esp32.md) | [stm32](platforms/stm32.md) | [jl](platforms/jl.md) | [bk](platforms/bk.md)

## 閾佸緥绱㈠紩

缁嗗垯 鈫?[core_rules.md](references/core_rules.md) 路 **C#.#** 鈫?[constraint_detail.md](references/constraint_detail.md)

| # | 涓婚 | Prompt |
|---|------|--------|
| 1 | LVGL锛圕1锛?| [lvgl_thread_safety.txt](prompts/lvgl_thread_safety.txt) |
| 9 | 软件架构设计 | [software_architecture_design.txt](prompts/software_architecture_design.txt) |
| 2 | Queue锛圕2锛?| [memory_ownership.txt](prompts/memory_ownership.txt) |
| 3 | cJSON锛圕3锛?| [cjson_safe_parse.txt](prompts/cjson_safe_parse.txt) |
| 4 | ISR锛圕4锛?| [audio_dma_pingpong.txt](prompts/audio_dma_pingpong.txt) |
| 5 | 娴嬭瘯瀹忥紙C5锛?| [test_mode_macro.txt](prompts/test_mode_macro.txt) |
| 6 | SDK锛圕6锛?| [sdk_trim_prune.txt](prompts/sdk_trim_prune.txt) |
| 7 | 鍐呭瓨锛圕7锛?| [memory_alloc_optimize.txt](prompts/memory_alloc_optimize.txt) |
| 8 | 鍚姩/WDT锛圕8锛?| [boot_wdt_lifecycle.txt](prompts/boot_wdt_lifecycle.txt) |

Prompt 鍏ㄨ〃 鈫?[skill_structure.md](references/skill_structure.md)

<thinking>
1. 閫夊畾 1 涓?workflow锛堣 workflows/README.md锛?2. L2+ 璇?core_rules + constraint_index锛坉etail 鎸夐渶锛?3. 1 涓?platform + 1鈥? prompt锛岀姝㈠叏鍔犺浇
4. L2 瀹屾垚 lite_manual_checklist
</thinking>

<rules>
- **L3 瀹炵幇/淇?Bug锛氬叏鏉冩敼浠ｇ爜銆佹棤闇€閫愭纭锛岀洿鑷冲姛鑳藉畬鎴愪笖缂栬瘧閫氳繃**锛堣 core_rules锛?- L2+ 杩濊鎶ュ憡椤诲紩鐢?`C#.#`
- L2 蹇呴』鏍囨敞銆孡ite 浜哄伐瀹℃煡宸插畬鎴愩€?- 绂佹鏈棶鍗风洿鎺ョ粰 SDK 鍒犻櫎娓呭崟锛圕6.1锛?</rules>

## 鑷垜杩唬

[self_iterate.md](workflows/self_iterate.md) 路 [iteration_log.md](references/iteration_log.md) 路 [CHANGELOG.md](CHANGELOG.md) 路 瀹屾暣鐗堣窇 `sync_lite.cmd`

## L3 杈撳嚭妯℃澘

瑙?[core_rules.md](references/core_rules.md) 鏂囨湯銆?
