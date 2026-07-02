#!/usr/bin/env python3
"""
交付证据包规范 v9.0.1 — 统一 evidence 格式。

所有 Skill 工具（run_review, auto_fix, constraint_discovery, scaffold, metrics_dashboard）
通过 --evidence 输出同一格式的 delivery_evidence.json，串联"发现 → 修复 → 验证"闭环。

用法:
    python tools/evidence_schema.py --self-test
    python tools/evidence_schema.py --schema  # 输出 JSON Schema
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Force UTF-8 on Windows
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


# ============================================================================
# 数据结构
# ============================================================================

@dataclass
class IssueEntry:
    """单条审查问题。"""
    id: str                     # 约束 ID，如 "C3.1"
    severity: str               # "P0" / "P1" / "P2"
    file: str                   # 文件路径（相对或绝对）
    line: int = 0               # 行号，0 表示不适用
    constraint: str = ""        # 约束域，如 "C3"
    message: str = ""           # 问题描述
    checker: str = ""           # 产生此 issue 的 checker 名


@dataclass
class FixSuggestion:
    """单条修复建议。"""
    constraint: str             # 约束 ID
    fix_type: str               # 修复类型，如 "goto_cleanup" / "check_return"
    risk_level: str             # "low" / "medium" / "high"
    file: str = ""              # 目标文件
    line_range: tuple[int, int] = (0, 0)  # 改动行范围
    suggestion: str = ""        # 文字建议
    confidence: float = 0.0     # 0.0-1.0
    pre_checks: list[str] = field(default_factory=list)
    post_checkers: list[str] = field(default_factory=list)
    diff: str = ""              # unified diff 预览


@dataclass
class GeneratedFile:
    """生成器产出的文件。"""
    path: str                   # 文件路径
    file_type: str              # "c" / "h" / "cmake" / "json" / "config"
    description: str = ""       # 文件用途说明


@dataclass
class ReproCommand:
    """复现命令。"""
    command: str                # shell 命令
    description: str = ""       # 命令说明
    expected_exit: int = 0      # 期望退出码


@dataclass
class DeliveryEvidence:
    """统一交付证据包。"""
    # ── 元数据 ──
    version: str = "9.0.1"
    timestamp: str = ""         # ISO 8601
    source_tool: str = ""       # 产出此 evidence 的工具名

    # ── 项目 profile ──
    project_profile: dict[str, Any] = field(default_factory=dict)
    # {"platform": "esp32", "features": {...}, "preset": "voice-screen"}

    # ── Suite 运行信息 ──
    suite_run: dict[str, Any] = field(default_factory=dict)
    # {"suite": "default", "checkers_run": 34, "checkers_skipped": 0}

    # ── 问题列表 ──
    issues: list[dict[str, Any]] = field(default_factory=list)
    # [IssueEntry-asdict, ...]

    # ── 生成文件 ──
    generated_files: list[dict[str, Any]] = field(default_factory=list)
    # [GeneratedFile-asdict, ...]

    # ── 修复建议 ──
    fix_suggestions: list[dict[str, Any]] = field(default_factory=list)
    # [FixSuggestion-asdict, ...]

    # ── 复现命令 ──
    reproduce_commands: list[dict[str, Any]] = field(default_factory=list)
    # [ReproCommand-asdict, ...]

    # ── 验证结果 ──
    verification_results: dict[str, Any] = field(default_factory=dict)
    # {"post_fix_checkers": [...], "all_passed": true, "remaining_issues": 0}

    # ── 假设项 ──
    assumptions: list[str] = field(default_factory=list)

    # ── 扩展元数据 ──
    metadata: dict[str, Any] = field(default_factory=dict)
    # {"tool_version": "9.0.1", "platform": "esp32", "preset": "voice-screen",
    #  "files_checked": 42, "duration_ms": 1500}

    def to_dict(self) -> dict[str, Any]:
        """转为可序列化 dict。"""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """转为 JSON 字符串。"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


# ============================================================================
# 构建辅助函数
# ============================================================================

def make_evidence(
    source_tool: str,
    *,
    platform: str = "",
    preset: str = "",
    suite: str = "default",
    issues: list[dict] | None = None,
    generated_files: list[dict] | None = None,
    fix_suggestions: list[dict] | None = None,
    reproduce_commands: list[dict] | None = None,
    assumptions: list[str] | None = None,
    metadata: dict | None = None,
) -> DeliveryEvidence:
    """快速构建 evidence 实例。"""
    profile = {}
    if platform:
        profile["platform"] = platform
    if preset:
        profile["preset"] = preset

    return DeliveryEvidence(
        timestamp=datetime.now(timezone.utc).isoformat(),
        source_tool=source_tool,
        project_profile=profile,
        suite_run={"suite": suite},
        issues=issues or [],
        generated_files=generated_files or [],
        fix_suggestions=fix_suggestions or [],
        reproduce_commands=reproduce_commands or [],
        assumptions=assumptions or [],
        metadata=metadata or {},
    )


