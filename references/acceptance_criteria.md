# 验收标准（Acceptance Criteria）

每个 workflow 的「结果怎样才算合格」。失败时的诊断路径见各 workflow 的 Step 3/4。

## 通用标准

| 检查项 | 命令 | 通过条件 |
|--------|------|----------|
| 元数据完整性 | `python scripts/check_skill_metadata.py` | exit=0 |
| 链接有效性 | `python tools/check_links.py` | 无 broken link |
| Quick Gate | `python scripts/quick_gate.py` | 全部 PASS（LVGL regression 为 non-blocking WARN） |

## Code Review（l2_code_review）

| 检查项 | 通过条件 |
|--------|----------|
| run_review.py exit code | exit=0（无 P0/P1 违规） |
| 输出格式 | 包含「结论」「违规项」「Checker 结果」「修复优先级」四节 |
| 违规引用 | 每条违规引用 `C#.#` 约束 ID + 文件:行号 |
| 正例对照 | 修复建议引用 `examples/good_*.c` 模式 |
| 自动化 | `run_review.py --self-test` exit=0 |

## Project Review（l2_project_review）

| 检查项 | 通过条件 |
|--------|----------|
| 全目录扫描 | `run_review.py --dir ./src --platform <x>` exit=0 |
| 密钥扫描 | `secret_scan_checker.py` 无 P0 发现 |
| 约束覆盖 | 关键约束（C1-C4, C7-C9）均有检查结果 |

## Crash Debug（debug_crash）

| 检查项 | 通过条件 |
|--------|----------|
| 症状路由 | `context_router.py --symptom-text` 命中 confidence >= medium |
| 验证探针 | 输出包含 `diagnostic_probes`，每个探针有明确的验证命令 |
| 根因假设 | >= 2 个独立证据支持（日志 + 代码定位 + 工具验证） |
| 修复验证 | 修复后 `run_review.py` exit=0 + 编译通过 |

## Memory Analysis（l2_memory_analysis）

| 检查项 | 通过条件 |
|--------|----------|
| 泄漏检查 | `cjson_leak_checker.py` exit=0 |
| 内存基线 | 输出包含 heap 使用基线值 |
| 池化分析 | 输出包含 pool 缩放建议（如有） |

## SDK Trimming（l3_sdk_trim）

| 检查项 | 通过条件 |
|--------|----------|
| SDK 扫描 | 输出包含保留/裁剪的驱动列表 |
| 编译验证 | 裁剪后编译通过 |
| 功能验证 | 核心功能不受影响（用户确认） |

## New Module（l3_new_module）

| 检查项 | 通过条件 |
|--------|----------|
| Codegen Contract | 包含 workflow/platform/module_type/tasks/queues/locks/timers |
| 模块边界表 | `module_boundary_checker.py` exit=0 |
| Codegen Gate | `codegen_gate.py` exit=0 |
| 编译验证 | 生成代码编译通过 |
| 公共 API | 所有 public API 有文档注释 |
| 禁止模式 | 无裸 portMAX_DELAY、ISR blocking、queue 传栈指针 |

## Bring-up（l3_bring_up）

| 检查项 | 通过条件 |
|--------|----------|
| 最小系统 | 输出包含 boot sequence + WDT 配置 |
| 外设验证 | 每个外设有独立的验证命令 |
| 平台对齐 | 代码符合 `platforms/xxx.md` 的 API 映射 |

## LVGL Page Generation（l3_lvgl_page）

| 检查项 | 通过条件 |
|--------|----------|
| MCP 流程 | 完整执行 get_lvgl_theme_skill → convert_image → generate_spec → generate_code → validate |
| 布局验证 | `validate_lvgl_layout_code` exit=0 |
| 截图回归 | 像素差异 < 1%（`compare_lvgl_screenshot`） |
| 绝对坐标 | 无绝对坐标，除非有 `LVGL_LAYOUT_EXCEPTION` 注释 |
| 资源路径 | 所有图片资源使用宏引用，无硬编码路径 |
| 信息完整度 | 8 项必需信息全部确认（屏幕参数/字体/图片/颜色/样式/数据绑定/LVGL版本/触摸类型） |

## HW/SW Co-debug（hw_sw_cocodebug）

| 检查项 | 通过条件 |
|--------|----------|
| IO 规划 | 输出包含 GPIO 分配表 + 冲突检查 |
| 时序分析 | 关键时序路径有标注 |
| 平台对齐 | GPIO/外设配置符合平台文档 |

## LVGL MCP Pipeline

| 阶段 | MCP Tool | 验收条件 |
|------|----------|----------|
| 主题加载 | `get_lvgl_theme_skill` | 返回 display config + layout rules |
| 图片转换 | `convert_image_to_lvgl_source` | 输出 .c + .h 文件，RGB565 格式，无错误 |
| 资源批量转换 | `convert_assets_to_lvgl` | 所有图片转换成功，输出 assets registry |
| 布局规格 | `generate_lvgl_layout_spec` | 返回 JSON spec，包含 flex/grid 布局 |
| 代码生成 | `generate_lvgl_page_code` | 输出 .c/.h，无绝对坐标 |
| 布局验证 | `validate_lvgl_layout_code` | exit=0，无 forbidden layout pattern |
| 渲染截图 | `lvgl_render` | 输出 PNG 截图 + object-tree JSON |
| 截图回归 | `run_lvgl_ui_regression` | 像素差异 < 1%，无 runtime error |
| 字体生成 | `generate_font_glyph` | 输出 .c 字体文件 + placeholder macro |

完整管线（不可跳步）：
```
get_lvgl_theme_skill → convert_image_to_lvgl_source → generate_lvgl_layout_spec → generate_lvgl_page_code → validate_lvgl_layout_code
```

## Release Readiness（发布级验收）

发布或安装 skill 之前，必须全部通过：

| 检查项 | 命令 | 通过条件 |
|--------|------|----------|
| Quick Gate | `python scripts/quick_gate.py` | 全部 PASS（LVGL regression 为 non-blocking WARN） |
| 元数据 | `python scripts/check_skill_metadata.py` | exit=0 |
| 链接 | `python tools/check_links.py` | 无 broken link |
| 规则覆盖 | `python scripts/check_rule_coverage.py` | exit=0，46 约束均有 shard |
| Forward Tests | `python scripts/skill_forward_eval.py` | 全部 PASS |
| Skill Iterate | `python scripts/skill_iterate.py --check` | exit=0 |
| Commit Audit | `python scripts/commit_audit.py --self-test` | exit=0 |
| Checker 自测 | `python tools/run_review.py --self-test` | exit=0 |
| Example 验证 | `python tools/run_review.py --validate-examples` | exit=0 |

## 失败诊断路径

| 失败类型 | 下一步 |
|----------|--------|
| run_review exit=1 | 查看 JSON 输出中的 `violations`，按 P0→P1→P2 优先级修复 |
| 编译失败 | 检查 platform doc 的编译命令，确认 SDK 路径 |
| 症状路由未命中 | 用 `--symptom-text` 重新描述，或手动选择 workflow |
| 截图回归失败 | 检查 `debug_overlay.png`，确认变更是否预期 |
| checker 无输出 | 确认 `--platform` 参数正确，文件路径存在 |
| MCP tool 不可用 | fallback 到 `workflows/l3_lvgl_page.md` 手动流程 |
| 链接检查失败 | 运行 `python tools/check_links.py` 定位 broken link |

## 工具接口参考

- CLI 工具：[tool_api_reference.md](tool_api_reference.md)
- MCP 工具：[mcp_tool_reference.md](mcp_tool_reference.md)
