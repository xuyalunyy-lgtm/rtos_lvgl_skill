#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tools" / "fixtures"


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