def issue_entry(
    cid: str,
    severity: str,
    file: str,
    line: int = 0,
    constraint: str = "",
    message: str = "",
    checker: str = "",
) -> dict[str, Any]:
    """构建 IssueEntry dict。"""
    return asdict(IssueEntry(
        id=cid, severity=severity, file=file, line=line,
        constraint=constraint or cid.split(".")[0] if "." in cid else cid,
        message=message, checker=checker,
    ))


def fix_suggestion(
    constraint: str,
    fix_type: str,
    risk_level: str = "medium",
    *,
    file: str = "",
    line_range: tuple[int, int] = (0, 0),
    suggestion: str = "",
    confidence: float = 0.5,
    pre_checks: list[str] | None = None,
    post_checkers: list[str] | None = None,
    diff: str = "",
) -> dict[str, Any]:
    """构建 FixSuggestion dict。"""
    return asdict(FixSuggestion(
        constraint=constraint, fix_type=fix_type, risk_level=risk_level,
        file=file, line_range=line_range, suggestion=suggestion,
        confidence=confidence, pre_checks=pre_checks or [],
        post_checkers=post_checkers or [], diff=diff,
    ))


def generated_file(path: str, file_type: str = "", description: str = "") -> dict[str, Any]:
    """构建 GeneratedFile dict。"""
    if not file_type:
        suffix = Path(path).suffix.lstrip(".")
        file_type = suffix or "unknown"
    return asdict(GeneratedFile(path=path, file_type=file_type, description=description))


def repro_command(command: str, description: str = "", expected_exit: int = 0) -> dict[str, Any]:
    """构建 ReproCommand dict。"""
    return asdict(ReproCommand(command=command, description=description, expected_exit=expected_exit))


# ============================================================================
# 校验
# ============================================================================

_REQUIRED_FIELDS = {"version", "timestamp", "source_tool"}
_VALID_SEVERITIES = {"P0", "P1", "P2"}
_VALID_RISK_LEVELS = {"low", "medium", "high"}


def validate_evidence(data: dict[str, Any]) -> list[str]:
    """校验 evidence dict，返回错误列表（空 = 合法）。"""
    errors: list[str] = []

    if not isinstance(data, dict):
        return ["evidence 必须是 dict"]

    for f in _REQUIRED_FIELDS:
        if f not in data:
            errors.append(f"缺少必填字段: {f}")

    # 校验 issues
    for i, issue in enumerate(data.get("issues", [])):
        if not isinstance(issue, dict):
            errors.append(f"issues[{i}] 必须是 dict")
            continue
        if "id" not in issue:
            errors.append(f"issues[{i}].id 缺失")
        sev = issue.get("severity", "")
        if sev and sev not in _VALID_SEVERITIES:
            errors.append(f"issues[{i}].severity 无效: {sev} (允许: {_VALID_SEVERITIES})")

    # 校验 fix_suggestions
    for i, fix in enumerate(data.get("fix_suggestions", [])):
        if not isinstance(fix, dict):
            errors.append(f"fix_suggestions[{i}] 必须是 dict")
            continue
        if "constraint" not in fix:
            errors.append(f"fix_suggestions[{i}].constraint 缺失")
        risk = fix.get("risk_level", "")
        if risk and risk not in _VALID_RISK_LEVELS:
            errors.append(f"fix_suggestions[{i}].risk_level 无效: {risk}")

    # 校验 generated_files
    for i, gf in enumerate(data.get("generated_files", [])):
        if not isinstance(gf, dict):
            errors.append(f"generated_files[{i}] 必须是 dict")
            continue
        if "path" not in gf:
            errors.append(f"generated_files[{i}].path 缺失")

    return errors


def is_valid_evidence(data: dict[str, Any]) -> bool:
    """快速校验：evidence 是否合法。"""
    return len(validate_evidence(data)) == 0


# ============================================================================
# 合并
# ============================================================================

