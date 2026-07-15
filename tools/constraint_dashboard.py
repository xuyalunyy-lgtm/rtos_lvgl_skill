#!/usr/bin/env python3
"""Render machine-readable constraint/checker coverage from the registry."""
from __future__ import annotations
import json
from collections import defaultdict
from checker_registry import ALL_CHECKERS, CONSTRAINT_MIGRATIONS, CONSTRAINT_SCHEMA_VERSION

MANUAL = {"C6", "C30", "C40"}
def main() -> int:
    coverage=defaultdict(list)
    for spec in ALL_CHECKERS:
        for domain in spec.domains: coverage[domain.split(".",1)[0]].append(spec.name)
    rows=[]
    for number in range(1,49):
        cid=f"C{number}"; checkers=sorted(coverage.get(cid,[]))
        rows.append({"constraint":cid,"status":"automatic" if checkers else "manual" if cid in MANUAL else "missing","checkers":checkers})
    print(json.dumps({"schema_version":CONSTRAINT_SCHEMA_VERSION,"migrations":CONSTRAINT_MIGRATIONS,"constraints":rows},ensure_ascii=False,indent=2))
    return 0
if __name__ == "__main__": raise SystemExit(main())
