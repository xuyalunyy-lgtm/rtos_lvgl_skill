#!/usr/bin/env bash
# Install FreeRTOS Skill for Claude Code → ~/.claude/skills/
# Usage: ./scripts/install_claude_code.sh
# Optional: ./scripts/install_claude_code.sh /path/to/firmware

set -euo pipefail
SOURCE="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${HOME}/.claude/skills/freertos-embedded-architect"
PROJECT_ROOT="${1:-}"

EXCLUDE=(
    --exclude .git
    --exclude fw-AC79_AIoT_SDK
    --exclude bk_idk-release-v2.2.1
    --exclude __pycache__
    --exclude freertos-skill-lite
)

if [[ ! -f "$SOURCE/SKILL.md" ]]; then
    echo "SKILL.md not found" >&2
    exit 1
fi

mkdir -p "$(dirname "$DEST")"
rm -rf "$DEST"
rsync -a "${EXCLUDE[@]}" "$SOURCE/" "$DEST/"

VER=$(awk '
  /^version:[[:space:]]*/ { sub(/^version:[[:space:]]*/, ""); print; exit }
  /^metadata:[[:space:]]*$/ { in_meta=1; next }
  in_meta && /^[^[:space:]]/ { in_meta=0 }
  in_meta && /^[[:space:]]+version:[[:space:]]*/ {
    sub(/^[[:space:]]+version:[[:space:]]*/, "");
    print;
    exit
  }
' "$DEST/SKILL.md")
echo "Claude Code skill installed: $DEST"
echo "Version: $VER"
echo "Invoke: /freertos-embedded-architect"
echo "Token guide: references/claude_code.md"

if [[ -n "$PROJECT_ROOT" && -d "$PROJECT_ROOT" ]]; then
    if [[ ! -f "$PROJECT_ROOT/CLAUDE.md" ]]; then
        cp "$SOURCE/templates/CLAUDE.embedded.md" "$PROJECT_ROOT/CLAUDE.md"
        echo "Created: $PROJECT_ROOT/CLAUDE.md (edit compile command)"
    fi
    if [[ ! -f "$PROJECT_ROOT/.claudeignore" ]]; then
        cp "$SOURCE/templates/claudeignore.embedded" "$PROJECT_ROOT/.claudeignore"
        echo "Created: $PROJECT_ROOT/.claudeignore"
    fi
fi

echo "Restart Claude Code to discover skill."
