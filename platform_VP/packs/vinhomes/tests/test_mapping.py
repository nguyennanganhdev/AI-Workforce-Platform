import json

import pytest

from awp_vinhomes import mapping
from fake_vinhomes import NAME, PHONE, TEAM, TICKET, ResultIn, submitted
from helpers import ATTRS, current, result


def test_ticket_submitted_becomes_a_case_intake():
    msg = submitted(7, version=9, emergency=True)
    intake = mapping.intake_from_message(msg)
    assert intake.message_id == "m-7" and intake.external_ref == TICKET
    assert intake.summary == "Vòi bếp rò nước" and "rò dưới bồn" in intake.description
    assert intake.requester_ref == "res-42" and intake.priority == "critical"
    # the resident's own words keep their source; what the system knows is "verified"
    by_key = {f.key: f for f in intake.facts}
    assert by_key["vị trí"].source == "reported" and by_key["vị trí"].value == "bồn rửa bếp"
    assert by_key["căn hộ"].value == "S1.01-1201" and by_key["căn hộ"].source == "verified"
    assert by_key["khẩn cấp"].source == "inferred"
    a = intake.attributes
    assert (a["ticket_id"], a["ticket_code"], a["ticket_generation"], a["ticket_version"]) == (TICKET, "VH-0001", 0, "9")
    assert a["team_id"] == TEAM and a["correlation_id"] == "corr-1" and a["is_emergency"] is True
    assert a["location"]["building_code"] == "S1.01" and a["category_id"]


def test_fact_sources_are_kept():
    facts = [{"key": k, "value": v, "source": s, "source_message_id": "x"} for k, v, s in
             [("a", "1", "customer_report"), ("b", 2, "staff_verified"), ("c", None, "agent_inference")]]
    intake = mapping.intake_from_message(submitted(facts=facts))
    got = {f.key: (f.value, f.source) for f in intake.facts if f.key in "abc"}
    assert got == {"a": ("1", "reported"), "b": ("2", "verified"), "c": ("", "inferred")}


def test_the_residents_name_and_phone_never_reach_the_model():
    leaky = f"Tôi là {NAME}, gọi {PHONE} hoặc +84 912 345 678 hoặc 0987-654-321 nhé"
    msg = submitted(title=f"{NAME} báo rò nước", description=leaky,
                    facts=[{"key": "liên hệ", "value": PHONE, "source": "customer_report", "source_message_id": "x"}])
    intake = mapping.intake_from_message(msg)
    dumped = json.dumps(intake.model_dump(), ensure_ascii=False)
    for secret in (NAME, PHONE, "912 345 678", "0987-654-321", "resident_name", "phone_number"):
        assert secret not in dumped, secret
    assert intake.requester_ref == "res-42" and "[số điện thoại]" in intake.description
    # follow-ups are free text from the resident too
    _ref, fu = mapping.follow_up_from_message(submitted(2, "information_provided", message=f"{NAME}: {PHONE}"))
    assert NAME not in fu.text and PHONE not in fu.text


def test_a_price_is_not_mistaken_for_a_phone_number():
    intake = mapping.intake_from_message(submitted(description="Chi phí dự kiến 1500000 đồng, cọc 500000"))
    assert "1500000" in intake.description and "500000" in intake.description


@pytest.mark.parametrize("kind,expected", [
    ("information_provided", "bổ sung thông tin"), ("plan_approved", "đã đồng ý phương án"),
    ("plan_rejected", "đã từ chối phương án"), ("plan_change_requested", "thay đổi phương án"),
    ("cancel_requested", "hủy yêu cầu")])
def test_every_other_message_is_a_follow_up(kind, expected):
    ref, fu = mapping.follow_up_from_message(submitted(3, kind, message="vào buổi chiều"))
    assert ref == TICKET and fu.message_id == "m-3" and fu.kind == kind
    assert expected in fu.text and "vào buổi chiều" in fu.text
    assert fu.attributes["source_message_id"] == "c-2"


def test_a_reopened_ticket_is_a_new_case():
    assert mapping.intake_from_message(submitted(generation=2)).external_ref == f"{TICKET}#g2"
    assert mapping.follow_up_from_message(submitted(4, "plan_approved", generation=2))[0] == f"{TICKET}#g2"


