#!/usr/bin/env python3
"""
Evidence Store v11.0.1 — 跨项目证据湖。

把 V9/V10 产出的 DeliveryEvidence、SupervisorReport、ReproBundle 统一入库，
支持 ingest/query/summarize/export/self-test。

默认使用本地 JSONL，不依赖外部服务。

用法:
    python tools/evidence_store.py ingest .codex/runs
    python tools/evidence_store.py ingest evidence.json --type evidence
    python tools/evidence_store.py query --project voice-screen --since 30d
    python tools/evidence_store.py query --type supervisor_report --status failed
    python tools/evidence_store.py summarize
    python tools/evidence_store.py export --format csv
    python tools/evidence_store.py --self-test
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Force UTF-8
if sys.platform == "win32":
    os.environ.setdefault("PYTHONUTF8", "1")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STORE = ROOT / ".codex" / "evidence" / "store.jsonl"


# ============================================================================
# 存储引擎
# ============================================================================

class EvidenceStore:
    """JSONL 证据存储。"""

    def __init__(self, store_path: Path | str = DEFAULT_STORE):
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.store_path.exists():
            self.store_path.touch()

    def _read_all(self) -> list[dict]:
        entries = []
        for line in self.store_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return entries

    def _append(self, entry: dict):
        with open(self.store_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def ingest(self, data: dict, record_type: str = "auto", source: str = "") -> dict:
        """入库一条记录，返回 {ok, record_id, type}。"""
        # 自动检测类型
        if record_type == "auto":
            record_type = self._detect_type(data)

        record_id = data.get("run_id") or data.get("job_id") or data.get("record_id")
        if not record_id:
            import hashlib
            record_id = hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()[:12]

        # 去重
        if self._exists(record_id):
            return {"ok": True, "record_id": record_id, "type": record_type, "duplicate": True}

        entry = {
            "_id": record_id,
            "_type": record_type,
            "_ingested_at": datetime.now(timezone.utc).isoformat(),
            "_source": source,
            **data,
        }
        self._append(entry)
        return {"ok": True, "record_id": record_id, "type": record_type, "duplicate": False}

    def _detect_type(self, data: dict) -> str:
        if "run_id" in data and "gate_decisions" in data:
            return "supervisor_report"
        if "source_tool" in data and "issues" in data:
            return "delivery_evidence"
        if "workflow" in data and "checker_json" in data:
            return "repro_bundle"
        if "job_id" in data and "intent" in data:
            return "job"
        return "unknown"

    def _exists(self, record_id: str) -> bool:
        for line in self.store_path.read_text(encoding="utf-8").splitlines():
            if f'"_id": "{record_id}"' in line or f'"_id":"{record_id}"' in line:
                return True
        return False

    def query(
        self,
        record_type: str | None = None,
        project: str | None = None,
        status: str | None = None,
        since_days: int | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """查询记录。"""
        entries = self._read_all()
        results = []

        cutoff = None
        if since_days:
            cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)

        for entry in entries:
            # 类型过滤
            if record_type and entry.get("_type") != record_type:
                continue
            # 项目过滤
            if project:
                tags = entry.get("tags", [])
                job_id = entry.get("job_id", "")
                plan = entry.get("plan", {})
                intent = plan.get("intent", "") or entry.get("intent", "")
                if project not in str(tags) and project not in job_id and project not in intent:
                    continue
            # 状态过滤
            if status and entry.get("status") != status:
                continue
            # 时间过滤
            if cutoff:
                ts = entry.get("_ingested_at") or entry.get("started_at") or entry.get("timestamp", "")
                try:
                    entry_time = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if entry_time < cutoff:
                        continue
                except (ValueError, TypeError):
                    pass

            results.append(entry)
            if len(results) >= limit:
                break

        return results

    def summarize(self) -> dict:
        """汇总统计。"""
        entries = self._read_all()
        type_counts = Counter(e.get("_type", "unknown") for e in entries)
        status_counts = Counter(e.get("status", "unknown") for e in entries)

        # 按时间统计（最近 30 天，按天）
        daily: Counter = Counter()
        for e in entries:
            ts = e.get("_ingested_at", "")[:10]
            if ts:
                daily[ts] += 1

        # 风险等级分布
        risk_counts: Counter = Counter()
        for e in entries:
            plan = e.get("plan", {})
            risk = plan.get("risk_level") or e.get("risk_level", "")
            if risk:
                risk_counts[risk] += 1

        return {
            "total_records": len(entries),
            "by_type": dict(type_counts),
            "by_status": dict(status_counts),
            "by_risk": dict(risk_counts),
            "daily_counts": dict(sorted(daily.items())[-30:]),
            "store_path": str(self.store_path),
            "store_size_bytes": self.store_path.stat().st_size,
        }

    def export_csv(self, output_path: Path | str | None = None) -> str:
        """导出为 CSV 格式字符串（或写入文件）。"""
        entries = self._read_all()
        if not entries:
            return ""

        # 收集所有键
        keys = set()
        for e in entries:
            keys.update(e.keys())
        keys = sorted(keys)

        lines = [",".join(keys)]
        for e in entries:
            row = []
            for k in keys:
                v = e.get(k, "")
                s = json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)
                s = s.replace('"', '""')
                row.append(f'"{s}"')
            lines.append(",".join(row))

        csv_str = "\n".join(lines)
        if output_path:
            Path(output_path).write_text(csv_str, encoding="utf-8")
        return csv_str

    def ingest_directory(self, dir_path: str, recursive: bool = True) -> dict:
        """批量入库目录下的 JSON 文件。"""
        root = Path(dir_path)
        if not root.is_dir():
            return {"ok": False, "error": f"目录不存在: {dir_path}"}

        pattern = "**/*.json" if recursive else "*.json"
        files = sorted(root.glob(pattern))

        ingested = 0
        skipped = 0
        errors = 0

        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                result = self.ingest(data, source=str(f.relative_to(root)))
                if result.get("duplicate"):
                    skipped += 1
                else:
                    ingested += 1
            except Exception:
                errors += 1

        return {"ok": True, "ingested": ingested, "skipped": skipped, "errors": errors, "files_found": len(files)}


# ============================================================================
# CLI
# ============================================================================

def run_self_test() -> int:
    import tempfile
    passed = 0
    failed = 0

    with tempfile.TemporaryDirectory() as tmp:
        store = EvidenceStore(Path(tmp) / "test.jsonl")

        # 1. Ingest delivery evidence
        ev = {"source_tool": "run_review", "issues": [{"id": "C3.1"}], "record_id": "ev-001"}
        r = store.ingest(ev)
        assert r["ok"] and r["type"] == "delivery_evidence"
        print("[PASS] ingest delivery_evidence")
        passed += 1

        # 2. Ingest supervisor report
        sr = {"run_id": "run-001", "job_id": "job-001", "status": "success",
              "gate_decisions": [], "plan": {"risk_level": "low"}}
        r = store.ingest(sr)
        assert r["ok"] and r["type"] == "supervisor_report"
        print("[PASS] ingest supervisor_report")
        passed += 1

        # 3. Ingest repro bundle
        rb = {"workflow": "debug_crash", "checker_json": [], "record_id": "rb-001"}
        r = store.ingest(rb)
        assert r["ok"] and r["type"] == "repro_bundle"
        print("[PASS] ingest repro_bundle")
        passed += 1

        # 4. Dedup
        r2 = store.ingest(ev)
        assert r2["duplicate"] is True
        print("[PASS] dedup")
        passed += 1

        # 5. Query by type
        results = store.query(record_type="supervisor_report")
        assert len(results) == 1
        assert results[0]["run_id"] == "run-001"
        print("[PASS] query by type")
        passed += 1

        # 6. Query by status
        results = store.query(status="success")
        assert len(results) >= 1
        print("[PASS] query by status")
        passed += 1

        # 7. Summarize
        summary = store.summarize()
        assert summary["total_records"] == 3
        assert summary["by_type"]["delivery_evidence"] == 1
        print("[PASS] summarize")
        passed += 1

        # 8. Export CSV
        csv = store.export_csv()
        assert "run_id" in csv or "source_tool" in csv
        print("[PASS] export_csv")
        passed += 1

        # 9. Ingest directory
        run_dir = Path(tmp) / "runs"
        run_dir.mkdir()
        (run_dir / "r1.json").write_text(json.dumps({"run_id": "dir-1", "status": "ok"}), encoding="utf-8")
        (run_dir / "r2.json").write_text(json.dumps({"run_id": "dir-2", "status": "fail"}), encoding="utf-8")
        r = store.ingest_directory(str(run_dir))
        assert r["ingested"] == 2
        print("[PASS] ingest_directory")
        passed += 1

    print(f"\nSelf-test: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Evidence Store v11.0.1")
    sub = parser.add_subparsers(dest="command")

    # ingest
    p_ingest = sub.add_parser("ingest", help="入库证据")
    p_ingest.add_argument("path", help="JSON 文件或目录路径")
    p_ingest.add_argument("--type", default="auto", help="记录类型")
    p_ingest.add_argument("--store", default=str(DEFAULT_STORE), help="存储路径")

    # query
    p_query = sub.add_parser("query", help="查询记录")
    p_query.add_argument("--type", help="按类型过滤")
    p_query.add_argument("--project", help="按项目过滤")
    p_query.add_argument("--status", help="按状态过滤")
    p_query.add_argument("--since", type=int, help="最近 N 天")
    p_query.add_argument("--limit", type=int, default=100)
    p_query.add_argument("--json", action="store_true")
    p_query.add_argument("--store", default=str(DEFAULT_STORE))

    # summarize
    p_sum = sub.add_parser("summarize", help="汇总统计")
    p_sum.add_argument("--json", action="store_true")
    p_sum.add_argument("--store", default=str(DEFAULT_STORE))

    # export
    p_exp = sub.add_parser("export", help="导出")
    p_exp.add_argument("--format", default="csv", choices=["csv", "jsonl"])
    p_exp.add_argument("--output", "-o")
    p_exp.add_argument("--store", default=str(DEFAULT_STORE))

    parser.add_argument("--self-test", action="store_true")

    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    if not args.command:
        parser.print_help()
        return 1

    store = EvidenceStore(args.store)

    if args.command == "ingest":
        path = Path(args.path)
        if path.is_dir():
            r = store.ingest_directory(str(path))
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
            r = store.ingest(data, record_type=args.type, source=str(path))
        print(json.dumps(r, ensure_ascii=False))
        return 0

    if args.command == "query":
        results = store.query(
            record_type=args.type, project=args.project,
            status=args.status, since_days=args.since, limit=args.limit,
        )
        if args.json:
            print(json.dumps(results, indent=2, ensure_ascii=False))
        else:
            print(f"结果: {len(results)} 条")
            for r in results:
                rid = r.get("_id", "?")
                typ = r.get("_type", "?")
                status = r.get("status", "N/A")
                print(f"  [{typ}] {rid} status={status}")
        return 0

    if args.command == "summarize":
        summary = store.summarize()
        if args.json:
            print(json.dumps(summary, indent=2, ensure_ascii=False))
        else:
            print(f"总记录: {summary['total_records']}")
            print(f"按类型: {summary['by_type']}")
            print(f"按状态: {summary['by_status']}")
            print(f"存储: {summary['store_path']} ({summary['store_size_bytes']} bytes)")
        return 0

    if args.command == "export":
        if args.format == "csv":
            csv = store.export_csv(args.output)
            if not args.output:
                print(csv)
        else:
            entries = store._read_all()
            out = "\n".join(json.dumps(e, ensure_ascii=False) for e in entries)
            if args.output:
                Path(args.output).write_text(out, encoding="utf-8")
            else:
                print(out)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
