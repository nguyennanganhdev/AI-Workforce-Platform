"""Request classification, policy overrides and consent/emergency consumer contracts."""

import json
from copy import deepcopy

import pytest
from src.graph.assessment import ASSESSMENT_SCHEMA, decide_request, parse_assessment
from src.graph.decision import GraphFault
from src.graph.workflow_contracts import (
    OPERATION_INPUTS,
    OPERATIONS,
    EmergencyInput,
    SelfHelpInput,
)
from workflow_fixture import (
    INFORMATION,
    REQUEST,
    Intake,
    async_test,
    harness,
    resident_resume,
    turn,
    waiting,
)


def proposal(intent="incident", action="ask_clarification", **extra):
    return {
        "intent": intent,
        "proposed_action": action,
        "explicit_staff_request": False,
        "self_help_declined": False,
        "self_help_failed": False,
        "emergency_signals": [],
        "missing_information": [],
        "reason": "Căn cứ từ tin nhắn mẫu.",
        **extra,
    }


class Policy:
    def __init__(self, **values):
        self.values = {
            "policy_version": "policy-assessment-1",
            "emergency": False,
            "staff_required": False,
            "self_help_allowed": False,
            "missing_information": [],
            "handoff_reason": "needs_staff",
            **values,
        }
        self.calls = []

    async def evaluate_request(self, request):
        self.calls.append(request)
        return deepcopy(self.values)


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p.update(workspace_id="forged"),
        lambda p: p.update(proposed_action="create_ticket_draft"),
        lambda p: p.update(intent="unknown"),
        lambda p: p.update(explicit_staff_request="yes"),
        lambda p: p.pop("missing_information"),
        lambda p: p.update(missing_information=["x"] * 17),
        lambda p: p.update(reason=" "),
        lambda p: p.update(emergency_signals=[{"tool": "shell"}]),
    ],
)
def test_strict_schema_rejects_model_authority(change):
    value = proposal()
    change(value)
    with pytest.raises(GraphFault, match="INVALID_REQUEST_ASSESSMENT"):
        parse_assessment(json.dumps(value))


def test_input_catalog_parity_and_schema():
    assert set(OPERATION_INPUTS) == set(OPERATIONS)
    assert OPERATION_INPUTS["process_self_help"] is SelfHelpInput
    assert OPERATION_INPUTS["escalate_emergency"] is EmergencyInput
    assert set(ASSESSMENT_SCHEMA["required"]) == set(proposal())


@pytest.mark.parametrize(
    "intent,action,policy,active,expected",
    [
        ("information", "start_ticket", {}, None, "retrieve_knowledge"),
        ("incident", "start_ticket", {}, None, "ask_clarification"),
        ("incident", "retrieve_self_help", {}, None, "ask_clarification"),
        (
            "incident",
            "retrieve_self_help",
            {"self_help_allowed": True},
            None,
            "retrieve_self_help",
        ),
        (
            "service_request",
            "retrieve_knowledge",
            {"staff_required": True},
            None,
            "start_ticket",
        ),
        (
            "incident",
            "start_ticket",
            {"staff_required": True},
            "existing",
            "continue_existing_ticket",
        ),
        ("information", "retrieve_knowledge", {}, "existing", "retrieve_knowledge"),
        (
            "incident",
            "retrieve_self_help",
            {"emergency": True},
            "existing",
            "emergency_handoff",
        ),
    ],
)
def test_policy_and_active_ticket_override_llm(
    intent, action, policy, active, expected
):
    assert (
        decide_request(proposal(intent, action), Policy(**policy).values, active)[
            "next_action"
        ]
        == expected
    )


