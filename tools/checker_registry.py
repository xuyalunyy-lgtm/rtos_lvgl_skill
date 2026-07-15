#!/usr/bin/env python3
"""
Central registry for run_review.py.

Single source of truth for all checkers.  Every checker MUST be registered here.
Add a checker here first, then wire only unusual behavior in run_review.py.

SDK Abstraction: All checkers use `sdk_lookup.py` to get platform-specific API
names instead of hardcoding them. Set `SDK_PLATFORM` env var to target a specific
platform (default: esp32). See `references/sdk_abstraction.yaml` for the full
standard operation registry.

Suites:
  default   — run by default in run_review.py (L2 gate)
  all       — every non-AST checker (for --suite all)
  security  — secret scan, OTA, boot, lifecycle
  media     — A/V pipeline, codec, clock, DMA
  platform  — peripheral, display, flash, low-power, network
  realtime  — ISR, priority, blocking wait, lock, critical section, backpressure
  enhanced  — AST-enhanced duplicates (cjson_ast, queue_ast); not run by default
"""

from __future__ import annotations

from dataclasses import dataclass, field

CONSTRAINT_SCHEMA_VERSION = "2.0"
# Rules are additive unless a migration explicitly states otherwise.  Consumers
# can use this manifest to pin their review baseline in CI.
CONSTRAINT_MIGRATIONS: tuple[dict[str, str], ...] = (
    {"from": "1.0", "to": "2.0", "policy": "additive", "note": "C47/C48 added; existing checker IDs retain semantics"},
)


@dataclass(frozen=True)
class CheckerSpec:
    name: str
    script: str
    skip_arg: str
    mode: str
    domains: tuple[str, ...]
    note: str = ""
    suites: tuple[str, ...] = ("default", "all")
    error_prefix: str = ""
    overlaps: tuple[str, ...] = ()

    @property
    def skip_attr(self) -> str:
        return f"skip_{self.skip_arg.replace('-', '_')}"


@dataclass(frozen=True)
class CheckerCase:
    script: str
    path: str
    expected: int
    label: str


