"""Acceptance gates cannot turn skipped/partial/scripted evidence into UAT."""

import copy

import pytest

from scripts.workforce.acceptance.judge import judge_evidence, score


def report():
    return {"mode": "offline_sql_scripted", "repetitions": 3, "business_threshold": 1.0,
        "evidence_index_sha256": "run-digest",
        "scenarios": [{"id": f"s-{i}", "critical": i < 10, "runs": [
            {"repeat": k, "passed": True, "problems": [], "evidence_sha256": f"{i}-{k}"}
            for k in (1, 2, 3)]} for i in range(24)]}


def judge(data):
    return {"report_sha256": "run-digest", "model": "independent-review-model", "independent": True,
            "verdicts": [{"scenario": s["id"], "repeat": r["repeat"], "evidence_sha256": r["evidence_sha256"],
                          "passed": True, "reason": "Reviewed persisted outcome"}
                         for s in data["scenarios"] for r in s["runs"]]}


def test_three_per_scenario_is_required_and_a_critical_failure_blocks_the_run():
    data = report()
    assert score(data)["automated_pass"]
    data["scenarios"][0]["runs"][1].update(passed=False, problems=["duplicate dispatch"])
    summary = score(data)
    assert not summary["automated_pass"] and not summary["critical_pass_k"]
    assert summary["human_review_queue"][0]["decision"] == "pending"
    data["scenarios"][0]["runs"].pop()
    with pytest.raises(ValueError, match="repetitions"):
        score(data)


def test_all_green_scripted_runs_and_missing_or_wrong_judge_never_certify_uat():
    data = report()
    assert not score(data)["business_accepted"]
    complete = judge(data)
    assert not score(data, complete)["business_accepted"]
    wrong = copy.deepcopy(complete)
    wrong["report_sha256"] = "other-run"
    with pytest.raises(ValueError, match="exact evidence"):
        score(data, wrong)
    complete["verdicts"].pop()
    with pytest.raises(ValueError, match="each repetition"):
        score(data, complete)


def test_independent_judge_failures_are_queued_for_human_review():
    data = report()
    data["mode"] = "business_sandbox_real_model"
    complete = judge(data)
    assert score(data, complete)["business_accepted"]
    complete["verdicts"][0].update(passed=False, reason="Resident received an ungrounded completion claim")
    assert not score(data, complete)["business_accepted"]
    assert score(data, complete)["human_review_queue"]


def test_missing_sql_and_duplicate_operations_cannot_pass_independent_assertions():
    assert judge_evidence({"test_result": "passed", "tables": {}}, {})
    evidence = {"test_result": "passed", "tables": {"wf_workflows": [{"state": "closed"}],
        "wf_unified_operations": [{"client_reference": "same"}, {"client_reference": "same"}]}}
    assert "duplicate operation client_reference" in judge_evidence(evidence, {})
