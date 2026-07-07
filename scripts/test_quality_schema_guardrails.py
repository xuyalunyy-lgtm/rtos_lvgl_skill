#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tools" / "fixtures"
LOG_FIXTURES = FIXTURES / "logs"


def _load_module(module_name: str, script_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load module from {script_path}")

    module = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


quality_gate = _load_module(
    "check_log_symptom_quality_gate_test_target",
    ROOT / "scripts" / "check_log_symptom_quality_gate.py",
)
quality_routes = _load_module(
    "check_log_symptom_routes_test_target",
    ROOT / "scripts" / "check_log_symptom_routes.py",
)
quick_gate = _load_module(
    "quick_gate_test_target",
    ROOT / "scripts" / "quick_gate.py",
)


def _valid_quality_report_payload() -> dict:
    return {
        "total_routes": 1,
        "coverage": [{"field": "route_name", "present": 1, "missing": 0, "coverage": 100.0}],
        "missing_field_alerts": {"field_a": 0},
        "sparse_routes": [],
        "missing_field_alert_count": 0,
        "route_conflicts": {
            "duplicate_patterns": [],
            "weak_strong_overlaps": [],
            "broad_patterns": [],
            "multi_match_fixtures": [],
        },
    }


def _valid_quality_payload() -> dict:
    return {
        "valid": True,
        "errors": [],
        "quality": _valid_quality_report_payload(),
    }


class SchemaValidationGuardrailsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.original_gate_schema = quality_gate.QUALITY_REPORT_SCHEMA_FILE
        self.original_routes_schema = quality_routes.QUALITY_REPORT_SCHEMA_FILE

    def tearDown(self) -> None:
        quality_gate.QUALITY_REPORT_SCHEMA_FILE = self.original_gate_schema
        quality_routes.QUALITY_REPORT_SCHEMA_FILE = self.original_routes_schema

    @staticmethod
    def _missing_schema_path() -> Path:
        return FIXTURES / "quality_gate_schema_missing.json"

    def test_quality_gate_schema_missing_file_reports_error(self):
        quality_gate.QUALITY_REPORT_SCHEMA_FILE = self._missing_schema_path()
        quality_routes.QUALITY_REPORT_SCHEMA_FILE = self._missing_schema_path()

        errors: list[str] = []
        _, _ = quality_gate._normalize_quality_payload(_valid_quality_payload(), errors)

        self.assertTrue(
            any("quality schema file missing" in err for err in errors),
            f"expected schema-missing error, got: {errors}",
        )

    def test_quality_gate_schema_corrupt_file_reports_error(self):
        corrupt_schema = FIXTURES / "quality_gate_schema_corrupt.json"
        quality_gate.QUALITY_REPORT_SCHEMA_FILE = corrupt_schema
        quality_routes.QUALITY_REPORT_SCHEMA_FILE = corrupt_schema

        errors: list[str] = []
        _, _ = quality_gate._normalize_quality_payload(_valid_quality_payload(), errors)

        self.assertTrue(
            any("invalid JSON in quality schema" in err for err in errors),
            f"expected schema-parse error, got: {errors}",
        )

    def test_routes_schema_missing_file_reports_error(self):
        missing_schema = self._missing_schema_path()
        quality_routes.QUALITY_REPORT_SCHEMA_FILE = missing_schema

        _, errors = quality_routes._validate_quality_report(_valid_quality_report_payload())
        self.assertTrue(
            any("quality schema file missing" in err for err in errors),
            f"expected schema-missing error, got: {errors}",
        )

    def test_routes_schema_corrupt_file_reports_error(self):
        corrupt_schema = FIXTURES / "quality_gate_schema_corrupt.json"
        quality_routes.QUALITY_REPORT_SCHEMA_FILE = corrupt_schema

        _, errors = quality_routes._validate_quality_report(_valid_quality_report_payload())

        self.assertTrue(
            any("invalid JSON in quality schema" in err for err in errors),
            f"expected schema-parse error, got: {errors}",
        )

    def test_quality_schema_fixture_paths_are_explicit(self):
        missing_schema = self._missing_schema_path()
        self.assertFalse(
            missing_schema.exists(),
            f"missing-schema fixture should remain absent to test missing-file behavior: {missing_schema}",
        )
        self.assertTrue(
            (FIXTURES / "quality_gate_schema_corrupt.json").exists(),
            "corrupt-schema fixture file should exist for corruption-path testing",
        )


class QualityGateFixtureRegressionTest(unittest.TestCase):
    def _run_gate_fixture(self, name: str):
        return quality_gate._run_routes_quality_payload(LOG_FIXTURES / name)

    def _get_errors(self, payload: object) -> list[str]:
        if isinstance(payload, dict):
            return [str(item) for item in payload.get("errors", [])]
        return []

    def test_empty_routes_fixture_stays_valid(self):
        payload, exit_code, errs = self._run_gate_fixture("quality_gate_empty_routes.json")
        self.assertEqual(exit_code, 0)
        self.assertFalse(errs, f"fixture run reported transport errors: {errs}")
        self.assertIsInstance(payload, dict)
        self.assertTrue(payload.get("valid"))
        quality = payload.get("quality", {})
        self.assertEqual(quality.get("total_routes"), 0)
        self.assertEqual(quality.get("missing_field_alert_count", 0), 0)

    def test_missing_fields_fixture_reports_validation_error(self):
        payload, exit_code, errs = self._run_gate_fixture("quality_gate_missing_fields.json")
        self.assertNotEqual(exit_code, 0)
        self.assertFalse(errs, f"fixture run transport failed unexpectedly: {errs}")
        self.assertIsInstance(payload, dict)
        self.assertFalse(payload.get("valid"))
        combined_errors = self._get_errors(payload)
        self.assertTrue(
            any("missing keys" in item for item in combined_errors),
            f"expected missing required keys error, got: {combined_errors}",
        )

    def test_multi_match_routes_fixture_is_detected(self):
        payload, exit_code, errs = self._run_gate_fixture("quality_gate_multi_match_routes.json")
        self.assertEqual(exit_code, 0)
        self.assertFalse(errs, f"fixture run reported transport errors: {errs}")

        quality = payload.get("quality", {})
        route_conflicts = quality.get("route_conflicts", {})
        multi = route_conflicts.get("multi_match_fixtures", [])
        self.assertIsInstance(multi, list)
        self.assertTrue(
            any(
                item.get("fixture") == "quality_gate_multi_match.log"
                and sorted(item.get("matched_routes", [])) == ["MM_A", "MM_B"]
                for item in multi
            ),
            f"expected multi-match fixture conflict, got: {multi}",
        )

    def test_conflict_over_threshold_fixture_records_conflicts(self):
        payload, exit_code, errs = self._run_gate_fixture("quality_gate_conflict_over_threshold.json")
        self.assertEqual(exit_code, 0)
        self.assertFalse(errs, f"fixture run reported transport errors: {errs}")
        quality = payload.get("quality", {})
        route_conflicts = quality.get("route_conflicts", {})
        self.assertIsInstance(route_conflicts, dict)
        self.assertGreater(
            len(route_conflicts.get("duplicate_patterns", []))
            + len(route_conflicts.get("weak_strong_overlaps", []))
            + len(route_conflicts.get("broad_patterns", [])),
            0,
            f"expected conflict fixture to trigger conflict counters, got: {route_conflicts}",
        )


class QuickGateStrictModeTest(unittest.TestCase):
    @staticmethod
    def _with_env(**values: str | None):
        backup = {key: os.environ.get(key) for key in values}
        for key, value in values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        return backup

    @staticmethod
    def _restore_env(backup: dict[str, str | None]):
        for key, value in backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_ci_environment_defaults_to_strict(self):
        backup = self._with_env(CI="1", SKILL_QUICK_GATE_STRICT=None)
        try:
            args = quick_gate.argparse.Namespace(strict=False)
            self.assertTrue(quick_gate._resolve_quality_strict(args))
        finally:
            self._restore_env(backup)

    def test_env_override_controls_strict_mode(self):
        backup = self._with_env(CI="1", SKILL_QUICK_GATE_STRICT="0")
        try:
            args = quick_gate.argparse.Namespace(strict=True)
            self.assertFalse(quick_gate._resolve_quality_strict(args))
        finally:
            self._restore_env(backup)


if __name__ == "__main__":
    unittest.main()
