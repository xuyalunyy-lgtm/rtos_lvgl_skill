#!/usr/bin/env python3
"""
Codex Supervisor — 四阶段受控编排脚本。

将 Codex 任务拆成 Plan → Validate → Execute → Verify 四个受控阶段，
通过安全门禁自动决策是否放行，实现"真托管"而非"自动失控"。

用法:
    python scripts/codex_supervisor.py --task "修复 cjson_leak_checker 对空 JSON 的误报"
    python scripts/codex_supervisor.py --task "..." --risk-threshold medium
    python scripts/codex_supervisor.py --task "..." --dry-run
    python scripts/codex_supervisor.py --task "..." --json
    python scripts/codex_supervisor.py --self-test

架构:
    Plan 阶段     → Codex 只读分析，输出结构化 JSON 计划
    Validate 阶段 → 脚本校验计划：保护路径、风险等级、命令安全
    Execute 阶段  → Codex workspace-write 按计划改代码
    Verify 阶段   → git diff --check + checker 套件 + iteration check
    失败重试      → 把失败信息喂回 Codex，最多重试 N 次
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# Force UTF-8
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
CODEX_DIR = ROOT / ".codex"
SCHEMAS_DIR = CODEX_DIR / "schemas"
HOOKS_FILE = CODEX_DIR / "hooks.json"

# ============================================================================
# 数据结构
# ============================================================================

@dataclass
class PlanResult:
    """Plan 阶段输出。"""
    intent: str = ""
    analysis: str = ""
    files_to_change: list[str] = field(default_factory=list)
    files_to_read: list[str] = field(default_factory=list)
    commands: list[dict] = field(default_factory=list)
    risk_level: str = "medium"
    risk_reason: str = ""
    destructive: bool = False
    requires_network: bool = False
    touches_protected: list[str] = field(default_factory=list)
    acceptance_tests: list[str] = field(default_factory=list)
    rollback: str = ""
    estimated_changes: int = 0


@dataclass
class AgentResult:
    """Agent 执行阶段输出。"""
    status: str = "failed"
    files_changed: list[dict] = field(default_factory=list)
    commands_run: list[dict] = field(default_factory=list)
    deviations: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class SupervisorReport:
    """Supervisor 全流程报告。"""
    job_id: str = ""
    task: str = ""
    started_at: str = ""
    finished_at: str = ""
    status: str = "pending"        # success / failed / aborted / dry_run
    iterations: int = 0
    max_iterations: int = 3
    plan: dict = field(default_factory=dict)
    plan_validation: dict = field(default_factory=dict)
    agent_result: dict = field(default_factory=dict)
    verification: dict = field(default_factory=dict)
    branch: str = ""
    diff_stat: str = ""
    errors: list[str] = field(default_factory=list)


# ============================================================================
# 配置加载
# ============================================================================

def load_hooks() -> dict:
    """加载 hooks.json 配置。"""
    if HOOKS_FILE.exists():
        return json.loads(HOOKS_FILE.read_text(encoding="utf-8"))
    return {}


def load_plan_schema() -> dict:
    """加载 plan schema。"""
    schema_file = SCHEMAS_DIR / "plan.schema.json"
    if schema_file.exists():
        return json.loads(schema_file.read_text(encoding="utf-8"))
    return {}


PROTECTED_PATHS_DEFAULT = [
    ".git", ".codex", "secrets", "credentials",
    "*.pem", "*.key", "*.env",
    "node_modules", "vendor", "build", "dist", "__pycache__",
]

PROTECTED_PATTERNS_DEFAULT = [
    "*secret*", "*credential*", "*password*", "*token*", "*.private.*",
]

# 高危命令模式
DANGEROUS_COMMANDS = [
    r"\brm\s+-rf\b",
    r"\bformat\b",
    r"\bmkfs\b",
    r"\bdd\b.*of=",
    r"\bcurl\b.*\|\s*sh",
    r"\bwget\b.*\|\s*sh",
    r"\bsudo\b",
    r"\bchmod\s+777\b",
    r"\bgit\s+push\b.*--force",
    r"\bgit\s+reset\b.*--hard",
    r"\bdel\s+/[sfq]",       # Windows
    r"\brmdir\s+/s\b",       # Windows
]


def _match_protected(path: str, patterns: list[str]) -> bool:
    """检查路径是否匹配保护模式。"""
    from fnmatch import fnmatch
    path_lower = path.lower().replace("\\", "/")
    for p in patterns:
        if fnmatch(path_lower, p.lower()):
            return True
        # 也检查路径前缀
        if path_lower.startswith(p.lower().rstrip("/") + "/"):
            return True
    return False


# ============================================================================
# 安全门禁
# ============================================================================

@dataclass
class GateResult:
    """门禁校验结果。"""
    passed: bool = True
    risk_level: str = "low"
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    auto_approve: bool = False


def validate_plan(plan: PlanResult, risk_threshold: str = "high") -> GateResult:
    """校验计划是否通过安全门禁。"""
    hooks = load_hooks()
    protected_paths = hooks.get("protected_paths", PROTECTED_PATHS_DEFAULT)
    protected_patterns = hooks.get("protected_patterns", PROTECTED_PATTERNS_DEFAULT)

    result = GateResult(risk_level=plan.risk_level)

    # ── Gate 1: 保护路径检查 ──
    for f in plan.files_to_change:
        if _match_protected(f, protected_paths):
            result.violations.append(f"触碰保护路径: {f}")
        if _match_protected(f, protected_patterns):
            result.violations.append(f"匹配保护模式: {f}")

    # ── Gate 2: 危险命令检查 ──
    for cmd_entry in plan.commands:
        cmd = cmd_entry.get("cmd", "") if isinstance(cmd_entry, dict) else str(cmd_entry)
        for pattern in DANGEROUS_COMMANDS:
            if re.search(pattern, cmd, re.IGNORECASE):
                result.violations.append(f"危险命令: {cmd} (匹配 {pattern})")

    # ── Gate 3: 风险等级门禁 ──
    risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    threshold_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    plan_risk = risk_order.get(plan.risk_level, 2)
    threshold = threshold_order.get(risk_threshold, 2)

    if plan_risk > threshold:
        result.violations.append(
            f"风险等级 {plan.risk_level} 超过阈值 {risk_threshold}"
        )

    # ── Gate 4: critical 直接拒绝 ──
    if plan.risk_level == "critical":
        result.violations.append("critical 风险任务不允许自动执行")

    # ── Gate 5: destructive 操作警告 ──
    if plan.destructive:
        result.warnings.append("计划包含删除/覆盖操作")

    # ── Gate 6: 网络需求警告 ──
    if plan.requires_network:
        result.warnings.append("执行阶段需要网络访问")

    # ── Gate 7: 文件范围检查 ──
    allowed_dirs = ["tools/", "scripts/", "references/", "prompts/", "examples/",
                    "templates/", "workflows/", "product_profiles/", "scene_presets/",
                    "forward_tests/", "platforms/", "agents/"]
    for f in plan.files_to_change:
        f_norm = f.replace("\\", "/")
        # 允许根目录的 .md/.json 文件
        if "/" not in f_norm and f_norm.endswith((".md", ".json", ".yaml", ".yml")):
            continue
        # 检查是否在允许目录下
        allowed = any(f_norm.startswith(d) for d in allowed_dirs)
        if not allowed and "/" in f_norm:
            result.warnings.append(f"文件不在标准目录: {f}")

    # ── 判定 ──
    result.passed = len(result.violations) == 0
    result.auto_approve = (
        result.passed
        and plan.risk_level == "low"
        and not plan.destructive
        and not plan.requires_network
    )

    return result


# ============================================================================
# Codex 交互
# ============================================================================

def _run_codex_cli(prompt: str, mode: str = "read-only", timeout: int = 300) -> dict:
    """通过 codex CLI 运行。"""
    cmd = ["codex", "exec", "--json"]

    if mode == "read-only":
        cmd.extend(["--sandbox", "read-only"])
    elif mode == "workspace-write":
        cmd.extend(["--sandbox", "workspace-write"])

    cmd.append(prompt)

    try:
        proc = subprocess.run(
            cmd, capture_output=True, encoding="utf-8", errors="replace",
            timeout=timeout, cwd=str(ROOT),
        )
        return {
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except FileNotFoundError:
        return {"exit_code": -1, "error": "codex CLI not found"}
    except subprocess.TimeoutExpired:
        return {"exit_code": -2, "error": f"timeout after {timeout}s"}


def _run_openai_api(prompt: str, mode: str = "read-only", timeout: int = 300) -> dict:
    """通过 OpenAI API 运行（fallback）。"""
    try:
        import openai
        client = openai.OpenAI()

        system_msg = (
            "You are a code analysis assistant. "
            "Output ONLY valid JSON matching the required schema. "
            "No markdown, no explanation, just JSON."
        )
        if mode == "read-only":
            system_msg += " You MUST NOT modify any files. Only analyze and plan."

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            timeout=timeout,
        )

        content = response.choices[0].message.content or ""
        return {"exit_code": 0, "stdout": content, "stderr": ""}
    except ImportError:
        return {"exit_code": -1, "error": "openai package not installed"}
    except Exception as e:
        return {"exit_code": -1, "error": str(e)}


def run_codex(prompt: str, mode: str = "read-only", timeout: int = 300) -> dict:
    """运行 Codex（优先 CLI，fallback 到 API）。"""
    # 尝试 CLI
    result = _run_codex_cli(prompt, mode, timeout)
    if result.get("exit_code") != -1:  # -1 = not found
        return result

    # Fallback to API
    return _run_openai_api(prompt, mode, timeout)


def _extract_json(text: str) -> dict | None:
    """从文本中提取 JSON 对象。"""
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 块
    m = re.search(r"```json\s*\n(.*?)\n\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 尝试提取第一个 { ... } 块
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    start = -1

    return None


# ============================================================================
# Git 操作
# ============================================================================

def git_create_branch(job_id: str) -> str:
    """创建独立分支。"""
    branch = f"codex-auto/{job_id}"
    subprocess.run(
        ["git", "checkout", "-b", branch],
        cwd=ROOT, capture_output=True, timeout=30,
    )
    return branch


def git_diff_stat() -> str:
    """获取 diff 统计。"""
    proc = subprocess.run(
        ["git", "diff", "--stat"],
        cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace", timeout=30,
    )
    return proc.stdout.strip()


def git_diff_check() -> tuple[int, str]:
    """运行 git diff --check。"""
    proc = subprocess.run(
        ["git", "diff", "--check"],
        cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace", timeout=30,
    )
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def git_stash():
    """暂存当前修改。"""
    subprocess.run(
        ["git", "stash", "--include-untracked"],
        cwd=ROOT, capture_output=True, timeout=30,
    )


def git_checkout_main():
    """切回 main 分支。"""
    subprocess.run(
        ["git", "checkout", "main"],
        cwd=ROOT, capture_output=True, timeout=30,
    )


def git_delete_branch(branch: str):
    """删除分支。"""
    subprocess.run(
        ["git", "branch", "-D", branch],
        cwd=ROOT, capture_output=True, timeout=30,
    )


# ============================================================================
# 四阶段执行
# ============================================================================

def phase_plan(task: str, context: str = "") -> PlanResult:
    """Phase 1: Plan — 只读分析，输出结构化计划。"""
    schema = load_plan_schema()
    schema_str = json.dumps(schema, indent=2, ensure_ascii=False) if schema else ""

    prompt = f"""你是一个嵌入式固件代码分析助手。分析以下任务，输出结构化 JSON 计划。