@async_test
async def test_second_node_and_knowledge_no_ticket_even_model_suggests_start():
    policy = Policy()
    intake = Intake(
        knowledge={
            "kind": "sufficient",
            "answer": "Thông tin có nguồn mẫu.",
            "retrievalRunId": "r",
            "citations": [{"documentId": "d", "version": "1", "chunkId": "c"}],
        }
    )
    h = harness(
        assess_model=[json.dumps(proposal("information", "start_ticket"))],
        request_policy=policy,
        intake=intake,
    )
    result = await h.graph.run(REQUEST)
    assert result["status"] == "completed", result
    assert result["state"]["decision"]["next_action"] == "retrieve_knowledge"
    assert not h.calls
    graph = h.graph.compiled.get_graph()
    assert any(
        edge.source == "receive_message" and edge.target == "assess_request"
        for edge in graph.edges
    )
    assert len(policy.calls) == 2
    assert policy.calls[1]["assessment"]["intent"] == "information"


@async_test
async def test_clarification_reassesses_with_question_and_previous_message_history():
    policy = Policy()
    h = harness(
        assess_model=[
            json.dumps(
                proposal(
                    missing_information=["Bạn muốn nhân viên hỗ trợ hay hướng dẫn?"]
                )
            ),
            json.dumps(
                proposal("service_request", "start_ticket", explicit_staff_request=True)
            ),
        ],
        request_policy=policy,
    )
    first = waiting(await h.graph.run(REQUEST))
    assert not h.calls
    policy.values["staff_required"] = True
    final = waiting(await h.graph.resume(resident_resume(first)))
    assert final["state"]["active_ticket_id"]
    model_input = json.loads(h.assessment_model.calls[1][-1].content)
    assert any(
        item["role"] == "assistant" and "Bạn muốn" in item["text"]
        for item in model_input["history"]
    )
    assert any(item.get("message_id") == "message-1" for item in model_input["history"])
    assert len(model_input["history"]) <= 24
    assert "output_schema" in model_input


@async_test
async def test_retrieval_insufficient_never_dispatches_staff():
    h = harness(
        assess_model=[json.dumps(proposal("information", "retrieve_knowledge"))],
        request_policy=Policy(),
    )
    result = waiting(await h.graph.run(REQUEST))
    assert result["state"]["next"] == "wait_for_resident"
    assert not h.calls
    assert "đủ nguồn" in result["state"]["reply"]


@async_test
async def test_missing_policy_does_not_fallback_to_llm_or_mutation():
    h = harness(request_policy=None)
    result = waiting(await h.graph.run(REQUEST))
    assert result["state"]["last_error"] == "REQUEST_POLICY_UNAVAILABLE"
    assert not h.calls and not h.assessment_model.calls


@async_test
async def test_emergency_policy_bypasses_llm_and_retrieval_alerts_before_profile():
    policy = Policy(emergency=True)

    def override(call, value):
        if call["operation"] == "get_verified_resident_context":
            return {
                "kind": "success",
                "value": {"kind": "missing", "questions": ["Căn hộ nào?"]},
            }

    h = harness(
        assess_model=[RuntimeError("LLM must not run")],
        request_policy=policy,
        override=override,
    )
    result = waiting(await h.graph.run(REQUEST))
    assert [c["operation"] for c in h.calls] == [
        "escalate_emergency",
        "create_ticket_draft",
        "get_verified_resident_context",
    ]
    assert not h.assessment_model.calls and not h.extraction_model.calls
    assert h.options.intake.calls == []
    assert result["state"]["emergency_ack"]["operation_id"]


@async_test
async def test_emergency_existing_ticket_escalates_same_id_and_reassesses():
    policy = Policy(staff_required=True)

    def override(call, value):
        if (
            call["operation"] == "submit_ticket_assessment"
            and policy.values["emergency"]
        ):
            value["triage"].update(
                is_emergency=True, priority="critical", severity="critical"
            )
            return {"kind": "success", "value": value}

    h = harness(
        request_policy=policy,
        model=[
            INFORMATION,
            turn(
                "information",
                title="Rò nước",
                description="Tình trạng nghiêm trọng hơn",
            ),
        ],
        override=override,
    )
    first = waiting(await h.graph.run(REQUEST))
    policy.values["emergency"] = True
    final = waiting(await h.graph.resume(resident_resume(first)))
    assert final["state"]["active_ticket_id"] == first["state"]["active_ticket_id"]
    assert sum(c["operation"] == "create_ticket_draft" for c in h.calls) == 1
    alert = next(c for c in h.calls if c["operation"] == "escalate_emergency")
    assert alert["input"]["ticket_id"] == first["state"]["active_ticket_id"]
    assert final["state"]["triage"]["is_emergency"]


