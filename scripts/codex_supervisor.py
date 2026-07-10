#!/usr/bin/env python3
"""
Codex Supervisor v10 — Supervised Codex managed execution system.

Four-phase controlled flow: Plan → Gate → Execute → Verify
Subcommand architecture:    plan | gate | run | verify | status | queue

Usage:
    python scripts/codex_supervisor.py plan --job .codex/jobs/fix-checker.json
    python scripts/codex_supervisor.py gate --plan .codex/runs/<id>/plan.json
    python scripts/codex_supervisor.py run  --job .codex/jobs/fix-checker.json
    python scripts/codex_supervisor.py run  --job .codex/jobs/fix-checker.json --dry-run
    python scripts/codex_supervisor.py verify --run-id <run_id>
    python scripts/codex_supervisor.py status --run-id <run_id>
    python scripts/codex_supervisor.py queue
    python scripts/codex_supervisor.py --self-test

Architecture:
    Plan  → Codex read-only analysis, outputs structured JSON plan
    Gate  → Safety gate: risk/path/command/network/destructive composite decision
    Execute → Codex workspace-write modifies code per plan (isolated branch/worktree)
    Verify  → git diff --check + checker suite + iteration check
    Report  → Aggregate Plan+Gate+AgentResult+Evidence+diff+verification
    Retry   → Retry with context on failure, re-gate each iteration, bounded loop
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path

# Force UTF-8
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
CODEX_DIR = ROOT / ".codex"
SCHEMAS_DIR = CODEX_DIR / "schemas"
HOOKS_FILE = CODEX_DIR / "hooks.json"
JOBS_DIR = CODEX_DIR / "jobs"
RUNS_DIR = CODEX_DIR / "runs"


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class JobDef:
    """Job definition."""
    job_id: str = ""
    intent: str = ""
    created_at: str = ""
    priority: str = "normal"
    allowed_paths: list[str] = field(default_factory=list)
    blocked_paths: list[str] = field(default_factory=list)
    allowed_commands: list[str] = field(default_factory=list)
    blocked_commands: list[str] = field(default_factory=list)
    risk_preference: str = "auto_low"
    max_iterations: int = 3
    require_clean_worktree: bool = True
    isolation_mode: str = "branch"
    verification_commands: list[dict] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    rollback_strategy: str = "delete_branch"
    context: str = ""
    tags: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    timeout_seconds: int = 600


@dataclass
class PlanResult:
    """Plan phase output."""
    intent: str = ""
    analysis: str = ""
    files_to_change: list[str] = field(default_factory=list)
    files_to_read: list[str] = field(default_factory=list)
    commands: list[dict] = field(default_factory=list)
    risk_level: str = "medium"
    risk_reason: str = ""
    destructive: bool = False
    requires_network: bool = False
    touches_protected: list[str] = field(default_factory=list)
    acceptance_tests: list[str] = field(default_factory=list)
    rollback: str = ""
    estimated_changes: int = 0


@dataclass
class GateDecision:
    """Gate decision."""
    decision: str = "reject"       # approve / reject / needs_confirmation / needs_review
    risk_level: str = "medium"
    risk_score: float = 0.0
    timestamp: str = ""
    reasons: list[dict] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    allowed_paths: list[str] = field(default_factory=list)
    blocked_paths: list[str] = field(default_factory=list)
    allowed_commands: list[str] = field(default_factory=list)
    blocked_commands: list[str] = field(default_factory=list)
    auto_approve: bool = False
    estimated_impact: dict = field(default_factory=dict)


@dataclass
class AgentResult:
    """Agent execution phase output."""
    status: str = "failed"
    files_changed: list[dict] = field(default_factory=list)
    commands_run: list[dict] = field(default_factory=list)
    deviations: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class SupervisorReport:
    """Final managed delivery report."""
    run_id: str = ""
    job_id: str = ""
    status: str = "pending"
    started_at: str = ""
    finished_at: str = ""
    duration_seconds: float = 0.0
    iterations: int = 0
    max_iterations: int = 3
    branch: str = ""
    isolation_mode: str = "branch"
    plan: dict = field(default_factory=dict)
    gate_decisions: list[dict] = field(default_factory=list)
    agent_results: list[dict] = field(default_factory=list)
    verification_results: list[dict] = field(default_factory=list)
    diff_stat: str = ""
    diff_summary: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)
    repro_bundle: dict = field(default_factory=dict)
    reproduce_commands: list[dict] = field(default_factory=list)
    rollback_command: str = ""
    remaining_risks: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    log_path: str = ""


# ============================================================================
# Configuration Loading
# ============================================================================

def load_hooks() -> dict:
    if HOOKS_FILE.exists():
        return json.loads(HOOKS_FILE.read_text(encoding="utf-8"))
    return {}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(data: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ============================================================================
# Path/Command Safety
# ============================================================================

PROTECTED_PATHS = [
    ".git", ".codex", "secrets", "credentials",
    "*.pem", "*.key", "*.env", "*.secret",
    "node_modules", "vendor", "build", "dist", "__pycache__",
]

PROTECTED_PATTERNS = [
    "*secret*", "*credential*", "*password*", "*token*", "*.private.*",
]

DANGEROUS_COMMANDS = [
    r"\brm\s+-rf\b", r"\bformat\b", r"\bmkfs\b", r"\bdd\b.*of=",
    r"\bcurl\b.*\|\s*sh", r"\bwget\b.*\|\s*sh", r"\bsudo\b",
    r"\bchmod\s+777\b", r"\bgit\s+push\b.*--force", r"\bgit\s+reset\b.*--hard",
    r"\bdel\s+/[sfq]", r"\brmdir\s+/s\b",
]

ALLOWED_DIRS = [
    "tools/", "scripts/", "references/", "prompts/", "examples/",
    "templates/", "workflows/", "product_profiles/", "scene_presets/",
    "forward_tests/", "platforms/", "agents/",
]


def _match_path(path: str, patterns: list[str]) -> bool:
    p = path.lower().replace("\\", "/")
    for pat in patterns:
        if fnmatch(p, pat.lower()):
            return True
        if p.startswith(pat.lower().rstrip("/") + "/"):
            return True
    return False


def _is_in_allowed_dir(path: str) -> bool:
    f = path.replace("\\", "/")
    if "/" not in f and f.endswith((".md", ".json", ".yaml", ".yml")):
        return True
    return any(f.startswith(d) for d in ALLOWED_DIRS)


# ============================================================================
# Git Operations
# ============================================================================

def git_status_short() -> str:
    proc = subprocess.run(
        ["git", "status", "--short"],
        cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace", timeout=10,
    )
    return proc.stdout.strip()


def git_is_clean() -> bool:
    return len(git_status_short()) == 0


def git_create_branch(name: str) -> bool:
    proc = subprocess.run(
        ["git", "checkout", "-b", name],
        cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace", timeout=15,
    )
    return proc.returncode == 0


def git_checkout(branch: str) -> bool:
    proc = subprocess.run(
        ["git", "checkout", branch],
        cwd=ROOT, capture_output=True, timeout=15,
    )
    return proc.returncode == 0


def git_delete_branch(name: str):
    subprocess.run(
        ["git", "branch", "-D", name],
        cwd=ROOT, capture_output=True, timeout=10,
    )


def git_stash():
    subprocess.run(
        ["git", "stash", "--include-untracked"],
        cwd=ROOT, capture_output=True, timeout=15,
    )


def git_diff_stat() -> str:
    proc = subprocess.run(
        ["git", "diff", "--stat"],
        cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace", timeout=15,
    )
    return proc.stdout.strip()


def git_diff_check() -> tuple[int, str]:
    proc = subprocess.run(
        ["git", "diff", "--check"],
        cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace", timeout=15,
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def git_diff_numstat() -> dict:
    proc = subprocess.run(
        ["git", "diff", "--numstat"],
        cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace", timeout=15,
    )
    files = insertions = deletions = 0
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            files += 1
            insertions += int(parts[0]) if parts[0] != "-" else 0
            deletions += int(parts[1]) if parts[1] != "-" else 0
    return {"files_changed": files, "insertions": insertions, "deletions": deletions}


# ============================================================================
# Codex Interaction
# ============================================================================

def _extract_json(text: str) -> dict | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```json\s*\n(.*?)\n\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    start = -1
    return None


def run_codex(prompt: str, mode: str = "read-only", timeout: int = 300) -> dict:
    """Run Codex (CLI preferred, fallback to OpenAI API)."""
    # CLI
    cmd = ["codex", "exec", "--json"]
    if mode == "read-only":
        cmd.extend(["--sandbox", "read-only"])
    elif mode == "workspace-write":
        cmd.extend(["--sandbox", "workspace-write"])
    cmd.append(prompt)

    try:
        proc = subprocess.run(
            cmd, capture_output=True, encoding="utf-8", errors="replace",
            timeout=timeout, cwd=str(ROOT),
        )
        return {"exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        return {"exit_code": -2, "error": f"timeout after {timeout}s"}

    # Fallback API
    try:
        import openai
        client = openai.OpenAI()
        sys_msg = "You are a code analysis assistant. Output ONLY valid JSON. No markdown, just JSON."
        if mode == "read-only":
            sys_msg += " You MUST NOT modify any files."
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": prompt}],
            temperature=0.1, timeout=timeout,
        )
        return {"exit_code": 0, "stdout": resp.choices[0].message.content or "", "stderr": ""}
    except ImportError:
        return {"exit_code": -1, "error": "codex CLI not found and openai not installed"}
    except Exception as e:
        return {"exit_code": -1, "error": str(e)}


# ============================================================================
# Gate Engine (v10.0.4)
# ============================================================================

RISK_SCORE = {"low": 15, "medium": 40, "high": 70, "critical": 95}
RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def run_gate(plan: PlanResult, job: JobDef | None = None) -> GateDecision:
    """Run gate engine and return decision."""
    hooks = load_hooks()
    protected = hooks.get("protected_paths", PROTECTED_PATHS)
    protected_patterns = hooks.get("protected_patterns", PROTECTED_PATTERNS)

    decision = GateDecision(
        timestamp=datetime.now(timezone.utc).isoformat(),
        risk_level=plan.risk_level,
        risk_score=RISK_SCORE.get(plan.risk_level, 50),
    )

    # Gate 1: Protected paths
    for f in plan.files_to_change:
        if _match_path(f, protected):
            decision.violations.append(f"Protected path: {f}")
            decision.blocked_paths.append(f)
        elif _match_path(f, protected_patterns):
            decision.violations.append(f"Protected pattern: {f}")
            decision.blocked_paths.append(f)
        else:
            decision.allowed_paths.append(f)
    decision.reasons.append({
        "gate": "protected_paths",
        "result": "fail" if any("Protected" in v for v in decision.violations) else "pass",
        "detail": f"Checked {len(plan.files_to_change)} file(s)",
        "weight": 30,
    })

    # Gate 2: Dangerous commands
    for cmd_entry in plan.commands:
        cmd = cmd_entry.get("cmd", "") if isinstance(cmd_entry, dict) else str(cmd_entry)
        blocked = False
        for pat in DANGEROUS_COMMANDS:
            if re.search(pat, cmd, re.IGNORECASE):
                decision.violations.append(f"Dangerous command: {cmd}")
                decision.blocked_commands.append(cmd)
                blocked = True
                break
        if not blocked:
            decision.allowed_commands.append(cmd)
    decision.reasons.append({
        "gate": "dangerous_commands",
        "result": "fail" if any("Dangerous command" in v for v in decision.violations) else "pass",
        "detail": f"Checked {len(plan.commands)} command(s)",
        "weight": 25,
    })

    # Gate 3: Risk level (soft gate, does not directly reject)
    pref = job.risk_preference if job else "auto_low"
    pref_map = {"auto_low": 0, "auto_medium": 1, "manual_high": 2, "reject_critical": 3}
    pref_order = pref_map.get(pref, 0)
    plan_risk = RISK_ORDER.get(plan.risk_level, 2)

    if plan_risk > pref_order:
        decision.warnings.append(f"Risk {plan.risk_level} exceeds preference {pref}")
    decision.reasons.append({
        "gate": "risk_preference",
        "result": "warn" if plan_risk > pref_order else "pass",
        "detail": f"Plan risk={plan.risk_level}, preference={pref}",
        "weight": 20,
    })

    # Gate 4: Critical direct rejection
    if plan.risk_level == "critical":
        decision.violations.append("Critical risk does not allow automatic execution")
    decision.reasons.append({
        "gate": "critical_block",
        "result": "fail" if plan.risk_level == "critical" else "pass",
        "detail": "Critical risk hard block",
        "weight": 50,
    })

    # Gate 5: Destructive
    if plan.destructive:
        decision.warnings.append("Contains delete/overwrite operations")
        decision.risk_score += 10

    # Gate 6: Network requirement
    if plan.requires_network:
        decision.warnings.append("Requires network access")
        decision.risk_score += 5

    # Gate 7: File scope
    for f in plan.files_to_change:
        if not _is_in_allowed_dir(f):
            decision.warnings.append(f"Non-standard directory: {f}")

    # Gate 8: Change volume
    if plan.estimated_changes > 500:
        decision.warnings.append(f"Estimated {plan.estimated_changes} lines changed (>500)")
        decision.risk_score += 10

    decision.estimated_impact = {
        "files_count": len(plan.files_to_change),
        "lines_changed": plan.estimated_changes,
    }

    # Composite decision
    has_violations = len(decision.violations) > 0
    decision.auto_approve = (
        not has_violations
        and plan.risk_level == "low"
        and not plan.destructive
        and not plan.requires_network
    )

    if has_violations:
        decision.decision = "reject"
    elif plan.risk_level in ("high", "critical"):
        decision.decision = "needs_confirmation"
    elif plan.risk_level == "medium":
        decision.decision = "needs_review"
    else:
        decision.decision = "approve"

    # Clamp risk score
    decision.risk_score = min(100, max(0, decision.risk_score))

    return decision


# ============================================================================
# Plan Phase
# ============================================================================

def phase_plan(job: JobDef, context: str = "") -> PlanResult:
    """Plan phase: read-only analysis."""
    schema_path = SCHEMAS_DIR / "plan.schema.json"
    schema_str = ""
    if schema_path.exists():
        schema_str = schema_path.read_text(encoding="utf-8")

    prompt = f"""Analyze the following task and output a structured JSON plan.

