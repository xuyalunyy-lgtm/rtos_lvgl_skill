#!/usr/bin/env bash
# 同步完整版 prompts/、platforms/ → freertos-skill-lite/
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec python3 scripts/sync_lite.py "$@"
