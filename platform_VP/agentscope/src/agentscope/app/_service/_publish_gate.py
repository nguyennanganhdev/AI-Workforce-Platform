"""One fail-closed publication policy for every business-agent authoring UI."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import UTC, datetime
from typing import Literal

from .._agent_spec import AgentSpec, spec_hash

MIN_TESTS_TO_PUBLISH = 3
PASS_THRESHOLD = 0.8
EVALUATOR = "agent_spec_model_v1"


def _report_hash(report: dict) -> str:
    payload = {key: value for key, value in report.items() if key != "report_hash"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _result_blocker(spec: AgentSpec, report: dict | None) -> str:
    if len(spec.tests) < MIN_TESTS_TO_PUBLISH:
        return f"Cần ít nhất {MIN_TESTS_TO_PUBLISH} kịch bản kiểm thử."
    if not any(test.safety_critical or test.must_not_include for test in spec.tests):
        return "Cần ít nhất một kịch bản an toàn bắt buộc (safety_critical)."
    if not report or report.get("spec_hash") != spec_hash(spec):
        return "Hãy chạy kiểm thử cho bản nháp hiện tại trước khi phát hành."
    if report.get("evaluator") != EVALUATOR or not report.get("ran_at"):
        return "Cần báo cáo kiểm thử bằng model; kiểm tra cấu hình tĩnh không đủ."
    results = report.get("results") or []
    ids = [result.get("test_id") for result in results]
    expected = {test.id for test in spec.tests}
    if len(expected) != len(spec.tests) or len(ids) != len(expected) or set(ids) != expected:
        return "Báo cáo không bao phủ đúng các kịch bản của bản nháp hiện tại."
    if report.get("errors") or report.get("model_error") or any(result.get("error") for result in results):
        if report.get("model_error"):
            return f"Chưa kiểm thử được {report.get('errors', 0)}/{len(results)} kịch bản: {report['model_error']}"
        return "Kiểm thử gặp lỗi model; hãy sửa lỗi và chạy lại trước khi phát hành."
    if any(result.get("model_evaluated") is not True or not isinstance(result.get("judge"), dict)
           for result in results):
        return "Mọi kịch bản phải được chạy và đánh giá bằng model."
    by_id = {result["test_id"]: result for result in results}
    for test in spec.tests:
        if (test.safety_critical or test.must_not_include) and by_id[test.id].get("passed") is not True:
            return "Kịch bản an toàn bắt buộc chưa đạt; không được phát hành."
    passed = sum(result.get("passed") is True for result in results)
    if passed / len(results) < PASS_THRESHOLD:
        return f"Kiểm thử đạt {passed}/{len(results)}; cần tối thiểu {int(PASS_THRESHOLD * 100)}%."
    if any(result.get("passed") is True and (result["judge"].get("passed") is not True
           or any(check.get("passed") is not True for check in result.get("checks", []))) for result in results):
        return "Kết quả kiểm thử không khớp đánh giá và kiểm tra an toàn."
    if report.get("total") != len(results) or report.get("passed") != passed:
        return "Thống kê báo cáo kiểm thử không khớp kết quả từng kịch bản."
    return ""


def seal_report(spec: AgentSpec, report: dict) -> dict:
    """Freeze server-generated evidence; derive readiness instead of trusting a flag."""
    sealed = copy.deepcopy(report)
    sealed["publishable"] = not _result_blocker(spec, sealed)
    sealed["report_hash"] = _report_hash(sealed)
    return sealed


def publish_blocker(spec: AgentSpec, report: dict | None) -> str:
    blocker = _result_blocker(spec, report)
    if blocker:
        return blocker
    if report.get("report_hash") != _report_hash(report):
        return "Báo cáo kiểm thử đã thay đổi; hãy chạy lại kiểm thử."
    return ""


def trusted_publication(
    spec: AgentSpec,
    *,
    source: Literal["system_leader", "approved_provisioning"],
    reason: str,
    actor: str,
) -> dict:
    """Explicit internal provisioning evidence; never accepted from authoring APIs."""
    if source not in {"system_leader", "approved_provisioning"} or not reason.strip() or not actor.strip():
        raise ValueError("Trusted provisioning requires source, actor and reason")
    report = {
        "spec_hash": spec_hash(spec), "source": source, "reason": reason,
        "actor": actor, "ran_at": datetime.now(UTC).isoformat(), "exempt": True,
    }
    report["report_hash"] = _report_hash(report)
    return report


def publication_blocker(spec: AgentSpec, report: dict | None, *, allow_provisioning: bool = False) -> str:
    """Readiness of a published version, including auditable internal exemptions."""
    if allow_provisioning and report and report.get("exempt") is True:
        if (report.get("source") in {"system_leader", "approved_provisioning"}
                and report.get("actor") and report.get("reason")
                and report.get("spec_hash") == spec_hash(spec)
                and report.get("report_hash") == _report_hash(report)):
            return ""
        return "Provenance cấp phát tin cậy không hợp lệ."
    return publish_blocker(spec, report)
