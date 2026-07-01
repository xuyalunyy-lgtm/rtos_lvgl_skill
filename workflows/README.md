# Workflow 绱㈠紩

> 鎺у埗骞抽潰鍏ュ彛锛歔SKILL.md](../SKILL.md) 路 缁撴瀯璇存槑锛歔skill_structure.md](../references/skill_structure.md)

閫夊畾 **1 涓?* workflow 鍚庢寜 Step 椤哄簭鎵ц锛沺rompt 浠呭姞杞借 workflow 鎸囧畾椤广€?

| 鏂囦欢 | 绾у埆 | 瑙﹀彂 |
|------|------|------|
| [l2_code_review.md](l2_code_review.md) | L2 | review / audit / 瀹℃煡 C 浠ｇ爜 |
| [l2_code_review_lite.md](l2_code_review_lite.md) | L2 | Lite 浜哄伐瀹℃煡 |
| [l2_architecture_review.md](l2_architecture_review.md) | L2 | 架构 review（I/P/O、FSM/HFSM、HAL 组件、C29-C45 效率契约、评分门禁） |
| [l2_project_review.md](l2_project_review.md) | L2 | 宸ョ▼/宸ヤ綔鍖?閲忎骇鍓嶅璁?|
| [debug_crash.md](debug_crash.md) | L2鈥揕3 | HardFault / 姝绘満 / WDT / frozen |
| [l3_sdk_trim.md](l3_sdk_trim.md) | L3 | SDK 鏀归€?/ 闇€姹傞┍鍔ㄨ鍓?|
| [l3_new_module.md](l3_new_module.md) | L3 | 鏂版ā鍧?/ 澶氫换鍔?/ MVP 璁捐 |
| [hw_sw_cocodebug.md](hw_sw_cocodebug.md) | L2 | 纭欢鑱旇皟 / IO 鍙ｅ垎閰?/ GPIO 鍐茬獊 / bring-up |
| [l3_bring_up.md](l3_bring_up.md) | L3 | 鏉跨骇 bring-up / 鏈€灏忕郴缁?/ 澶栬閫愪釜楠岃瘉 / 閲忎骇闂幆 |
| [l2_memory_analysis.md](l2_memory_analysis.md) | L2 | 鍐呭瓨涓撻」鍒嗘瀽 / 鍩虹嚎閲囬泦 / 娉勬紡鎺掓煡 / 缂╂睜缂╂爤 |
| [l3_lvgl_page.md](l3_lvgl_page.md) | L3 | LVGL 鍗曢〉闈㈢敓鎴愶紙瑙勬牸鏀堕泦鈫掍唬鐮佺敓鎴愨啋MVP 鑱斿姩鈫掑唴瀛樻鏌ワ級 |
| [self_iterate.md](self_iterate.md) | L3 | Skill 缁存姢 / 鑷垜杩唬 |

## 鏍囧噯鍔犺浇椤哄簭锛圠2+锛?

1. `references/core_rules.md`
2. `references/constraint_index.md`锛?*榛樿**锛涘畬鏁寸煩闃佃 `constraint_detail.md`锛?
3. `platforms/xxx.md`锛? 涓級
4. workflow 鎸囧畾鐨?1鈥? 涓?`prompts/*.txt`
5. 瀹屾暣鐗堬細`tools/run_review.py`锛涜寖渚?**Grep/Read 鍗曟枃浠?*锛屽嬁鎵归噺璇?examples/

Architecture 同步校验:
`python scripts/check_architecture_sync.py`

**Claude Code 鐪?token** 鈫?[claude_code.md](../references/claude_code.md)


