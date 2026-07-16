"""Single source of truth for runtime distribution exclusions.

All install scripts and validation tools MUST import from here.
Do NOT maintain separate exclude lists in individual scripts.
"""

# Directories excluded from runtime distribution
RUNTIME_EXCLUDE_DIRS: set[str] = {
    # Version control
    ".git",
    # CI/CD
    ".github",
    # IDE configs
    ".vscode",
    ".claude",
    ".codex",
    # Python caches
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    # Node
    "node_modules",
    # Test outputs and forward tests
    "forward_tests",
    "out",
    # Generated artifacts (not source)
    "artifacts",
    # Archived content (not runtime)
    "archive",
    # Lite distribution (generated separately)
    "freertos-skill-lite",
    # SDK directories (user-provided, not distributed)
    "fw-AC79_AIoT_SDK",
    "bk_idk-release-v2.2.1",
    # Local metrics/evidence (per-machine)
    ".skill_metrics",
    ".skill_evidence",
}

RUNTIME_EXCLUDE_NAME_PATTERNS: tuple[str, ...] = (
    ".tmp_*",
)

RUNTIME_EXCLUDE_RELATIVE_DIRS: set[str] = set()

# Root-only files excluded from installed skill
RUNTIME_EXCLUDE_ROOT_FILES: set[str] = {
    "README.md",
    "INSTALL.md",
    "CHANGELOG.md",
}