@async_test
async def test_policy_rechecks_llm_emergency_signal():
    class Recheck(Policy):
        async def evaluate_request(self, request):
            if (request.get("assessment") or {}).get("emergency_signals"):
                self.values["emergency"] = True
            return await super().evaluate_request(request)

    h = harness(
        assess_model=[
            json.dumps(
                proposal(action="emergency_handoff", emergency_signals=["tia lửa"])
            )
        ],
        request_policy=Recheck(),
        override=lambda c, v: (
            {"kind": "accepted", "operationId": "alert"}
            if c["operation"] == "escalate_emergency"
            else None
        ),
    )
    result = waiting(await h.graph.run(REQUEST))
    assert result["state"]["pending"]["operation"] == "escalate_emergency"
    assert len(h.calls) == 1


@async_test
async def test_self_help_offer_then_explicit_backend_consent_then_outcome():
    policy = Policy(self_help_allowed=True)
    stage = "offered"

    def override(call, value):
        if call["operation"] == "process_self_help":
            value.update(
                status=stage,
                consent_recorded=stage == "accepted",
                consent_source_message_id=call["input"]["source_message"]["id"],
                recorded=True,
                source_message_id=call["input"]["source_message"]["id"],
            )
            return {"kind": "success", "value": value}

    h = harness(
        assess_model=[json.dumps(proposal(action="retrieve_self_help"))],
        request_policy=policy,
        override=override,
    )
    first = waiting(await h.graph.run(REQUEST))
    assert "Bước thử nghiệm" not in first["state"]["reply"]
    stage = "accepted"
    guided = waiting(
        await h.graph.resume(
            resident_resume(first, {"id": "consent", "text": "Tôi đồng ý"})
        )
    )
    assert "1. Bước thử nghiệm" in guided["state"]["reply"]
    assert guided["state"]["self_help_citations"]
    stage = "succeeded"
    final = await h.graph.resume(
        resident_resume(guided, {"id": "outcome", "text": "Đã xử lý được"})
    )
    assert final["status"] == "completed"
    assert not final["state"].get("active_ticket_id")
    assert all(c["operation"] == "process_self_help" for c in h.calls)


@pytest.mark.parametrize("status", ["declined", "failed", "stopped"])
@async_test
async def test_recorded_self_help_decline_failure_stops_go_to_ticket(status):
    policy = Policy(self_help_allowed=True)
    stage = "offered"

    def override(call, value):
        if call["operation"] == "process_self_help":
            value.update(
                status=stage,
                recorded=True,
                source_message_id=call["input"]["source_message"]["id"],
            )
            return {"kind": "success", "value": value}

    h = harness(
        request_policy=policy,
        assess_model=[json.dumps(proposal(action="retrieve_self_help"))],
        override=override,
    )
    first = waiting(await h.graph.run(REQUEST))
    stage = status
    final = waiting(await h.graph.resume(resident_resume(first)))
    assert final["state"]["active_ticket_id"]
    assert final["state"]["handoff_reason"] == (
        "self_help_declined" if status == "declined" else "self_help_failed"
    )
    assert sum(c["operation"] == "create_ticket_draft" for c in h.calls) == 1


