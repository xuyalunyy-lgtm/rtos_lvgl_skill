#!/usr/bin/env bash
# 安装 FreeRTOS Skill 到本机 Cursor（~/.cursor/skills/）
# 用法: ./scripts/install_skill.sh
#       ./scripts/install_skill.sh /path/to/skill

set -euo pipefail

SOURCE="${1:-$(cd "$(dirname "$0")/.." && pwd)}"
DEST="${HOME}/.cursor/skills/freertos-embedded-architect"

if [[ ! -f "${SOURCE}/SKILL.md" ]]; then
  echo "错误: 未找到 ${SOURCE}/SKILL.md" >&2
  exit 1
fi

if [[ "${SKIP_MCP_ENV_INSTALL:-0}" != "1" && -f "${SOURCE}/scripts/install_mcp_environment.py" ]]; then
  PYTHON_BIN="${PYTHON:-}"
  if [[ -z "${PYTHON_BIN}" ]]; then
    if command -v python3 >/dev/null 2>&1; then
      PYTHON_BIN="python3"
    elif command -v python >/dev/null 2>&1; then
      PYTHON_BIN="python"
    else
      echo "错误: Python 3.10+ is required to install MCP dependencies." >&2
      exit 1
    fi
  fi
  "${PYTHON_BIN}" "${SOURCE}/scripts/install_mcp_environment.py" --quiet
fi

mkdir -p "$(dirname "$DEST")"
rm -rf "$DEST"
mkdir -p "$DEST"

rsync -a \
  --exclude '.git' \
  --exclude '.github' \
  --exclude '.vscode' \
  --exclude 'fw-AC79_AIoT_SDK' \
  --exclude 'bk_idk-release-v2.2.1' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.pytest_cache' \
  --exclude 'node_modules' \
  --exclude 'freertos-skill-lite' \
  --exclude 'archive' \
  --exclude 'artifacts' \
  --exclude 'forward_tests' \
  --exclude '/README.md' \
  --exclude '/INSTALL.md' \
  --exclude '/CHANGELOG.md' \
  "${SOURCE}/" "${DEST}/"

VER=$(awk '
  /^version:[[:space:]]*/ { sub(/^version:[[:space:]]*/, ""); print; exit }
  /^metadata:[[:space:]]*$/ { in_meta=1; next }
  in_meta && /^[^[:space:]]/ { in_meta=0 }
  in_meta && /^[[:space:]]+version:[[:space:]]*/ {
    sub(/^[[:space:]]+version:[[:space:]]*/, "");
    print;
    exit
  }
' "${DEST}/SKILL.md")
echo "已安装: ${DEST}"
echo "版本: ${VER}"
echo "重启 Cursor 或新开 Agent 对话后生效。"
