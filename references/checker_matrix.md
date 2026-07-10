# Checker Matrix

> Auto-generated from checker_registry.py.

| Checker | Constraints | Error Prefix | Mode | Self-test Fixture | Example Fixture | Overlaps |
|---|---|---|---|---|---|---|
| lvgl_thread_checker | C1 | C1 | per-file | lvgl good, lvgl bad | C1 good, C1 good, C1.1 bad | - |
| queue_ownership_checker | C2 | C2 | per-file | queue good, queue bad | C2 good, C2 good, C2 good, C2/C8 good, C2.2 bad, C10 good | queue_ast_checker |
| queue_ast_checker | C2 | C2 | per-file | - | - | queue_ownership_checker |
| cjson_leak_checker | C3 | C3 | per-file | cjson good, cjson bad | C3 good, C3.1 bad | cjson_ast_checker |
| cjson_ast_checker | C3 | C3 | per-file | - | - | cjson_leak_checker |
| test_macro_checker | C5 | C5 | batch | test macro good, test macro bad | - | - |
| stack_alloc_checker | C7.3 | C7 | batch | stack alloc good, stack alloc bad | - | - |
| boot_sequence_checker | C8 | C8 | batch | boot good, boot bad | - | - |
| secret_scan_checker | C9 | C9 | batch | secret good, secret bad | - | - |
| voice_sequence_checker | C10 | C10 | batch | - | C10 good, C10 bad | - |
| coding_style_checker | C11 | C11 | batch | coding style good, coding style bad | - | - |
| function_length_checker | C11.5 | C11 | batch | function length good, function length bad | C11.5 good | - |
| return_check_checker | C12 | C12 | batch | return check good, return check bad | C12 bad | - |
| state_machine_checker | C13 | C13 | batch | state machine good, state machine bad | - | - |
| logging_checker | C14 | C14 | batch | logging good, logging bad | C14 good, C14 bad | - |
| log_desensitize_checker | C14.4 | C14 | batch | log desensitize good, log desensitize bad | - | - |
| priority_checker | C15 | C15 | batch | priority good, priority bad | - | - |
| timer_checker | C16 | C16 | batch | timer good, timer bad | - | - |
| peripheral_driver_checker | C18 | C18 | batch | - | - | - |
| flash_nvs_checker | C19 | C19 | batch | - | - | - |
| network_resilience_checker | C20 | C20 | batch | - | - | - |
| low_power_checker | C21 | C21 | batch | - | - | - |
| ota_safety_checker | C22 | C22 | batch | ota good, ota bad | C22 good, C22 bad | - |
| display_driver_checker | C23 | C23 | batch | - | - | - |
| peripheral_shutdown_checker | C24 | C24 | batch | peripheral shutdown good, peripheral shutdown bad | - | - |
| av_pipeline_checker | C25 | C25 | batch | - | C25 good, C25 bad | - |
| media_format_checker | C26 | C26 | batch | - | C26 good, C26 bad | - |
| av_clock_jitter_checker | C27 | C27 | batch | - | C27 good, C27 bad | - |
| av_dma_buffer_checker | C28 | C28 | batch | - | C28 good, C28 bad | - |
| module_boundary_checker | C29 | C29 | batch | module boundary good, module boundary bad | C29 good, C29.6 bad, C29.7 bad | - |
| blocking_wait_checker | C31 | C31 | batch | timeout good, timeout bad | C31 good, C31 bad | - |
| observability_checker | C32 | C32 | batch | observability good, observability bad | - | - |
| lifecycle_checker | C33 | C33 | batch | lifecycle good, lifecycle bad | - | - |
| critical_path_checker | C35 | C35 | batch | critical path good, critical path bad | - | - |
| efficiency_budget_checker | C36, C37 | C36 | batch | efficiency good, efficiency bad | C36/C37 good, C36/C37 bad | backpressure_checker |
| backpressure_checker | C37 | C37 | batch | backpressure good, backpressure bad | - | efficiency_budget_checker |
| config_matrix_checker | C39 | C39 | batch | config matrix good, config matrix bad | - | - |
| board_resource_checker | C42 | C42 | batch | board resource good, board resource bad | - | - |
| lock_budget_checker | C43 | C43 | batch | lock budget good, lock budget bad | C43 good, C43 bad | - |
| critical_section_checker | C44 | C44 | batch | critical section good, critical section bad | C44 good, C44 bad | - |
| sensor_integration_checker | C45 | C45 | batch | sensor integration good, sensor integration bad | C45 good, C45 bad | - |
| isr_safety_checker | C4 | C4 | per-file | isr good, isr bad | C4.1 bad | - |
