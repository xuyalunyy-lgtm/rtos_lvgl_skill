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

# The skill has no bundled service dependency.

mkdir -p "$(dirname "$DEST")"
rm -rf "$DEST"
mkdir -p "$DEST"

rsync -a \
  --exclude '.git' \
  --exclude '.github' \
  --exclude '.vscode' \
  --exclude '.claude' \
  --exclude '.codex' \
  --exclude 'fw-AC79_AIoT_SDK' \
  --exclude 'bk_idk-release-v2.2.1' \
  --exclude '__pycache__' \
  --exclude '.mypy_cache' \
  --exclude '*.pyc' \
  --exclude '.pytest_cache' \
  --exclude '.tmp_*' \
  --exclude 'node_modules' \
  --exclude 'freertos-skill-lite' \
  --exclude 'archive' \
  --exclude 'artifacts' \
  --exclude 'forward_tests' \
  --exclude 'out' \
  --exclude '.skill_metrics' \
  --exclude '.skill_evidence' \
  --exclude '/README.md' \
  --exclude '/INSTALL.md' \
  --exclude '/CHANGELOG.md' \
  "${SOURCE}/" "${DEST}/"

VER=$(awk -F '"' '/^version[[:space:]]*=/ { print $2; exit }' "${DEST}/pyproject.toml")
echo "已安装: ${DEST}"
echo "版本: ${VER}"
echo "重启 Cursor 或新开 Agent 对话后生效。"
