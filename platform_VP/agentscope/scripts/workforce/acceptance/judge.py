"""Read persisted evidence independently of the scripted room/test driver."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def judge_evidence(evidence: dict, expectations: dict) -> list[str]:
    problems = []
    if evidence.get("test_result") != "passed":
        problems.append("deterministic runtime assertions did not pass")
    if not evidence.get("tables", {}).get("wf_workflows"):
        problems.append("missing persisted workflow evidence")
    tables = evidence.get("tables", {})
    operations = tables.get("wf_unified_operations", [])
    references = [op["client_reference"] for op in operations]
    if len(references) != len(set(references)):
        problems.append("duplicate operation client_reference")
    receipts = tables.get("wf_unified_receipts", [])
    event_ids = [(row["integration_id"], row["external_event_id"]) for row in receipts]
    if len(event_ids) != len(set(event_ids)):
        problems.append("duplicate provider event application")
    for table, checks in expectations.items():
        rows = tables.get(table, [])
        if "count" in checks and len(rows) != checks["count"]:
            problems.append(f"{table}: expected {checks['count']} rows, got {len(rows)}")
        for field, expected in checks.get("contains", {}).items():
            if not any(row.get(field) == expected for row in rows):
                problems.append(f"{table}: missing {field}={expected}")
    return problems


def score(report: dict, judge_report: dict | None = None) -> dict:
    """pass^k means every repetition passed; missing/failed evidence fails closed."""
    scenarios = report["scenarios"]
    repetitions = report["repetitions"]
    if repetitions < 3 or not 20 <= len(scenarios) <= 30:
        raise ValueError("Acceptance requires 20–30 scenarios and at least three repetitions")
    ids = [scenario["id"] for scenario in scenarios]
    if len(ids) != len(set(ids)):
        raise ValueError("Scenario IDs must be unique")
    for scenario in scenarios:
        runs = scenario["runs"]
        if len(runs) != repetitions or {r["repeat"] for r in runs} != set(range(1, repetitions + 1)):
            raise ValueError("Every scenario needs exactly the declared repetitions")
        scenario["pass_k"] = all(r["passed"] for r in runs)
    critical = [s for s in scenarios if s["critical"]]
    if not critical:
        raise ValueError("Critical safety, tenant and duplicate-action scenarios are required")
    critical_pass = all(s["pass_k"] for s in critical)
    business = [s for s in scenarios if not s["critical"]]
    business_rate = sum(s["pass_k"] for s in business) / len(business) if business else 0.0
    automated = critical_pass and business_rate >= report["business_threshold"]
    review_queue = [
        {"scenario": s["id"], "repeat": r["repeat"], "evidence_sha256": r["evidence_sha256"],
         "reasons": r["problems"], "reviewer": None, "decision": "pending"}
        for s in scenarios for r in s["runs"] if not r["passed"]
    ]
    # A deterministic fake-model test run must never certify model/business UAT.
    model_judge = "not_run"
    judge_pass = False
    if judge_report is not None:
        if judge_report.get("report_sha256") != report["evidence_index_sha256"]:
            raise ValueError("Independent judge report does not bind this exact evidence index")
        if not judge_report.get("model") or judge_report.get("independent") is not True:
            raise ValueError("Independent judge model/provenance is required")
        verdicts = judge_report.get("verdicts", [])
        expected = {(s["id"], r["repeat"], r["evidence_sha256"]) for s in scenarios for r in s["runs"]}
        actual = {(v["scenario"], v["repeat"], v["evidence_sha256"]) for v in verdicts}
        if actual != expected or len(verdicts) != len(expected):
            raise ValueError("Judge must review each repetition exactly once using its evidence digest")
        if any(not isinstance(v.get("passed"), bool) or not str(v.get("reason", "")).strip() for v in verdicts):
            raise ValueError("Judge verdicts need a boolean and a reason")
        for verdict in verdicts:
            if not verdict["passed"]:
                review_queue.append({**verdict, "reviewer": None, "decision": "pending"})
        judge_pass = all(v["passed"] for v in verdicts)
        model_judge = "passed" if judge_pass else "failed"
    return {
        "automated_pass": automated, "critical_pass_k": critical_pass,
        "business_pass_k_rate": business_rate,
        "passed_scenarios": sum(s["pass_k"] for s in scenarios),
        "independent_model_judge": model_judge, "human_review_queue": review_queue,
        "business_accepted": automated and judge_pass and not review_queue and report.get("mode") == "business_sandbox_real_model",
    }


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))
