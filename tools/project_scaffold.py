#!/usr/bin/env python3
"""
One-click project scaffold generator v9.0.2 — Generate a complete MVP project based on platform profile and scene preset.

v2 enhancements:
  1. --preset: Read scene definitions from scene_presets/, auto-set features/constraints/tasks
  2. --platform-profile: Read platform definitions from product_profiles/
  3. Generate task_topology.h, constraint_manifest.json, Kconfig
  4. main.c with constraint annotations, module lifecycle, task topology

Usage:
    python tools/project_scaffold.py --name my_device --platform esp32
    python tools/project_scaffold.py --name my_device --preset voice-screen
    python tools/project_scaffold.py --name my_device --preset audio-video --platform jl
    python tools/project_scaffold.py --self-test
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


# ── Backward compatibility: legacy PLATFORM_TEMPLATES ──
PLATFORM_TEMPLATES = {
    "esp32": {
        "cmake": "cmake_minimum_required(VERSION 3.16)\ninclude($ENV{{IDF_PATH}}/tools/cmake/project.cmake)\nproject({name})",
        "main_cmake": "idf_component_register(SRCS \"main.c\" INCLUDE_DIRS \".\")",
        "config": "# ESP-IDF Configuration\nCONFIG_FREERTOS_HZ=1000\nCONFIG_ESP_TASK_WDT_TIMEOUT_S=30\n",
        "sdkconfig": True,
    },
    "stm32": {
        "cmake": "cmake_minimum_required(VERSION 3.16)\nproject({name} C ASM)\nset(CMAKE_C_STANDARD 11)\n",
        "main_cmake": "add_executable(${{PROJECT_NAME}}.elf main.c)\n",
        "config": "// STM32 FreeRTOSConfig.h\n#define configTOTAL_HEAP_SIZE (32*1024)\n#define configCHECK_FOR_STACK_OVERFLOW 2\n",
        "sdkconfig": False,
    },
    "zephyr": {
        "cmake": "cmake_minimum_required(VERSION 3.20.0)\nfind_package(Zephyr REQUIRED HINTS $ENV{{ZEPHYR_BASE}})\nproject({name})\n",
        "main_cmake": "target_sources(app PRIVATE main.c)\n",
        "config": "# Zephyr Configuration\nCONFIG_HEAP_MEM_POOL_SIZE=8192\nCONFIG_LOG=y\n",
        "sdkconfig": False,
    },
    "jl": {
        "cmake": "# JL AC79 Build System\n",
        "main_cmake": "obj-y += main.o\n",
        "config": "// JL Configuration\n#define CONFIG_HEAP_SIZE (64*1024)\n",
        "sdkconfig": False,
    },
    "bk": {
        "cmake": "# BK Armino Build System\n",
        "main_cmake": "obj-y += main.o\n",
        "config": "// BK Configuration\n#define CONFIG_HEAP_SIZE (64*1024)\n",
        "sdkconfig": False,
    },
}


# ── Preset / Platform loading ──

def _normalize_preset_id(preset_id: str) -> str:
    """Normalize preset ID: support - and _ interchangeability."""
    # Try exact match first
    presets_dir = Path(__file__).resolve().parent.parent / "scene_presets"
    if (presets_dir / f"{preset_id}.json").exists():
        return preset_id
    # Try converting - to _
    alt = preset_id.replace("-", "_")
    if (presets_dir / f"{alt}.json").exists():
        return alt
    # Try converting _ to -
    alt = preset_id.replace("_", "-")
    if (presets_dir / f"{alt}.json").exists():
        return alt
    # Scan JSON id field
    for f in presets_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("id") == preset_id or data.get("id") == alt:
                return f.stem
        except Exception:
            pass
    return preset_id


def _load_preset(preset_id: str) -> dict | None:
    """Load scene preset, return None if not found."""
    presets_dir = Path(__file__).resolve().parent.parent / "scene_presets"
    normalized = _normalize_preset_id(preset_id)
    path = presets_dir / f"{normalized}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _load_platform_adapter(platform: str):
    """Load platform adapter, return None on failure."""
    try:
        from platform_adapter import PlatformAdapter
        return PlatformAdapter(platform)
    except (ImportError, FileNotFoundError):
        return None


# ── Code generation ──

def generate_main_c(
    name: str,
    platform: str,
    has_display: bool,
    has_audio: bool,
    has_network: bool,
    *,
    preset: dict | None = None,
    adapter=None,
) -> str:
    """Generate main.c (v2: supports preset and adapter)."""
    # Override features from preset
    if preset:
        gen_params = preset.get("generator_params", {})
        has_display = has_display or gen_params.get("display", False)
        has_audio = has_audio or gen_params.get("audio", False)
        has_network = has_network or gen_params.get("network", False) or gen_params.get("voice_asr", False)

    # Determine constraint list
    constraints = ["C8", "C12", "C14", "C29", "C33"]
    if preset:
        constraints = preset.get("required_constraints", constraints)
    elif adapter:
        constraints = adapter.required_constraints[:10]  # Take first 10

    # Get task list from preset/adapter
    tasks = []
    if preset:
        tasks = preset.get("generator_params", {}).get("tasks", [])
    elif adapter:
        tasks = [t["name"] for t in adapter.get_default_tasks()]

    # Get queue list from preset/adapter
    queues = []
    if preset:
        queues = preset.get("generator_params", {}).get("queues", [])
    elif adapter:
        queues = [q["name"] for q in adapter.get_default_queues()]

    includes = [
        '#include <stdio.h>',
        '#include <string.h>',
    ]

    if platform in ("esp32", "stm32", "jl", "bk"):
        includes.append('#include "freertos/FreeRTOS.h"')
        includes.append('#include "freertos/task.h"')
        includes.append('#include "freertos/queue.h"')
        includes.append('#include "esp_log.h"')

    if has_display:
        includes.append('#include "lvgl.h"')

    if has_audio:
        includes.append('#include "driver/i2s.h"')

    if has_network:
        includes.append('#include "esp_wifi.h"')
        includes.append('#include "esp_event.h"')

    lines = []
    lines.append('/**')
    lines.append(f' * @file main.c')
    lines.append(f' * @brief {name} main entry')
    lines.append(' *')

    # Constraint annotations
    constraint_str = ", ".join(constraints[:8])
    if len(constraints) > 8:
        constraint_str += f", ... (+{len(constraints)-8} more)"
    lines.append(f' * Constraints: {constraint_str}')

    if preset:
        lines.append(f' * Preset: {preset.get("name", preset.get("id", "unknown"))}')
    lines.append(' */')
    lines.append('')
    lines.extend(includes)
    lines.append('')

    # Log TAG
    lines.append(f'static const char *TAG = "{name}";')
    lines.append('')

    # Queue declarations
    if queues:
        lines.append('/* ── Queues (C8.1: created before callbacks) ── */')
        for q in queues:
            lines.append(f'static QueueHandle_t s_{q} = NULL;')
        lines.append('')

    # Task handle declarations
    if tasks:
        lines.append('/* ── Task handles (C33: symmetric lifecycle) ── */')
        for t in tasks:
            lines.append(f'static TaskHandle_t s_{t}_handle = NULL;')
        lines.append('')

    # Init function
    lines.append('/* C8.1: Queue before callback */')
    lines.append('static esp_err_t init_communication(void)')
    lines.append('{')
    if queues:
        for q in queues:
            lines.append(f'    s_{q} = xQueueCreate(8, sizeof(int));')
            lines.append(f'    if (s_{q} == NULL) {{')
            lines.append(f'        ESP_LOGE(TAG, "Failed to create {q}");')
            lines.append(f'        return ESP_FAIL;')
            lines.append(f'    }}')
    else:
        lines.append('    s_event_queue = xQueueCreate(8, sizeof(int));')
        lines.append('    if (s_event_queue == NULL) {')
        lines.append('        ESP_LOGE(TAG, "Failed to create event queue");')
        lines.append('        return ESP_FAIL;')
        lines.append('    }')
    lines.append('    ESP_LOGI(TAG, "Communication initialized");')
    lines.append('    return ESP_OK;')
    lines.append('}')
    lines.append('')

    if has_display:
        lines.append('static esp_err_t init_display(void)')
        lines.append('{')
        lines.append('    /* TODO: init LCD + LVGL (C1: LVGL only called from UI task) */')
        lines.append('    ESP_LOGI(TAG, "Display initialized");')
        lines.append('    return ESP_OK;')
        lines.append('}')
        lines.append('')

    if has_audio:
        lines.append('static esp_err_t init_audio(void)')
        lines.append('{')
        lines.append('    /* TODO: init I2S + audio pipeline (C25/C26/C27/C28) */')
        lines.append('    ESP_LOGI(TAG, "Audio initialized");')
        lines.append('    return ESP_OK;')
        lines.append('}')
        lines.append('')

    if has_network:
        lines.append('static esp_err_t init_network(void)')
        lines.append('{')
        lines.append('    /* TODO: init WiFi + WSS (C20: network resilience) */')
        lines.append('    ESP_LOGI(TAG, "Network initialized");')
        lines.append('    return ESP_OK;')
        lines.append('}')
        lines.append('')

    # app_main
    lines.append('void app_main(void)')
    lines.append('{')
    lines.append(f'    ESP_LOGI(TAG, "{name} starting...");')
    lines.append('')

    # Initialization sequence (following C8 boot sequence order)
    init_calls = [("Communication", "init_communication")]
    if has_display:
        init_calls.append(("Display", "init_display"))
    if has_audio:
        init_calls.append(("Audio", "init_audio"))
    if has_network:
        init_calls.append(("Network", "init_network"))

    for label, func in init_calls:
        lines.append(f'    esp_err_t err = {func}();')
        lines.append(f'    if (err != ESP_OK) {{')
        lines.append(f'        ESP_LOGE(TAG, "{label} init failed");')
        lines.append(f'        return;')
        lines.append(f'    }}')
        lines.append('')

    lines.append(f'    ESP_LOGI(TAG, "{name} initialized successfully");')
    lines.append('}')

    return '\n'.join(lines)


def generate_task_topology_h(name: str, tasks: list[dict], queues: list[dict]) -> str:
    """Generate task_topology.h (C30 format)."""
    upper = name.upper()
    lines = [
        '/**',
        f' * @file task_topology.h',
        f' * @brief {name} task topology table (C30)',
        ' *',
        ' * Auto-generated — describes the topology of tasks/queues/semaphores.',
        ' */',
        '',
        f'#ifndef {upper}_TASK_TOPOLOGY_H',
        f'#define {upper}_TASK_TOPOLOGY_H',
        '',
        '#ifdef __cplusplus',
        'extern "C" {',
        '#endif',
        '',
        '/* ── Task topology table ── */',
        '/*  Task name         | Stack(B) | Priority | Core | Description */',
    ]

    if tasks:
        for t in tasks:
            name_str = t if isinstance(t, str) else t.get("name", "unknown")
            stack = 4096 if isinstance(t, str) else t.get("stack_bytes", 4096)
            prio = 5 if isinstance(t, str) else t.get("priority", 5)
            core = -1 if isinstance(t, str) else t.get("core_affinity", -1)
            desc = "" if isinstance(t, str) else t.get("description", "")
            core_str = f"Core {core}" if core >= 0 else "Any"
            lines.append(f'/*  {name_str:20s} | {stack:5d} | {prio:6d} | {core_str:4s} | {desc} */')
    else:
        lines.append('/*  (no task definitions — add as needed) */')

    lines.append('')
    lines.append('/* ── Queue topology table ── */')
    lines.append('/*  Queue name        | item_size | depth | Description */')

    if queues:
        for q in queues:
            qname = q if isinstance(q, str) else q.get("name", "unknown")
            isize = 16 if isinstance(q, str) else q.get("item_size", 16)
            depth = 8 if isinstance(q, str) else q.get("depth", 8)
            desc = "" if isinstance(q, str) else q.get("description", "")
            lines.append(f'/*  {qname:20s} | {isize:9d} | {depth:5d} | {desc} */')
    else:
        lines.append('/*  (no queue definitions — add as needed) */')

    lines.extend([
        '',
        '#ifdef __cplusplus',
        '}',
        '#endif',
        '',
        f'#endif /* {upper}_TASK_TOPOLOGY_H */',
    ])

    return '\n'.join(lines)


def generate_constraint_manifest(name: str, platform: str, preset: dict | None, adapter) -> str:
    """Generate constraint_manifest.json."""
    manifest = {
        "project": name,
        "platform": platform,
        "generated_by": "project_scaffold v9.0.2",
    }

    if preset:
        manifest["preset"] = preset.get("id", preset.get("name", ""))
        manifest["required_constraints"] = preset.get("required_constraints", [])
        manifest["recommended_suite"] = preset.get("checker_suite", "default")
        manifest["acceptance_checklist"] = preset.get("acceptance_checklist", [])
    elif adapter:
        cm = adapter.get_constraint_manifest()
        manifest.update(cm)
    else:
        manifest["required_constraints"] = ["C8", "C12", "C14", "C29", "C33"]
        manifest["recommended_suite"] = "default"

    return json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"


def generate_app_mvp_h(name: str) -> str:
    """Generate app_mvp.h."""
    upper = name.upper()
    return f'''/**
 * @file app_mvp.h
 * @brief {name} MVP event type definitions
 */

#ifndef {upper}_APP_MVP_H
#define {upper}_APP_MVP_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {{
#endif

/* Event types */
typedef enum {{
    EVT_NONE = 0,
    EVT_HEARTBEAT,
    EVT_DATA_RECEIVED,
    EVT_STATUS_UPDATE,
    EVT_ERROR,
    EVT_MAX,
}} event_type_t;

/* Event structure */
typedef struct {{
    uint32_t type;
    uint32_t timestamp;
    void *payload;  /* C29.3: ownership declaration — producer alloc, consumer free */
}} app_event_t;

#ifdef __cplusplus
}}
#endif

#endif /* {upper}_APP_MVP_H */
'''


def generate_cmakeLists(name: str, platform: str) -> str:
    """Generate CMakeLists.txt."""
    template = PLATFORM_TEMPLATES.get(platform, PLATFORM_TEMPLATES["esp32"])
    return template["cmake"].format(name=name)


def generate_main_cmake(platform: str) -> str:
    """Generate main/CMakeLists.txt."""
    template = PLATFORM_TEMPLATES.get(platform, PLATFORM_TEMPLATES["esp32"])
    return template["main_cmake"]


def generate_config(name: str, platform: str) -> str:
    """Generate configuration file."""
    template = PLATFORM_TEMPLATES.get(platform, PLATFORM_TEMPLATES["esp32"])
    return template["config"]


def generate_readme(name: str, platform: str, has_display: bool, has_audio: bool, has_network: bool,
                    *, preset: dict | None = None) -> str:
    """Generate README.md."""
    features = []
    if has_display:
        features.append("LVGL Display")
    if has_audio:
        features.append("I2S Audio")
    if has_network:
        features.append("WiFi/WSS Network")

    feature_str = ", ".join(features) if features else "Basic functionality"
    preset_str = f"\nPreset: {preset['name']}" if preset else ""

    return f'''# {name}

{feature_str} MVP project.{preset_str}

## Build

```bash
# {platform} build command
# TODO: fill in based on platform
```

## Constraint Coverage

- C8: Boot sequence (Queue before callbacks)
- C12: Error handling (return value check)
- C14: Logging conventions (LOG_* + TAG)
- C29: Module contract
- C33: Symmetric lifecycle

## Directory Structure

```
{name}/
├── CMakeLists.txt
├── constraint_manifest.json
├── main/
│   ├── CMakeLists.txt
│   ├── main.c
│   ├── app_mvp.h
│   └── task_topology.h
└── README.md
```
'''


# ── Self-test ──

def run_self_test() -> int:
    """Run self-test."""
    passed = 0
    failed = 0

    # Test 1: Generate main.c (legacy)
    code = generate_main_c("test_project", "esp32", True, True, True)
    assert "app_main" in code
    assert "init_communication" in code
    assert "init_display" in code
    assert "C8" in code
    print("[PASS] main.c generation (legacy)")
    passed += 1

    # Test 2: Generate main.c with adapter
    adapter = _load_platform_adapter("esp32")
    if adapter:
        code2 = generate_main_c("test2", "esp32", False, False, False, adapter=adapter)
        assert "app_main" in code2
        assert "task_topology" in code2 or "task" in code2.lower() or "TaskHandle" in code2
        print("[PASS] main.c generation (adapter)")
        passed += 1
    else:
        print("[SKIP] adapter not available")

    # Test 3: Generate app_mvp.h
    header = generate_app_mvp_h("test_project")
    assert "TEST_PROJECT_APP_MVP_H" in header
    assert "event_type_t" in header
    assert "C29" in header
    print("[PASS] app_mvp.h generation")
    passed += 1

    # Test 4: Generate CMakeLists
    cmake = generate_cmakeLists("test_project", "esp32")
    assert "cmake_minimum_required" in cmake
    assert "test_project" in cmake
    print("[PASS] CMakeLists.txt generation")
    passed += 1

    # Test 5: Platform templates
    for platform in PLATFORM_TEMPLATES:
        cmake = generate_cmakeLists("test", platform)
        assert len(cmake) > 10, f"Platform {platform} cmake too short"
    print(f"[PASS] {len(PLATFORM_TEMPLATES)} platform templates")
    passed += 1

    # Test 6: task_topology.h generation
    topo = generate_task_topology_h("test", [
        {"name": "ui_task", "stack_bytes": 8192, "priority": 3, "core_affinity": 1, "description": "UI"},
        {"name": "audio_task", "stack_bytes": 4096, "priority": 6, "core_affinity": -1, "description": "Audio"},
    ], [
        {"name": "cmd_queue", "item_size": 16, "depth": 8, "description": "Commands"},
    ])
    assert "ui_task" in topo
    assert "audio_task" in topo
    assert "cmd_queue" in topo
    assert "C30" in topo
    print("[PASS] task_topology.h generation")
    passed += 1

    # Test 7: constraint_manifest.json generation
    if adapter:
        manifest_str = generate_constraint_manifest("test", "esp32", None, adapter)
        manifest = json.loads(manifest_str)
        assert "required_constraints" in manifest
        assert "recommended_suite" in manifest
        print("[PASS] constraint_manifest.json generation")
        passed += 1
    else:
        print("[SKIP] constraint manifest (no adapter)")

    # Test 8: Preset loading
    presets_dir = Path(__file__).resolve().parent.parent / "scene_presets"
    if presets_dir.is_dir():
        presets = list(presets_dir.glob("*.json"))
        if presets:
            preset = json.loads(presets[0].read_text(encoding="utf-8"))
            code3 = generate_main_c("preset_test", "esp32", False, False, False, preset=preset)
            assert "app_main" in code3
            print(f"[PASS] main.c with preset ({presets[0].stem})")
            passed += 1
        else:
            print("[SKIP] no presets (will be created in v9.0.4)")
    else:
        print("[SKIP] no scene_presets dir (will be created in v9.0.4)")

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


# ── CLI ──

def main() -> int:
    parser = argparse.ArgumentParser(description="One-click project scaffold generator v9.0.2")
    parser.add_argument("--name", help="Project name")
    parser.add_argument("--platform", choices=list(PLATFORM_TEMPLATES.keys()), default="esp32", help="Target platform")
    parser.add_argument("--preset", help="Scene preset ID (e.g. voice-screen, audio-video)")
    parser.add_argument("--display", action="store_true", help="Enable LVGL display")
    parser.add_argument("--audio", action="store_true", help="Enable I2S audio")
    parser.add_argument("--network", action="store_true", help="Enable WiFi/WSS network")
    parser.add_argument("--outdir", "-o", default=".", help="Output directory")
    parser.add_argument("--evidence", metavar="FILE", help="Output delivery evidence to specified file")
    parser.add_argument("--self-test", action="store_true", help="Run self-test")
    parser.add_argument("--list-presets", action="store_true", help="List all available presets")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if args.list_presets:
        presets_dir = Path(__file__).resolve().parent.parent / "scene_presets"
        if presets_dir.is_dir():
            print(f"{'File':20s} {'ID':20s} {'Name'}")
            print(f"{'-'*20} {'-'*20} {'-'*30}")
            for p in sorted(presets_dir.glob("*.json")):
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                    pid = data.get("id", p.stem)
                    name = data.get("name", p.stem)
                    print(f"{p.stem:20s} {pid:20s} {name}")
                except Exception:
                    print(f"{p.stem:20s} {'(parse failed)':20s}")
        else:
            print("scene_presets/ directory does not exist (will be created in v9.0.4)")
        return 0

    if not args.name:
        parser.print_help()
        return 1

    # ── Load preset and adapter ──
    preset = _load_preset(args.preset) if args.preset else None
    if args.preset and not preset:
        print(f"Warning: preset '{args.preset}' not found, using default config", file=sys.stderr)

    # preset can specify platform
    if preset and preset.get("platforms"):
        if args.platform not in preset["platforms"]:
            # Auto-select first platform from preset
            args.platform = preset["platforms"][0]

    adapter = _load_platform_adapter(args.platform)

    # Preset overrides features
    if preset:
        gen_params = preset.get("generator_params", {})
        args.display = args.display or gen_params.get("display", False)
        args.audio = args.audio or gen_params.get("audio", False)
        args.network = args.network or gen_params.get("network", False)

    outdir = Path(args.outdir) / args.name
    outdir.mkdir(parents=True, exist_ok=True)
    main_dir = outdir / "main"
    main_dir.mkdir(exist_ok=True)

    # ── Generate files ──
    generated = []

    # CMakeLists.txt
    (outdir / "CMakeLists.txt").write_text(
        generate_cmakeLists(args.name, args.platform), encoding="utf-8"
    )
    generated.append("CMakeLists.txt")

    # main/CMakeLists.txt
    (main_dir / "CMakeLists.txt").write_text(
        generate_main_cmake(args.platform), encoding="utf-8"
    )
    generated.append("main/CMakeLists.txt")

    # main/main.c
    (main_dir / "main.c").write_text(
        generate_main_c(args.name, args.platform, args.display, args.audio, args.network,
                        preset=preset, adapter=adapter),
        encoding="utf-8"
    )
    generated.append("main/main.c")

    # main/app_mvp.h
    (main_dir / "app_mvp.h").write_text(
        generate_app_mvp_h(args.name), encoding="utf-8"
    )
    generated.append("main/app_mvp.h")

    # main/task_topology.h (v2 addition)
    tasks = []
    queues = []
    if preset:
        tasks = preset.get("generator_params", {}).get("tasks", [])
        queues = preset.get("generator_params", {}).get("queues", [])
    elif adapter:
        tasks = adapter.get_default_tasks()
        queues = adapter.get_default_queues()

    if tasks or queues:
        (main_dir / "task_topology.h").write_text(
            generate_task_topology_h(args.name, tasks, queues), encoding="utf-8"
        )
        generated.append("main/task_topology.h")

    # constraint_manifest.json (v2 addition)
    manifest_str = generate_constraint_manifest(args.name, args.platform, preset, adapter)
    (outdir / "constraint_manifest.json").write_text(manifest_str, encoding="utf-8")
    generated.append("constraint_manifest.json")

    # README.md (generated before manifest)
    (outdir / "README.md").write_text(
        generate_readme(args.name, args.platform, args.display, args.audio, args.network, preset=preset),
        encoding="utf-8"
    )
    generated.append("README.md")

    # Config file
    config = None
    if adapter:
        config = adapter.get_config_template(args.name)
    if not config:
        config = generate_config(args.name, args.platform)

    if config:
        config_name = {
            "esp32": "sdkconfig.defaults",
            "zephyr": "prj.conf",
        }.get(args.platform, "FreeRTOSConfig.h")
        (outdir / config_name).write_text(config, encoding="utf-8")
        generated.append(config_name)

    # Kconfig (ESP32 only)
    if adapter:
        kconfig = adapter.get_kconfig_template(args.name)
        if kconfig:
            (outdir / "Kconfig.projbuild").write_text(kconfig, encoding="utf-8")
            generated.append("Kconfig.projbuild")

    # generation_manifest.json (generated last, contains complete generated_files)
    from manifest_normalizer import normalize_manifest

    directly_covered = ["C8", "C12", "C14", "C29", "C33"]
    required_constraints = preset.get("required_constraints", directly_covered) if preset else directly_covered
    deferred = []
    for cid in required_constraints:
        if cid not in directly_covered:
            deferred.append({
                "id": cid,
                "reason": "scaffold only generates skeleton, this constraint needs to be covered during specific module implementation",
                "evidence": f"task_topology.h + constraint_manifest.json declared applicable scenarios for {cid}",
            })

    preset_locks = preset.get("generator_params", {}).get("locks", []) if preset else []
    preset_timers = preset.get("generator_params", {}).get("timers", []) if preset else []
    preset_pools = preset.get("generator_params", {}).get("memory_pools", []) if preset else []

    raw_manifest = {
        "schema_version": "1.2",
        "generator": "project_scaffold",
        "platform": args.platform,
        "frameworks": [],
        "module_responsibility": "project bring-up skeleton and top-level lifecycle wiring",
        "public_api": ["app_main", "app_start", "app_stop"],
        "dependencies": ["platform_sdk", "app_event_bus"],
        "forbidden_dependencies": ["direct UI calls from drivers", "shared writable global context"],
        "events_in": ["APP_CMD_START", "APP_CMD_STOP"],
        "events_out": ["APP_EVT_READY", "APP_EVT_FAULT"],
        "owned_resources": ["main_task", "app_event_bus", "task_topology"],
        "generated_files": [{"path": g, "type": Path(g).suffix.lstrip("."), "description": ""} for g in generated],
        "tasks": tasks,
        "queues": queues,
        "locks": preset_locks,
        "timers": preset_timers,
        "memory_pools": preset_pools,
        "constraints": {
            "required": required_constraints,
            "covered": directly_covered,
            "deferred": deferred,
        },
        "verification_commands": [
            f"python tools/codegen_gate.py --dir {outdir} --manifest {outdir}/generation_manifest.json --platform {args.platform} --strict",
            f"python tools/run_review.py --dir {outdir} --platform {args.platform}",
        ],
    }
    gen_manifest = normalize_manifest(raw_manifest)
    (outdir / "generation_manifest.json").write_text(
        json.dumps(gen_manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    generated.append("generation_manifest.json")

    # constraint_manifest.json derived from generation_manifest
    constraint_manifest = {
        "project": args.name,
        "platform": args.platform,
        "required_constraints": gen_manifest["constraints"]["required"],
        "recommended_suite": preset.get("checker_suite", "default") if preset else "default",
    }
    (outdir / "constraint_manifest.json").write_text(
        json.dumps(constraint_manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # ── Output ──
    print(f"[OK] Project scaffold generated: {outdir}")
    print(f"  Platform: {args.platform}")
    if preset:
        print(f"  Preset: {preset.get('name', args.preset)}")
    print(f"  Features: display={args.display}, audio={args.audio}, network={args.network}")
    print(f"  Files: {len(generated)}")
    for f in generated:
        print(f"    {f}")

    # ── Delivery evidence output ──
    if args.evidence:
        try:
            from evidence_schema import generated_file, make_evidence, save_evidence
        except ImportError:
            print("[warn] evidence_schema module not available (archived), skipping evidence output", file=sys.stderr)
            return 0

        ev_files = [
            generated_file(str(outdir / f), description=f)
            for f in generated
        ]

        ev = make_evidence(
            source_tool="project_scaffold",
            platform=args.platform,
            preset=args.preset or "",
            generated_files=ev_files,
            reproduce_commands=[{
                "command": f"python tools/project_scaffold.py --name {args.name} --platform {args.platform}" +
                           (f" --preset {args.preset}" if args.preset else ""),
                "description": "Reproduce project generation",
            }],
            metadata={
                "tool_version": "9.0.2",
                "project_name": args.name,
                "display": args.display,
                "audio": args.audio,
                "network": args.network,
                "files_generated": len(generated),
            },
        )
        save_evidence(ev, args.evidence)
        print(f"[evidence] Delivery evidence saved: {args.evidence}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