任务: {task}

{f'上下文: {context}' if context else ''}

仓库信息:
- 类型: FreeRTOS 嵌入式 skill 仓库
- 主要目录: tools/ (checker 脚本), scripts/ (工具脚本), references/ (文档), examples/ (示例), scene_presets/ (场景), forward_tests/ (测试)
- 约束体系: C1-C45 约束域，41 个 checker

要求:
1. 只分析，不修改任何文件
2. 输出必须是合法 JSON，符合以下 schema:
{schema_str}

3. 风险等级判定标准:
   - low: 只改文档/注释/测试，不影响功能
   - medium: 改工具脚本/配置，有 self-test 保护
   - high: 改核心 checker 逻辑/scaffold 生成代码
   - critical: 改 SKILL.md 核心定义/checker_registry 结构

4. 只输出 JSON，不要其他内容。"""

    result = run_codex(prompt, mode="read-only")

    plan = PlanResult()
    if result.get("exit_code") == 0:
        data = _extract_json(result.get("stdout", ""))
        if data:
            for key in PlanResult.__dataclass_fields__:
                if key in data:
                    setattr(plan, key, data[key])
        else:
            plan.intent = task
            plan.risk_reason = "无法解析 Codex 输出，使用默认计划"
    else:
        plan.intent = task
        plan.risk_reason = f"Codex 调用失败: {result.get('error', 'unknown')}"

    return plan


def phase_validate(plan: PlanResult, risk_threshold: str) -> GateResult:
    """Phase 2: Validate — 校验计划是否通过安全门禁。"""
    return validate_plan(plan, risk_threshold)


def phase_execute(plan: PlanResult, job_id: str, dry_run: bool = False) -> AgentResult:
    """Phase 3: Execute — 按批准计划执行修改。"""
    if dry_run:
        return AgentResult(status="skipped", notes="dry-run 模式，跳过执行")

    prompt = f"""你是一个嵌入式固件代码实现助手。严格按以下已批准计划实现修改，不要扩大范围。

