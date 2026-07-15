from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import project_doctor


class ProjectDoctorTests(unittest.TestCase):
    def test_detects_esp_idf_and_frameworks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main").mkdir()
            (root / "build").mkdir()
            (root / "sdkconfig").write_text('CONFIG_IDF_TARGET="esp32s3"\nCONFIG_FREERTOS_HZ=1000\n', encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()
