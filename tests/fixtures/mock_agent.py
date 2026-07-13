#!/usr/bin/env python3
"""Mock agent for E2E protocol testing.

Outputs multiline JSON with case_id, workflow, clarification_required, initial_files.
Reads the prompt file and classifies using the real classify_request.

Usage:
    python tests/fixtures/mock_agent.py /path/to/prompt.txt
"""
import json
import sys
from pathlib import Path

# Add tools to path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from context_router import classify_request, WORKFLOWS

prompt_file = Path(sys.argv[1])
prompt_text = prompt_file.read_text(encoding="utf-8")

# Extract the request from the prompt (after "Request: ")
request = prompt_text.split("Request:", 1)[-1].strip() if "Request:" in prompt_text else prompt_text

# Extract case_id
import re
case_id_match = re.search(r'"case_id":\s*"([^"]+)"', prompt_text)
case_id = case_id_match.group(1) if case_id_match else "unknown"

result = classify_request(request)

if result.get("clarification_required"):
    decision = {
        "case_id": case_id,
        "workflow": None,
        "clarification_required": True,
        "initial_files": [],
    }
else:
    wf = result["workflow"]
    wf_file = WORKFLOWS.get(wf, {}).get("file", f"workflows/{wf}.md")
    decision = {
        "case_id": case_id,
        "workflow": wf,
        "clarification_required": False,
        "initial_files": [wf_file],
    }

# Output as multiline formatted JSON (tests parser robustness)
print(json.dumps(decision, ensure_ascii=False, indent=2))
