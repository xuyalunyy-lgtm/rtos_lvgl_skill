#!/usr/bin/env python3
"""
Audit the skill metadata contract for Codex/OpenAI distribution.

This keeps the local iteration loop aligned with quick_validate-style
constraints without depending on external validator paths.
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_NAME = "freertos-embedded-architect"
DESCRIPTION_LIMIT = 1024
SKILL_LINE_LIMIT = 99
AGENT_KEYS = ("display_name", "short_description", "default_prompt")
NAME_RE = re.compile(r"^[a-z0-9-]{1,63}$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def rel_label(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def read_text(path: Path, errors: list[str], root: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"{rel_label(path, root)} unreadable: {exc}")
        return ""


def parse_frontmatter(path: Path, errors: list[str], root: Path) -> tuple[dict[str, str], str]:
    text = read_text(path, errors, root)
    label = rel_label(path, root)
    if not text.startswith("---"):
        errors.append(f"{label} missing YAML frontmatter")
        return {}, ""

    parts = text.split("---", 2)
    if len(parts) < 3:
        errors.append(f"{label} malformed YAML frontmatter")
        return {}, ""

    raw = parts[1].strip("\r\n")
    fields: dict[str, str] = {}
    lines = raw.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue

        if line.startswith((" ", "\t")):
            i += 1
            continue

        if ":" not in line:
            i += 1
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()

        if value in (">", ">-", "|", "|-"):
            block: list[str] = []
            i += 1
            while i < len(lines) and (lines[i].startswith((" ", "\t")) or not lines[i].strip()):
                block.append(lines[i].strip())
                i += 1
            if value.startswith(">"):
                fields[key] = " ".join(part for part in block if part)
            else:
                fields[key] = "\n".join(block)
            continue

        fields[key] = value.strip("\"'")
        i += 1

    metadata_match = re.search(
        r"^metadata:\s*\n(?:[ \t]+[^\n]*\n)*?[ \t]+version:\s*([^\s#]+)",
        raw,
        re.MULTILINE,
    )
    if metadata_match:
        fields["metadata.version"] = metadata_match.group(1).strip().strip("\"'")

    return fields, raw


def check_skill(path: Path, errors: list[str], root: Path) -> tuple[str | None, int]:
    fields, raw = parse_frontmatter(path, errors, root)
    label = rel_label(path, root)
    name = fields.get("name", "")
    version = fields.get("metadata.version") or fields.get("version", "")
    description = fields.get("description", "")
    line_count = len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0

    if name != EXPECTED_NAME:
        errors.append(f"{label} name must be {EXPECTED_NAME}, got {name or '<missing>'}")
    elif not NAME_RE.match(name):
        errors.append(f"{label} name is not valid hyphen-case: {name}")

    if not version:
        errors.append(f"{label} missing metadata.version")
    elif not SEMVER_RE.match(version):
        errors.append(f"{label} metadata.version is not semver: {version}")

    if re.search(r"^version:\s*", raw, re.MULTILINE):
        errors.append(f"{label} version must be nested under metadata.version")

    if not description:
        errors.append(f"{label} missing description")
    elif len(description) > DESCRIPTION_LIMIT:
        errors.append(f"{label} description is {len(description)} chars > {DESCRIPTION_LIMIT}")
    elif "Use when" not in description:
        errors.append(f"{label} description should include 'Use when' trigger guidance")

    if line_count > SKILL_LINE_LIMIT:
        errors.append(f"{label} has {line_count} lines > {SKILL_LINE_LIMIT}")

    return version or None, len(description)


def parse_agent_metadata(path: Path, errors: list[str], root: Path) -> dict[str, str]:
    text = read_text(path, errors, root)
    label = rel_label(path, root)
    if not text:
        return {}

    if not re.search(r"^interface:\s*$", text, re.MULTILINE):
        errors.append(f"{label} missing interface block")

    values: dict[str, str] = {}
    in_interface = False
    for line in text.splitlines():
        if re.match(r"^interface:\s*$", line):
            in_interface = True
            continue
        if not in_interface:
            continue
        if not line.strip():
            continue
        if not line.startswith((" ", "\t")):
            break

        match = re.match(r"^[ \t]+([a-z_]+):\s*(.*)\s*$", line)
        if not match:
            continue
        key, value = match.group(1), match.group(2).strip().strip("\"'")
        values[key] = value

    for key in AGENT_KEYS:
        if not values.get(key):
            errors.append(f"{label} missing interface.{key}")

    extra = sorted(set(values) - set(AGENT_KEYS))
    if extra:
        errors.append(f"{label} has unapproved interface keys: {', '.join(extra)}")

    default_prompt = values.get("default_prompt", "")
    if default_prompt and f"${EXPECTED_NAME}" not in default_prompt:
        errors.append(f"{label} default_prompt must reference ${EXPECTED_NAME}")

    short_description = values.get("short_description", "")
    if len(short_description) > 80:
        errors.append(f"{label} short_description is {len(short_description)} chars > 80")

    return values


def validate_root(root: Path) -> tuple[list[str], int, int, str | None]:
    errors: list[str] = []
    full_skill = root / "SKILL.md"
    full_agent_path = root / "agents" / "openai.yaml"

    full_version, full_desc_len = check_skill(full_skill, errors, root)
    lite_desc_len = 0

    # Lite checks are optional — skip if freertos-skill-lite/ doesn't exist
    lite_skill = root / "freertos-skill-lite" / "SKILL.md"
    lite_agent_path = root / "freertos-skill-lite" / "agents" / "openai.yaml"
    if lite_skill.exists():
        lite_version, lite_desc_len = check_skill(lite_skill, errors, root)
        if full_version and lite_version and full_version != lite_version:
            errors.append(f"SKILL version mismatch: full {full_version} vs Lite {lite_version}")
        lite_agent = parse_agent_metadata(lite_agent_path, errors, root)
        full_agent = parse_agent_metadata(full_agent_path, errors, root)
        if full_agent and lite_agent and full_agent != lite_agent:
            errors.append("agents/openai.yaml differs between full and Lite")
    else:
        _ = parse_agent_metadata(full_agent_path, errors, root)

    return errors, full_desc_len, lite_desc_len, full_version


def write_fixture(root: Path, *, description: str, full_version: str, lite_version: str | None = None) -> None:
    lite_version = lite_version or full_version
    agent = (
        'interface:\n'
        '  display_name: "FreeRTOS Embedded Architect"\n'
        '  short_description: "Review and design FreeRTOS IoT firmware"\n'
        f'  default_prompt: "Use ${EXPECTED_NAME} to review this FreeRTOS firmware change."\n'
    )

    for path in (
        root / "SKILL.md",
        root / "freertos-skill-lite" / "SKILL.md",
        root / "agents" / "openai.yaml",
        root / "freertos-skill-lite" / "agents" / "openai.yaml",
    ):
        path.parent.mkdir(parents=True, exist_ok=True)

    (root / "SKILL.md").write_text(skill_text(description, full_version), encoding="utf-8")
    (root / "freertos-skill-lite" / "SKILL.md").write_text(
        skill_text(description, lite_version),
        encoding="utf-8",
    )
    (root / "agents" / "openai.yaml").write_text(agent, encoding="utf-8")
    (root / "freertos-skill-lite" / "agents" / "openai.yaml").write_text(agent, encoding="utf-8")


def skill_text(description: str, version: str, *, body_lines: int = 3, root_version: bool = False) -> str:
    version_block = f"version: {version}" if root_version else f"metadata:\n  version: {version}"
    body = "\n".join(f"line {index}" for index in range(body_lines))
    return (
        "---\n"
        f"name: {EXPECTED_NAME}\n"
        f"{version_block}\n"
        "description: >-\n"
        f"  {description}\n"
        "---\n\n"
        "# Fixture\n\n"
        f"{body}\n"
    )


def run_self_test() -> int:
    valid_desc = "Review FreeRTOS firmware. Use when user asks for embedded code review."

    def mutate_description(root: Path) -> None:
        long_desc = "Use when " + ("x" * 1030)
        (root / "SKILL.md").write_text(skill_text(long_desc, "1.2.3"), encoding="utf-8")

    def mutate_root_version(root: Path) -> None:
        (root / "SKILL.md").write_text(
            skill_text(valid_desc, "1.2.3", root_version=True),
            encoding="utf-8",
        )

    def mutate_version_mismatch(root: Path) -> None:
        (root / "freertos-skill-lite" / "SKILL.md").write_text(
            skill_text(valid_desc, "1.2.4"),
            encoding="utf-8",
        )

    def mutate_agent_drift(root: Path) -> None:
        (root / "freertos-skill-lite" / "agents" / "openai.yaml").write_text(
            'interface:\n'
            '  display_name: "FreeRTOS Embedded Architect"\n'
            '  short_description: "Changed"\n'
            f'  default_prompt: "Use ${EXPECTED_NAME} to review this FreeRTOS firmware change."\n',
            encoding="utf-8",
        )

    def mutate_line_budget(root: Path) -> None:
        (root / "SKILL.md").write_text(
            skill_text(valid_desc, "1.2.3", body_lines=100),
            encoding="utf-8",
        )

    cases: list[tuple[str, Callable[[Path], None] | None, str | None]] = [
        ("valid fixture", None, None),
        ("description limit", mutate_description, "description is"),
        ("root-level version", mutate_root_version, "version must be nested"),
        ("version mismatch", mutate_version_mismatch, "SKILL version mismatch"),
        ("agent drift", mutate_agent_drift, "agents/openai.yaml differs"),
        ("line budget", mutate_line_budget, "lines >"),
    ]

    failures: list[str] = []
    for name, mutate, expected in cases:
        with tempfile.TemporaryDirectory(prefix="skill-metadata-") as tmp:
            root = Path(tmp)
            write_fixture(root, description=valid_desc, full_version="1.2.3")
            if mutate:
                mutate(root)

            errors, _full_len, _lite_len, _version = validate_root(root)
            if expected is None:
                ok = not errors
            else:
                ok = any(expected in error for error in errors)

            if ok:
                print(f"[PASS] {name}")
            else:
                failures.append(f"{name}: expected {expected or 'no errors'}, got {errors}")
                print(f"[FAIL] {name}")

    if failures:
        print("[skill-metadata:self-test] failed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("[skill-metadata:self-test] all fixtures passed")
    return 0


def print_result(root: Path) -> int:
    errors, full_desc_len, lite_desc_len, full_version = validate_root(root)
    if errors:
        print("[skill-metadata] metadata contract failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(
        "[skill-metadata] metadata contract OK "
        f"(description chars: full={full_desc_len}, lite={lite_desc_len}; version={full_version})"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit skill metadata contract")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="skill repository root")
    parser.add_argument("--self-test", action="store_true", help="run positive/negative fixture tests")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    return print_result(args.root.resolve())


if __name__ == "__main__":
    sys.exit(main())