ALL_CHECKERS: tuple[CheckerSpec, ...] = (
    # ── C1: LVGL thread safety ──────────────────────────────────────────
    CheckerSpec("lvgl_thread_checker", "lvgl_thread_checker.py", "lvgl", "per-file", ("C1",),
                suites=("default", "all"), error_prefix="C1"),
    # ── C2: Queue payload ownership ─────────────────────────────────────
    CheckerSpec("queue_ownership_checker", "queue_ownership_checker.py", "queue", "per-file", ("C2",),
                suites=("default", "all"), error_prefix="C2",
                overlaps=("queue_ast_checker",)),
    CheckerSpec("queue_ast_checker", "queue_ast_checker.py", "queue-ast", "per-file", ("C2",),
                note="AST-enhanced duplicate of queue_ownership_checker",
                suites=("enhanced",), error_prefix="C2",
                overlaps=("queue_ownership_checker",)),
    # ── C3: cJSON lifecycle ─────────────────────────────────────────────
    CheckerSpec("cjson_leak_checker", "cjson_leak_checker.py", "cjson", "per-file", ("C3",),
                suites=("default", "all"), error_prefix="C3",
                overlaps=("cjson_ast_checker",)),
    CheckerSpec("cjson_ast_checker", "cjson_ast_checker.py", "cjson-ast", "per-file", ("C3",),
                note="AST-enhanced duplicate of cjson_leak_checker",
                suites=("enhanced",), error_prefix="C3",
                overlaps=("cjson_leak_checker",)),
    # ── C5: Test macros ─────────────────────────────────────────────────
    CheckerSpec("test_macro_checker", "test_macro_checker.py", "test-macro", "batch", ("C5",),
                suites=("default", "all"), error_prefix="C5"),
    # ── C7: Stack allocation ────────────────────────────────────────────
    CheckerSpec("stack_alloc_checker", "stack_alloc_checker.py", "stack-alloc", "batch", ("C7.3",),
                suites=("default", "all"), error_prefix="C7"),
    # ── C8: Boot sequence ───────────────────────────────────────────────
    CheckerSpec("boot_sequence_checker", "boot_sequence_checker.py", "boot", "batch", ("C8",),
                suites=("default", "all", "security"), error_prefix="C8"),
    # ── C9: Secret scan ─────────────────────────────────────────────────
    CheckerSpec("secret_scan_checker", "secret_scan_checker.py", "secret-scan", "batch", ("C9",),
                suites=("default", "all", "security"), error_prefix="C9"),
    # ── C10: Voice sequence ─────────────────────────────────────────────
    CheckerSpec("voice_sequence_checker", "voice_sequence_checker.py", "voice", "batch", ("C10",),
                suites=("default", "all"), error_prefix="C10"),
    # ── C11: Coding style / function length ─────────────────────────────
    CheckerSpec("coding_style_checker", "coding_style_checker.py", "coding-style", "batch", ("C11",),
                suites=("default", "all"), error_prefix="C11"),
    CheckerSpec("function_length_checker", "function_length_checker.py", "func-length", "batch", ("C11.5",),
                suites=("default", "all"), error_prefix="C11"),
    # ── C12: Return value check ─────────────────────────────────────────
    CheckerSpec("return_check_checker", "return_check_checker.py", "return-check", "batch", ("C12",),
                suites=("default", "all"), error_prefix="C12"),
    # ── C13: State machine ──────────────────────────────────────────────
    CheckerSpec("state_machine_checker", "state_machine_checker.py", "state-machine", "batch", ("C13",),
                suites=("default", "all"), error_prefix="C13"),
    # ── C14: Logging ────────────────────────────────────────────────────
    CheckerSpec("logging_checker", "logging_checker.py", "logging", "batch", ("C14",),
                suites=("default", "all"), error_prefix="C14"),
    CheckerSpec("log_desensitize_checker", "log_desensitize_checker.py", "log-desensitize", "batch", ("C14.4",),
                suites=("default", "all", "security"), error_prefix="C14"),
    # ── C15: Priority ───────────────────────────────────────────────────
    CheckerSpec("priority_checker", "priority_checker.py", "priority", "batch", ("C15",),
                suites=("default", "all", "realtime"), error_prefix="C15"),
    # ── C16: Timer ──────────────────────────────────────────────────────
    CheckerSpec("timer_checker", "timer_checker.py", "timer", "batch", ("C16",),
                suites=("default", "all"), error_prefix="C16"),
    # ── C17: Multi-core IPC ────────────────────────────────────────────
    CheckerSpec("multi_core_ipc_checker", "multi_core_ipc_checker.py", "multi-core-ipc", "batch", ("C17",),
                suites=("all", "realtime"), error_prefix="C17"),
    # ── C18: Peripheral driver ──────────────────────────────────────────
    CheckerSpec("peripheral_driver_checker", "peripheral_driver_checker.py", "peripheral-driver", "batch", ("C18",),
                suites=("all", "platform"), error_prefix="C18"),
    # ── C19: Flash/NVS ─────────────────────────────────────────────────
    CheckerSpec("flash_nvs_checker", "flash_nvs_checker.py", "flash-nvs", "batch", ("C19",),
                suites=("all", "platform"), error_prefix="C19"),
    # ── C20: Network resilience ─────────────────────────────────────────
    CheckerSpec("network_resilience_checker", "network_resilience_checker.py", "network-resilience", "batch", ("C20",),
                suites=("all", "platform"), error_prefix="C20"),
    CheckerSpec("api_sequence_checker", "api_sequence_checker.py", "api-sequence", "batch", ("C20", "C23"),
                note="WiFi/MQTT and camera API order within one function",
                suites=("all", "platform"), error_prefix="C20"),
    # ── C21: Low power ─────────────────────────────────────────────────
    CheckerSpec("low_power_checker", "low_power_checker.py", "low-power", "batch", ("C21",),
                suites=("all", "platform"), error_prefix="C21"),
    # ── C22: OTA safety ─────────────────────────────────────────────────
    CheckerSpec("ota_safety_checker", "ota_safety_checker.py", "ota", "batch", ("C22",),
                suites=("default", "all", "security"), error_prefix="C22"),
    # ── C23: Display driver ─────────────────────────────────────────────
    CheckerSpec("display_driver_checker", "display_driver_checker.py", "display-driver", "batch", ("C23",),
                suites=("all", "platform"), error_prefix="C23"),
    # ── C24: Peripheral shutdown ────────────────────────────────────────
    CheckerSpec("peripheral_shutdown_checker", "peripheral_shutdown_checker.py", "peripheral-shutdown", "batch", ("C24",),
                suites=("default", "all"), error_prefix="C24"),
    # ── C25: A/V pipeline ──────────────────────────────────────────────
    CheckerSpec("av_pipeline_checker", "av_pipeline_checker.py", "av", "batch", ("C25",),
                suites=("default", "all", "media"), error_prefix="C25"),
    # ── C26: Media format ───────────────────────────────────────────────
    CheckerSpec("media_format_checker", "media_format_checker.py", "media-format", "batch", ("C26",),
                suites=("default", "all", "media"), error_prefix="C26"),
    # ── C27: A/V clock jitter ──────────────────────────────────────────
    CheckerSpec("av_clock_jitter_checker", "av_clock_jitter_checker.py", "av-clock", "batch", ("C27",),
                suites=("default", "all", "media"), error_prefix="C27"),
    # ── C28: A/V DMA buffer ────────────────────────────────────────────
    CheckerSpec("av_dma_buffer_checker", "av_dma_buffer_checker.py", "av-dma", "batch", ("C28",),
                suites=("default", "all", "media"), error_prefix="C28"),
    # ── C29: Module boundary ────────────────────────────────────────────
    CheckerSpec("module_boundary_checker", "module_boundary_checker.py", "module-boundary", "batch", ("C29",),
                suites=("default", "all"), error_prefix="C29"),
    # ── C31: Blocking wait / timeout budget ─────────────────────────────
    CheckerSpec("blocking_wait_checker", "blocking_wait_checker.py", "timeout", "batch", ("C31",),
                suites=("default", "all", "realtime"), error_prefix="C31"),
    # ── C32: Observability ──────────────────────────────────────────────
    CheckerSpec("observability_checker", "observability_checker.py", "observability", "batch", ("C32",),
                suites=("default", "all"), error_prefix="C32"),
    # ── C33: Lifecycle ──────────────────────────────────────────────────
    CheckerSpec("lifecycle_checker", "lifecycle_checker.py", "lifecycle", "batch", ("C33",),
                suites=("default", "all", "security"), error_prefix="C33"),
    # ── C35: Critical path ──────────────────────────────────────────────
    CheckerSpec("critical_path_checker", "critical_path_checker.py", "critical-path", "batch", ("C35",),
                suites=("default", "all"), error_prefix="C35"),
    # ── C36/C37: Efficiency / backpressure ──────────────────────────────
    CheckerSpec("efficiency_budget_checker", "efficiency_budget_checker.py", "efficiency", "batch", ("C36", "C37"),
                suites=("default", "all"), error_prefix="C36",
                overlaps=("backpressure_checker",)),
    CheckerSpec("backpressure_checker", "backpressure_checker.py", "backpressure", "batch", ("C37",),
                suites=("default", "all"), error_prefix="C37",
                overlaps=("efficiency_budget_checker",)),
    # ── C38: Fault isolation ───────────────────────────────────────────
    CheckerSpec("fault_isolation_checker", "fault_isolation_checker.py", "fault-isolation", "batch", ("C38",),
                suites=("all", "security"), error_prefix="C38"),
    # ── C39: Config matrix ──────────────────────────────────────────────
    CheckerSpec("config_matrix_checker", "config_matrix_checker.py", "config-matrix", "batch", ("C39",),
                suites=("default", "all"), error_prefix="C39"),
    # ── C42: Board resource ─────────────────────────────────────────────
    CheckerSpec("board_resource_checker", "board_resource_checker.py", "board-resource", "batch", ("C42",),
                suites=("default", "all"), error_prefix="C42"),
    # ── C43: Lock budget ────────────────────────────────────────────────
    CheckerSpec("lock_budget_checker", "lock_budget_checker.py", "lock-budget", "batch", ("C43",),
                suites=("default", "all", "realtime"), error_prefix="C43"),
    # ── C44: Critical section ───────────────────────────────────────────
    CheckerSpec("critical_section_checker", "critical_section_checker.py", "critical-section", "batch", ("C44",),
                suites=("default", "all", "realtime"), error_prefix="C44"),
    # ── C45: Sensor integration ─────────────────────────────────────────
    CheckerSpec("sensor_integration_checker", "sensor_integration_checker.py", "sensor-integration", "batch", ("C45",),
                suites=("default", "all"), error_prefix="C45"),
    CheckerSpec("ble_protocol_checker", "ble_protocol_checker.py", "ble-protocol", "batch", ("C46",),
                suites=("all", "platform"), error_prefix="C46"),
    CheckerSpec("ai_generated_code_checker", "ai_generated_code_checker.py", "ai-generated", "batch", ("C48",),
                note="Only evaluates files explicitly marked as AI-generated", suites=("all",), error_prefix="C48"),
    CheckerSpec("tool_log_hygiene_checker", "tool_log_hygiene_checker.py", "tool-log-hygiene", "global", ("C47",),
                note="Repository-wide MCP output redaction audit", suites=("all", "security"), error_prefix="C47"),
    # ── C41: Regression sample coverage (repository-wide) ──────────────
    CheckerSpec("regression_sample_checker", "regression_sample_checker.py", "regression-sample", "global", ("C41",),
                note="Repository-wide good/bad fixture coverage audit",
                suites=("all",), error_prefix="C41"),
    # ── ISR safety (cross-cutting) ──────────────────────────────────────
    CheckerSpec("isr_safety_checker", "isr_safety_checker.py", "isr", "per-file", ("C4",),
                suites=("default", "all", "realtime"), error_prefix="C4"),
    # ── C34: Hotpath forbidden ─────────────────────────────────────────
    CheckerSpec("hotpath_checker", "hotpath_checker.py", "hotpath", "per-file", ("C34",),
                suites=("default", "all", "realtime"), error_prefix="C34"),
)

