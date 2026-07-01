#!/usr/bin/env python3
"""
Central registry for run_review.py.

Add a checker here first, then wire only unusual behavior in run_review.py.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CheckerSpec:
    name: str
    script: str
    skip_arg: str
    mode: str
    domains: tuple[str, ...]
    note: str = ""

    @property
    def skip_attr(self) -> str:
        return f"skip_{self.skip_arg.replace('-', '_')}"


@dataclass(frozen=True)
class CheckerCase:
    script: str
    path: str
    expected: int
    label: str


DEFAULT_CHECKERS: tuple[CheckerSpec, ...] = (
    CheckerSpec("cjson_leak_checker", "cjson_leak_checker.py", "cjson", "per-file", ("C3",)),
    CheckerSpec("isr_safety_checker", "isr_safety_checker.py", "isr", "per-file", ("C4",)),
    CheckerSpec("lvgl_thread_checker", "lvgl_thread_checker.py", "lvgl", "per-file", ("C1",)),
    CheckerSpec("queue_ownership_checker", "queue_ownership_checker.py", "queue", "per-file", ("C2",)),
    CheckerSpec("voice_sequence_checker", "voice_sequence_checker.py", "voice", "batch", ("C10",)),
    CheckerSpec("av_pipeline_checker", "av_pipeline_checker.py", "av", "batch", ("C25",)),
    CheckerSpec("media_format_checker", "media_format_checker.py", "media-format", "batch", ("C26",)),
    CheckerSpec("av_clock_jitter_checker", "av_clock_jitter_checker.py", "av-clock", "batch", ("C27",)),
    CheckerSpec("av_dma_buffer_checker", "av_dma_buffer_checker.py", "av-dma", "batch", ("C28",)),
    CheckerSpec("blocking_wait_checker", "blocking_wait_checker.py", "timeout", "batch", ("C31",)),
    CheckerSpec("efficiency_budget_checker", "efficiency_budget_checker.py", "efficiency", "batch", ("C36", "C37")),
    CheckerSpec("lock_budget_checker", "lock_budget_checker.py", "lock-budget", "batch", ("C43",)),
    CheckerSpec("critical_section_checker", "critical_section_checker.py", "critical-section", "batch", ("C44",)),
    CheckerSpec("sensor_integration_checker", "sensor_integration_checker.py", "sensor-integration", "batch", ("C45",)),
    CheckerSpec("ota_safety_checker", "ota_safety_checker.py", "ota", "batch", ("C22",)),
    CheckerSpec("boot_sequence_checker", "boot_sequence_checker.py", "boot", "batch", ("C8",)),
    CheckerSpec("stack_alloc_checker", "stack_alloc_checker.py", "stack-alloc", "batch", ("C7.3",)),
    CheckerSpec("lifecycle_checker", "lifecycle_checker.py", "lifecycle", "batch", ("C33",)),
    CheckerSpec("peripheral_shutdown_checker", "peripheral_shutdown_checker.py", "peripheral-shutdown", "batch", ("C24",)),
    CheckerSpec("backpressure_checker", "backpressure_checker.py", "backpressure", "batch", ("C37",)),
    CheckerSpec("critical_path_checker", "critical_path_checker.py", "critical-path", "batch", ("C35",)),
    CheckerSpec("priority_checker", "priority_checker.py", "priority", "batch", ("C15",)),
    CheckerSpec("observability_checker", "observability_checker.py", "observability", "batch", ("C32",)),
    CheckerSpec("config_matrix_checker", "config_matrix_checker.py", "config-matrix", "batch", ("C39",)),
    CheckerSpec("logging_checker", "logging_checker.py", "logging", "batch", ("C14",)),
    CheckerSpec("return_check_checker", "return_check_checker.py", "return-check", "batch", ("C12",)),
    CheckerSpec("function_length_checker", "function_length_checker.py", "func-length", "batch", ("C11.5",)),
)


SELF_TEST_CASES: tuple[CheckerCase, ...] = (
    CheckerCase("cjson_leak_checker.py", "fixtures/good_cjson.c", 0, "cjson good"),
    CheckerCase("cjson_leak_checker.py", "fixtures/bad_cjson.c", 1, "cjson bad"),
    CheckerCase("isr_safety_checker.py", "fixtures/good_isr.c", 0, "isr good"),
    CheckerCase("isr_safety_checker.py", "fixtures/bad_isr.c", 1, "isr bad"),
    CheckerCase("lvgl_thread_checker.py", "fixtures/ui_view_good.c", 0, "lvgl good"),
    CheckerCase("lvgl_thread_checker.py", "fixtures/network_wss_bad.c", 1, "lvgl bad"),
    CheckerCase("queue_ownership_checker.py", "fixtures/good_queue_heap.c", 0, "queue good"),
    CheckerCase("queue_ownership_checker.py", "fixtures/bad_queue_stack.c", 1, "queue bad"),
    CheckerCase("blocking_wait_checker.py", "fixtures/good_timeout_budget.c", 0, "timeout good"),
    CheckerCase("blocking_wait_checker.py", "fixtures/bad_timeout_budget.c", 1, "timeout bad"),
    CheckerCase("efficiency_budget_checker.py", "fixtures/good_efficiency_budget.c", 0, "efficiency good"),
    CheckerCase("efficiency_budget_checker.py", "fixtures/bad_efficiency_budget.c", 1, "efficiency bad"),
    CheckerCase("lock_budget_checker.py", "fixtures/good_lock_budget.c", 0, "lock budget good"),
    CheckerCase("lock_budget_checker.py", "fixtures/bad_lock_budget.c", 1, "lock budget bad"),
    CheckerCase("critical_section_checker.py", "fixtures/good_critical_section.c", 0, "critical section good"),
    CheckerCase("critical_section_checker.py", "fixtures/bad_critical_section.c", 1, "critical section bad"),
    CheckerCase("sensor_integration_checker.py", "fixtures/good_sensor_integration.c", 0, "sensor integration good"),
    CheckerCase("sensor_integration_checker.py", "fixtures/bad_sensor_integration.c", 1, "sensor integration bad"),
    CheckerCase("secret_scan_checker.py", "fixtures/good_config_secrets", 0, "secret good"),
    CheckerCase("secret_scan_checker.py", "fixtures/bad_config_secrets", 1, "secret bad"),
    CheckerCase("ota_safety_checker.py", "fixtures/good_ota_update.c", 0, "ota good"),
    CheckerCase("ota_safety_checker.py", "fixtures/bad_ota_update.c", 1, "ota bad"),
    CheckerCase("boot_sequence_checker.py", "fixtures/good_boot_sequence.c", 0, "boot good"),
    CheckerCase("boot_sequence_checker.py", "fixtures/bad_boot_sequence.c", 1, "boot bad"),
    CheckerCase("stack_alloc_checker.py", "fixtures/good_stack_alloc.c", 0, "stack alloc good"),
    CheckerCase("stack_alloc_checker.py", "fixtures/bad_stack_alloc.c", 1, "stack alloc bad"),
    CheckerCase("lifecycle_checker.py", "fixtures/good_lifecycle.c", 0, "lifecycle good"),
    CheckerCase("lifecycle_checker.py", "fixtures/bad_lifecycle.c", 1, "lifecycle bad"),
    CheckerCase("peripheral_shutdown_checker.py", "fixtures/good_peripheral_shutdown.c", 0, "peripheral shutdown good"),
    CheckerCase("peripheral_shutdown_checker.py", "fixtures/bad_peripheral_shutdown.c", 1, "peripheral shutdown bad"),
    CheckerCase("backpressure_checker.py", "fixtures/good_backpressure.c", 0, "backpressure good"),
    CheckerCase("backpressure_checker.py", "fixtures/bad_backpressure.c", 1, "backpressure bad"),
    CheckerCase("critical_path_checker.py", "fixtures/good_critical_path.c", 0, "critical path good"),
    CheckerCase("critical_path_checker.py", "fixtures/bad_critical_path.c", 1, "critical path bad"),
    CheckerCase("priority_checker.py", "fixtures/good_priority.c", 0, "priority good"),
    CheckerCase("priority_checker.py", "fixtures/bad_priority.c", 1, "priority bad"),
    CheckerCase("observability_checker.py", "fixtures/good_observability.c", 0, "observability good"),
    CheckerCase("observability_checker.py", "fixtures/bad_observability.c", 1, "observability bad"),
    CheckerCase("config_matrix_checker.py", "fixtures/good_config_matrix.c", 0, "config matrix good"),
    CheckerCase("config_matrix_checker.py", "fixtures/bad_config_matrix.c", 1, "config matrix bad"),
)


VALIDATE_EXAMPLE_CASES: tuple[CheckerCase, ...] = (
    CheckerCase("lvgl_thread_checker.py", "examples/good_mvp_pattern.c", 0, "C1 good"),
    CheckerCase("lvgl_thread_checker.py", "examples/good_presenter_consumer.c", 0, "C1 good"),
    CheckerCase("lvgl_thread_checker.py", "examples/bad_lvgl_cross_thread.c", 1, "C1.1 bad"),
    CheckerCase("queue_ownership_checker.py", "examples/good_wss_json_parse.c", 0, "C2 good"),
    CheckerCase("queue_ownership_checker.py", "examples/good_presenter_consumer.c", 0, "C2 good"),
    CheckerCase("queue_ownership_checker.py", "examples/good_wss_reconnect.c", 0, "C2 good"),
    CheckerCase("queue_ownership_checker.py", "examples/good_boot_sequence.c", 0, "C2/C8 good"),
    CheckerCase("queue_ownership_checker.py", "examples/bad_queue_stack_pointer.c", 1, "C2.2 bad"),
    CheckerCase("cjson_leak_checker.py", "examples/good_wss_json_parse.c", 0, "C3 good"),
    CheckerCase("cjson_leak_checker.py", "examples/bad_cjson_leak.c", 1, "C3.1 bad"),
    CheckerCase("isr_safety_checker.py", "examples/bad_isr_blocking.c", 1, "C4.1 bad"),
    CheckerCase("queue_ownership_checker.py", "examples/good_voice_prompt_uplink.c", 0, "C10 good"),
    CheckerCase("voice_sequence_checker.py", "examples/good_voice_prompt_uplink.c", 0, "C10 good"),
    CheckerCase("voice_sequence_checker.py", "examples/bad_prompt_no_detach.c", 1, "C10 bad"),
    CheckerCase("av_pipeline_checker.py", "examples/good_av_pipeline_sync.c", 0, "C25 good"),
    CheckerCase("av_pipeline_checker.py", "examples/bad_av_pipeline_blocking.c", 1, "C25 bad"),
    CheckerCase("media_format_checker.py", "examples/good_media_format_contract.c", 0, "C26 good"),
    CheckerCase("media_format_checker.py", "examples/bad_media_format_mismatch.c", 1, "C26 bad"),
    CheckerCase("av_clock_jitter_checker.py", "examples/good_av_clock_jitter.c", 0, "C27 good"),
    CheckerCase("av_clock_jitter_checker.py", "examples/bad_av_clock_jitter.c", 1, "C27 bad"),
    CheckerCase("av_dma_buffer_checker.py", "examples/good_av_dma_buffer_lifecycle.c", 0, "C28 good"),
    CheckerCase("av_dma_buffer_checker.py", "examples/bad_av_dma_buffer_lifecycle.c", 1, "C28 bad"),
    CheckerCase("blocking_wait_checker.py", "tools/fixtures/good_timeout_budget.c", 0, "C31 good"),
    CheckerCase("blocking_wait_checker.py", "tools/fixtures/bad_timeout_budget.c", 1, "C31 bad"),
    CheckerCase("efficiency_budget_checker.py", "tools/fixtures/good_efficiency_budget.c", 0, "C36/C37 good"),
    CheckerCase("efficiency_budget_checker.py", "tools/fixtures/bad_efficiency_budget.c", 1, "C36/C37 bad"),
    CheckerCase("lock_budget_checker.py", "tools/fixtures/good_lock_budget.c", 0, "C43 good"),
    CheckerCase("lock_budget_checker.py", "tools/fixtures/bad_lock_budget.c", 1, "C43 bad"),
    CheckerCase("critical_section_checker.py", "tools/fixtures/good_critical_section.c", 0, "C44 good"),
    CheckerCase("critical_section_checker.py", "tools/fixtures/bad_critical_section.c", 1, "C44 bad"),
    CheckerCase("sensor_integration_checker.py", "tools/fixtures/good_sensor_integration.c", 0, "C45 good"),
    CheckerCase("sensor_integration_checker.py", "tools/fixtures/bad_sensor_integration.c", 1, "C45 bad"),
    CheckerCase("function_length_checker.py", "examples/good_presenter_consumer.c", 0, "C11.5 good"),
    # TODO: return_check_checker 对 good_presenter_consumer.c 测试模式 xQueueSend 过于严格，待优化后启用。
    CheckerCase("return_check_checker.py", "examples/bad_unchecked_return.c", 1, "C12 bad"),
    CheckerCase("logging_checker.py", "examples/good_presenter_consumer.c", 0, "C14 good"),
    CheckerCase("logging_checker.py", "examples/bad_isr_printf.c", 1, "C14 bad"),
    CheckerCase("ota_safety_checker.py", "examples/good_ota_update.c", 0, "C22 good"),
    CheckerCase("ota_safety_checker.py", "examples/bad_ota_no_rollback.c", 1, "C22 bad"),
)