@pytest.mark.parametrize(
    "change",
    [
        lambda v: v.update(consent_recorded=False),
        lambda v: v.update(consent_source_message_id="other"),
        lambda v: v["procedure"].update(approved=False),
        lambda v: v["procedure"].update(eligible=False),
        lambda v: v["procedure"].update(expires_at="2026-09-29T00:00:00Z"),
        lambda v: v["procedure"].update(citations=[]),
        lambda v: v["procedure"].update(stop_conditions=[]),
    ],
)
@async_test
async def test_no_instruction_without_approval_eligibility_consent_and_sources(change):
    def override(call, value):
        if call["operation"] == "process_self_help":
            value.update(
                status="accepted",
                consent_recorded=True,
                consent_source_message_id=call["input"]["source_message"]["id"],
            )
            change(value)
            return {"kind": "success", "value": value}

    h = harness(
        assess_model=[json.dumps(proposal(action="retrieve_self_help"))],
        request_policy=Policy(self_help_allowed=True),
        override=override,
    )
    result = waiting(await h.graph.run(REQUEST))
    assert result["state"]["pending"]["operation"] == "process_self_help"
    assert "Bước thử nghiệm" not in result["state"]["reply"]
    assert not result["state"].get("active_ticket_id")


@async_test
async def test_safety_guidance_remains_visible_when_emergency_ack_unknown():
    guide = {
        "approved": True,
        "answer": "Hướng dẫn an toàn mẫu đã duyệt.",
        "retrievalRunId": "policy-safety",
        "citations": [{"documentId": "safety", "version": "1", "chunkId": "c"}],
    }
    h = harness(
        request_policy=Policy(emergency=True, safety_guidance=guide),
        override=lambda c, v: (
            {
                "kind": "failure",
                "outcome": "unknown",
                "code": "LOST",
                "retryable": False,
            }
            if c["operation"] == "escalate_emergency"
            else None
        ),
    )
    result = waiting(await h.graph.run(REQUEST))
    assert guide["answer"] in result["state"]["reply"]
    assert not h.assessment_model.calls and len(h.calls) == 1


@async_test
async def test_unapproved_safety_text_does_not_block_alert_or_reach_resident():
    h = harness(
        request_policy=Policy(
            emergency=True,
            safety_guidance={"approved": False, "answer": "UNAPPROVED INSTRUCTION"},
        ),
        override=lambda c, v: (
            {"kind": "accepted", "operationId": "alert"}
            if c["operation"] == "escalate_emergency"
            else None
        ),
    )
    result = waiting(await h.graph.run(REQUEST))
    assert result["state"]["pending"]["operation"] == "escalate_emergency"
    assert "UNAPPROVED INSTRUCTION" not in result["state"]["reply"]


@async_test
async def test_existing_ticket_information_is_answered_without_appending_price_query():
    policy = Policy(staff_required=True)
    h = harness(
        request_policy=policy,
        assess_model=[
            json.dumps(proposal("incident", "start_ticket")),
            json.dumps(proposal("information", "retrieve_knowledge")),
        ],
        intake=Intake(
            knowledge={
                "kind": "sufficient",
                "answer": "Nguồn giá mẫu nêu giới hạn áp dụng.",
                "retrievalRunId": "r",
                "citations": [{"documentId": "d", "version": "1", "chunkId": "c"}],
            }
        ),
    )
    first = waiting(await h.graph.run(REQUEST))
    policy.values["staff_required"] = False
    count = len(h.calls)
    result = await h.graph.resume(
        resident_resume(
            first, {"id": "price", "text": "Thay vòi nước thường hết bao nhiêu?"}
        )
    )
    assert result["status"] == "completed"
    assert len(h.calls) == count
    assert result["state"]["active_ticket_id"] == first["state"]["active_ticket_id"]


@async_test
async def test_missing_procedure_does_not_create_repair_ticket():
    h = harness(
        request_policy=Policy(self_help_allowed=True),
        assess_model=[json.dumps(proposal(action="retrieve_self_help"))],
        override=lambda c, v: (
            {
                "kind": "success",
                "value": {
                    "status": "unavailable",
                    "policy_version": c["input"]["policy_version"],
                },
            }
            if c["operation"] == "process_self_help"
            else None
        ),
    )
    result = waiting(await h.graph.run(REQUEST))
    assert not result["state"].get("active_ticket_id")
    assert [c["operation"] for c in h.calls] == ["process_self_help"]