Task: {job.intent}
{f'Context: {context}' if context else ''}
{f'Job context: {job.context}' if job.context else ''}

Repository: FreeRTOS embedded skill, main directories: tools/ scripts/ references/ examples/ scene_presets/ forward_tests/

Output JSON must include: intent, files_to_change, risk_level(low/medium/high/critical), destructive(bool), requires_network(bool)
Risk criteria: low=docs/tests, medium=tool scripts, high=checker core, critical=SKILL/checker_registry

Output JSON only."""

    result = run_codex(prompt, mode="read-only", timeout=300)

    plan = PlanResult(intent=job.intent)
    if result.get("exit_code") == 0:
        data = _extract_json(result.get("stdout", ""))
        if data:
            for key in PlanResult.__dataclass_fields__:
                if key in data:
                    setattr(plan, key, data[key])
    else:
        plan.risk_reason = f"Codex call failed: {result.get('error', 'unknown')}"

    return plan


# ============================================================================
# Execute Phase
# ============================================================================

def phase_execute(plan: PlanResult, job: JobDef, dry_run: bool = False) -> AgentResult:
    """Execute phase: execute per plan."""
    if dry_run:
        return AgentResult(status="skipped", notes="dry-run mode")

    prompt = f"""Strictly implement changes according to the approved plan below. Do not expand scope.

