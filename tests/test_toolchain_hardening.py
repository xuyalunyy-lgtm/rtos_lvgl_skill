from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tools"))

import quick_gate
import run_review


class QuickGateHardeningTests(unittest.TestCase):
    def test_filter_accepts_stable_slug(self) -> None:
        selected = quick_gate._select_steps(quick_gate.STEPS, ["serial-mcp"])
        self.assertEqual([step.name for step in selected], ["serial MCP"])

    def test_step_timeout_is_reported(self) -> None:
        step = quick_gate.GateStep(
            "timeout fixture",
            [sys.executable, "-c", "import time; time.sleep(1)"],
            timeout_seconds=0.01,
        )
        result = quick_gate.run_step_capture(1, step)
        self.assertTrue(result.timed_out)
        self.assertFalse(result.passed)
        self.assertIn("Timed out", result.output)


class RunReviewProtocolTests(unittest.TestCase):
    def test_checker_jsonl_protocol_rejects_text_counting(self) -> None:
        payload = {
            "protocol_version": "checker-result/v1",
            "checker": "fixture",
            "domains": ["C1"],
            "files_checked": 1,
            "violations": 1,
            "issues": [{"id": "C1", "severity": "P1", "file": "x.c:1", "issue": "fixture"}],
        }
        parsed = run_review._parse_checker_jsonl(json.dumps(payload))
        self.assertEqual(parsed["violations"], 1)
        with self.assertRaises(ValueError):
            run_review._parse_checker_jsonl("Summary: 0 warnings")

    def test_dry_run_plan_uses_symptom_checker_targets(self) -> None:
        args = type("Args", (), {
            "from_symptom_plan": "plan.json", "symptom_checker_targets": ("fault_isolation_checker",),
            "scan_secrets": False, "git_remotes": False, "dir": None, "files": [], "log": None,
            "repro_output": None, "skip_stack": True, "evidence": None, "describe": "fixture",
            "platform": "esp32",
        })()
        plan = run_review.build_execution_plan(args, [])
        self.assertEqual([step["name"] for step in plan["steps"]], ["fault_isolation_checker"])


if __name__ == "__main__":
    unittest.main()