@async_test
async def test_closed_ticket_never_clears_active_id_or_creates_second_ticket():
    policy = Policy(staff_required=True)
    h = harness(
        request_policy=policy, model=[INFORMATION, turn("status"), turn("new_incident")]
    )
    first = waiting(await h.graph.run(REQUEST))
    h.mutable.update(status="closed", confirmed=True)
    terminal = await h.graph.resume(
        resident_resume(first, {"id": "status", "text": "Tiến độ ra sao?"})
    )
    assert terminal["state"]["phase"] == "terminal"
    request = deepcopy(REQUEST)
    request.update(
        operationId="another-message",
        message={"id": "new-incident", "text": "Tôi báo một sự cố khác"},
    )
    result = await h.graph.run(request)
    assert result["state"]["active_ticket_id"] == terminal["state"]["active_ticket_id"]
    assert "cuộc hội thoại mới" in result["state"]["reply"]
    assert sum(c["operation"] == "create_ticket_draft" for c in h.calls) == 1


@async_test
async def test_old_python_topology_is_rejected_without_reset():
    h = harness()
    await h.graph.run(REQUEST)
    state = await h.graph.read(REQUEST["context"])
    state["workflow_version"] = "pd-workflow-python-1"
    await h.graph.compiled.aupdate_state(
        h.graph._config(REQUEST["context"]), {"data": state}
    )
    with pytest.raises(GraphFault, match="WORKFLOW_MIGRATION_REQUIRED"):
        await h.graph.read(REQUEST["context"])


@async_test
async def test_malformed_classification_never_reaches_mutation():
    h = harness(
        request_policy=Policy(),
        assess_model=[
            '{"intent":"incident","proposed_action":"start_ticket","tool":"shell"}'
        ],
    )
    result = waiting(await h.graph.run(REQUEST))
    assert result["state"]["last_error"] == "INVALID_REQUEST_ASSESSMENT"
    assert not h.calls


@async_test
async def test_missing_policy_version_requires_review():
    policy = Policy(policy_version="")
    h = harness(request_policy=policy)
    result = waiting(await h.graph.run(REQUEST))
    assert result["state"]["phase"] == "review"
    assert not h.calls and not h.assessment_model.calls


@async_test
async def test_policy_timeout_cannot_trigger_staff_or_self_help():
    import asyncio

    class SlowPolicy:
        async def evaluate_request(self, request):
            await asyncio.Event().wait()

    h = harness(request_policy=SlowPolicy(), timeout_ms=30)
    result = waiting(await h.graph.run(REQUEST))
    assert result["state"]["last_error"] == "PORT_TIMEOUT"
    assert not h.calls and not h.assessment_model.calls


@async_test
async def test_lost_emergency_ack_reconciles_without_second_alert():
    def override(call, value):
        if call["operation"] == "escalate_emergency":
            return {
                "kind": "failure",
                "code": "LOST",
                "outcome": "unknown",
                "retryable": False,
            }
        if call["operation"] == "submit_ticket_assessment":
            value["triage"].update(
                is_emergency=True, priority="critical", severity="critical"
            )
            return {"kind": "success", "value": value}

    h = harness(request_policy=Policy(emergency=True), override=override)
    first = waiting(await h.graph.run(REQUEST))
    key = first["state"]["pending"]["idempotencyKey"]
    request = {
        "context": REQUEST["context"],
        "operationId": "emergency-reconcile",
        "interruptId": first["interrupts"][0]["id"],
        "source": {
            "kind": "backend",
            "event": {
                "eventId": "alert-result",
                "aggregateVersion": 0,
                "generation": 0,
                "bindingId": REQUEST["context"]["bindingId"],
                "interruptId": first["interrupts"][0]["id"],
            },
        },
    }
    graph = h.factory.create(h.dependencies)
    final = waiting(await graph.resume(request))
    assert final["state"]["phase"] == "waiting_supervisor"
    assert h.reconciliations[0]["idempotencyKey"] == key
    assert sum(c["operation"] == "escalate_emergency" for c in h.calls) == 1
