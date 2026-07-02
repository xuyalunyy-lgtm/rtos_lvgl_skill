#!/usr/bin/env python3
"""
Project Operating Model v16.0.2 — 统一项目事实源。

把 RTOS tasks、IPC、frameworks、platform profile、constraints、checker coverage
合并为一个项目操作模型。

用法:
    python tools/project_operating_model.py --dir tools/fixtures/mini_esp32 --platform esp32
    python tools/project_operating_model.py --dir tools/fixtures/mini_esp32 --json
    python tools/project_operating_model.py --self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build_operating_model(dir_path: str, platform: str = "") -> dict:
    """构建项目操作模型。"""
    from rtos_model import scan_source_dir
    from framework_profile import detect_frameworks, load_all_packs

    # 1. RTOS 系统模型
    rtos = scan_source_dir(dir_path)

    # 2. Framework 检测
    frameworks = detect_frameworks(dir_path, platform)

    # 3. 加载 platform profile
    platform_profile = {}
    profile_path = ROOT / "product_profiles" / f"{platform}.json"
    if profile_path.exists():
        platform_profile = json.loads(profile_path.read_text(encoding="utf-8"))

    # 4. Constraint coverage
    all_framework_constraints = []
    for fw in frameworks:
        pack_path = ROOT / "frameworks" / f"{fw['framework_id']}.json"
        if pack_path.exists():
            pack = json.loads(pack_path.read_text(encoding="utf-8"))
            for c in pack.get("constraints", []):
                all_framework_constraints.append({
                    "id": c["id"],
                    "framework": fw["framework_id"],
                    "severity": c.get("severity", "P2"),
                    "has_checker": len(pack.get("checker_scripts", [])) > 0,
                })

    # 5. RTOS core constraint coverage (from checker_registry)
    core_covered = []
    try:
        sys.path.insert(0, str(ROOT / "tools"))
        from checker_registry import ALL_CHECKERS
        for spec in ALL_CHECKERS:
            core_covered.extend(spec.domains)
    except ImportError:
        pass
    core_covered = sorted(set(core_covered))

    # 6. 统计
    return {
        "project": Path(dir_path).name,
        "platform": platform,
        "rtos_model": {
            "task_count": len(rtos.get("tasks", [])),
            "queue_count": len(rtos.get("queues", [])),
            "mutex_count": len(rtos.get("mutexes", [])),
            "semaphore_count": len(rtos.get("semaphores", [])),
            "timer_count": len(rtos.get("timers", [])),
            "isr_count": len(rtos.get("isrs", [])),
        },
        "rtos_details": rtos,
        "frameworks": frameworks,
        "framework_count": len(frameworks),
        "platform_profile": {
            "name": platform_profile.get("name", ""),
            "features": platform_profile.get("features", {}),
            "required_constraints": platform_profile.get("required_constraints", []),
        },
        "constraint_coverage": {
            "core_covered": core_covered,
            "core_covered_count": len(core_covered),
            "framework_constraints": all_framework_constraints,
            "framework_constraint_count": len(all_framework_constraints),
        },
    }


def run_self_test() -> int:
    passed = 0
    failed = 0

    # 1. mini_esp32 操作模型
    mini = ROOT / "tools" / "fixtures" / "mini_esp32"
    if mini.is_dir():
        model = build_operating_model(str(mini), "esp32")
        assert model["rtos_model"]["task_count"] >= 3
        assert model["framework_count"] >= 1  # esp-idf should be detected
        assert model["constraint_coverage"]["core_covered_count"] >= 30
        print(f"[PASS] mini_esp32: {model['rtos_model']['task_count']} tasks, {model['framework_count']} frameworks, {model['constraint_coverage']['core_covered_count']} core constraints")
        passed += 1

    # 2. mini_zephyr 操作模型
    mini_z = ROOT / "tools" / "fixtures" / "mini_zephyr"
    if mini_z.is_dir():
        model = build_operating_model(str(mini_z), "zephyr")
        assert model["rtos_model"]["task_count"] >= 2
        print(f"[PASS] mini_zephyr: {model['rtos_model']['task_count']} tasks, {model['framework_count']} frameworks")
        passed += 1

    # 3. JSON 序列化
    if mini.is_dir():
        j = json.dumps(model, indent=2)
        data = json.loads(j)
        assert "rtos_model" in data
        assert "frameworks" in data
        print("[PASS] JSON serialization")
        passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Project Operating Model v16.0.2")
    parser.add_argument("--dir", help="项目目录")
    parser.add_argument("--platform", default="", help="平台")
    parser.add_argument("--output", "-o", help="输出文件")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.dir:
        parser.print_help()
        return 1

    model = build_operating_model(args.dir, args.platform)

    if args.output:
        Path(args.output).write_text(json.dumps(model, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"模型已保存: {args.output}")
    elif args.json:
        print(json.dumps(model, indent=2, ensure_ascii=False))
    else:
        print(f"Project: {model['project']}")
        print(f"Platform: {model['platform']}")
        print(f"RTOS: {model['rtos_model']}")
        print(f"Frameworks: {model['framework_count']}")
        print(f"Core constraints covered: {model['constraint_coverage']['core_covered_count']}")
        print(f"Framework constraints: {model['constraint_coverage']['framework_constraint_count']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
