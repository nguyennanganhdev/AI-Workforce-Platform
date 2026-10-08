"""The fixed workflow asks the backend's intake question before handing over, and asks before filing at all
when the model itself says nothing was reported yet."""

import json
from copy import deepcopy

import pytest
from src.graph.assessment import decide_request
from test_assessment import Policy, proposal
from workflow_fixture import REQUEST, async_test, harness, resident_resume, waiting

QUESTION = "Bạn thấy nước rò ở đâu trong nhà tắm: vòi, ống, bồn cầu, tường hay trần? Nếu chưa xác định được, bạn cứ nói chưa rõ nhé."


def reported(message_id, **details):
    return json.dumps({"intent": "information", "title": "Ống âm tường vỡ", "description": "Ống âm tường bị vỡ từ sáng.",
                       "facts": [{"key": key, "value": value, "source": "customer_report", "source_message_id": message_id}
                                 for key, value in details.items()], "answers": {}})


def backend_asks(times):
    """An incident update as the backend answers it: the resident's words, and its question while a detail is missing."""
    asked = []

    def override(call, result):
        if call["operation"] != "update_ticket_incident":
            return None
        incident = {**call["input"]["incident"], "title": "Nhà tắm của tôi bị rò nước", "description": "Nhà tắm của tôi bị rò nước"}
        asked.append(call)
        questions = [QUESTION] if len(asked) <= times else []
        return {"kind": "success", "value": {**result, "incident": incident, "questions": questions}}

    return override


@pytest.mark.parametrize("staff_required", [True, False])
def test_nothing_reported_yet_is_asked_about_even_though_an_incident_is_a_matter_for_staff(staff_required):
    # The backend answers staff_required for every incident; that used to file a request at once.
    unclear = proposal("incident", "ask_clarification", missing_information=["Bạn đang gặp sự cố gì?"])
    assert decide_request(unclear, Policy(staff_required=staff_required).values, None)["next_action"] == "ask_clarification"
    insisting = {**unclear, "explicit_staff_request": True}
    assert decide_request(insisting, Policy(staff_required=True).values, None)["next_action"] == "start_ticket"
    danger = decide_request(unclear, Policy(staff_required=True, emergency=True).values, None)
    assert danger["next_action"] == "emergency_handoff"


@async_test
async def test_the_backends_question_is_asked_and_nothing_is_handed_over_until_it_is_answered():
    request = deepcopy(REQUEST)
    request["message"] = {"id": "message-1", "text": "Nhà tắm của tôi bị rò nước", "fileIds": ["file-leak"]}
    h = harness(model=[reported("message-1", symptom="bị rò nước", area="Nhà tắm"),
                       reported("message-2", item="chân vòi lavabo")], override=backend_asks(1))
    first = waiting(await h.graph.run(request))
    assert first["state"]["reply"] == QUESTION
    assert not any(c["operation"] == "handoff_ticket" for c in h.calls)
    # What the graph keeps is what the backend recorded, not the model's own title and description.
    assert first["state"]["incident"]["title"] == "Nhà tắm của tôi bị rò nước"

    answer = {"id": "message-2", "text": "Rò ở chân vòi lavabo"}
    done = waiting(await h.graph.resume(resident_resume(first, answer)))
    handoff = next(c for c in h.calls if c["operation"] == "handoff_ticket")
    # The photo sent with the first message is still on the request.
    assert handoff["input"]["message"]["file_ids"] == ["file-leak"]
    assert done["state"]["phase"] == "waiting_supervisor"


@async_test
async def test_the_same_question_may_be_asked_again_without_ending_in_review():
    h = harness(model=[reported("message-1", symptom="bị rò nước")] * 3, override=backend_asks(2))
    first = waiting(await h.graph.run(REQUEST))
    second = waiting(await h.graph.resume(resident_resume(first, {"id": "message-2", "text": "ok"})))
    assert second["state"]["reply"] == QUESTION and second["state"]["phase"] != "review"
    # The backend stops asking after two questions and lets the report through for a person to look at.
    third = waiting(await h.graph.resume(resident_resume(second, {"id": "message-3", "text": "ok"})))
    assert any(c["operation"] == "handoff_ticket" for c in h.calls) and third["state"]["phase"] == "waiting_supervisor"


@async_test
async def test_an_emergency_is_not_held_back_by_the_question():
    emergency = {"kind": "emergency", "reason": "test-policy-rule", "policyVersion": "policy-test-1"}
    from workflow_fixture import Intake

    h = harness(model=[reported("message-1", symptom="có mùi gas")], override=backend_asks(5), intake=Intake(policy=emergency))
    result = waiting(await h.graph.run(REQUEST))
    # The incident is assessed and routed at once; the resident is not asked for the missing detail.
    assert result["state"]["reply"] != QUESTION
    assert [c["operation"] for c in h.calls][-2:] == ["submit_ticket_assessment", "resolve_management_destination"]
