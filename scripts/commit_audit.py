#!/usr/bin/env python3
"""
Proactive release/commit audit for this skill repository.

The checks are deliberately small and deterministic so they can run in every
self-iteration loop. Use --self-test to prove the failure gates still work.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN_RESIDUE = (
    "AI" + "Alarm" + "Clock",
    "AI" + "Alarm",
    "bk" + "_printer",
    "带屏" + "打" + "印" + "机",
    "打" + "印" + "机",
    "PRINT" + "ER_",
    "printer" + "_",
)
RESIDUE_EXCLUDE = {
    "references/iteration_log.md",
    "references/iteration_log_archive_2026Q2.md",
    "freertos-skill-lite/references/iteration_log.md",
    "freertos-skill-lite/references/iteration_log_archive_2026Q2.md",
}
GENERIC_PREFIXES = (
    "SKILL.md",
    "references/",
    "workflows/",
    "prompts/",
    "platforms/",
    "product_profiles/",
)
MAJOR_REFACTOR_MARKERS = (
    "major-refactor: yes",
    "whole-skill-refactor: yes",
    "Major refactor",
    "大重构",
    "整体重构",
    "全局重构",
)
EFFICIENCY_MARKERS = (
    "20x-impact:",
    "20x",
    "20 倍",
    "20倍",
)


@dataclass
class RepoSnapshot:
    root: Path
    version: str | None
    head_version: str | None
    lite_version: str | None
    changed_files: list[str]
    changelog_head: str
    iteration_head: str
    status: str
    stat: str
    log: str


@dataclass
class AuditResult:
    warnings: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)


def run_git(root: Path, args: list[str], *, check: bool = False) -> tuple[int, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{proc.stdout}")
    return proc.returncode, proc.stdout.strip()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def parse_version(text: str) -> str | None:
    for line_no, line in enumerate(text.splitlines()):
        if line.strip() == "metadata:":
            for child in text.splitlines()[line_no + 1:]:
                if child and not child.startswith((" ", "\t")):
                    break
                stripped = child.strip()
                if stripped.startswith("version:"):
                    return stripped.split(":", 1)[1].strip().strip("\"'")
        if line.startswith("version:"):
            return line.split(":", 1)[1].strip().strip("\"'")
    return None


def semver_tuple(version: str | None) -> tuple[int, int, int] | None:
    if not version:
        return None
    parts = version.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def read_head_file(root: Path, path: str) -> str:
    rc, out = run_git(root, ["show", f"HEAD:{path}"])
    return out if rc == 0 else ""


def changed_files(root: Path) -> list[str]:
    rc, out = run_git(root, ["status", "--porcelain=v1"])
    if rc != 0 or not out:
        return []
    files: list[str] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.rsplit(" -> ", 1)[1]
        if path:
            normalized = path.replace("\\", "/")
            abs_path = root / normalized
            if abs_path.is_dir():
                files.extend(
                    child.relative_to(root).as_posix()
                    for child in sorted(abs_path.rglob("*"))
                    if child.is_file()
                )
            else:
                files.append(normalized)
    return files


def collect_snapshot(root: Path, max_log: int) -> RepoSnapshot:
    skill_text = read_text(root / "SKILL.md")
    lite_text = read_text(root / "freertos-skill-lite" / "SKILL.md")
    head_skill_text = read_head_file(root, "SKILL.md")

    _rc, status = run_git(root, ["status", "--short"])
    _rc, stat = run_git(root, ["diff", "--stat", "HEAD", "--"])
    _rc, log = run_git(root, ["log", "--oneline", f"-{max_log}"])

    return RepoSnapshot(
        root=root,
        version=parse_version(skill_text),
        head_version=parse_version(head_skill_text),
        lite_version=parse_version(lite_text),
        changed_files=changed_files(root),
        changelog_head=read_text(root / "CHANGELOG.md")[:2000],
        iteration_head=read_text(root / "references" / "iteration_log.md")[:2600],
        status=status,
        stat=stat,
        log=log,
    )


def has_marker(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def is_major_release(current: str | None, previous: str | None) -> bool:
    current_tuple = semver_tuple(current)
    previous_tuple = semver_tuple(previous)
    if not current_tuple or not previous_tuple or current_tuple == previous_tuple:
        return False
    return current_tuple[0] > previous_tuple[0] or current_tuple[1:] == (0, 0)


def should_scan_residue(path: str) -> bool:
    return (
        path not in RESIDUE_EXCLUDE
        and path.startswith(GENERIC_PREFIXES)
    )


def evaluate(snapshot: RepoSnapshot) -> AuditResult:
    result = AuditResult()
    files = set(snapshot.changed_files)

    if snapshot.version and snapshot.lite_version and snapshot.version != snapshot.lite_version:
        result.failures.append(f"SKILL.md version {snapshot.version} != Lite version {snapshot.lite_version}")

    if snapshot.version:
        if snapshot.version not in snapshot.changelog_head:
            result.failures.append(f"CHANGELOG top section does not mention current version {snapshot.version}")
        if snapshot.version not in snapshot.iteration_head:
            result.failures.append(f"iteration_log top section does not mention current version {snapshot.version}")

    if is_major_release(snapshot.version, snapshot.head_version):
        notes = f"{snapshot.changelog_head}\n{snapshot.iteration_head}"
        if not has_marker(notes, MAJOR_REFACTOR_MARKERS):
            result.failures.append("major release lacks whole-skill refactor evidence")
        if not has_marker(notes, EFFICIENCY_MARKERS):
            result.failures.append("major release lacks 20x efficiency impact evidence")

    if any(path.startswith("tools/") and path.endswith(".py") for path in files):
        checker_script_changed = any(path.startswith("tools/") and path.endswith("_checker.py") for path in files)
        if checker_script_changed and "tools/checker_registry.py" not in files:
            result.warnings.append("checker script changed without checker_registry.py change")

    if any(path.startswith("prompts/") for path in files):
        if not any(path.startswith("workflows/") for path in files):
            result.warnings.append("prompt changed without workflow routing change; verify it is already routed")

    if any(path.startswith(("SKILL.md", "references/", "workflows/", "prompts/", "agents/")) for path in files):
        if not any(path.startswith("freertos-skill-lite/") for path in files):
            result.warnings.append("runtime docs changed but Lite output is not changed; run sync_lite.py")

    for path in snapshot.changed_files:
        if not should_scan_residue(path):
            continue
        text = read_text(snapshot.root / path)
        for token in FORBIDDEN_RESIDUE:
            if token in text:
                result.failures.append(f"product-specific residue {token!r} in {path}")
                break

    return result


def print_snapshot(snapshot: RepoSnapshot) -> None:
    print("commit audit")
    print(
        "  version: "
        f"current={snapshot.version or '<missing>'}, "
        f"HEAD={snapshot.head_version or '<missing>'}, "
        f"lite={snapshot.lite_version or '<missing>'}"
    )
    print(f"  changed files: {len(snapshot.changed_files)}")
    print(f"\n== recent commits ==\n{snapshot.log or '<empty>'}")
    print(f"\n== working tree ==\n{snapshot.status or '<empty>'}")
    print(f"\n== diff stat ==\n{snapshot.stat or '<empty>'}")


def print_result(result: AuditResult) -> None:
    if result.warnings:
        print("\nWARNINGS:")
        for item in result.warnings:
            print(f"  - {item}")
    else:
        print("\nWARNINGS: none")

    if result.failures:
        print("\nFAILURES:")
        for item in result.failures:
            print(f"  - {item}")
    else:
        print("\nFAILURES: none")


def audit(root: Path, *, strict_release: bool, max_log: int) -> int:
    snapshot = collect_snapshot(root, max_log)
    result = evaluate(snapshot)
    print_snapshot(snapshot)
    print_result(result)
    return 1 if strict_release and result.failures else 0


def write_skill(path: Path, version: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        "name: freertos-embedded-architect\n"
        "metadata:\n"
        f"  version: {version}\n"
        "description: >-\n"
        "  Test skill. Use when auditing releases.\n"
        "---\n",
        encoding="utf-8",
    )


def write_release_docs(root: Path, version: str, *, refactor: bool = True, impact: bool = True) -> None:
    markers: list[str] = []
    if refactor:
        markers.append("major-refactor: yes")
    if impact:
        markers.append("20x-impact: release safety gate")
    body = "\n".join(f"- {marker}" for marker in markers)
    (root / "CHANGELOG.md").write_text(f"# Changelog\n\n## {version}\n\n{body}\n", encoding="utf-8")
    (root / "references").mkdir(parents=True, exist_ok=True)
    (root / "references" / "iteration_log.md").write_text(
        f"# Iteration\n\n### {version}\n\n{body}\n",
        encoding="utf-8",
    )


def init_fixture_repo(root: Path, version: str = "1.2.3") -> None:
    (root / "freertos-skill-lite").mkdir(parents=True, exist_ok=True)
    write_skill(root / "SKILL.md", version)
    write_skill(root / "freertos-skill-lite" / "SKILL.md", version)
    write_release_docs(root, version)
    run_git(root, ["init"], check=True)
    run_git(root, ["config", "user.email", "audit@example.invalid"], check=True)
    run_git(root, ["config", "user.name", "Audit Test"], check=True)
    run_git(root, ["add", "."], check=True)
    run_git(root, ["commit", "-m", "test: initial"], check=True)


def run_self_test() -> int:
    cases: list[tuple[str, callable, tuple[str, ...]]] = []

    def valid_minor(root: Path) -> None:
        init_fixture_repo(root, "1.2.3")
        write_skill(root / "SKILL.md", "1.3.0")
        write_skill(root / "freertos-skill-lite" / "SKILL.md", "1.3.0")
        write_release_docs(root, "1.3.0")

    cases.append(("valid minor", valid_minor, ()))

    def version_mismatch(root: Path) -> None:
        init_fixture_repo(root, "1.2.3")
        write_skill(root / "SKILL.md", "1.3.0")
        write_skill(root / "freertos-skill-lite" / "SKILL.md", "1.2.3")
        write_release_docs(root, "1.3.0")

    cases.append(("version mismatch", version_mismatch, ("SKILL.md version",)))

    def major_missing_refactor(root: Path) -> None:
        init_fixture_repo(root, "1.2.3")
        write_skill(root / "SKILL.md", "2.0.0")
        write_skill(root / "freertos-skill-lite" / "SKILL.md", "2.0.0")
        write_release_docs(root, "2.0.0", refactor=False, impact=True)

    cases.append(("major missing refactor", major_missing_refactor, ("whole-skill refactor",)))

    def major_missing_impact(root: Path) -> None:
        init_fixture_repo(root, "1.2.3")
        write_skill(root / "SKILL.md", "2.0.0")
        write_skill(root / "freertos-skill-lite" / "SKILL.md", "2.0.0")
        write_release_docs(root, "2.0.0", refactor=True, impact=False)

    cases.append(("major missing 20x", major_missing_impact, ("20x efficiency",)))

    def product_residue(root: Path) -> None:
        init_fixture_repo(root, "1.2.3")
        (root / "prompts").mkdir(exist_ok=True)
        (root / "prompts" / "bad.txt").write_text("AI" + "Alarm" + "Clock", encoding="utf-8")

    cases.append(("product residue", product_residue, ("product-specific residue",)))

    failures: list[str] = []
    for name, setup, expected_fragments in cases:
        with tempfile.TemporaryDirectory(prefix="commit-audit-") as tmp:
            root = Path(tmp)
            setup(root)
            result = evaluate(collect_snapshot(root, 4))
            text = "\n".join(result.failures + result.warnings)
            ok = all(fragment in text for fragment in expected_fragments)
            if not expected_fragments:
                ok = not result.failures
            if ok:
                print(f"[PASS] {name}")
            else:
                failures.append(f"{name}: expected {expected_fragments}, got {result}")
                print(f"[FAIL] {name}")

    if failures:
        print("[commit-audit:self-test] failed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("[commit-audit:self-test] all fixtures passed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit recent commits and current release state")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="repository root")
    parser.add_argument("--max-log", type=int, default=12, help="number of recent commits to show")
    parser.add_argument("--strict-release", action="store_true", help="fail on release-gate violations")
    parser.add_argument("--self-test", action="store_true", help="run positive/negative fixture tests")
    args = parser.parse_args()
    if args.self_test:
        return run_self_test()
    return audit(args.root.resolve(), strict_release=args.strict_release, max_log=args.max_log)


if __name__ == "__main__":
    sys.exit(main())