def test_malformed_messages_are_named_not_guessed():
    broken = submitted()
    del broken["request"]["title"]
    with pytest.raises(mapping.BadMessage):
        mapping.intake_from_message(broken)
    with pytest.raises(mapping.BadMessage):
        mapping.follow_up_from_message({**submitted(2, "information_provided"), "message_type": "mystery"})
    with pytest.raises(mapping.BadMessage):
        mapping.intake_from_message(submitted(2, "information_provided"))


# ---- results -------------------------------------------------------------------
def valid(body: dict) -> dict:
    """The contract's own validation (strict, extra fields refused)."""
    ResultIn.model_validate(body)
    return body


def test_resolved_on_an_open_ticket_is_in_progress():
    body = valid(mapping.result_message(ATTRS, result(), current()))
    assert body["message_type"] == "in_progress" and "result" not in body
    assert (body["ticket_version"], body["ticket_generation"], body["supervisor_run_id"]) == ("7", 0, "case_abc")
    assert (body["team_id"], body["ticket_id"], body["ticket_code"]) == (TEAM, TICKET, "VH-0001")
    assert body["correlation_id"] == "corr-1"


@pytest.mark.parametrize("status", ["resolved", "closed"])
def test_resolved_on_a_finished_ticket_is_completed(status):
    body = valid(mapping.result_message(ATTRS, result(answer="Việc đã xong."), current(status)))
    assert body["message_type"] == "completed" and body["result"]["outcome"] == "work_completed"
    assert body["result"]["work_order_ids"] == [] and body["result"]["evidence_ids"] == []


def test_a_cancelled_ticket_is_reported_as_cancelled_whatever_the_outcome():
    for outcome in ("resolved", "needs_human", "failed"):
        body = valid(mapping.result_message(ATTRS, result(outcome), current("cancelled")))
        assert body["message_type"] == "cancelled" and "result" not in body and "error" not in body


def test_needs_human_and_cannot_resolve_hand_over_to_a_person():
    body = valid(mapping.result_message(ATTRS, result("needs_human", "Cần BQL xem.", ["thiếu giờ hẹn"]), current()))
    assert body["message_type"] == "failed" and body["error"] == {
        "code": "NEEDS_HUMAN_REVIEW", "retryable": False, "message": "thiếu giờ hẹn"}
    assert body["result"]["outcome"] == "needs_human_review"
    body = valid(mapping.result_message(ATTRS, result("cannot_resolve", ""), current()))
    assert body["error"]["code"] == "CANNOT_RESOLVE" and body["error"]["retryable"] is False
    assert body["result"]["outcome"] == "unable_to_resolve" and body["message"]  # never empty


def test_a_platform_failure_is_retryable_and_says_nothing_internal_to_the_resident():
    body = valid(mapping.result_message(ATTRS, result("failed", "Mình chưa có thông tin.", ["could not start: boom"]),
                                         current()))
    assert body["message_type"] == "failed" and body["error"]["retryable"] is True
    assert "boom" not in body["message"] and "boom" in body["error"]["message"]


def test_the_message_id_is_stable_for_the_same_news_and_changes_with_the_version():
    first = mapping.result_message(ATTRS, result(), current(version=7))
    again = mapping.result_message(ATTRS, result(), current(version=7), sent_at="2030-01-01T00:00:00+00:00")
    later = mapping.result_message(ATTRS, result(), current(version=8))
    assert first["message_id"] == again["message_id"] != later["message_id"]
    assert len(first["message_id"]) <= 160


def test_long_and_empty_text_still_fit_the_contract():
    valid(mapping.result_message(ATTRS, result(answer="x" * 20000), current()))
    valid(mapping.result_message(ATTRS, result(answer=""), current()))
    valid(mapping.result_message(ATTRS, result("needs_human", "y" * 20000, ["z" * 5000]), current()))


def test_the_receipt_is_valid():
    body = valid(mapping.accepted_message(submitted(5)))
    assert body["message_type"] == "accepted" and body["ticket_version"] == "7"
    assert body["message_id"] == mapping.accepted_message(submitted(5))["message_id"]
