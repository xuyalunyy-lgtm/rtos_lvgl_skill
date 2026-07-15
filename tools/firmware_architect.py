#!/usr/bin/env python3
"""Declarative firmware architecture planner and portable module code generator.

Usage:
  python tools/firmware_architect.py --init-spec architecture.json
  python tools/firmware_architect.py --spec architecture.json --outdir generated
  python tools/firmware_architect.py --self-test
"""
from __future__ import annotations

import argparse
import json
import re
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PLATFORMS = ("esp32", "stm32", "jl", "bk", "zephyr", "freertos")
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
DEFAULT_CONSTRAINTS = ("C12", "C13", "C29", "C30", "C31", "C32", "C33", "C37", "C41")

EXAMPLE_SPEC: dict[str, Any] = {
    "schema_version": "firmware-architecture/v1",
    "project": "environment_monitor",
    "platform": "esp32",
    "description": "Sample software-only firmware architecture.",
    "modules": [
        {
            "name": "sensor_service",
            "responsibility": "normalize sensor samples and publish events",
            "input": "sample command",
            "output": "normalized sample event",
            "dependencies": ["platform_sensor_api", "app_event_bus"],
            "forbidden_dependencies": ["lvgl", "network_client"],
            "tasks": ["sensor_task"],
            "queues": ["sensor_events"],
        },
        {
            "name": "network_service",
            "responsibility": "publish normalized events to the network",
            "input": "normalized sample event",
            "output": "delivery status event",
            "dependencies": ["app_event_bus", "network_stack"],
            "forbidden_dependencies": ["sensor_private_state"],
            "tasks": ["network_task"],
            "queues": ["sensor_events"],
        },
    ],
    "tasks": [
        {"name": "sensor_task", "module": "sensor_service", "stack_bytes": 3072, "priority": 6,
         "period_ms": 100, "deadline_ms": 30, "produces": ["sensor_events"], "consumes": []},
        {"name": "network_task", "module": "network_service", "stack_bytes": 4096, "priority": 4,
         "period_ms": 0, "deadline_ms": 100, "produces": [], "consumes": ["sensor_events"]},
    ],
    "queues": [
        {"name": "sensor_events", "item_type": "sensor_event_t", "item_size": 32, "depth": 8,
         "producer_tasks": ["sensor_task"], "consumer_tasks": ["network_task"],
         "send_timeout_ms": 10, "recv_timeout_ms": 50, "full_policy": "drop_oldest"},
    ],
    "constraints": ["C12", "C13", "C29", "C30", "C31", "C32", "C33", "C37", "C41"],
}


def _identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", value.lower())


def _upper(value: str) -> str:
    return _identifier(value).upper()


