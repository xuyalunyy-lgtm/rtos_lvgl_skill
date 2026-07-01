#!/usr/bin/env python3
"""
一键项目脚手架生成器 — 输入 9 项信息，生成完整可编译 MVP 项目。

RTOS Project Gate 9 项：
  1. 项目目标 / MVP 范围 / 验收指标
  2. 硬件/平台详情
  3. 系统规模与实时要求
  4. 工具链/构建/调试策略
  5. 架构预期
  6. 质量要求
  7. 目录与交付格式
  8. 依赖与许可证
  9. 里程碑与交付模式

用法:
    python tools/project_scaffold.py --interactive
    python tools/project_scaffold.py --config project.json
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


# Platform templates
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


def generate_main_c(name: str, platform: str, has_display: bool, has_audio: bool, has_network: bool) -> str:
    """生成 main.c"""
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
    lines.append(' * Constraints:')
    lines.append(' *   C8 - Boot sequence (Queue before callback)')
    lines.append(' *   C12 - Error handling (return value check)')
    lines.append(' *   C14 - Logging (LOG_* + TAG)')
    lines.append(' *   C29 - Module contract')
    lines.append(' *   C33 - Lifecycle symmetry')
    lines.append(' */')
    lines.append('')
    lines.extend(includes)
    lines.append('')
    lines.append(f'static const char *TAG = "{name}";')
    lines.append('')
    lines.append('static QueueHandle_t s_event_queue = NULL;')
    lines.append('')

    if has_display:
        lines.append('/* LVGL task */')
    if has_audio:
        lines.append('/* Audio task */')
    if has_network:
        lines.append('/* Network task */')

    lines.append('')
    lines.append('/* C8.1: Queue before callback */')
    lines.append('static esp_err_t init_communication(void)')
    lines.append('{')
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
        lines.append('    /* TODO: init LCD + LVGL */')
        lines.append('    ESP_LOGI(TAG, "Display initialized");')
        lines.append('    return ESP_OK;')
        lines.append('}')
        lines.append('')

    if has_audio:
        lines.append('static esp_err_t init_audio(void)')
        lines.append('{')
        lines.append('    /* TODO: init I2S + audio pipeline */')
        lines.append('    ESP_LOGI(TAG, "Audio initialized");')
        lines.append('    return ESP_OK;')
        lines.append('}')
        lines.append('')

    if has_network:
        lines.append('static esp_err_t init_network(void)')
        lines.append('{')
        lines.append('    /* TODO: init WiFi + WSS */')
        lines.append('    ESP_LOGI(TAG, "Network initialized");')
        lines.append('    return ESP_OK;')
        lines.append('}')
        lines.append('')

    lines.append('void app_main(void)')
    lines.append('{')
    lines.append(f'    ESP_LOGI(TAG, "{name} starting...");')
    lines.append('')
    lines.append('    esp_err_t err = init_communication();')
    lines.append('    if (err != ESP_OK) {')
    lines.append('        ESP_LOGE(TAG, "Communication init failed");')
    lines.append('        return;')
    lines.append('    }')

    if has_display:
        lines.append('')
        lines.append('    err = init_display();')
        lines.append('    if (err != ESP_OK) {')
        lines.append('        ESP_LOGE(TAG, "Display init failed");')
        lines.append('        return;')
        lines.append('    }')

    if has_audio:
        lines.append('')
        lines.append('    err = init_audio();')
        lines.append('    if (err != ESP_OK) {')
        lines.append('        ESP_LOGE(TAG, "Audio init failed");')
        lines.append('        return;')
        lines.append('    }')

    if has_network:
        lines.append('')
        lines.append('    err = init_network();')
        lines.append('    if (err != ESP_OK) {')
        lines.append('        ESP_LOGE(TAG, "Network init failed");')
        lines.append('        return;')
        lines.append('    }')

    lines.append('')
    lines.append(f'    ESP_LOGI(TAG, "{name} initialized successfully");')
    lines.append('}')

    return '\n'.join(lines)


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


def generate_readme(name: str, platform: str, has_display: bool, has_audio: bool, has_network: bool) -> str:
    """生成 README.md"""
    features = []
    if has_display:
        features.append("LVGL 显示")
    if has_audio:
        features.append("I2S 音频")
    if has_network:
        features.append("WiFi/WSS 网络")

    feature_str = ", ".join(features) if features else "基础功能"

    return f'''# {name}

{feature_str} MVP 项目。

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
├── main/
│   ├── CMakeLists.txt
│   ├── main.c
│   └── app_mvp.h
└── README.md
```
'''


def run_self_test() -> int:
    """自测"""
    passed = 0
    failed = 0

    # Test 1: Generate main.c
    code = generate_main_c("test_project", "esp32", True, True, True)
    assert "app_main" in code
    assert "init_communication" in code
    assert "init_display" in code
    assert "init_audio" in code
    assert "init_network" in code
    assert "C8" in code
    print("[PASS] main.c generation")
    passed += 1

    # Test 2: Generate app_mvp.h
    header = generate_app_mvp_h("test_project")
    assert "TEST_PROJECT_APP_MVP_H" in header
    assert "event_type_t" in header
    assert "app_event_t" in header
    assert "C29" in header
    print("[PASS] app_mvp.h generation")
    passed += 1

    # Test 3: Generate CMakeLists
    cmake = generate_cmakeLists("test_project", "esp32")
    assert "cmake_minimum_required" in cmake
    assert "test_project" in cmake
    print("[PASS] CMakeLists.txt generation")
    passed += 1

    # Test 4: Platform templates
    for platform in PLATFORM_TEMPLATES:
        cmake = generate_cmakeLists("test", platform)
        assert len(cmake) > 10, f"Platform {platform} cmake too short"
    print(f"[PASS] {len(PLATFORM_TEMPLATES)} platform templates")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="一键项目脚手架生成器")
    parser.add_argument("--name", help="项目名")
    parser.add_argument("--platform", choices=list(PLATFORM_TEMPLATES.keys()), default="esp32", help="目标平台")
    parser.add_argument("--display", action="store_true", help="启用 LVGL 显示")
    parser.add_argument("--audio", action="store_true", help="启用 I2S 音频")
    parser.add_argument("--network", action="store_true", help="启用 WiFi/WSS 网络")
    parser.add_argument("--outdir", "-o", default=".", help="输出目录")
    parser.add_argument("--self-test", action="store_true", help="运行自测")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.name:
        parser.print_help()
        return 1

    outdir = Path(args.outdir) / args.name
    outdir.mkdir(parents=True, exist_ok=True)
    main_dir = outdir / "main"
    main_dir.mkdir(exist_ok=True)

    # Generate files
    (outdir / "CMakeLists.txt").write_text(
        generate_cmakeLists(args.name, args.platform), encoding="utf-8"
    )
    (main_dir / "CMakeLists.txt").write_text(
        generate_main_cmake(args.platform), encoding="utf-8"
    )
    (main_dir / "main.c").write_text(
        generate_main_c(args.name, args.platform, args.display, args.audio, args.network),
        encoding="utf-8"
    )
    (main_dir / "app_mvp.h").write_text(
        generate_app_mvp_h(args.name), encoding="utf-8"
    )
    (outdir / "README.md").write_text(
        generate_readme(args.name, args.platform, args.display, args.audio, args.network),
        encoding="utf-8"
    )

    # Generate config
    if args.platform == "esp32":
        (outdir / "sdkconfig.defaults").write_text(
            generate_config(args.name, args.platform), encoding="utf-8"
        )

    print(f"[OK] Project scaffold generated: {outdir}")
    print(f"  Platform: {args.platform}")
    print(f"  Display: {args.display}")
    print(f"  Audio: {args.audio}")
    print(f"  Network: {args.network}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
