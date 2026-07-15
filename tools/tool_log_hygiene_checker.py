#!/usr/bin/env python3
"""C47 repository-wide MCP output hygiene audit."""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from checker_io import configure_stdout, make_issue, output_json

ROOT = Path(__file__).resolve().parent.parent
SENSITIVE_OUTPUT = re.compile(r"(?:print|logger\.(?:debug|info|warning|error))\s*\([^\n]*(?:password|passwd|token|secret|api[_-]?key)", re.I)
REDACTION_HINT = re.compile(r"redact|mask|\[REDACTED\]|sensitive", re.I)
def check() -> list[dict]:
    issues=[]
    for folder in (ROOT / "mcp",):
        for path in folder.glob("*.py"):
            if path.name.startswith("test_"): continue
            text=path.read_text(encoding="utf-8", errors="replace")
            for m in SENSITIVE_OUTPUT.finditer(text):
                line=text[:m.start()].count("\n")+1
                nearby=text[max(0,m.start()-180):m.start()+180]
                if not REDACTION_HINT.search(nearby):
                    issues.append(make_issue(path, line, "C47.1", "P0", "MCP output/log may expose a credential; redact before returning or logging"))
    return issues
def main() -> int:
    configure_stdout(); parser=argparse.ArgumentParser(); parser.add_argument("--jsonl",action="store_true"); parser.add_argument("--json",action="store_true"); args=parser.parse_args(); issues=check()
    payload={"protocol_version":"checker-result/v1","checker":"C47 tool log hygiene checker","domains":["C47"],"files_checked":len(list((ROOT/"mcp").glob("*.py"))),"violations":len(issues),"issues":issues}
    if args.jsonl: print(json.dumps(payload,ensure_ascii=False,separators=(",",":")))
    elif args.json: output_json(payload)
    else: print("C47 tool log hygiene: " + ("passed" if not issues else f"{len(issues)} issue(s)"))
    return 1 if issues else 0
if __name__ == "__main__": raise SystemExit(main())
