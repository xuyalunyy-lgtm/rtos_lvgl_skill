from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import os
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tools"))

import quick_gate
import review_history
import run_review
from checker_io import filter_inactive_kconfig_blocks
from checker_registry import ALL_CHECKERS
from sdk_lookup import SdkLookup


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
        self.assertGreaterEqual(result.duration_seconds, 0.0)


class RunReviewProtocolTests(unittest.TestCase):
    def test_review_history_reports_baseline_then_improvement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first = {"total_issues": 4}
            first_history = review_history.append(first, directory)
            second = {"total_issues": 1}
            second_history = review_history.append(second, directory)
        self.assertEqual(first_history["trend"], "baseline")
        self.assertEqual(second_history["trend"], "improved")
        self.assertEqual(second_history["previous_total_issues"], 4)

    def test_generic_freertos_sdk_map_is_complete(self) -> None:
        self.assertEqual(SdkLookup("freertos").validate(), [])

    def test_run_review_passes_zephyr_platform_to_checker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan = Path(directory) / "plan.json"
            plan.write_text(json.dumps({"checker_targets": ["zephyr_pattern_checker"]}), encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable, str(ROOT / "tools" / "run_review.py"),
                    "--dir", str(ROOT / "tools" / "fixtures"), "--include-bad", "--platform", "zephyr",
                    "--from-symptom-plan", str(plan), "--skip-stack", "--json", "--no-history",
                ],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
        report = json.loads(completed.stdout)
        result = next(item for item in report["checkers"] if item["checker"] == "zephyr_pattern_checker")
        self.assertEqual(completed.returncode, 1)
        self.assertEqual(report["review_context"]["platform"], "zephyr")
        self.assertGreater(result["issues"], 0)

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
        plan = run_review.build_execution_plan(args, [Path("fixture.c")])
        self.assertEqual([step["name"] for step in plan["steps"]], ["fault_isolation_checker"])

    def test_changed_only_uses_git_diff_and_skips_deleted_paths(self) -> None:
        completed = run_review.subprocess.CompletedProcess(
            ["git", "diff"], 0, stdout="src/a.c\ninclude/a.h\n", stderr="",
        )
        with patch.object(run_review.subprocess, "run", return_value=completed) as run:
            with patch.object(run_review, "collect_c_files", return_value=[Path("src/a.c"), Path("include/a.h")]) as collect:
                result = run_review.collect_changed_c_files("origin/main")
        self.assertEqual(result, [Path("src/a.c"), Path("include/a.h")])
        self.assertIn("origin/main...HEAD", run.call_args.args[0])
        self.assertEqual(collect.call_args.args[0], ["src/a.c", "include/a.h"])

    def test_registered_c41_is_global_checker(self) -> None:
        spec = next(spec for spec in ALL_CHECKERS if spec.name == "regression_sample_checker")
        self.assertEqual(spec.domains, ("C41",))
        self.assertEqual(spec.mode, "global")

        args = type("Args", (), {
            "json": True,
            "from_symptom_plan": "fixture-plan.json",
            "symptom_checker_targets": ("regression_sample_checker",),
        })()
        exit_code, results = run_review.run_registered_checkers(args, [])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["checker"], "regression_sample_checker")
        self.assertGreaterEqual(exit_code, 0)

    def test_known_disabled_kconfig_block_is_not_scanned(self) -> None:
        source = """#ifdef CONFIG_BT_ENABLED
unsafe_bt_call();
#endif
#ifdef CONFIG_WIFI_ENABLED
unsafe_wifi_call();
#endif
"""
        with patch.dict(os.environ, {"SKILL_KCONFIG_VALUES": json.dumps({"CONFIG_BT_ENABLED": "y", "CONFIG_WIFI_ENABLED": "n"})}):
            filtered = filter_inactive_kconfig_blocks(source)
        self.assertIn("unsafe_bt_call", filtered)
        self.assertNotIn("unsafe_wifi_call", filtered)
        self.assertEqual(source.count("\n"), filtered.count("\n"))

    def test_cross_file_lock_order_cycle(self) -> None:
        checker = ROOT / "tools" / "lock_budget_checker.py"
        good = [ROOT / "tools" / "fixtures" / "good_lock_order_a.c", ROOT / "tools" / "fixtures" / "good_lock_order_b.c"]
        bad = [ROOT / "tools" / "fixtures" / "bad_lock_order_a.c", ROOT / "tools" / "fixtures" / "bad_lock_order_b.c"]
        good_result = subprocess.run([sys.executable, str(checker), *(str(path) for path in good)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        bad_result = subprocess.run([sys.executable, str(checker), *(str(path) for path in bad)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(good_result.returncode, 0)
        self.assertEqual(bad_result.returncode, 1)
        self.assertIn("C43.6", bad_result.stdout)

    def test_cross_file_resource_lifecycle(self) -> None:
        checker = ROOT / "tools" / "lifecycle_checker.py"
        good = [
            ROOT / "tools" / "fixtures" / "good_cross_file_lifecycle_owner.c",
            ROOT / "tools" / "fixtures" / "good_cross_file_lifecycle_cleanup.c",
        ]
        bad = [ROOT / "tools" / "fixtures" / "bad_cross_file_lifecycle_owner.c"]
        good_result = subprocess.run([sys.executable, str(checker), *(str(path) for path in good)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        bad_result = subprocess.run([sys.executable, str(checker), *(str(path) for path in bad)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(good_result.returncode, 0)
        self.assertEqual(bad_result.returncode, 1)
        self.assertIn("g_leaked_queue", bad_result.stdout)


if __name__ == "__main__":
    unittest.main()
