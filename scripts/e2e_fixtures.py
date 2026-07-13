"""
Shared frozen requests for Agent E2E evaluation.

Single source of truth for run_agent_e2e.py and validate_agent_e2e.py.
"""
from __future__ import annotations

FROZEN_REQUESTS = [
    {
        "id": "e2e_01",
        "request": "Review this ESP32 cJSON parsing code for buffer overflow risks",
        "expected_workflow": "code_review",
        "expected_clarification": False,
        "must_load_prefix": "workflows/l2_code_review",
        "must_not_load": ["workflows/l3_lvgl_page", "workflows/debug_crash"],
    },
    {
        "id": "e2e_02",
        "request": "设备死机了，看门狗一直在重启，帮我分析日志",
        "expected_workflow": "crash_debug",
        "expected_clarification": False,
        "must_load_prefix": "workflows/debug_crash",
        "must_not_load": ["workflows/l2_code_review", "workflows/l3_lvgl_page"],
    },
    {
        "id": "e2e_03",
        "request": "根据这张设计截图生成 LVGL 界面代码",
        "expected_workflow": "lvgl_page",
        "expected_clarification": False,
        "must_load_prefix": "workflows/l3_lvgl_page",
        "must_not_load": ["workflows/l2_code_review", "workflows/debug_crash"],
    },
    {
        "id": "e2e_04",
        "request": "Analyze heap fragmentation in this STM32 firmware",
        "expected_workflow": "memory_analysis",
        "expected_clarification": False,
        "must_load_prefix": "workflows/l2_memory_analysis",
        "must_not_load": ["workflows/l3_lvgl_page", "workflows/debug_crash"],
    },
    {
        "id": "e2e_05",
        "request": "新板子刚焊好，需要验证外设工作是否正常",
        "expected_workflow": "bring_up",
        "expected_clarification": False,
        "must_load_prefix": "workflows/l3_bring_up",
        "must_not_load": ["workflows/l2_code_review", "workflows/l3_lvgl_page"],
    },
    {
        "id": "e2e_06",
        "request": "flash 空间不够了，帮我裁剪一下 SDK",
        "expected_workflow": "sdk_trim",
        "expected_clarification": False,
        "must_load_prefix": "workflows/l3_sdk_trim",
        "must_not_load": ["workflows/l2_code_review", "workflows/l3_lvgl_page"],
    },
    {
        "id": "e2e_07",
        "request": "用 manifest 生成一个多页面应用的脚手架",
        "expected_workflow": "app_manifest",
        "expected_clarification": False,
        "must_load_prefix": "workflows/l3_lvgl_page",
        "must_not_load": ["workflows/l2_code_review", "workflows/debug_crash"],
    },
    {
        "id": "e2e_08",
        "request": "帮我设计一个 MQTT 通信模块，需要支持断线重连",
        "expected_workflow": "new_module",
        "expected_clarification": False,
        "must_load_prefix": "workflows/l3_new_module",
        "must_not_load": ["workflows/l3_lvgl_page", "workflows/debug_crash"],
    },
    {
        "id": "e2e_09",
        "request": "Project review: audit the entire workspace before release",
        "expected_workflow": "project_review",
        "expected_clarification": False,
        "must_load_prefix": "workflows/l2_project_review",
        "must_not_load": ["workflows/l3_lvgl_page", "workflows/debug_crash"],
    },
    {
        "id": "e2e_10",
        "request": "SPI 和 I2C 引脚冲突了，帮我看看怎么解决",
        "expected_workflow": "hw_sw_debug",
        "expected_clarification": False,
        "must_load_prefix": "workflows/hw_sw_cocodebug",
        "must_not_load": ["workflows/l3_lvgl_page", "workflows/debug_crash"],
    },
    {
        "id": "e2e_11",
        "request": "帮我看看这个问题",
        "expected_workflow": None,
        "expected_clarification": True,
        "must_load_prefix": None,
        "must_not_load": [],
    },
    {
        "id": "e2e_12",
        "request": "LVGL page crashes with HardFault during rendering, need both UI fix and crash debug",
        "expected_workflow": None,
        "expected_clarification": True,
        "must_load_prefix": None,
        "must_not_load": [],
    },
]
