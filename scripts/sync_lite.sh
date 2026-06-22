#!/usr/bin/env bash
# 同步完整版 agents/、prompts/、platforms/、workflows/、references/ → freertos-skill-lite/
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec python3 scripts/sync_lite.py "$@"