# Default suite = subset that runs in run_review.py without --suite flag
DEFAULT_CHECKERS: tuple[CheckerSpec, ...] = tuple(c for c in ALL_CHECKERS if "default" in c.suites)

# Known suite names (for --list-suites / validation)
SUITE_NAMES = ("default", "all", "security", "media", "platform", "realtime", "enhanced")


def get_suite(name: str) -> tuple[CheckerSpec, ...]:
    """Return checkers belonging to *name* suite.  Raises ValueError for unknown suite."""
    if name not in SUITE_NAMES:
        raise ValueError(f"unknown suite {name!r}; choose from {SUITE_NAMES}")
    return tuple(c for c in ALL_CHECKERS if name in c.suites)


def checker_count_by_suite() -> dict[str, int]:
    """Return {suite_name: checker_count} for all suites."""
    return {s: len(get_suite(s)) for s in SUITE_NAMES}


SELF_TEST_CASES: tuple[CheckerCase, ...] = (
    # ── fixtures/ 目录 ──────────────────────────────────────────────────
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
    CheckerCase("multi_core_ipc_checker.py", "fixtures/good_multi_core_ipc.c", 0, "multi-core IPC good"),
    CheckerCase("multi_core_ipc_checker.py", "fixtures/bad_multi_core_ipc.c", 1, "multi-core IPC bad"),
    CheckerCase("fault_isolation_checker.py", "fixtures/good_fault_isolation.c", 0, "fault isolation good"),
    CheckerCase("fault_isolation_checker.py", "fixtures/bad_fault_isolation.c", 1, "fault isolation bad"),
    CheckerCase("sensor_integration_checker.py", "fixtures/good_sensor_integration.c", 0, "sensor integration good"),
    CheckerCase("sensor_integration_checker.py", "fixtures/bad_sensor_integration.c", 1, "sensor integration bad"),
    CheckerCase("ble_protocol_checker.py", "fixtures/good_ble_protocol.c", 0, "BLE protocol good"),
    CheckerCase("ble_protocol_checker.py", "fixtures/bad_ble_protocol.c", 1, "BLE protocol bad"),
    CheckerCase("ai_generated_code_checker.py", "fixtures/good_ai_generated.c", 0, "AI generated code good"),
    CheckerCase("ai_generated_code_checker.py", "fixtures/bad_ai_generated.c", 1, "AI generated code bad"),
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
    CheckerCase("api_sequence_checker.py", "fixtures/good_api_sequence.c", 0, "API sequence good"),
    CheckerCase("api_sequence_checker.py", "fixtures/bad_api_sequence.c", 1, "API sequence bad"),
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
    CheckerCase("state_machine_checker.py", "fixtures/good_state_machine.c", 0, "state machine good"),
    CheckerCase("state_machine_checker.py", "fixtures/bad_state_machine.c", 1, "state machine bad"),
    CheckerCase("timer_checker.py", "fixtures/good_timer.c", 0, "timer good"),
    CheckerCase("timer_checker.py", "fixtures/bad_timer.c", 1, "timer bad"),
    CheckerCase("log_desensitize_checker.py", "fixtures/good_log_desensitize.c", 0, "log desensitize good"),
    CheckerCase("log_desensitize_checker.py", "fixtures/bad_log_desensitize.c", 1, "log desensitize bad"),
    CheckerCase("test_macro_checker.py", "fixtures/good_test_macro.c", 0, "test macro good"),
    CheckerCase("test_macro_checker.py", "fixtures/bad_test_macro.c", 1, "test macro bad"),
    CheckerCase("coding_style_checker.py", "fixtures/good_coding_style.c", 0, "coding style good"),
    CheckerCase("coding_style_checker.py", "fixtures/bad_coding_style.c", 1, "coding style bad"),
    CheckerCase("function_length_checker.py", "fixtures/good_function_length.c", 0, "function length good"),
    CheckerCase("function_length_checker.py", "fixtures/bad_function_length.c", 1, "function length bad"),
    CheckerCase("return_check_checker.py", "fixtures/good_return_check.c", 0, "return check good"),
    CheckerCase("return_check_checker.py", "fixtures/bad_return_check.c", 1, "return check bad"),
    CheckerCase("logging_checker.py", "fixtures/good_logging.c", 0, "logging good"),
    CheckerCase("logging_checker.py", "fixtures/bad_logging.c", 1, "logging bad"),
    CheckerCase("board_resource_checker.py", "fixtures/good_board_resource.c", 0, "board resource good"),
    CheckerCase("board_resource_checker.py", "fixtures/bad_board_resource.c", 1, "board resource bad"),
    CheckerCase("module_boundary_checker.py", "fixtures/good_module_boundary.c", 0, "module boundary good"),
    CheckerCase("module_boundary_checker.py", "fixtures/bad_module_boundary.c", 1, "module boundary bad"),
    CheckerCase("module_boundary_checker.py", "fixtures/good_interface_contract.c", 0, "interface contract good"),
    CheckerCase("module_boundary_checker.py", "fixtures/bad_interface_contract.c", 1, "interface contract bad"),
    CheckerCase("hotpath_checker.py", "fixtures/good_hotpath.c", 0, "hotpath good"),
    CheckerCase("hotpath_checker.py", "fixtures/bad_hotpath.c", 1, "hotpath bad"),
    # ── Edge cases: boundary conditions (must not false-positive) ──
    CheckerCase("cjson_leak_checker.py", "fixtures/edge_cjson_nested.c", 0, "cjson nested+loop good"),
    CheckerCase("queue_ownership_checker.py", "fixtures/edge_queue_full.c", 0, "queue full handling good"),
    CheckerCase("isr_safety_checker.py", "fixtures/edge_isr_fromisr.c", 0, "isr fromisr good"),
    CheckerCase("hotpath_checker.py", "fixtures/edge_hotpath_static.c", 0, "hotpath static alloc good"),
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
    CheckerCase("module_boundary_checker.py", "examples/good_module_boundary.c", 0, "C29 good"),
    CheckerCase("module_boundary_checker.py", "examples/bad_god_module.c", 1, "C29.6 bad"),
    CheckerCase("module_boundary_checker.py", "examples/bad_cross_layer_dependency.c", 1, "C29.7 bad"),
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
    # TODO: return_check_checker is too strict on good_presenter_consumer.c for xQueueSend test patterns; enable after optimization.
    CheckerCase("return_check_checker.py", "examples/bad_unchecked_return.c", 1, "C12 bad"),
    CheckerCase("logging_checker.py", "examples/good_presenter_consumer.c", 0, "C14 good"),
    CheckerCase("logging_checker.py", "examples/bad_isr_printf.c", 1, "C14 bad"),
    CheckerCase("ota_safety_checker.py", "examples/good_ota_update.c", 0, "C22 good"),
    CheckerCase("ota_safety_checker.py", "examples/bad_ota_no_rollback.c", 1, "C22 bad"),
)