def merge_evidences(evidences: list[DeliveryEvidence]) -> DeliveryEvidence:
    """合并多个 evidence 为一个汇总 evidence。"""
    if not evidences:
        return DeliveryEvidence()
    if len(evidences) == 1:
        return evidences[0]

    base = DeliveryEvidence(
        version=evidences[0].version,
        timestamp=datetime.now(timezone.utc).isoformat(),
        source_tool="evidence_merge",
        project_profile=dict(evidences[0].project_profile),
        suite_run={"suite": "merged", "source_suites": []},
    )

    seen_issues: set[str] = set()
    seen_fixes: set[str] = set()
    seen_files: set[str] = set()

    for ev in evidences:
        # 合并 suite 信息
        suite_name = ev.suite_run.get("suite", "unknown")
        if suite_name not in base.suite_run.get("source_suites", []):
            base.suite_run.setdefault("source_suites", []).append(suite_name)

        # 合并 issues（去重）
        for issue in ev.issues:
            key = f"{issue.get('id')}:{issue.get('file')}:{issue.get('line', 0)}"
            if key not in seen_issues:
                seen_issues.add(key)
                base.issues.append(issue)

        # 合并 fix_suggestions（去重）
        for fix in ev.fix_suggestions:
            key = f"{fix.get('constraint')}:{fix.get('file')}:{fix.get('fix_type')}"
            if key not in seen_fixes:
                seen_fixes.add(key)
                base.fix_suggestions.append(fix)

        # 合并 generated_files（去重）
        for gf in ev.generated_files:
            path = gf.get("path", "")
            if path and path not in seen_files:
                seen_files.add(path)
                base.generated_files.append(gf)

        # 合并 reproduce_commands
        for rc in ev.reproduce_commands:
            cmd = rc.get("command", "")
            if cmd and cmd not in {r.get("command") for r in base.reproduce_commands}:
                base.reproduce_commands.append(rc)

        # 合并 assumptions
        for a in ev.assumptions:
            if a not in base.assumptions:
                base.assumptions.append(a)

        # 合并 metadata（后者覆盖前者）
        base.metadata.update(ev.metadata)

    # 汇总 verification
    all_issues = len(base.issues)
    base.verification_results = {
        "merged_from": len(evidences),
        "total_issues": all_issues,
        "total_fixes": len(base.fix_suggestions),
        "total_generated": len(base.generated_files),
    }

    return base


# ============================================================================
# JSON Schema
# ============================================================================

EVIDENCE_JSON_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://freertos-skill.dev/schemas/delivery_evidence.json",
    "title": "FreeRTOS Skill Delivery Evidence",
    "description": "统一交付证据包格式，用于串联审查、修复、验证闭环。",
    "type": "object",
    "required": ["version", "timestamp", "source_tool"],
    "properties": {
        "version": {"type": "string", "description": "证据格式版本"},
        "timestamp": {"type": "string", "format": "date-time", "description": "ISO 8601 时间戳"},
        "source_tool": {"type": "string", "description": "产出此 evidence 的工具名"},
        "project_profile": {
            "type": "object",
            "properties": {
                "platform": {"type": "string"},
                "preset": {"type": "string"},
                "features": {"type": "object"},
            },
        },
        "suite_run": {
            "type": "object",
            "properties": {
                "suite": {"type": "string"},
                "checkers_run": {"type": "integer"},
                "checkers_skipped": {"type": "integer"},
            },
        },
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "severity"],
                "properties": {
                    "id": {"type": "string"},
                    "severity": {"type": "string", "enum": ["P0", "P1", "P2"]},
                    "file": {"type": "string"},
                    "line": {"type": "integer"},
                    "constraint": {"type": "string"},
                    "message": {"type": "string"},
                    "checker": {"type": "string"},
                },
            },
        },
        "generated_files": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["path"],
                "properties": {
                    "path": {"type": "string"},
                    "file_type": {"type": "string"},
                    "description": {"type": "string"},
                },
            },
        },
        "fix_suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["constraint", "fix_type"],
                "properties": {
                    "constraint": {"type": "string"},
                    "fix_type": {"type": "string"},
                    "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
                    "file": {"type": "string"},
                    "line_range": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 2,
                        "maxItems": 2,
                    },
                    "suggestion": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "pre_checks": {"type": "array", "items": {"type": "string"}},
                    "post_checkers": {"type": "array", "items": {"type": "string"}},
                    "diff": {"type": "string"},
                },
            },
        },
        "reproduce_commands": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["command"],
                "properties": {
                    "command": {"type": "string"},
                    "description": {"type": "string"},
                    "expected_exit": {"type": "integer"},
                },
            },
        },
        "verification_results": {
            "type": "object",
            "properties": {
                "post_fix_checkers": {"type": "array", "items": {"type": "string"}},
                "all_passed": {"type": "boolean"},
                "remaining_issues": {"type": "integer"},
            },
        },
        "assumptions": {"type": "array", "items": {"type": "string"}},
        "metadata": {"type": "object"},
    },
}


# ============================================================================
# 持久化
# ============================================================================

