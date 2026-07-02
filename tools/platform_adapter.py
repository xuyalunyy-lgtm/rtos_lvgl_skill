#!/usr/bin/env python3
"""
平台适配器 v9.0.2 — 统一平台模板/配置/生成器接口。

从 product_profiles/ 加载平台定义，为 project_scaffold 和 module_contract_gen
提供统一的模板生成接口。

用法:
    python tools/platform_adapter.py --list
    python tools/platform_adapter.py esp32 --templates
    python tools/platform_adapter.py --self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROFILES_DIR = Path(__file__).resolve().parent.parent / "product_profiles"
PRESETS_DIR = Path(__file__).resolve().parent.parent / "scene_presets"


class PlatformAdapter:
    """统一平台适配器，封装 product profile 为生成器接口。"""

    def __init__(self, platform: str, profile: dict | None = None):
        self.platform = platform
        self.profile = profile or self._load_profile(platform)

    @staticmethod
    def _load_profile(platform: str) -> dict:
        path = PROFILES_DIR / f"{platform}.json"
        if not path.exists():
            raise FileNotFoundError(f"产品 profile 不存在: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    # ── 属性访问 ──

    @property
    def name(self) -> str:
        return self.profile.get("name", self.platform)

    @property
    def features(self) -> dict[str, bool]:
        return self.profile.get("features", {})

    @property
    def required_constraints(self) -> list[str]:
        return self.profile.get("required_constraints", [])

    @property
    def optional_constraints(self) -> list[str]:
        return self.profile.get("optional_constraints", [])

    @property
    def common_pitfalls(self) -> list[str]:
        return self.profile.get("common_pitfalls", [])

    @property
    def stack_recommendations(self) -> dict:
        return self.profile.get("stack_recommendations", {})

    def _get_stack_bytes(self, task_type: str, default: int = 4096) -> int:
        """安全获取栈大小，兼容 {min_bytes, recommended_bytes} 和纯 int 两种格式。"""
        rec = self.stack_recommendations.get(task_type)
        if isinstance(rec, int):
            return rec
        if isinstance(rec, dict):
            return rec.get("recommended_bytes", default)
        return default

    @property
    def task_priority_style(self) -> str:
        return self.profile.get("task_priority_style", "higher_is_higher")

    # ── 模板生成 ──

    def get_cmake_template(self, project_name: str) -> str:
        """生成根 CMakeLists.txt。"""
        templates = {
            "esp32": f"cmake_minimum_required(VERSION 3.16)\ninclude($ENV{{IDF_PATH}}/tools/cmake/project.cmake)\nproject({project_name})",
            "stm32": f"cmake_minimum_required(VERSION 3.16)\nproject({project_name} C ASM)\nset(CMAKE_C_STANDARD 11)\n",
            "zephyr": f"cmake_minimum_required(VERSION 3.20.0)\nfind_package(Zephyr REQUIRED HINTS $ENV{{ZEPHYR_BASE}})\nproject({project_name})\n",
            "jl": f"# JL AC79 Build System\n",
            "bk": f"# BK7231 Build System\n",
        }
        return templates.get(self.platform, f"# {self.platform} Build System\nproject({project_name})\n")

    def get_main_cmake_template(self) -> str:
        """生成 main/ 子目录 CMakeLists.txt。"""
        templates = {
            "esp32": 'idf_component_register(SRCS "main.c" INCLUDE_DIRS ".")',
            "stm32": "add_executable(${PROJECT_NAME}.elf main.c)\n",
            "zephyr": "target_sources(app PRIVATE main.c)\n",
            "jl": "obj-y += main.o\n",
            "bk": "obj-y += main.o\n",
        }
        return templates.get(self.platform, "# main component\n")

    def get_config_template(self, project_name: str) -> str | None:
        """生成平台配置文件（sdkconfig.defaults / prj.conf 等）。"""
        if self.platform == "esp32":
            return self._esp32_sdkconfig()
        if self.platform == "zephyr":
            return self._zephyr_prj_conf()
        if self.platform == "stm32":
            return self._stm32_freertos_config()
        return None

    def _esp32_sdkconfig(self) -> str:
        lines = [
            "# ESP-IDF Configuration",
            "CONFIG_FREERTOS_HZ=1000",
            "CONFIG_ESP_TASK_WDT_TIMEOUT_S=30",
        ]
        if self.features.get("wifi"):
            lines.append("CONFIG_ESP_WIFI_TASK_PINNED_TO_CORE_1=y")
        if self.features.get("psram"):
            lines.append("CONFIG_SPIRAM=y")
            lines.append("CONFIG_SPIRAM_USE_MALLOC=y")
        if self.features.get("lvgl"):
            lines.append("CONFIG_LV_COLOR_DEPTH_16=y")
        if self.features.get("ota"):
            lines.append("CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE=y")
        return "\n".join(lines) + "\n"

    def _zephyr_prj_conf(self) -> str:
        lines = [
            "# Zephyr Configuration",
            "CONFIG_HEAP_MEM_POOL_SIZE=8192",
            "CONFIG_LOG=y",
        ]
        if self.features.get("wifi"):
            lines.append("CONFIG_WIFI=y")
        if self.features.get("lvgl"):
            lines.append("CONFIG_LV_Z_HOR_RES_MAX=320")
        return "\n".join(lines) + "\n"

    def _stm32_freertos_config(self) -> str:
        lines = [
            "// STM32 FreeRTOSConfig.h",
            "#define configTOTAL_HEAP_SIZE (32*1024)",
            "#define configCHECK_FOR_STACK_OVERFLOW 2",
            "#define configUSE_MUTEXES 1",
        ]
        if self.features.get("lvgl"):
            lines.append("#define configUSE_TIMERS 1")
        return "\n".join(lines) + "\n"

    def get_kconfig_template(self, project_name: str) -> str | None:
        """生成 Kconfig.projbuild（仅 ESP32）。"""
        if self.platform != "esp32":
            return None
        lines = [
            f'menu "{project_name} Configuration"',
            "",
            "    config APP_WIFI_SSID",
            '        string "WiFi SSID"',
            '        default "myssid"',
            "",
            "    config APP_WIFI_PASSWORD",
            '        string "WiFi Password"',
            '        default "mypassword"',
            "",
        ]
        if self.features.get("lvgl"):
            lines.extend([
                "    config APP_LVGL_THEME",
                '        int "LVGL Theme (0=dark, 1=light)"',
                "        default 0",
                "",
            ])
        lines.append("endmenu")
        return "\n".join(lines) + "\n"

    # ── 任务拓扑生成 ──

    def get_default_tasks(self) -> list[dict]:
        """根据平台 features 生成默认任务列表。"""
        tasks = []

        # 基础任务
        tasks.append({
            "name": "main_task",
            "stack_bytes": 4096,
            "priority": 5,
            "core_affinity": -1,
            "description": "主逻辑任务",
        })

        if self.features.get("lvgl"):
            tasks.append({
                "name": "ui_task",
                "stack_bytes": self._get_stack_bytes("lvgl", 8192),
                "priority": 3,
                "core_affinity": 1 if self.features.get("dual_core") else -1,
                "description": "LVGL UI 渲染任务",
            })

        if self.features.get("i2s_audio") or self.features.get("voice_asr") or self.features.get("audio"):
            tasks.append({
                "name": "audio_task",
                "stack_bytes": self._get_stack_bytes("audio", 4096),
                "priority": 6,
                "core_affinity": 1 if self.features.get("dual_core") else -1,
                "description": "音频采集/播放任务",
            })

        if self.features.get("wss_tls"):
            tasks.append({
                "name": "network_task",
                "stack_bytes": self._get_stack_bytes("wss_tls", 8192),
                "priority": 4,
                "core_affinity": 0 if self.features.get("dual_core") else -1,
                "description": "WSS/TLS 网络任务",
            })

        if self.features.get("ota"):
            tasks.append({
                "name": "ota_task",
                "stack_bytes": 4096,
                "priority": 2,
                "core_affinity": -1,
                "description": "OTA 升级任务（按需创建）",
            })

        return tasks

    def get_default_queues(self) -> list[dict]:
        """根据平台 features 生成默认队列列表。"""
        queues = []

        if self.features.get("lvgl"):
            queues.append({
                "name": "ui_cmd_queue",
                "item_size": 16,
                "depth": 8,
                "backpressure": "drop_oldest",
                "timeout_ms": 50,
                "description": "UI 命令队列",
            })

        if self.features.get("i2s_audio"):
            queues.append({
                "name": "audio_frame_queue",
                "item_size": 128,
                "depth": 4,
                "backpressure": "drop_oldest",
                "timeout_ms": 100,
                "description": "音频帧队列",
            })

        if self.features.get("voice_asr"):
            queues.append({
                "name": "asr_result_queue",
                "item_size": 64,
                "depth": 4,
                "backpressure": "drop_oldest",
                "timeout_ms": 200,
                "description": "ASR 识别结果队列",
            })

        return queues

    # ── 约束清单 ──

    def get_constraint_manifest(self) -> dict:
        """生成项目约束清单。"""
        return {
            "platform": self.platform,
            "required_constraints": self.required_constraints,
            "optional_constraints": self.optional_constraints,
            "excluded_constraints": self.profile.get("excluded_constraints", []),
            "recommended_suite": self._recommend_suite(),
        }

    def _recommend_suite(self) -> str:
        """根据 features 推荐 checker suite。"""
        if self.features.get("i2s_audio") or self.features.get("av_sync"):
            return "media"
        if self.features.get("wss_tls") or self.features.get("ota"):
            return "security"
        return "default"

    # ── 生成器参数 ──

    def get_generator_params(self) -> dict:
        """返回给 project_scaffold 的生成器参数。"""
        return {
            "platform": self.platform,
            "features": self.features,
            "tasks": self.get_default_tasks(),
            "queues": self.get_default_queues(),
            "constraints": self.get_constraint_manifest(),
            "priority_style": self.task_priority_style,
        }


# ── Preset 加载 ──

def load_preset(preset_id: str) -> dict:
    """加载场景 preset。"""
    if not PRESETS_DIR.is_dir():
        raise FileNotFoundError(f"scene_presets 目录不存在: {PRESETS_DIR}")
    path = PRESETS_DIR / f"{preset_id}.json"
    if not path.exists():
        available = [p.stem for p in PRESETS_DIR.glob("*.json")]
        raise FileNotFoundError(f"Preset 不存在: {preset_id}（可用: {', '.join(available)}）")
    return json.loads(path.read_text(encoding="utf-8"))


def list_presets() -> list[dict]:
    """列出所有可用 preset。"""
    if not PRESETS_DIR.is_dir():
        return []
    presets = []
    for p in sorted(PRESETS_DIR.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            presets.append({"id": p.stem, "name": data.get("name", p.stem)})
        except Exception:
            presets.append({"id": p.stem, "name": "(解析失败)"})
    return presets


def list_platforms() -> list[str]:
    """列出所有可用平台。"""
    if not PROFILES_DIR.is_dir():
        return []
    return sorted(p.stem for p in PROFILES_DIR.glob("*.json"))


# ── 自测 ──

def run_self_test() -> int:
    passed = 0
    failed = 0

    platforms = list_platforms()
    assert len(platforms) >= 4, f"Expected >=4 platforms, got {len(platforms)}"
    print(f"[PASS] {len(platforms)} platforms available")
    passed += 1

    for plat in platforms:
        try:
            adapter = PlatformAdapter(plat)
            cmake = adapter.get_cmake_template("test")
            assert len(cmake) > 5, f"{plat} cmake too short"
            tasks = adapter.get_default_tasks()
            assert len(tasks) >= 1, f"{plat} no default tasks"
            manifest = adapter.get_constraint_manifest()
            assert "required_constraints" in manifest, f"{plat} missing manifest"
            print(f"[PASS] {plat}: cmake OK, {len(tasks)} tasks, {len(manifest['required_constraints'])} constraints")
            passed += 1
        except Exception as e:
            print(f"[FAIL] {plat}: {e}")
            failed += 1

    # Test preset loading (if available)
    presets = list_presets()
    if presets:
        for p in presets:
            try:
                data = load_preset(p["id"])
                assert "name" in data, f"Preset {p['id']} missing name"
                print(f"[PASS] preset {p['id']}: {data['name']}")
                passed += 1
            except Exception as e:
                print(f"[FAIL] preset {p['id']}: {e}")
                failed += 1
    else:
        print(f"[SKIP] no presets found (will be created in v9.0.4)")

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="平台适配器 v9.0.2")
    parser.add_argument("platform", nargs="?", help="平台名")
    parser.add_argument("--list", action="store_true", help="列出所有平台")
    parser.add_argument("--list-presets", action="store_true", help="列出所有 preset")
    parser.add_argument("--templates", action="store_true", help="输出平台模板")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--self-test", action="store_true", help="运行自测")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if args.list:
        for p in list_platforms():
            print(p)
        return 0

    if args.list_presets:
        for p in list_presets():
            print(f"  {p['id']:20s} {p['name']}")
        return 0

    if not args.platform:
        parser.print_help()
        return 1

    try:
        adapter = PlatformAdapter(args.platform)
    except FileNotFoundError as e:
        print(f"错误: {e}", file=sys.stderr)
        return 1

    if args.json:
        from checker_io import output_json
        output_json(adapter.get_generator_params())
    elif args.templates:
        print(f"=== {adapter.name} 模板 ===")
        print(f"\n--- CMakeLists.txt ---")
        print(adapter.get_cmake_template("my_project"))
        print(f"\n--- main/CMakeLists.txt ---")
        print(adapter.get_main_cmake_template())
        config = adapter.get_config_template("my_project")
        if config:
            print(f"\n--- Config ---")
            print(config)
        kconfig = adapter.get_kconfig_template("my_project")
        if kconfig:
            print(f"\n--- Kconfig ---")
            print(kconfig)
    else:
        print(f"平台: {adapter.name}")
        print(f"Features: {', '.join(k for k, v in adapter.features.items() if v)}")
        print(f"约束: {len(adapter.required_constraints)} 必选, {len(adapter.optional_constraints)} 可选")
        print(f"推荐 Suite: {adapter.get_constraint_manifest()['recommended_suite']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
