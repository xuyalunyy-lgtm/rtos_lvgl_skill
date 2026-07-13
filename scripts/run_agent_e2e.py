#!/usr/bin/env python3
"""
Agent E2E executor — runs frozen requests through a real Agent and produces
a machine-readable report for validation.

Usage:
    # With explicit command:
    python scripts/run_agent_e2e.py --agent-command "codex --model gpt-4"

    # With environment variable:
    E2E_AGENT_COMMAND="codex --model gpt-4" python scripts/run_agent_e2e.py

    # Mock mode (for local testing):
    python scripts/run_agent_e2e.py --mock

    # Output:
    python scripts/run_agent_e2e.py --json > artifacts/agent_e2e_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Frozen requests (shared with validate_agent_e2e.py) ──

from e2e_fixtures import FROZEN_REQUESTS

AGENT_PROMPT_TEMPLATE = """You are a firmware architect assistant. For the following request, respond with ONLY a JSON object (no markdown, no explanation):

{{
  "case_id": "{case_id}",
  "workflow": "<chosen workflow name or null if clarification needed>",
  "clarification_required": <true or false>,
  "initial_files": ["<list of files you would load first>"]
}}

Request: {request}
"""


def run_mock(request: dict) -> dict:
    """Mock agent that uses classify_request for deterministic testing."""
    sys.path.insert(0, str(ROOT / "tools"))
    from context_router import classify_request, WORKFLOWS

    result = classify_request(request["request"])
    if result.get("clarification_required"):
        return {
            "case_id": request["id"],
            "workflow": None,
            "clarification_required": True,
            "initial_files": [],
        }
    wf = result["workflow"]
    wf_file = WORKFLOWS.get(wf, {}).get("file", f"workflows/{wf}.md")
    return {
        "case_id": request["id"],
        "workflow": wf,
        "clarification_required": False,
        "initial_files": [wf_file],
    }


def run_agent(request: dict, agent_command: str, timeout: int = 60) -> dict:
    """Run a single request through the Agent."""
    prompt = AGENT_PROMPT_TEMPLATE.format(
        case_id=request["id"],
        request=request["request"],
    )

    def _try_once() -> dict:
        """Single attempt to run agent and parse result."""
        import shlex

        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_file = Path(tmpdir) / "prompt.txt"
            prompt_file.write_text(prompt, encoding="utf-8")

            start = time.time()
            try:
                cmd_parts = shlex.split(agent_command) + [str(prompt_file)]
            except ValueError:
                # Fallback for malformed commands
                cmd_parts = agent_command.split() + [str(prompt_file)]

            proc = subprocess.run(
                cmd_parts,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmpdir,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            elapsed = time.time() - start

            if proc.returncode != 0:
                return {
                    "case_id": request["id"],
                    "error": "execution_error",
                    "stderr": proc.stderr[:500],
                    "elapsed_seconds": elapsed,
                }

            # Parse JSON from stdout: try full output first, then line-by-line
            output = proc.stdout.strip()

            # 1) Try parsing entire stdout as JSON
            try:
                decision = json.loads(output)
                if isinstance(decision, dict):
                    decision["elapsed_seconds"] = elapsed
                    return decision
            except json.JSONDecodeError:
                pass

            # 2) Try extracting JSON object from mixed output
            import re
            json_match = re.search(r'\{[^{}]*"case_id"[^{}]*\}', output, re.DOTALL)
            if json_match:
                try:
                    decision = json.loads(json_match.group())
                    decision["elapsed_seconds"] = elapsed
                    return decision
                except json.JSONDecodeError:
                    pass

            # 3) Line-by-line fallback
            for line in output.splitlines():
                line = line.strip()
                if line.startswith("{"):
                    try:
                        decision = json.loads(line)
                        decision["elapsed_seconds"] = elapsed
                        return decision
                    except json.JSONDecodeError:
                        continue

            return {
                "case_id": request["id"],
                "error": "parse_error",
                "raw_output": output[:500],
                "elapsed_seconds": elapsed,
            }

    # Execute with single retry on failure
    for attempt in range(2):
        try:
            result = _try_once()
            if result.get("error") and attempt == 0:
                time.sleep(2)  # Brief pause before retry
                continue
            return result
        except subprocess.TimeoutExpired:
            if attempt == 0:
                time.sleep(2)
                continue
            return {
                "case_id": request["id"],
                "error": "timeout",
                "timeout_seconds": timeout,
            }
        except Exception as e:
            if attempt == 0:
                time.sleep(2)
                continue
            return {
                "case_id": request["id"],
                "error": "execution_error",
                "stderr": str(e)[:500],
            }

    # Should not reach here, but just in case
    return {"case_id": request["id"], "error": "max_retries_exceeded"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent E2E executor")
    parser.add_argument("--agent-command", help="Agent command (or set E2E_AGENT_COMMAND)")
    parser.add_argument("--mock", action="store_true", help="Use mock agent for testing")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    parser.add_argument("--timeout", type=int, default=60, help="Per-request timeout in seconds")
    args = parser.parse_args()

    agent_command = args.agent_command or os.environ.get("E2E_AGENT_COMMAND", "")
    if not args.mock and not agent_command:
        print("ERROR: provide --agent-command or set E2E_AGENT_COMMAND (or use --mock)", file=sys.stderr)
        return 1

    import hashlib
    import platform

    # Sanitize: don't persist full command (may contain secrets)
    if args.mock:
        agent_label = "mock:classify_request"
    else:
        cmd_hash = hashlib.sha256(agent_command.encode()).hexdigest()[:12]
        # Extract binary name only (e.g., "codex" from "codex --model gpt-4")
        binary = agent_command.split()[0] if agent_command else "unknown"
        agent_label = f"{binary} (cmd_hash={cmd_hash})"

    report = {
        "meta": {
            "total": len(FROZEN_REQUESTS),
            "agent_label": agent_label,
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "commit_sha": subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True
            ).stdout.strip() if (ROOT / ".git").exists() else "unknown",
        },
        "decisions": [],
    }

    for req in FROZEN_REQUESTS:
        if args.mock:
            decision = run_mock(req)
        else:
            decision = run_agent(req, agent_command, args.timeout)
        report["decisions"].append(decision)

    # Summary
    errors = sum(1 for d in report["decisions"] if d.get("error"))
    completed = report["meta"]["total"] - errors
    report["meta"]["completed"] = completed
    report["meta"]["errors"] = errors

    if args.json:
        json.dump(report, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        print(f"Agent E2E Report: {completed}/{report['meta']['total']} completed")
        print(f"Agent: {report['meta']['agent_label']}")
        print(f"Commit: {report['meta']['commit_sha'][:12]}")
        for d in report["decisions"]:
            if d.get("error"):
                print(f"  [{d['error']}] {d['case_id']}")
            else:
                wf = d.get("workflow") or "clarification"
                print(f"  [ok] {d['case_id']} → {wf}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