def save_evidence(evidence: DeliveryEvidence, path: str | Path) -> Path:
    """保存 evidence 到 JSON 文件。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(evidence.to_json(), encoding="utf-8")
    return p


def load_evidence(path: str | Path) -> DeliveryEvidence:
    """从 JSON 文件加载 evidence。"""
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    # 从 dict 重建 DeliveryEvidence（忽略未知字段）
    known = {f.name for f in DeliveryEvidence.__dataclass_fields__.values()}
    filtered = {k: v for k, v in data.items() if k in known}
    return DeliveryEvidence(**filtered)


# ============================================================================
# 自测
# ============================================================================

def _self_test() -> int:
    """evidence_schema 自测。"""
    errors: list[str] = []

    # 1. 构建 → 序列化 → 校验
    ev = make_evidence(
        source_tool="evidence_schema_selftest",
        platform="esp32",
        preset="voice-screen",
        issues=[
            issue_entry("C3.1", "P0", "main.c", 42, "C3", "cJSON 未释放", "cjson_leak"),
            issue_entry("C12.1", "P1", "audio.c", 100, "C12", "返回值未检查", "return_check"),
        ],
        fix_suggestions=[
            fix_suggestion("C3", "goto_cleanup", "low", file="main.c",
                           suggestion="在 error path 中调用 cJSON_Delete"),
        ],
        generated_files=[
            generated_file("main.c", description="主入口"),
            generated_file("CMakeLists.txt", "cmake", "构建配置"),
        ],
        reproduce_commands=[
            repro_command("python tools/run_review.py --dir ./src", "运行审查"),
        ],
        assumptions=["假设平台为 ESP32-S3", "假设使用 ESP-IDF 5.x"],
        metadata={"tool_version": "9.0.1", "files_checked": 5},
    )

    # 序列化
    j = ev.to_json()
    data = json.loads(j)

    # 校验
    errs = validate_evidence(data)
    if errs:
        errors.append(f"构建的 evidence 校验失败: {errs}")

    # 2. 必填字段缺失
    bad = {"version": "9.0.1"}  # 缺 timestamp, source_tool
    errs = validate_evidence(bad)
    if len(errs) < 2:
        errors.append(f"缺失字段校验不足: {errs}")

    # 3. 无效 severity
    bad2 = {"version": "9.0.1", "timestamp": "", "source_tool": "t",
            "issues": [{"id": "X", "severity": "P9"}]}
    errs = validate_evidence(bad2)
    if not any("severity" in e for e in errs):
        errors.append(f"无效 severity 未检出: {errs}")

    # 4. 合并
    ev2 = make_evidence("tool2", issues=[
        issue_entry("C4.1", "P0", "isr.c", 10, "C4", "ISR 中调用非安全函数"),
    ])
    merged = merge_evidences([ev, ev2])
    if len(merged.issues) != 3:
        errors.append(f"合并 issues 数量错误: {len(merged.issues)} (期望 3)")
    if merged.source_tool != "evidence_merge":
        errors.append(f"合并 source_tool 错误: {merged.source_tool}")

    # 5. 重复 issue 去重
    ev3 = make_evidence("tool3", issues=[
        issue_entry("C3.1", "P0", "main.c", 42, "C3", "cJSON 未释放"),
    ])
    merged2 = merge_evidences([ev, ev3])
    if len(merged2.issues) != 2:
        errors.append(f"去重失败: {len(merged2.issues)} (期望 2)")

    # 6. 保存/加载
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp = f.name
    try:
        save_evidence(ev, tmp)
        loaded = load_evidence(tmp)
        if loaded.source_tool != ev.source_tool:
            errors.append(f"保存/加载 source_tool 不一致: {loaded.source_tool}")
        if len(loaded.issues) != len(ev.issues):
            errors.append(f"保存/加载 issues 数量不一致: {len(loaded.issues)}")
    finally:
        os.unlink(tmp)

    # 7. JSON Schema 合法性
    if "properties" not in EVIDENCE_JSON_SCHEMA:
        errors.append("JSON Schema 缺少 properties")

    # 输出
    if errors:
        print("evidence_schema 自测: FAIL")
        for e in errors:
            print(f"  ✗ {e}")
        return 1

    print("evidence_schema 自测: PASS (7/7)")
    return 0


# ============================================================================
# CLI
# ============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(description="交付证据包规范 v9.0.1")
    parser.add_argument("--self-test", action="store_true", help="运行自测")
    parser.add_argument("--schema", action="store_true", help="输出 JSON Schema")
    args = parser.parse_args()

    if args.self_test:
        return _self_test()

    if args.schema:
        from checker_io import output_json
        output_json(EVIDENCE_JSON_SCHEMA)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