Plan:
{json.dumps(asdict(plan), indent=2, ensure_ascii=False)}

Rules:
1. Only modify files in files_to_change
2. Only implement the intent content
3. Run commands in commands
4. Output JSON: status(success/partial/failed), files_changed, commands_run, deviations, errors, notes
Output JSON only."""

    result = run_codex(prompt, mode="workspace-write", timeout=600)

    agent = AgentResult()
    if result.get("exit_code") == 0:
        data = _extract_json(result.get("stdout", ""))
        if data:
            for key in AgentResult.__dataclass_fields__:
                if key in data:
                    setattr(agent, key, data[key])
    else:
        agent.errors.append(f"Codex call failed: {result.get('error', 'unknown')}")

    return agent


# ============================================================================
# Verify Phase
# ============================================================================

def phase_verify(job: JobDef, iteration: int = 0) -> dict:
    """Verify phase: run verification suite."""
    checks = []
    all_passed = True

    # 1. git diff --check
    rc, output = git_diff_check()
    passed = rc == 0
    checks.append({"name": "git_diff_check", "passed": passed, "output": output[:500] or "clean"})
    if not passed:
        all_passed = False

    # 2. skill_iterate.py --check
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "skill_iterate.py"), "--check"],
        cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace",
        timeout=300, env={**os.environ, "PYTHONUTF8": "1"},
    )
    passed = proc.returncode == 0
    checks.append({"name": "skill_iterate", "passed": passed, "output": (proc.stdout + proc.stderr)[-800:]})
    if not passed:
        all_passed = False

    # 3. run_review --self-test
    proc2 = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "run_review.py"), "--self-test"],
        cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace",
        timeout=300, env={**os.environ, "PYTHONUTF8": "1"},
    )
    passed = proc2.returncode == 0
    checks.append({"name": "run_review_self_test", "passed": passed, "output": (proc2.stdout + proc2.stderr)[-500:]})
    if not passed:
        all_passed = False

    # 4. Custom verification commands
    for vc in job.verification_commands:
        cmd = vc.get("cmd", "")
        timeout = vc.get("timeout_seconds", 120)
        try:
            proc3 = subprocess.run(
                cmd, shell=True, capture_output=True, encoding="utf-8", errors="replace",
                timeout=timeout, cwd=str(ROOT),
            )
            passed = proc3.returncode == 0
        except Exception as e:
            passed = False
        checks.append({"name": vc.get("description", cmd), "passed": passed, "output": ""})
        if not passed:
            all_passed = False

    return {"all_passed": all_passed, "checks": checks, "iteration": iteration}


# ============================================================================
# Report Aggregation (v10.0.5)
# ============================================================================

def build_report(
    run_id: str, job: JobDef, plan: PlanResult, gates: list[GateDecision],
    agents: list[AgentResult], verifications: list[dict],
    branch: str, started_at: str, status: str,
) -> SupervisorReport:
    """Aggregate all phase outputs into final report."""
    now = datetime.now(timezone.utc).isoformat()
    started = datetime.fromisoformat(started_at)
    duration = (datetime.now(timezone.utc) - started).total_seconds()

    diff_stat = git_diff_stat()
    diff_summary = git_diff_numstat()

    # Reproduce commands
    repro = [
        {"cmd": f"python scripts/codex_supervisor.py run --job .codex/jobs/{job.job_id}.json",
         "description": "Reproduce managed execution"},
    ]

    # Rollback command
    rollback = ""
    if branch:
        rollback = f"git checkout main && git branch -D {branch}"

    report = SupervisorReport(
        run_id=run_id, job_id=job.job_id, status=status,
        started_at=started_at, finished_at=now, duration_seconds=duration,
        iterations=len(agents), max_iterations=job.max_iterations,
        branch=branch, isolation_mode=job.isolation_mode,
        plan=asdict(plan),
        gate_decisions=[asdict(g) for g in gates],
        agent_results=[asdict(a) for a in agents],
        verification_results=verifications,
        diff_stat=diff_stat, diff_summary=diff_summary,
        reproduce_commands=repro,
        rollback_command=rollback,
        errors=[e for a in agents for e in a.errors],
    )

    return report


def save_report(report: SupervisorReport, run_dir: Path):
    """Save report (JSON + Markdown)."""
    run_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    save_json(asdict(report), run_dir / "supervisor_report.json")

    # Markdown
    md_lines = [
        f"# Supervisor Report — {report.run_id}",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Job | {report.job_id} |",
        f"| Status | **{report.status}** |",
        f"| Iterations | {report.iterations}/{report.max_iterations} |",
        f"| Branch | {report.branch} |",
        f"| Duration | {report.duration_seconds:.1f}s |",
        "",
        "## Plan",
        f"- Intent: {report.plan.get('intent', 'N/A')}",
        f"- Risk: {report.plan.get('risk_level', 'N/A')}",
        f"- Files: {len(report.plan.get('files_to_change', []))}",
        "",
        "## Gate",
    ]
    for i, gate in enumerate(report.gate_decisions):
        md_lines.append(f"- 轮 {i+1}: **{gate.get('decision', 'N/A')}** (score={gate.get('risk_score', 0)})")
        for v in gate.get("violations", []):
            md_lines.append(f"  - ❌ {v}")
        for w in gate.get("warnings", []):
            md_lines.append(f"  - ⚠️ {w}")

    md_lines.extend(["", "## Diff", f"```", report.diff_stat, "```", ""])

    md_lines.append("## Verification")
    for vr in report.verification_results:
        md_lines.append(f"- 轮 {vr.get('iteration', '?')}: {'✅' if vr.get('all_passed') else '❌'}")
        for c in vr.get("checks", []):
            md_lines.append(f"  - {'✅' if c.get('passed') else '❌'} {c.get('name', '')}")

    if report.errors:
        md_lines.extend(["", "## Errors"])
        for e in report.errors:
            md_lines.append(f"- {e}")

    if report.rollback_command:
        md_lines.extend(["", "## Rollback", f"```bash", report.rollback_command, "```"])

    (run_dir / "supervisor_report.md").write_text("\n".join(md_lines), encoding="utf-8")


# ============================================================================
# Logging (v10.0.2)
# ============================================================================

class RunLogger:
    """JSONL run logger."""
    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.log_path = run_dir / "run.jsonl"
        run_dir.mkdir(parents=True, exist_ok=True)

    def log(self, event: str, data: dict | None = None):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **(data or {}),
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ============================================================================
# Dirty Tree Detection (v10.0.3)
# ============================================================================

def check_worktree(job: JobDef, logger: RunLogger) -> tuple[bool, str]:
    """Check worktree status, return (ok, message)."""
    dirty = git_status_short()
    if dirty and job.require_clean_worktree:
        logger.log("dirty_tree_detected", {"files": dirty[:500]})
        return False, f"Worktree has uncommitted changes:\n{dirty[:300]}\n\nPlease commit/stash first or set require_clean_worktree=false in the job"
    return True, ""


# ============================================================================
# Main Orchestration (v10.0.2/v10.0.6)
# ============================================================================

def run_pipeline(job: JobDef, dry_run: bool = False, json_output: bool = False) -> SupervisorReport:
    """Main orchestration: Plan → Gate → Execute → Verify (bounded retry)."""
    run_id = uuid.uuid4().hex[:12]
    run_dir = RUNS_DIR / run_id
    logger = RunLogger(run_dir)
    started_at = datetime.now(timezone.utc).isoformat()

    def _log(msg: str):
        logger.log("info", {"message": msg})
        if not json_output:
            print(f"[supervisor:{run_id[:8]}] {msg}", flush=True)

    _log(f"Started: {job.intent[:60]}")

    # Dirty tree detection
    ok, msg = check_worktree(job, logger)
    if not ok:
        report = SupervisorReport(
            run_id=run_id, job_id=job.job_id, status="aborted",
            started_at=started_at, errors=[msg],
        )
        save_report(report, run_dir)
        return report

    # Isolation branch
    branch = f"codex-auto/{run_id}"
    if not dry_run and job.isolation_mode != "none":
        if job.isolation_mode == "branch":
            git_stash()
            git_create_branch(branch)
            _log(f"Created branch: {branch}")

    # Retry loop
    gates: list[GateDecision] = []
    agents: list[AgentResult] = []
    verifications: list[dict] = []
    status = "pending"

    for iteration in range(1, job.max_iterations + 1):
        _log(f"\n{'='*40} 迭代 {iteration}/{job.max_iterations} {'='*40}")

        # Phase 1: Plan
        _log("Phase 1: Plan")
        prev_context = ""
        if iteration > 1 and verifications:
            last = verifications[-1]
            failed = [c for c in last.get("checks", []) if not c.get("passed")]
            if failed:
                prev_context = "Previous verification failed:\n" + "\n".join(
                    f"- {c['name']}: {c.get('output', '')[:200]}" for c in failed
                )
        plan = phase_plan(job, prev_context)
        _log(f"  Risk={plan.risk_level}, Files={len(plan.files_to_change)}")

        # Phase 2: Gate
        _log("Phase 2: Gate")
        gate = run_gate(plan, job)
        gates.append(gate)
        _log(f"  Decision={gate.decision}, Score={gate.risk_score}")

        if gate.violations:
            for v in gate.violations:
                _log(f"  ❌ {v}")

        if gate.decision == "reject":
            status = "aborted"
            _log("Gate rejected, aborting.")
            break

        if gate.decision == "needs_confirmation" and not dry_run:
            _log("⚠️ Requires manual confirmation, auto-approved in non-interactive mode.")

        # Phase 3: Execute
        _log("Phase 3: Execute")
        agent = phase_execute(plan, job, dry_run=dry_run)
        agents.append(agent)
        _log(f"  Status={agent.status}")

        if agent.status == "failed":
            _log(f"  Failed: {agent.errors}")
            if iteration < job.max_iterations:
                _log("  Cleaning up changes, preparing to retry...")
                subprocess.run(["git", "checkout", "."], cwd=ROOT, capture_output=True, timeout=15)
            continue

        if dry_run:
            status = "dry_run"
            break

        # Phase 4: Verify
        _log("Phase 4: Verify")
        diff_stat = git_diff_stat()
        if diff_stat:
            _log(f"  Diff: {diff_stat[:200]}")

        verification = phase_verify(job, iteration)
        verifications.append(verification)
        _log(f"  Verification: {'Passed' if verification['all_passed'] else 'Failed'}")

        for c in verification.get("checks", []):
            _log(f"    {'✅' if c['passed'] else '❌'} {c['name']}")

        if verification["all_passed"]:
            status = "success"
            _log(f"\n✅ Success! ({iteration} iteration(s))")
            break

        if iteration < job.max_iterations:
            _log("Verification failed, cleaning up and retrying...")
            subprocess.run(["git", "checkout", "."], cwd=ROOT, capture_output=True, timeout=15)
    else:
        status = "failed"
        _log(f"\n❌ Exceeded maximum retries ({job.max_iterations})")

    # Aggregate report
    report = build_report(
        run_id, job, plan if 'plan' in dir() else PlanResult(),
        gates, agents, verifications, branch, started_at, status,
    )
    report.log_path = str(logger.log_path)
    save_report(report, run_dir)

    # Failure cleanup
    if status in ("failed", "aborted") and not dry_run:
        git_checkout("main")
        git_delete_branch(branch)
        report.rollback_command = f"Auto-rolled back: deleted branch {branch}"

    _log(f"Report: {run_dir}")
    return report


# ============================================================================
# Subcommands (v10.0.2)
# ============================================================================

def _load_job(path: str) -> JobDef:
    """Load job JSON file."""
    data = load_json(Path(path))
    known = {f.name for f in JobDef.__dataclass_fields__.values()}
    return JobDef(**{k: v for k, v in data.items() if k in known})


def cmd_plan(args) -> int:
    """plan subcommand: generate plan only."""
    job = _load_job(args.job)
    plan = phase_plan(job, args.context or "")

    if args.output:
        save_json(asdict(plan), Path(args.output))
        print(f"Plan saved: {args.output}")
    else:
        print(json.dumps(asdict(plan), indent=2, ensure_ascii=False))
    return 0


def cmd_gate(args) -> int:
    """gate subcommand: validate plan against gate."""
    plan_data = load_json(Path(args.plan))
    known = {f.name for f in PlanResult.__dataclass_fields__.values()}
    plan = PlanResult(**{k: v for k, v in plan_data.items() if k in known})

    job = _load_job(args.job) if args.job else JobDef()
    gate = run_gate(plan, job)

    print(json.dumps(asdict(gate), indent=2, ensure_ascii=False))
    return 0 if gate.decision != "reject" else 1


def cmd_run(args) -> int:
    """run subcommand: full orchestration."""
    job = _load_job(args.job)
    if args.max_iterations:
        job.max_iterations = args.max_iterations

    report = run_pipeline(job, dry_run=args.dry_run, json_output=args.json)

    if args.json:
        print(json.dumps(asdict(report), indent=2, ensure_ascii=False))
    else:
        print(f"\n{'='*50}")
        print(f"Run {report.run_id}: {report.status}")
        print(f"Iterations: {report.iterations}, Duration: {report.duration_seconds:.1f}s")
        if report.branch:
            print(f"Branch: {report.branch}")
        print(f"Report: {RUNS_DIR / report.run_id}")
        print(f"{'='*50}")

    return 0 if report.status in ("success", "dry_run") else 1


def cmd_verify(args) -> int:
    """verify subcommand: re-run verification."""
    run_dir = RUNS_DIR / args.run_id
    report_path = run_dir / "supervisor_report.json"
    if not report_path.exists():
        print(f"Error: run {args.run_id} not found", file=sys.stderr)
        return 1

    report_data = load_json(report_path)
    job = _load_job(str(JOBS_DIR / f"{report_data['job_id']}.json")) if (JOBS_DIR / f"{report_data['job_id']}.json").exists() else JobDef()
    verification = phase_verify(job)

    print(json.dumps(verification, indent=2, ensure_ascii=False))
    return 0 if verification["all_passed"] else 1


def cmd_status(args) -> int:
    """status subcommand: view run status."""
    run_dir = RUNS_DIR / args.run_id
    report_path = run_dir / "supervisor_report.json"
    if not report_path.exists():
        print(f"Error: run {args.run_id} not found", file=sys.stderr)
        return 1

    report = load_json(report_path)
    print(f"Run:       {report.get('run_id')}")
    print(f"Job:       {report.get('job_id')}")
    print(f"Status:    {report.get('status')}")
    print(f"Started:   {report.get('started_at')}")
    print(f"Finished:  {report.get('finished_at')}")
    print(f"Iterations:{report.get('iterations')}/{report.get('max_iterations')}")
    print(f"Branch:    {report.get('branch')}")
    if report.get("diff_stat"):
        print(f"Diff:   {report['diff_stat'][:100]}")
    return 0


def cmd_queue(args) -> int:
    """queue 子命令：列出待处理 jobs。"""
    if not JOBS_DIR.is_dir():
        print("无待处理任务。")
        return 0

    jobs = sorted(JOBS_DIR.glob("*.json"))
    if not jobs:
        print("无待处理任务。")
        return 0

    print(f"待处理任务: {len(jobs)} 个")
    for jf in jobs:
        try:
            data = load_json(jf)
            print(f"  {data.get('job_id', jf.stem):20s} {data.get('intent', '')[:60]}")
        except Exception:
            print(f"  {jf.stem:20s} (解析失败)")
    return 0


# ============================================================================
# 自测 (v10.0.8)
# ============================================================================

def run_self_test() -> int:
    passed = 0
    failed = 0

    # 1. JobDef
    job = JobDef(job_id="test-1", intent="test task")
    assert job.job_id == "test-1"
    print("[PASS] JobDef construction")
    passed += 1

    # 2. PlanResult
    plan = PlanResult(intent="test", files_to_change=["tools/x.py"], risk_level="low")
    assert plan.risk_level == "low"
    print("[PASS] PlanResult construction")
    passed += 1

    # 3. Gate — low risk approve
    gate = run_gate(plan, job)
    assert gate.decision == "approve"
    assert gate.auto_approve is True
    print("[PASS] Gate: low risk → approve")
    passed += 1

    # 4. Gate — protected path
    plan_bad = PlanResult(intent="bad", files_to_change=[".git/config"], risk_level="low")
    gate2 = run_gate(plan_bad, job)
    assert gate2.decision == "reject"
    assert any("保护" in v for v in gate2.violations)
    print("[PASS] Gate: protected path → reject")
    passed += 1

    # 5. Gate — dangerous command
    plan_danger = PlanResult(intent="danger", files_to_change=["tools/x.py"],
                             commands=[{"cmd": "rm -rf /tmp/x"}], risk_level="low")
    gate3 = run_gate(plan_danger, job)
    assert gate3.decision == "reject"
    print("[PASS] Gate: dangerous command → reject")
    passed += 1

    # 6. Gate — risk preference
    plan_high = PlanResult(intent="high", files_to_change=["tools/x.py"], risk_level="high")
    gate4 = run_gate(plan_high, job)
    assert gate4.decision == "needs_confirmation"
    print("[PASS] Gate: high risk → needs_confirmation")
    passed += 1

    # 7. Gate — critical block
    plan_crit = PlanResult(intent="crit", files_to_change=["tools/x.py"], risk_level="critical")
    gate5 = run_gate(plan_crit, JobDef(risk_preference="reject_critical"))
    assert gate5.decision == "reject"
    print("[PASS] Gate: critical → reject")
    passed += 1

    # 8. Gate — medium risk
    plan_med = PlanResult(intent="med", files_to_change=["tools/x.py"], risk_level="medium")
    gate6 = run_gate(plan_med, job)
    assert gate6.decision == "needs_review"
    print("[PASS] Gate: medium → needs_review")
    passed += 1

    # 9. _extract_json
    assert _extract_json('```json\n{"a":1}\n```') == {"a": 1}
    assert _extract_json('text {"a":2} more') == {"a": 2}
    print("[PASS] _extract_json")
    passed += 1

    # 10. git_is_clean (structural)
    assert isinstance(git_is_clean(), bool)
    print("[PASS] git_is_clean")
    passed += 1

    # 11. RunLogger
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        logger = RunLogger(Path(tmp))
        logger.log("test", {"key": "value"})
        assert logger.log_path.exists()
        line = logger.log_path.read_text().strip()
        data = json.loads(line)
        assert data["event"] == "test"
        print("[PASS] RunLogger")
        passed += 1

    # 12. Schema 文件存在
    for name in ["job.schema.json", "plan.schema.json", "gate_decision.schema.json",
                  "agent_result.schema.json", "supervisor_report.schema.json"]:
        assert (SCHEMAS_DIR / name).exists(), f"Missing schema: {name}"
    print(f"[PASS] {5} schemas exist")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


# ============================================================================
# CLI
# ============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Codex Supervisor v10 — 受监管的 Codex 托管执行系统",
    )
    sub = parser.add_subparsers(dest="command")

    # plan
    p_plan = sub.add_parser("plan", help="只读分析，生成计划")
    p_plan.add_argument("--job", required=True, help="Job JSON 文件路径")
    p_plan.add_argument("--context", default="", help="额外上下文")
    p_plan.add_argument("--output", "-o", help="计划输出文件")

    # gate
    p_gate = sub.add_parser("gate", help="校验计划是否通过门禁")
    p_gate.add_argument("--plan", required=True, help="Plan JSON 文件路径")
    p_gate.add_argument("--job", help="Job JSON 文件（可选）")

    # run
    p_run = sub.add_parser("run", help="完整编排：Plan → Gate → Execute → Verify")
    p_run.add_argument("--job", required=True, help="Job JSON 文件路径")
    p_run.add_argument("--max-iterations", type=int, help="覆盖最大重试次数")
    p_run.add_argument("--dry-run", action="store_true", help="只生成计划，不执行")
    p_run.add_argument("--json", action="store_true", help="JSON 输出")

    # verify
    p_verify = sub.add_parser("verify", help="重新运行验证套件")
    p_verify.add_argument("--run-id", required=True, help="Run ID")

    # status
    p_status = sub.add_parser("status", help="查看 run 状态")
    p_status.add_argument("--run-id", required=True, help="Run ID")

    # queue
    sub.add_parser("queue", help="列出待处理 jobs")

    # self-test
    parser.add_argument("--self-test", action="store_true", help="运行自测")

    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.command:
        parser.print_help()
        return 1

    handlers = {
        "plan": cmd_plan,
        "gate": cmd_gate,
        "run": cmd_run,
        "verify": cmd_verify,
        "status": cmd_status,
        "queue": cmd_queue,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
