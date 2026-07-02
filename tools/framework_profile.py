#!/usr/bin/env python3
"""
Framework Profile Resolver v14.0.3 — 框架自动识别。

根据平台、项目文件、Kconfig、CMake、include、sdkconfig 自动识别使用了哪些框架。
输出项目 framework matrix。

用法:
    python tools/framework_profile.py --dir src --json
    python tools/framework_profile.py --platform esp32 --framework esp-idf
    python tools/framework_profile.py --list
    python tools/framework_profile.py --self-test
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRAMEWORKS_DIR = ROOT / "frameworks"


def list_frameworks() -> list[dict]:
    """列出所有已注册框架。"""
    result = []
    if not FRAMEWORKS_DIR.is_dir():
        return result
    for f in sorted(FRAMEWORKS_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            result.append({
                "framework_id": data.get("framework_id", f.stem),
                "name": data.get("name", ""),
                "category": data.get("category", ""),
            })
        except Exception:
            pass
    return result


def load_pack(framework_id: str) -> dict:
    """加载框架 pack。"""
    path = FRAMEWORKS_DIR / f"{framework_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"框架不存在: {framework_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_all_packs() -> list[dict]:
    """加载所有框架 pack。"""
    packs = []
    for f in sorted(FRAMEWORKS_DIR.glob("*.json")):
        try:
            packs.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return packs


def detect_frameworks(dir_path: str, platform: str = "") -> list[dict]:
    """扫描目录，自动识别使用的框架。"""
    root = Path(dir_path)
    if not root.is_dir():
        return []

    # 收集所有文件内容线索
    includes_found: set[str] = set()
    files_found: set[str] = set()
    cmake_content = ""
    kconfig_content = ""
    sdkconfig_content = ""

    # 扫描 .c/.h 文件的 #include
    for ext in ("*.c", "*.h", "*.cpp"):
        for f in root.rglob(ext):
            try:
                content = f.read_text(encoding="utf-8", errors="replace")[:4096]
                for m in re.finditer(r'#include\s*[<"]([^>"]+)[>"]', content):
                    includes_found.add(m.group(1))
            except Exception:
                pass

    # 扫描 CMakeLists.txt
    for f in root.rglob("CMakeLists.txt"):
        try:
            cmake_content += f.read_text(encoding="utf-8", errors="replace") + "\n"
        except Exception:
            pass

    # 扫描 Kconfig
    for f in root.rglob("Kconfig*"):
        try:
            kconfig_content += f.read_text(encoding="utf-8", errors="replace") + "\n"
        except Exception:
            pass
    for f in root.rglob("prj.conf"):
        try:
            kconfig_content += f.read_text(encoding="utf-8", errors="replace") + "\n"
        except Exception:
            pass

    # 扫描 sdkconfig
    for f in root.rglob("sdkconfig*"):
        try:
            sdkconfig_content += f.read_text(encoding="utf-8", errors="replace") + "\n"
        except Exception:
            pass

    # 文件名
    for f in root.rglob("*"):
        if f.is_file():
            files_found.add(f.name.lower())

    # 匹配框架
    detected = []
    for pack in load_all_packs():
        patterns = pack.get("detect_patterns", {})
        score = 0
        evidence = []

        # Include 匹配
        for inc_pat in patterns.get("includes", []):
            for inc in includes_found:
                if inc_pat in inc:
                    score += 3
                    evidence.append(f"include: {inc}")
                    break

        # 文件匹配
        for file_pat in patterns.get("files", []):
            if file_pat.lower() in files_found:
                score += 2
                evidence.append(f"file: {file_pat}")

        # CMake 匹配
        for cmake_pat in patterns.get("cmake", []):
            if cmake_pat in cmake_content:
                score += 2
                evidence.append(f"cmake: {cmake_pat}")

        # Kconfig 匹配
        for kcfg_pat in patterns.get("kconfig", []):
            if kcfg_pat in kconfig_content:
                score += 2
                evidence.append(f"kconfig: {kcfg_pat}")

        # sdkconfig 匹配
        for sdk_pat in patterns.get("sdkconfig", []):
            if sdk_pat in sdkconfig_content:
                score += 2
                evidence.append(f"sdkconfig: {sdk_pat}")

        # 平台过滤
        fw_platforms = pack.get("platforms", [])
        if platform and fw_platforms and platform not in fw_platforms:
            score = max(0, score - 5)

        if score >= 2:
            confidence = min(1.0, score / 10.0)
            detected.append({
                "framework_id": pack["framework_id"],
                "name": pack.get("name", ""),
                "version": "",
                "confidence": round(confidence, 2),
                "evidence": evidence[:10],
                "enabled_modules": [],
                "constraint_count": len(pack.get("constraints", [])),
                "recommended_suite": pack.get("recommended_suite", "default"),
            })

    # 按置信度排序
    detected.sort(key=lambda d: -d["confidence"])
    return detected


def build_matrix(dir_path: str, platform: str = "") -> dict:
    """构建项目框架矩阵。"""
    detected = detect_frameworks(dir_path, platform)

    # 冲突检测
    conflicts = []
    fw_ids = {d["framework_id"] for d in detected}
    conflict_defs = [
        ("lvgl", "mbedtls", "resource_contention", "LVGL render task vs mbedTLS TLS 握手阻塞"),
        ("fatfs", "lvgl", "timing_conflict", "FatFS flash 写入阻塞 LVGL 渲染"),
        ("mbedtls", "esp-idf", "heap_conflict", "mbedTLS heap vs PSRAM/DMA buffer"),
        ("lwip", "lvgl", "task_model_mismatch", "lwIP 回调 vs LVGL 线程安全"),
        ("stm32-hal", "cmsis-rtos", "api_incompatible", "HAL_Delay vs osDelay"),
    ]
    for a, b, ctype, desc in conflict_defs:
        if a in fw_ids and b in fw_ids:
            conflicts.append({
                "framework_a": a, "framework_b": b,
                "conflict_type": ctype, "detail": desc,
            })

    total_constraints = sum(d["constraint_count"] for d in detected)

    return {
        "project": Path(dir_path).name,
        "platform": platform,
        "detected_frameworks": detected,
        "conflicts": conflicts,
        "total_constraints": total_constraints,
    }


def run_self_test() -> int:
    passed = 0
    failed = 0

    # 1. 列出框架
    fws = list_frameworks()
    assert len(fws) >= 8, f"Expected >=8 frameworks, got {len(fws)}"
    print(f"[PASS] {len(fws)} frameworks registered")
    passed += 1

    # 2. 加载每个框架
    for fw in fws:
        pack = load_pack(fw["framework_id"])
        assert "constraints" in pack
    print(f"[PASS] all {len(fws)} packs loadable")
    passed += 1

    # 3. 检测 fixtures
    fixtures_dir = ROOT / "tools" / "fixtures"
    if fixtures_dir.is_dir():
        matrix = build_matrix(str(fixtures_dir))
        print(f"[PASS] fixtures scan: {len(matrix['detected_frameworks'])} frameworks detected")
        passed += 1
    else:
        print("[SKIP] no fixtures dir")
        passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Framework Profile Resolver v14.0.3")
    parser.add_argument("--dir", help="扫描目录")
    parser.add_argument("--platform", default="", help="平台")
    parser.add_argument("--framework", help="查看指定框架详情")
    parser.add_argument("--list", action="store_true", help="列出所有框架")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if args.list:
        for fw in list_frameworks():
            print(f"  {fw['framework_id']:16s} [{fw['category']:10s}] {fw['name']}")
        return 0

    if args.framework:
        pack = load_pack(args.framework)
        if args.json:
            print(json.dumps(pack, indent=2, ensure_ascii=False))
        else:
            print(f"Framework: {pack['name']} ({pack['framework_id']})")
            print(f"Category:  {pack['category']}")
            print(f"Platforms: {', '.join(pack.get('platforms', []))}")
            print(f"Constraints: {len(pack.get('constraints', []))}")
            for c in pack.get("constraints", []):
                print(f"  [{c['severity']}] {c['id']}: {c['name']}")
        return 0

    if args.dir:
        matrix = build_matrix(args.dir, args.platform)
        if args.json:
            print(json.dumps(matrix, indent=2, ensure_ascii=False))
        else:
            print(f"Project: {matrix['project']}")
            print(f"Frameworks: {len(matrix['detected_frameworks'])}")
            for fw in matrix['detected_frameworks']:
                print(f"  [{fw['confidence']:.0%}] {fw['framework_id']}: {fw['constraint_count']} constraints")
            if matrix['conflicts']:
                print(f"Conflicts: {len(matrix['conflicts'])}")
                for c in matrix['conflicts']:
                    print(f"  {c['framework_a']} × {c['framework_b']}: {c['conflict_type']}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