def load_spec(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read architecture spec: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("architecture spec must be a JSON object")
    return data


def validate_spec(spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if spec.get("schema_version") != "firmware-architecture/v1":
        errors.append("schema_version must be firmware-architecture/v1")
    for key in ("project", "platform", "modules", "tasks", "queues"):
        if key not in spec:
            errors.append(f"missing required field: {key}")
    project = spec.get("project", "")
    if not isinstance(project, str) or not NAME_RE.fullmatch(project):
        errors.append("project must be a lowercase C identifier")
    if spec.get("platform") not in PLATFORMS:
        errors.append(f"platform must be one of {', '.join(PLATFORMS)}")
    for collection in ("modules", "tasks", "queues"):
        if not isinstance(spec.get(collection, []), list):
            errors.append(f"{collection} must be a list")

    modules = spec.get("modules", [])
    module_names = _validate_named_items(modules, "module", errors)
    task_names = _validate_named_items(spec.get("tasks", []), "task", errors)
    queue_names = _validate_named_items(spec.get("queues", []), "queue", errors)

    for module in modules if isinstance(modules, list) else []:
        if not isinstance(module, dict):
            continue
        for field in ("responsibility", "input", "output"):
            if not isinstance(module.get(field), str) or not module[field].strip():
                errors.append(f"module {module.get('name', '?')} requires non-empty {field}")
        for task in module.get("tasks", []):
            if task not in task_names:
                errors.append(f"module {module.get('name', '?')} references unknown task {task}")
        for queue in module.get("queues", []):
            if queue not in queue_names:
                errors.append(f"module {module.get('name', '?')} references unknown queue {queue}")

    for task in spec.get("tasks", []) if isinstance(spec.get("tasks", []), list) else []:
        if not isinstance(task, dict):
            continue
        if task.get("module") not in module_names:
            errors.append(f"task {task.get('name', '?')} references unknown module {task.get('module')}")
        for numeric in ("stack_bytes", "priority", "period_ms", "deadline_ms"):
            if not isinstance(task.get(numeric), int) or task[numeric] < 0:
                errors.append(f"task {task.get('name', '?')} requires non-negative integer {numeric}")
        if task.get("stack_bytes", 0) == 0:
            errors.append(f"task {task.get('name', '?')} stack_bytes must be positive")
        for queue in task.get("produces", []) + task.get("consumes", []):
            if queue not in queue_names:
                errors.append(f"task {task.get('name', '?')} references unknown queue {queue}")

    for queue in spec.get("queues", []) if isinstance(spec.get("queues", []), list) else []:
        if not isinstance(queue, dict):
            continue
        for numeric in ("item_size", "depth", "send_timeout_ms", "recv_timeout_ms"):
            if not isinstance(queue.get(numeric), int) or queue[numeric] <= 0:
                errors.append(f"queue {queue.get('name', '?')} requires positive integer {numeric}")
        for task in queue.get("producer_tasks", []) + queue.get("consumer_tasks", []):
            if task not in task_names:
                errors.append(f"queue {queue.get('name', '?')} references unknown task {task}")
        if queue.get("full_policy") not in {"drop_oldest", "drop_newest", "coalesce", "reject"}:
            errors.append(f"queue {queue.get('name', '?')} full_policy must be explicit")
        queue_name = queue.get("name", "")
        task_map = {task.get("name"): task for task in spec.get("tasks", []) if isinstance(task, dict)}
        for task_name in queue.get("producer_tasks", []):
            if queue_name not in task_map.get(task_name, {}).get("produces", []):
                errors.append(f"queue {queue_name} producer {task_name} must declare it in task.produces")
        for task_name in queue.get("consumer_tasks", []):
            if queue_name not in task_map.get(task_name, {}).get("consumes", []):
                errors.append(f"queue {queue_name} consumer {task_name} must declare it in task.consumes")
    return errors


def _validate_named_items(items: Any, kind: str, errors: list[str]) -> set[str]:
    names: set[str] = set()
    if not isinstance(items, list):
        return names
    for item in items:
        if not isinstance(item, dict):
            errors.append(f"{kind} entry must be an object")
            continue
        name = item.get("name", "")
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            errors.append(f"{kind} name must be a lowercase C identifier: {name!r}")
        elif name in names:
            errors.append(f"duplicate {kind} name: {name}")
        else:
            names.add(name)
    return names


def render_module_header(module: dict[str, Any]) -> str:
    name = module["name"]
    upper = _upper(name)
    dependencies = ", ".join(module.get("dependencies", [])) or "none"
    forbidden = ", ".join(module.get("forbidden_dependencies", [])) or "none"
    return f'''/* Auto-generated by firmware_architect. Edit implementation TODOs, not this contract. */
#ifndef {upper}_H
#define {upper}_H

#include <stdbool.h>
#include <stdint.h>

typedef enum {{
    {upper}_OK = 0,
    {upper}_ERR_STATE,
    {upper}_ERR_TIMEOUT,
    {upper}_ERR_RESOURCE,
    {upper}_ERR_IO,
}} {name}_result_t;

typedef enum {{
    {upper}_STATE_UNINIT = 0,
    {upper}_STATE_IDLE,
    {upper}_STATE_RUNNING,
    {upper}_STATE_STOPPING,
    {upper}_STATE_ERROR,
}} {name}_state_t;

typedef struct {{
    {name}_state_t state;
    {name}_result_t last_error;
    uint32_t timeout_count;
    uint32_t drop_count;
}} {name}_status_t;

/* module_boundary:
 * responsibility: {module['responsibility']}
 * public_api: {name}_init, {name}_start, {name}_stop, {name}_deinit, {name}_get_status
 * dependencies: {dependencies}
 * forbidden_dependencies: {forbidden}
 * events_in: {module['input']}
 * events_out: {module['output']}
 * owned_resources: {', '.join(module.get('tasks', [])) or 'none'}, {', '.join(module.get('queues', [])) or 'none'}
 * context: task only
 * blocking: start/stop are non-blocking; worker waits use declared finite queue timeouts
 * lifecycle: init -> start -> stop -> deinit
 */

{name}_result_t {name}_init(void);
{name}_result_t {name}_start(void);
{name}_result_t {name}_stop(void);
{name}_result_t {name}_deinit(void);
{name}_status_t {name}_get_status(void);

#endif /* {upper}_H */
'''


def render_module_source(module: dict[str, Any]) -> str:
    name = module["name"]
    upper = _upper(name)
    return f'''/* Auto-generated portable lifecycle skeleton. */
#include "{name}.h"

static {name}_status_t s_status = {{ {upper}_STATE_UNINIT, {upper}_OK, 0u, 0u }};

{name}_result_t {name}_init(void)
{{
    if (s_status.state != {upper}_STATE_UNINIT) {{
        return {upper}_ERR_STATE;
    }}
    /* TODO: acquire only resources owned by this module. */
    s_status.state = {upper}_STATE_IDLE;
    return {upper}_OK;
}}

{name}_result_t {name}_start(void)
{{
    if (s_status.state != {upper}_STATE_IDLE) {{
        return {upper}_ERR_STATE;
    }}
    /* TODO: create/notify declared tasks; every wait must use a finite timeout. */
    s_status.state = {upper}_STATE_RUNNING;
    return {upper}_OK;
}}

{name}_result_t {name}_stop(void)
{{
    if (s_status.state == {upper}_STATE_UNINIT || s_status.state == {upper}_STATE_IDLE) {{
        return {upper}_OK;
    }}
    if (s_status.state != {upper}_STATE_RUNNING) {{
        return {upper}_ERR_STATE;
    }}
    s_status.state = {upper}_STATE_STOPPING;
    /* TODO: signal task exit and join/confirm resource release within a finite timeout. */
    s_status.state = {upper}_STATE_IDLE;
    return {upper}_OK;
}}

{name}_result_t {name}_deinit(void)
{{
    if (s_status.state == {upper}_STATE_RUNNING) {{
        {name}_result_t result = {name}_stop();
        if (result != {upper}_OK) {{
            return result;
        }}
    }}
    if (s_status.state != {upper}_STATE_IDLE && s_status.state != {upper}_STATE_UNINIT) {{
        return {upper}_ERR_STATE;
    }}
    /* TODO: release every resource acquired by init. */
    s_status.state = {upper}_STATE_UNINIT;
    return {upper}_OK;
}}

{name}_status_t {name}_get_status(void)
{{
    return s_status;
}}
'''


def render_architecture_markdown(spec: dict[str, Any]) -> str:
    lines = [f"# {spec['project']} Firmware Architecture", "", spec.get("description", ""), "", "## Module Boundaries", "",
             "| Module | Responsibility | Input | Output | Tasks | Queues |", "|---|---|---|---|---|---|"]
    for module in spec["modules"]:
        lines.append(
            f"| {module['name']} | {module['responsibility']} | {module['input']} | {module['output']} | "
            f"{', '.join(module.get('tasks', [])) or '-'} | {', '.join(module.get('queues', [])) or '-'} |"
        )
    lines.extend(["", "## Task Topology", "", "| Task | Module | Stack (bytes) | Priority | Period | Deadline | Produces | Consumes |",
                  "|---|---|---:|---:|---:|---:|---|---|"])
    for task in spec["tasks"]:
        lines.append(f"| {task['name']} | {task['module']} | {task['stack_bytes']} | {task['priority']} | {task['period_ms']} ms | {task['deadline_ms']} ms | {', '.join(task.get('produces', [])) or '-'} | {', '.join(task.get('consumes', [])) or '-'} |")
    lines.extend(["", "## Queue Contracts", "", "| Queue | Type | Size | Depth | Producers | Consumers | Send timeout | Receive timeout | Full policy |",
                  "|---|---|---:|---:|---|---|---:|---:|---|"])
    for queue in spec["queues"]:
        lines.append(f"| {queue['name']} | {queue.get('item_type', 'event_t')} | {queue['item_size']} | {queue['depth']} | {', '.join(queue.get('producer_tasks', []))} | {', '.join(queue.get('consumer_tasks', []))} | {queue['send_timeout_ms']} ms | {queue['recv_timeout_ms']} ms | {queue['full_policy']} |")
    lines.extend(["", "## Constraints", "", ", ".join(spec.get("constraints", DEFAULT_CONSTRAINTS)), ""])
    return "\n".join(lines)


def generate(spec: dict[str, Any], outdir: Path, force: bool = False) -> list[Path]:
    errors = validate_spec(spec)
    if errors:
        raise ValueError("Invalid architecture spec:\n- " + "\n- ".join(errors))
    if outdir.exists() and any(outdir.iterdir()) and not force:
        raise ValueError(f"output directory is not empty: {outdir} (use --force to overwrite generated paths)")
    include = outdir / "include"
    source = outdir / "src"
    include.mkdir(parents=True, exist_ok=True)
    source.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    for module in spec["modules"]:
        header = include / f"{module['name']}.h"
        implementation = source / f"{module['name']}.c"
        header.write_text(render_module_header(module), encoding="utf-8")
        implementation.write_text(render_module_source(module), encoding="utf-8")
        generated.extend([header, implementation])
    architecture = outdir / "architecture.md"
    architecture.write_text(render_architecture_markdown(spec), encoding="utf-8")
    generated.append(architecture)

    queue_specs = [
        {**queue, "drop_counter": queue.get("drop_counter") or f"s_{queue['name']}_drop_count"}
        for queue in spec["queues"]
    ]
    raw_manifest = {
        "schema_version": "1.1",
        "generator": "firmware_architect",
        "platform": spec["platform"],
        "frameworks": [],
        "module_responsibility": "declarative firmware module boundaries and lifecycle skeletons",
        "public_api": [f"{module['name']}_init" for module in spec["modules"]],
        "dependencies": sorted({dependency for module in spec["modules"] for dependency in module.get("dependencies", [])}),
        "forbidden_dependencies": sorted({dependency for module in spec["modules"] for dependency in module.get("forbidden_dependencies", [])}),
        "events_in": [module["input"] for module in spec["modules"]],
        "events_out": [module["output"] for module in spec["modules"]],
        "owned_resources": [task["name"] for task in spec["tasks"]] + [queue["name"] for queue in spec["queues"]],
        "generated_files": [{"path": str(path.relative_to(outdir)).replace("\\", "/"), "type": path.suffix.lstrip("."), "description": "architecture generated"} for path in generated],
        "tasks": spec["tasks"], "queues": queue_specs, "locks": [], "timers": [], "memory_pools": [],
        "constraints": {"required": list(dict.fromkeys([*DEFAULT_CONSTRAINTS, *spec.get("constraints", [])])), "covered": ["C12", "C13", "C29", "C30", "C31", "C32", "C33"], "deferred": [{"id": "C37", "reason": "queue policies are declared; module implementation must add counters and recovery action", "evidence": "architecture.md"}, {"id": "C41", "reason": "generated skeleton requires project-specific good/bad regression samples", "evidence": "architecture.md"}]},
        "verification_commands": [f"python tools/codegen_gate.py --dir {outdir} --manifest {outdir / 'generation_manifest.json'} --platform {spec['platform']} --strict", f"python tools/run_review.py --dir {outdir} --platform {spec['platform']}"],
    }
    from manifest_normalizer import normalize_manifest
    manifest = normalize_manifest(raw_manifest)
    manifest_path = outdir / "generation_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    generated.append(manifest_path)
    return generated


def run_self_test() -> int:
    with tempfile.TemporaryDirectory() as directory:
        outdir = Path(directory) / "generated"
        generated = generate(EXAMPLE_SPEC, outdir)
        assert (outdir / "include" / "sensor_service.h").is_file()
        assert (outdir / "src" / "network_service.c").is_file()
        assert (outdir / "generation_manifest.json").is_file()
        assert len(generated) == 6
        invalid = {**EXAMPLE_SPEC, "platform": "unknown"}
        assert validate_spec(invalid)
    print("Self-test: 4 passed, 0 failed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, help="Architecture JSON specification")
    parser.add_argument("--outdir", type=Path, help="Output directory")
    parser.add_argument("--init-spec", type=Path, help="Write a starter architecture specification")
    parser.add_argument("--force", action="store_true", help="Allow overwriting generated paths in a non-empty output directory")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return run_self_test()
    if args.init_spec:
        args.init_spec.parent.mkdir(parents=True, exist_ok=True)
        args.init_spec.write_text(json.dumps(EXAMPLE_SPEC, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Starter architecture spec written: {args.init_spec}")
        return 0
    if not args.spec or not args.outdir:
        parser.error("--spec and --outdir are required unless --init-spec or --self-test is used")
    try:
        generated = generate(load_spec(args.spec), args.outdir, args.force)
    except ValueError as exc:
        print(f"error: {exc}")
        return 2
    print(f"Generated {len(generated)} architecture artifacts in {args.outdir}")
    print(f"Next: python tools/codegen_gate.py --dir {args.outdir} --manifest {args.outdir / 'generation_manifest.json'} --platform {load_spec(args.spec)['platform']} --strict")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