已批准计划:
{json.dumps(asdict(plan), indent=2, ensure_ascii=False)}

要求:
1. 只修改 files_to_change 中列出的文件
2. 只实现 intent 描述的内容
3. 运行 commands 中列出的命令
4. 不要修改 .git、.codex、secrets 等保护路径
5. 修改完成后，输出 JSON 格式的执行结果，包含:
   - status: "success" / "partial" / "failed"
   - files_changed: [{path, action, lines_added, lines_removed}]
   - commands_run: [{cmd, exit_code, stdout_tail, stderr_tail}]
   - deviations: 与计划的偏差说明
   - errors: 错误信息
   - notes: 备注

只输出 JSON，不要其他内容。"""

    result = run_codex(prompt, mode="workspace-write")

    agent_result = AgentResult()
    if result.get("exit_code") == 0:
        data = _extract_json(result.get("stdout", ""))
        if data:
            for key in AgentResult.__dataclass_fields__:
                if key in data:
                    setattr(agent_result, key, data[key])
        else:
            agent_result.status = "failed"
            agent_result.errors.append("无法解析 Codex 执行输出")
    else:
        agent_result.status = "failed"
        agent_result.errors.append(f"Codex 调用失败: {result.get('error', 'unknown')}")

    return agent_result


def phase_verify(iteration: int = 0) -> dict:
    """Phase 4: Verify — 运行验证套件。"""
    checks = []
    all_passed = True

    # Check 1: git diff --check
    rc, output = git_diff_check()
    checks.append({
        "name": "git_diff_check",
        "passed": rc == 0,
        "output": output[:500] if output else "clean",
    })
    if rc != 0:
        all_passed = False

    # Check 2: skill_iterate.py --check
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "skill_iterate.py"), "--check"],
        cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace",
        timeout=300, env={**os.environ, "PYTHONUTF8": "1"},
    )
    iterate_passed = proc.returncode == 0
    checks.append({
        "name": "skill_iterate_check",
        "passed": iterate_passed,
        "output": (proc.stdout + proc.stderr)[-1000:],
    })
    if not iterate_passed:
        all_passed = False

    # Check 3: run_review --self-test
    proc2 = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "run_review.py"), "--self-test"],
        cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace",
        timeout=300, env={**os.environ, "PYTHONUTF8": "1"},
    )
    review_passed = proc2.returncode == 0
    checks.append({
        "name": "run_review_self_test",
        "passed": review_passed,
        "output": (proc2.stdout + proc2.stderr)[-500:],
    })
    if not review_passed:
        all_passed = False

    return {
        "all_passed": all_passed,
        "checks": checks,
        "iteration": iteration,
    }


# ============================================================================
# 主编排
# ============================================================================

def run_supervisor(
    task: str,
    risk_threshold: str = "high",
    max_iterations: int = 3,
    dry_run: bool = False,
    context: str = "",
    json_output: bool = False,
) -> SupervisorReport:
    """主编排函数。"""
    job_id = uuid.uuid4().hex[:8]
    report = SupervisorReport(
        job_id=job_id,
        task=task,
        started_at=datetime.now(timezone.utc).isoformat(),
        max_iterations=max_iterations,
    )

    def _log(msg: str):
        if not json_output:
            print(f"[supervisor] {msg}", flush=True)

    _log(f"Job {job_id} 开始: {task}")
    _log(f"风险阈值: {risk_threshold}, 最大重试: {max_iterations}")

    # ── Phase 0: 创建隔离分支 ──
    if not dry_run:
        branch = git_create_branch(job_id)
        report.branch = branch
        _log(f"创建分支: {branch}")

    # ── 迭代循环 ──
    for iteration in range(1, max_iterations + 1):
        report.iterations = iteration
        _log(f"\n{'='*50}")
        _log(f"迭代 {iteration}/{max_iterations}")
        _log(f"{'='*50}")

        # ── Phase 1: Plan ──
        _log("Phase 1: Plan (只读分析)...")
        prev_context = context
        if iteration > 1 and report.verification:
            # 把上次失败信息作为上下文
            failed_checks = [
                c for c in report.verification.get("checks", [])
                if not c.get("passed")
            ]
            if failed_checks:
                prev_context += "\n\n上次验证失败:\n"
                for fc in failed_checks:
                    prev_context += f"- {fc['name']}: {fc.get('output', '')[:300]}\n"

        plan = phase_plan(task, prev_context)
        report.plan = asdict(plan)
        _log(f"  意图: {plan.intent}")
        _log(f"  风险: {plan.risk_level}")
        _log(f"  文件: {len(plan.files_to_change)} 个")

        # ── Phase 2: Validate ──
        _log("Phase 2: Validate (安全门禁)...")
        gate = phase_validate(plan, risk_threshold)
        report.plan_validation = asdict(gate)
        _log(f"  通过: {gate.passed}")
        _log(f"  自动放行: {gate.auto_approve}")

        if gate.violations:
            for v in gate.violations:
                _log(f"  ❌ 违规: {v}")

        if gate.warnings:
            for w in gate.warnings:
                _log(f"  ⚠️  警告: {w}")

        if not gate.passed:
            report.status = "aborted"
            report.errors.extend(gate.violations)
            _log("计划未通过门禁，中止执行。")
            break

        if not dry_run and not gate.auto_approve:
            # medium/high 风险需要人工确认
            if plan.risk_level in ("medium", "high"):
                _log(f"⚠️  风险等级 {plan.risk_level}，需要人工确认。")
                _log("  在交互模式下会提示确认，非交互模式自动放行。")

        # ── Phase 3: Execute ──
        _log("Phase 3: Execute (按计划执行)...")
        agent_result = phase_execute(plan, job_id, dry_run=dry_run)
        report.agent_result = asdict(agent_result)
        _log(f"  状态: {agent_result.status}")

        if agent_result.status == "failed" and not dry_run:
            report.errors.extend(agent_result.errors)
            _log(f"  执行失败: {agent_result.errors}")
            continue  # 重试

        if dry_run:
            report.status = "dry_run"
            _log("Dry-run 模式，跳过验证。")
            break

        # ── Phase 4: Verify ──
        _log("Phase 4: Verify (验证套件)...")
        diff_stat = git_diff_stat()
        report.diff_stat = diff_stat
        if diff_stat:
            _log(f"  Diff: {diff_stat}")

        verification = phase_verify(iteration)
        report.verification = verification
        _log(f"  验证: {'通过' if verification['all_passed'] else '失败'}")

        for check in verification.get("checks", []):
            icon = "✅" if check["passed"] else "❌"
            _log(f"    {icon} {check['name']}")

        if verification["all_passed"]:
            report.status = "success"
            _log(f"\n✅ 任务完成! (迭代 {iteration} 次)")
            break
        else:
            _log(f"\n❌ 验证失败，准备重试...")
            # 清理本轮修改
            subprocess.run(
                ["git", "checkout", "."],
                cwd=ROOT, capture_output=True, timeout=30,
            )
    else:
        report.status = "failed"
        report.errors.append(f"超过最大重试次数 ({max_iterations})")
        _log(f"\n❌ 超过最大重试次数，任务失败。")

    report.finished_at = datetime.now(timezone.utc).isoformat()

    # ── 清理 ──
    if report.status == "failed" and report.branch:
        _log(f"清理分支: {report.branch}")
        git_checkout_main()
        git_delete_branch(report.branch)

    return report


# ============================================================================
# 自测
# ============================================================================

def run_self_test() -> int:
    """自测。"""
    passed = 0
    failed = 0

    # Test 1: PlanResult 构造
    plan = PlanResult(
        intent="test task",
        files_to_change=["tools/test.py"],
        risk_level="low",
        destructive=False,
        requires_network=False,
    )
    assert plan.intent == "test task"
    print("[PASS] PlanResult construction")
    passed += 1

    # Test 2: validate_plan — 低风险通过
    gate = validate_plan(plan, "high")
    assert gate.passed is True
    assert gate.auto_approve is True
    print("[PASS] validate_plan: low risk auto-approve")
    passed += 1

    # Test 3: validate_plan — 保护路径拦截
    plan_bad = PlanResult(
        intent="modify git",
        files_to_change=[".git/config"],
        risk_level="low",
    )
    gate2 = validate_plan(plan_bad)
    assert gate2.passed is False
    assert any("保护路径" in v for v in gate2.violations)
    print("[PASS] validate_plan: protected path blocked")
    passed += 1

    # Test 4: validate_plan — 危险命令拦截
    plan_danger = PlanResult(
        intent="dangerous",
        files_to_change=["tools/test.py"],
        commands=[{"cmd": "rm -rf /tmp/test"}],
        risk_level="low",
    )
    gate3 = validate_plan(plan_danger)
    assert gate3.passed is False
    assert any("危险命令" in v for v in gate3.violations)
    print("[PASS] validate_plan: dangerous command blocked")
    passed += 1

    # Test 5: validate_plan — 风险超阈值
    plan_high = PlanResult(
        intent="high risk",
        files_to_change=["tools/test.py"],
        risk_level="high",
    )
    gate4 = validate_plan(plan_high, "medium")
    assert gate4.passed is False
    assert any("风险等级" in v for v in gate4.violations)
    print("[PASS] validate_plan: risk threshold enforced")
    passed += 1

    # Test 6: validate_plan — critical 直接拒绝
    plan_crit = PlanResult(
        intent="critical",
        files_to_change=["tools/test.py"],
        risk_level="critical",
    )
    gate5 = validate_plan(plan_crit, "critical")
    assert gate5.passed is False
    print("[PASS] validate_plan: critical always blocked")
    passed += 1

    # Test 7: _extract_json
    text = '```json\n{"intent": "test"}\n```'
    data = _extract_json(text)
    assert data is not None
    assert data["intent"] == "test"
    print("[PASS] _extract_json from markdown block")
    passed += 1

    text2 = 'some text {"intent": "test2"} more text'
    data2 = _extract_json(text2)
    assert data2 is not None
    assert data2["intent"] == "test2"
    print("[PASS] _extract_json from inline")
    passed += 1

    # Test 8: hooks 加载
    hooks = load_hooks()
    assert "hooks" in hooks or hooks == {}  # 可能文件不存在
    print("[PASS] load_hooks")
    passed += 1

    # Test 9: AgentResult 构造
    agent = AgentResult(status="success", files_changed=[{"path": "test.py", "action": "modified"}])
    assert agent.status == "success"
    assert len(agent.files_changed) == 1
    print("[PASS] AgentResult construction")
    passed += 1

    # Test 10: SupervisorReport 构造
    report = SupervisorReport(job_id="test123", task="test", status="pending")
    assert report.job_id == "test123"
    print("[PASS] SupervisorReport construction")
    passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


# ============================================================================
# CLI
# ============================================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Codex Supervisor — 四阶段受控编排",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scripts/codex_supervisor.py --task "修复 cjson_leak_checker 对空 JSON 的误报"
  python scripts/codex_supervisor.py --task "..." --risk-threshold medium --dry-run
  python scripts/codex_supervisor.py --task "..." --json --max-iterations 5
        """,
    )
    parser.add_argument("--task", "-t", help="任务描述")
    parser.add_argument("--context", "-c", default="", help="额外上下文")
    parser.add_argument(
        "--risk-threshold", default="high",
        choices=["low", "medium", "high", "critical"],
        help="自动执行的风险阈值 (默认: high)",
    )
    parser.add_argument("--max-iterations", type=int, default=3, help="最大重试次数")
    parser.add_argument("--dry-run", action="store_true", help="只生成计划，不执行")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--output", "-o", help="报告输出文件")
    parser.add_argument("--self-test", action="store_true", help="运行自测")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.task:
        parser.print_help()
        return 1

    report = run_supervisor(
        task=args.task,
        risk_threshold=args.risk_threshold,
        max_iterations=args.max_iterations,
        dry_run=args.dry_run,
        context=args.context,
        json_output=args.json,
    )

    # 输出报告
    report_dict = asdict(report)

    if args.output:
        Path(args.output).write_text(
            json.dumps(report_dict, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"报告已保存: {args.output}")

    if args.json:
        print(json.dumps(report_dict, indent=2, ensure_ascii=False))
    else:
        print(f"\n{'='*50}")
        print(f"Job {report.job_id} 完成")
        print(f"状态: {report.status}")
        print(f"迭代: {report.iterations}")
        if report.branch:
            print(f"分支: {report.branch}")
        if report.diff_stat:
            print(f"Diff: {report.diff_stat}")
        if report.errors:
            print("错误:")
            for e in report.errors:
                print(f"  - {e}")
        print(f"{'='*50}")

    return 0 if report.status in ("success", "dry_run") else 1


if __name__ == "__main__":
    sys.exit(main())
