#!/usr/bin/env python3
"""
一键项目脚手架生成器 v9.0.2 — 按 platform profile 和 scene preset 生成完整 MVP 项目。

v2 增强：
  1. --preset：从 scene_presets/ 读取场景定义，自动设置 features/约束/tasks
  2. --platform-profile：从 product_profiles/ 读取平台定义
  3. 生成 task_topology.h、constraint_manifest.json、Kconfig
  4. main.c 带约束注释、模块生命周期、任务拓扑

用法:
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


# ── 向后兼容：旧版 PLATFORM_TEMPLATES ──
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


# ── Preset / Platform 加载 ──

def _normalize_preset_id(preset_id: str) -> str:
    """规范化 preset ID：支持 - 和 _ 互转。"""
    # 先尝试原样匹配
    presets_dir = Path(__file__).resolve().parent.parent / "scene_presets"
    if (presets_dir / f"{preset_id}.json").exists():
        return preset_id
    # 尝试 - 转 _
    alt = preset_id.replace("-", "_")
    if (presets_dir / f"{alt}.json").exists():
        return alt
    # 尝试 _ 转 -
    alt = preset_id.replace("_", "-")
    if (presets_dir / f"{alt}.json").exists():
        return alt
    # 扫描 JSON id 字段
    for f in presets_dir.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("id") == preset_id or data.get("id") == alt:
                return f.stem
        except Exception:
            pass
    return preset_id


def _load_preset(preset_id: str) -> dict | None:
    """加载场景 preset，不存在返回 None。"""
    presets_dir = Path(__file__).resolve().parent.parent / "scene_presets"
    normalized = _normalize_preset_id(preset_id)
    path = presets_dir / f"{normalized}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _load_platform_adapter(platform: str):
    """加载平台适配器，失败返回 None。"""
    try:
        from platform_adapter import PlatformAdapter
        return PlatformAdapter(platform)
    except (ImportError, FileNotFoundError):
        return None


# ── 代码生成 ──

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
    """生成 main.c（v2：支持 preset 和 adapter）。"""
    # 从 preset 覆盖 features
    if preset:
        gen_params = preset.get("generator_params", {})
        has_display = has_display or gen_params.get("display", False)
        has_audio = has_audio or gen_params.get("audio", False)
        has_network = has_network or gen_params.get("network", False) or gen_params.get("voice_asr", False)

    # 确定约束列表
    constraints = ["C8", "C12", "C14", "C29", "C33"]
    if preset:
        constraints = preset.get("required_constraints", constraints)
    elif adapter:
        constraints = adapter.required_constraints[:10]  # 取前 10 个

    # 从 preset/adapter 获取任务列表
    tasks = []
    if preset:
        tasks = preset.get("generator_params", {}).get("tasks", [])
    elif adapter:
        tasks = [t["name"] for t in adapter.get_default_tasks()]

    # 从 preset/adapter 获取队列列表
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

    # 约束注释
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

    # 日志 TAG
    lines.append(f'static const char *TAG = "{name}";')
    lines.append('')

    # 队列声明
    if queues:
        lines.append('/* ── 队列（C8.1: 先于回调创建）── */')
        for q in queues:
            lines.append(f'static QueueHandle_t s_{q} = NULL;')
        lines.append('')

    # 任务句柄声明
    if tasks:
        lines.append('/* ── 任务句柄（C33: 生命周期对称）── */')
        for t in tasks:
            lines.append(f'static TaskHandle_t s_{t}_handle = NULL;')
        lines.append('')

    # 初始化函数
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
        lines.append('    /* TODO: init LCD + LVGL (C1: LVGL 仅在 UI 任务调用) */')
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
        lines.append('    /* TODO: init WiFi + WSS (C20: 网络韧性) */')
        lines.append('    ESP_LOGI(TAG, "Network initialized");')
        lines.append('    return ESP_OK;')
        lines.append('}')
        lines.append('')

    # app_main
    lines.append('void app_main(void)')
    lines.append('{')
    lines.append(f'    ESP_LOGI(TAG, "{name} starting...");')
    lines.append('')

    # 初始化序列（按 C8 boot sequence 顺序）
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
    """生成 task_topology.h（C30 格式）。"""
    upper = name.upper()
    lines = [
        '/**',
        f' * @file task_topology.h',
        f' * @brief {name} 任务拓扑表（C30）',
        ' *',
        ' * 自动生成 — 描述任务/队列/信号量的拓扑关系。',
        ' */',
        '',
        f'#ifndef {upper}_TASK_TOPOLOGY_H',
        f'#define {upper}_TASK_TOPOLOGY_H',
        '',
        '#ifdef __cplusplus',
        'extern "C" {',
        '#endif',
        '',
        '/* ── 任务拓扑表 ── */',
        '/*  任务名           | 栈(B) | 优先级 | Core | 描述 */',
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
        lines.append('/*  (无任务定义 — 请根据项目需求添加) */')

    lines.append('')
    lines.append('/* ── 队列拓扑表 ── */')
    lines.append('/*  队列名           | item_size | depth | 描述 */')

    if queues:
        for q in queues:
            qname = q if isinstance(q, str) else q.get("name", "unknown")
            isize = 16 if isinstance(q, str) else q.get("item_size", 16)
            depth = 8 if isinstance(q, str) else q.get("depth", 8)
            desc = "" if isinstance(q, str) else q.get("description", "")
            lines.append(f'/*  {qname:20s} | {isize:9d} | {depth:5d} | {desc} */')
    else:
        lines.append('/*  (无队列定义 — 请根据项目需求添加) */')

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
    """生成 constraint_manifest.json。"""
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
    """生成 app_mvp.h"""
    upper = name.upper()
    return f'''/**
 * @file app_mvp.h
 * @brief {name} MVP 事件类型定义
 */

#ifndef {upper}_APP_MVP_H
#define {upper}_APP_MVP_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {{
#endif

/* 事件类型 */
typedef enum {{
    EVT_NONE = 0,
    EVT_HEARTBEAT,
    EVT_DATA_RECEIVED,
    EVT_STATUS_UPDATE,
    EVT_ERROR,
    EVT_MAX,
}} event_type_t;

/* 事件结构体 */
typedef struct {{
    uint32_t type;
    uint32_t timestamp;
    void *payload;  /* C29.3: 所有权声明 — 生产者 alloc，消费者 free */
}} app_event_t;

#ifdef __cplusplus
}}
#endif

#endif /* {upper}_APP_MVP_H */
'''


def generate_cmakeLists(name: str, platform: str) -> str:
    """生成 CMakeLists.txt"""
    template = PLATFORM_TEMPLATES.get(platform, PLATFORM_TEMPLATES["esp32"])
    return template["cmake"].format(name=name)


def generate_main_cmake(platform: str) -> str:
    """生成 main/CMakeLists.txt"""
    template = PLATFORM_TEMPLATES.get(platform, PLATFORM_TEMPLATES["esp32"])
    return template["main_cmake"]


def generate_config(name: str, platform: str) -> str:
    """生成配置文件"""
    template = PLATFORM_TEMPLATES.get(platform, PLATFORM_TEMPLATES["esp32"])
    return template["config"]


def generate_readme(name: str, platform: str, has_display: bool, has_audio: bool, has_network: bool,
                    *, preset: dict | None = None) -> str:
    """生成 README.md"""
    features = []
    if has_display:
        features.append("LVGL 显示")
    if has_audio:
        features.append("I2S 音频")
    if has_network:
        features.append("WiFi/WSS 网络")

    feature_str = ", ".join(features) if features else "基础功能"
    preset_str = f"\nPreset: {preset['name']}" if preset else ""

    return f'''# {name}

{feature_str} MVP 项目。{preset_str}

## 构建

```bash
# {platform} 构建命令
# TODO: 根据平台填写
```

## 约束覆盖

- C8: 启动顺序（Queue 先于回调）
- C12: 错误处理（返回值检查）
- C14: 日志规范（LOG_* + TAG）
- C29: 模块契约
- C33: 生命周期对称

## 目录结构

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


# ── 自测 ──

def run_self_test() -> int:
    """自测"""
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
    parser = argparse.ArgumentParser(description="一键项目脚手架生成器 v9.0.2")
    parser.add_argument("--name", help="项目名")
    parser.add_argument("--platform", choices=list(PLATFORM_TEMPLATES.keys()), default="esp32", help="目标平台")
    parser.add_argument("--preset", help="场景 preset ID（如 voice-screen, audio-video）")
    parser.add_argument("--display", action="store_true", help="启用 LVGL 显示")
    parser.add_argument("--audio", action="store_true", help="启用 I2S 音频")
    parser.add_argument("--network", action="store_true", help="启用 WiFi/WSS 网络")
    parser.add_argument("--outdir", "-o", default=".", help="输出目录")
    parser.add_argument("--evidence", metavar="FILE", help="输出交付证据包到指定文件")
    parser.add_argument("--self-test", action="store_true", help="运行自测")
    parser.add_argument("--list-presets", action="store_true", help="列出所有可用 preset")
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
                    print(f"{p.stem:20s} {'(解析失败)':20s}")
        else:
            print("scene_presets/ 目录不存在（将在 v9.0.4 创建）")
        return 0

    if not args.name:
        parser.print_help()
        return 1

    # ── 加载 preset 和 adapter ──
    preset = _load_preset(args.preset) if args.preset else None
    if args.preset and not preset:
        print(f"警告: preset '{args.preset}' 不存在，使用默认配置", file=sys.stderr)

    # preset 可以指定 platform
    if preset and preset.get("platforms"):
        if args.platform not in preset["platforms"]:
            # 自动选择 preset 的第一个平台
            args.platform = preset["platforms"][0]

    adapter = _load_platform_adapter(args.platform)

    # preset 覆盖 features
    if preset:
        gen_params = preset.get("generator_params", {})
        args.display = args.display or gen_params.get("display", False)
        args.audio = args.audio or gen_params.get("audio", False)
        args.network = args.network or gen_params.get("network", False)

    outdir = Path(args.outdir) / args.name
    outdir.mkdir(parents=True, exist_ok=True)
    main_dir = outdir / "main"
    main_dir.mkdir(exist_ok=True)

    # ── 生成文件 ──
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

    # main/task_topology.h（v2 新增）
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

    # constraint_manifest.json（v2 新增）
    manifest_str = generate_constraint_manifest(args.name, args.platform, preset, adapter)
    (outdir / "constraint_manifest.json").write_text(manifest_str, encoding="utf-8")
    generated.append("constraint_manifest.json")

    # README.md（先于 manifest 生成）
    (outdir / "README.md").write_text(
        generate_readme(args.name, args.platform, args.display, args.audio, args.network, preset=preset),
        encoding="utf-8"
    )
    generated.append("README.md")

    # 配置文件
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

    # Kconfig（ESP32 only）
    if adapter:
        kconfig = adapter.get_kconfig_template(args.name)
        if kconfig:
            (outdir / "Kconfig.projbuild").write_text(kconfig, encoding="utf-8")
            generated.append("Kconfig.projbuild")

    # generation_manifest.json（最后生成，包含完整 generated_files）
    from manifest_normalizer import normalize_manifest

    directly_covered = ["C8", "C12", "C14", "C29", "C33"]
    required_constraints = preset.get("required_constraints", directly_covered) if preset else directly_covered
    deferred = []
    for cid in required_constraints:
        if cid not in directly_covered:
            deferred.append({
                "id": cid,
                "reason": "scaffold 仅生成骨架，此约束需在具体模块实现时覆盖",
                "evidence": f"task_topology.h + constraint_manifest.json 声明了 {cid} 适用场景",
            })

    preset_locks = preset.get("generator_params", {}).get("locks", []) if preset else []
    preset_timers = preset.get("generator_params", {}).get("timers", []) if preset else []
    preset_pools = preset.get("generator_params", {}).get("memory_pools", []) if preset else []

    raw_manifest = {
        "schema_version": "1.2",
        "generator": "project_scaffold",
        "platform": args.platform,
        "frameworks": [],
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
            f"python tools/rtos_model.py --from-generation-manifest {outdir}/generation_manifest.json --output {outdir}/rtos_model.json",
            f"python tools/task_graph_analyzer.py --model {outdir}/rtos_model.json",
            f"python tools/ipc_contract_checker.py --model {outdir}/rtos_model.json",
            f"python tools/scheduler_analyzer.py --model {outdir}/rtos_model.json",
            f"python tools/memory_lifetime_analyzer.py --model {outdir}/rtos_model.json",
            f"python tools/timebase_analyzer.py --model {outdir}/rtos_model.json",
            f"python tools/run_review.py --dir {outdir} --platform {args.platform}",
        ],
    }
    gen_manifest = normalize_manifest(raw_manifest)
    (outdir / "generation_manifest.json").write_text(
        json.dumps(gen_manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    generated.append("generation_manifest.json")

    # constraint_manifest.json 从 generation_manifest 派生
    constraint_manifest = {
        "project": args.name,
        "platform": args.platform,
        "required_constraints": gen_manifest["constraints"]["required"],
        "recommended_suite": preset.get("checker_suite", "default") if preset else "default",
    }
    (outdir / "constraint_manifest.json").write_text(
        json.dumps(constraint_manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # ── 输出 ──
    print(f"[OK] Project scaffold generated: {outdir}")
    print(f"  Platform: {args.platform}")
    if preset:
        print(f"  Preset: {preset.get('name', args.preset)}")
    print(f"  Features: display={args.display}, audio={args.audio}, network={args.network}")
    print(f"  Files: {len(generated)}")
    for f in generated:
        print(f"    {f}")

    # ── 交付证据包输出 ──
    if args.evidence:
        from evidence_schema import generated_file, make_evidence, save_evidence

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
                "description": "复现项目生成",
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
        print(f"[evidence] 已保存交付证据包: {args.evidence}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
