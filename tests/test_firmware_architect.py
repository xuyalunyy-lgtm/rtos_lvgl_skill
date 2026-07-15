from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import firmware_architect


class FirmwareArchitectTests(unittest.TestCase):
    def test_generates_normalized_manifest_and_portable_modules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            outdir = Path(directory) / "generated"
            generated = firmware_architect.generate(copy.deepcopy(firmware_architect.EXAMPLE_SPEC), outdir)
            manifest = json.loads((outdir / "generation_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(generated), 6)
            self.assertEqual(manifest["schema_version"], "1.2")
            self.assertEqual(manifest["queues"][0]["drop_counter"], "s_sensor_events_drop_count")
            self.assertIn("module_boundary:", (outdir / "include" / "sensor_service.h").read_text(encoding="utf-8"))
            completed = subprocess.run(
                [
                    sys.executable, str(ROOT / "tools" / "codegen_gate.py"),
                    "--dir", str(outdir), "--manifest", str(outdir / "generation_manifest.json"),
                    "--platform", "esp32", "--strict",
                ],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_rejects_topology_references_to_unknown_queue(self) -> None:
        spec = copy.deepcopy(firmware_architect.EXAMPLE_SPEC)
        spec["tasks"][0]["produces"] = ["missing_queue"]
        errors = firmware_architect.validate_spec(spec)
        self.assertTrue(any("unknown queue missing_queue" in error for error in errors))

    def test_rejects_split_brain_queue_topology(self) -> None:
        spec = copy.deepcopy(firmware_architect.EXAMPLE_SPEC)
        spec["queues"][0]["producer_tasks"] = ["network_task"]
        errors = firmware_architect.validate_spec(spec)
        self.assertTrue(any("producer network_task" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
