from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import project_doctor


class ProjectDoctorTests(unittest.TestCase):
    def test_detects_esp_idf_and_frameworks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main").mkdir()
            (root / "build").mkdir()
            (root / "sdkconfig").write_text(
                'CONFIG_IDF_TARGET="esp32s3"\nCONFIG_FREERTOS_HZ=1000\nCONFIG_BT_ENABLED=y\n# CONFIG_WIFI_ENABLED is not set\n',
                encoding="utf-8",
            )
            (root / "CMakeLists.txt").write_text('set(IDF_VERSION "5.2.1")\nidf_component_register(SRCS main.c)\n', encoding="utf-8")
            (root / "main" / "main.c").write_text('#include "freertos/FreeRTOS.h"\n#include "lvgl.h"\n', encoding="utf-8")
            (root / "build" / "app.elf").write_bytes(b"ELF")
            report = project_doctor.inspect_project(root)
        self.assertEqual(report["primary_platform"], "esp32")
        self.assertIn("cmake", report["build_systems"])
        self.assertTrue(any(item["name"] == "freertos" for item in report["frameworks"]))
        manifest = report["project_manifest"]
        self.assertEqual(manifest["platform"]["chip"], "esp32s3")
        self.assertEqual(manifest["sdk"]["name"], "esp-idf")
        self.assertEqual(manifest["build"]["command"], ["idf.py", "build"])
        self.assertEqual(manifest["build"]["artifacts"]["elf"], ["build/app.elf"])
        self.assertIn("CONFIG_BT_ENABLED", manifest["configuration"]["enabled"])
        self.assertNotIn("CONFIG_WIFI_ENABLED", manifest["configuration"]["enabled"])

    def test_reports_uncertain_empty_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = project_doctor.inspect_project(Path(directory))
        codes = {item["code"] for item in report["findings"]}
        self.assertIn("PLATFORM_UNCERTAIN", codes)
        self.assertIn("NO_EMBEDDED_SOURCE", codes)

    def test_detects_zephyr_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "build" / "zephyr").mkdir(parents=True)
            (root / "west.yml").write_text("manifest:\n  self:\n    path: app\n", encoding="utf-8")
            (root / "prj.conf").write_text("CONFIG_MAIN_STACK_SIZE=2048\n", encoding="utf-8")
            (root / "build" / "zephyr" / ".config").write_text('CONFIG_BOARD="nrf52840dk_nrf52840"\n', encoding="utf-8")
            (root / "app.overlay").write_text("/ { chosen { zephyr,console = &uart0; }; };\n", encoding="utf-8")
            (root / "src" / "main.c").write_text("#include <zephyr/kernel.h>\n", encoding="utf-8")
            report = project_doctor.inspect_project(root)
        self.assertEqual(report["primary_platform"], "zephyr")
        self.assertTrue(any(item["name"] == "zephyr" for item in report["frameworks"]))
        self.assertEqual(report["project_manifest"]["platform"]["board"], "nrf52840dk_nrf52840")
        self.assertEqual(report["project_manifest"]["build"]["command"], ["west", "build", "-b", "nrf52840dk_nrf52840", "."])

    def test_detects_stm32_cubemx_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Core" / "Src").mkdir(parents=True)
            (root / "Core" / "Inc").mkdir(parents=True)
            (root / "Debug").mkdir()
            (root / "board.ioc").write_text(
                "Mcu.Name=STM32H743ZITx\nProjectManager.ProjectName=display_node\nMxCube.Version=6.12.1\n",
                encoding="utf-8",
            )
            (root / "Makefile").write_text("all:\n\t@echo build\n", encoding="utf-8")
            (root / "Core" / "Inc" / "FreeRTOSConfig.h").write_text("#define configUSE_PREEMPTION 1\n", encoding="utf-8")
            (root / "Core" / "Src" / "main.c").write_text('#include "stm32h7xx_hal.h"\n', encoding="utf-8")
            (root / "Debug" / "display_node.axf").write_bytes(b"AXF")
            (root / "Debug" / "display_node.map").write_text("map", encoding="utf-8")
            report = project_doctor.inspect_project(root)
        manifest = report["project_manifest"]
        self.assertEqual(report["primary_platform"], "stm32")
        self.assertEqual(manifest["platform"]["chip"], "stm32h743zitx")
        self.assertEqual(manifest["platform"]["board"], "display_node")
        self.assertEqual(manifest["sdk"]["version"], "6.12.1")
        self.assertEqual(manifest["build"]["command"], ["make", "-j"])
        self.assertEqual(manifest["build"]["artifacts"]["elf"], ["Debug/display_node.axf"])

    def test_detects_jieli_sdk_and_unique_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "apps" / "common" / "system").mkdir(parents=True)
            (root / "apps" / "demo" / "demo_wifi" / "include").mkdir(parents=True)
            (root / "cpu" / "wl82" / "tools").mkdir(parents=True)
            (root / "Makefile").write_text("ac791n_demo_wifi:\n\t@echo build\n", encoding="utf-8")
            (root / "apps" / "common" / "system" / "version.c").write_text(
                'const char *sdk_version(void) { return "AC79NN_SDK_V1.2.13"; }\n', encoding="utf-8"
            )
            (root / "apps" / "demo" / "demo_wifi" / "include" / "app_config.h").write_text(
                "#define CONFIG_WIFI_ENABLE 1\n", encoding="utf-8"
            )
            (root / "apps" / "demo" / "demo_wifi" / "main.c").write_text("void thread_fork(void);\n", encoding="utf-8")
            (root / "cpu" / "wl82" / "tools" / "sdk.elf").write_bytes(b"ELF")
            (root / "cpu" / "wl82" / "tools" / "jl_isd.fw").write_bytes(b"FW")
            report = project_doctor.inspect_project(root)
        manifest = report["project_manifest"]
        self.assertEqual(report["primary_platform"], "jl")
        self.assertEqual(manifest["platform"]["chip"], "wl82")
        self.assertEqual(manifest["sdk"]["version"], "AC79NN_SDK_V1.2.13")
        self.assertEqual(manifest["build"]["command"], ["make", "ac791n_demo_wifi"])
        self.assertEqual(manifest["build"]["artifacts"]["firmware"], ["cpu/wl82/tools/jl_isd.fw"])

    def test_detects_bk_armino_soc_and_build(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "middleware" / "soc" / "bk7258").mkdir(parents=True)
            (root / "projects" / "app" / "config" / "bk7258").mkdir(parents=True)
            (root / "projects" / "app" / "main").mkdir(parents=True)
            (root / "Makefile").write_text("all:\n\t@echo armino\n", encoding="utf-8")
            (root / "middleware" / "soc" / "bk7258" / "bk7258.defconfig").write_text(
                "CONFIG_FREERTOS=y\n", encoding="utf-8"
            )
            (root / "projects" / "app" / "config" / "bk7258" / "config").write_text(
                "CONFIG_LVGL=y\n", encoding="utf-8"
            )
            (root / "projects" / "app" / "main" / "app_main.c").write_text("void bk_init(void);\n", encoding="utf-8")
            report = project_doctor.inspect_project(root)
        manifest = report["project_manifest"]
        self.assertEqual(report["primary_platform"], "bk")
        self.assertEqual(manifest["platform"]["chip"], "bk7258")
        self.assertEqual(manifest["sdk"]["name"], "armino-idk")
        self.assertEqual(manifest["build"]["command"], ["make", "bk7258"])
        self.assertIn("CONFIG_LVGL", manifest["configuration"]["enabled"])

    def test_plans_task_from_project_facts_and_intent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main").mkdir()
            (root / "sdkconfig").write_text('CONFIG_IDF_TARGET="esp32s3"\n', encoding="utf-8")
            (root / "CMakeLists.txt").write_text("idf_component_register(SRCS main.c)\n", encoding="utf-8")
            (root / "main" / "main.c").write_text('#include "freertos/FreeRTOS.h"\n', encoding="utf-8")
            report = project_doctor.inspect_project(root)
            task_plan = project_doctor.plan_task(report, "审查这个 cJSON 模块", "compact")
        self.assertEqual(task_plan["status"], "ready")
        self.assertEqual(task_plan["classification"]["workflow"], "code_review")
        self.assertEqual(task_plan["detected_facts"], {"platform": "esp32", "rtos": "freertos"})
        required = {item["path"] for item in task_plan["load_plan"]["required_files"]}
        self.assertIn("workflows/l2_code_review.md", required)
        self.assertIn("references/micro_C03.md", required)

    def test_writes_manifest_only_when_explicitly_requested(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main").mkdir()
            (root / "sdkconfig").write_text('CONFIG_IDF_TARGET="esp32c6"\n', encoding="utf-8")
            (root / "CMakeLists.txt").write_text("idf_component_register(SRCS main.c)\n", encoding="utf-8")
            (root / "main" / "main.c").write_text("void app_main(void) {}\n", encoding="utf-8")
            report = project_doctor.inspect_project(root)
            destination = project_doctor.write_manifest(report, root / "generated" / "project_manifest.json")
            written = destination.read_text(encoding="utf-8")
        self.assertIn('"chip": "esp32c6"', written)
        self.assertIn('"generated_at"', written)

    def test_run_review_receives_detected_kconfig_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sdkconfig").write_text("CONFIG_BT_ENABLED=y\n", encoding="utf-8")
            completed = type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()
            with patch.object(project_doctor.subprocess, "run", return_value=completed) as run:
                project_doctor._run_review(root, "esp32", ["sdkconfig"], "esp-idf")
        command = run.call_args.args[0]
        self.assertIn("--config", command)
        self.assertIn(str(root / "sdkconfig"), command)
        self.assertIn("--build-system", command)
        self.assertIn("esp-idf", command)


if __name__ == "__main__":
    unittest.main()
