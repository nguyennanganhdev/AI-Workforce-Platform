"""No-key acceptance rehearsal on real SQL/API/worker paths with scripted peers.

This command does not load .env or connect to a deployed application. Each
scenario starts a new disposable SQLite database; MCP and models are fakes.
Independent DB/event checks read the captured evidence after the driver exits.
Real-model/Domain UAT is recorded separately and is never inferred from this run.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import inspect, text

from scripts.workforce.acceptance.judge import digest, judge_evidence, read_json, score

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
TABLES = (
    "wf_workflows", "wf_workflow_bindings", "wf_workflow_checkpoints",
    "wf_unified_operations", "wf_unified_receipts", "wf_unified_approvals",
    "wf_unified_case_entries", "wf_public_events", "wf_durable_jobs",
)


def source_manifest() -> dict:
    origin_path = ROOT / ".acceptance-origin.json"
    origin = read_json(origin_path) if origin_path.is_file() else None

    def git(*args):
        if origin is not None:
            return origin["commit"] if args == ("rev-parse", "HEAD") else origin["branch"]
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()

    paths = sorted([*ROOT.joinpath("src").rglob("*.py"), *ROOT.joinpath("tests/workforce").rglob("*.py"),
                    *HERE.rglob("*.py"), HERE / "scenarios.json"])
    hashes = {p.relative_to(ROOT).as_posix(): digest(p) for p in paths}
    declaration = ROOT.parent.parent / "vinhome_Recident/deploy/platform/vinhomes-declaration.json"
    return {"commit": git("rev-parse", "HEAD"), "branch": git("branch", "--show-current"),
            "source_sha256": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
            "files": hashes, "model": "scripted-no-network", "image": "host-python",
            "declaration_sha256": digest(declaration), "schema_revision": "0018_unified_recovery",
            "snapshot_origin": origin["source_root"] if origin is not None else None,
            "python": sys.version, "seed": 42}


def load_case(scenario: dict, modules: dict):
    relative = scenario["file"]
    if relative not in modules:
        path = (ROOT / relative).resolve()
        if ROOT not in path.parents or not path.is_file():
            raise ValueError("Scenario must reference a test inside this checkout")
        # Companion test modules import the harness by its ordinary test name.
        if str(path.parent) not in sys.path:
            sys.path.insert(0, str(path.parent))
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[path.stem] = module
        spec.loader.exec_module(module)
        modules[relative] = module
    cls = getattr(modules[relative], scenario["class"])
    return cls(scenario["method"])


def execute(scenario: dict, repeat: int, modules: dict) -> dict:
    case = load_case(scenario, modules)
    evidence = {"scenario": scenario["id"], "repeat": repeat, "tables": {}, "test_result": "error"}
    teardown = case.asyncTearDown

    async def capture():
        try:
            async with case.engine.connect() as conn:
                available = await conn.run_sync(lambda c: set(inspect(c).get_table_names()))
                for table in TABLES:
                    if table in available:
                        rows = (await conn.execute(text(f'SELECT * FROM "{table}"'))).mappings().all()
                        evidence["tables"][table] = [dict(row) for row in rows]
            evidence["mcp_calls"] = getattr(case, "mcp_calls", [])
        finally:
            await teardown()

    case.asyncTearDown = capture
    result = unittest.TestResult()
    case.run(result)
    evidence["test_result"] = "passed" if result.wasSuccessful() and not result.skipped else "failed"
    evidence["errors"] = [message for _, message in [*result.failures, *result.errors, *result.skipped]]
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--business-threshold", required=True, type=float,
                        help="Set the agreed pass^k threshold before the run; no inferred agreement")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--judge-report", type=Path)
    args = parser.parse_args()
    if args.repetitions < 3 or not 0 < args.business_threshold <= 1:
        parser.error("Use repetitions >=3 and business threshold in (0, 1]")
    scenarios = read_json(HERE / "scenarios.json")["scenarios"]
    if not 20 <= len(scenarios) <= 30 or len({s["id"] for s in scenarios}) != len(scenarios):
        parser.error("Use 20–30 distinct acceptance scenarios")
    if args.output.exists():
        parser.error("Output already exists; choose a fresh run directory")
    args.output.mkdir(parents=True)
    report = {"mode": "offline_sql_scripted", "created_at": datetime.now(UTC).isoformat(),
              "repetitions": args.repetitions, "business_threshold": args.business_threshold,
              "manifest": source_manifest(), "scenarios": []}
    modules = {}
    for scenario in scenarios:
        item = {**scenario, "runs": []}
        for repeat in range(1, args.repetitions + 1):
            try:
                evidence = execute(scenario, repeat, modules)
            except Exception as exc:  # noqa: BLE001 - preserve failed scenario evidence and finish the matrix
                evidence = {"scenario": scenario["id"], "repeat": repeat, "test_result": "error",
                            "tables": {}, "errors": [f"{type(exc).__name__}: {exc}"]}
            path = args.output / f"{scenario['id']}-{repeat}.json"
            path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            problems = judge_evidence(read_json(path), scenario.get("expect", {}))
            item["runs"].append({"repeat": repeat, "passed": not problems, "problems": problems,
                                 "evidence_file": path.name, "evidence_sha256": digest(path)})
            print(f"{scenario['id']} {repeat}/{args.repetitions}: {'PASS' if not problems else 'FAIL'}", flush=True)
        report["scenarios"].append(item)
        # A crash leaves every completed scenario and its evidence recoverable.
        (args.output / "partial.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    index = [{"scenario": s["id"], "repeat": r["repeat"], "sha256": r["evidence_sha256"]}
             for s in report["scenarios"] for r in s["runs"]]
    report["evidence_index_sha256"] = hashlib.sha256(json.dumps(index, sort_keys=True).encode()).hexdigest()
    report["source_unchanged"] = source_manifest()["source_sha256"] == report["manifest"]["source_sha256"]
    report["summary"] = score(report, read_json(args.judge_report) if args.judge_report else None)
    if not report["source_unchanged"]:
        report["summary"]["automated_pass"] = False
        report["summary"]["business_accepted"] = False
        report["summary"]["human_review_queue"].append({"reason": "Source changed during the run; repeat on the final source", "decision": "pending"})
    (args.output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output / "human-review.json").write_text(json.dumps(report["summary"]["human_review_queue"], ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0 if report["summary"]["automated_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
