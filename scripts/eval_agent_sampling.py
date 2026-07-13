#!/usr/bin/env python3
"""
DEPRECATED — compatibility wrapper for eval_routing_sampling.py.

This script will be removed in the next major version.
Use eval_routing_sampling.py instead.

Usage:
    python scripts/eval_routing_sampling.py
    python scripts/eval_routing_sampling.py --json
"""
from __future__ import annotations

import sys
import warnings

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

warnings.warn(
    "eval_agent_sampling.py is deprecated. Use eval_routing_sampling.py instead. "
    "This wrapper will be removed in the next major version.",
    DeprecationWarning,
    stacklevel=1,
)

print(
    "WARNING: eval_agent_sampling.py is deprecated.\n"
    "  Use: python scripts/eval_routing_sampling.py\n"
    "  This wrapper will be removed in the next major version.\n",
    file=sys.stderr,
)

# Delegate to the new script
from pathlib import Path
import importlib.util

new_script = Path(__file__).resolve().parent / "eval_routing_sampling.py"
spec = importlib.util.spec_from_file_location("eval_routing_sampling", new_script)
module = importlib.util.module_from_spec(spec)

# Forward all arguments
sys.argv[0] = str(new_script)
spec.loader.exec_module(module)
raise SystemExit(module.main())
