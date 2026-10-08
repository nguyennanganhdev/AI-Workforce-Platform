from copy import deepcopy

import pytest
from src.graph import WORKFLOW_NODES
from workflow_fixture import (
    INFORMATION,
    REQUEST,
    Intake,
    async_test,
    event_fixture,
    harness,
    resident_resume,
    set_event,
    turn,
    waiting,
)


@async_test
async def test_full_workflow_checkpointed_plans_and_schema():
    h = harness()
    result = waiting(await h.graph.run(REQUEST))
    state = result["state"]
    assert state["phase"] == "waiting_supervisor"
    assert state["active_ticket_id"] == "ticket-synthetic"
    assert [c["operation"] for c in h.calls] == [
        "create_ticket_draft",
        "get_verified_resident_context",
        "update_ticket_incident",
        "submit_ticket_assessment",
        "resolve_management_destination",
        "handoff_ticket",
        "register_supervisor_wait",
    ]
    assert len(h.saved_plans) == 7
    message = h.calls[-2]["input"]["message"]
    assert message["schema_version"] == "1.0"
    assert message["resident"]["resident_name"] == "Cư dân mẫu"
    assert message["facts"][0]["source"] == "customer_report"
    assert set(WORKFLOW_NODES) <= set(h.graph.compiled.get_graph().nodes)
    other = h.factory.create(h.dependencies)
    assert (await other.read(REQUEST["context"]))["active_ticket_id"] == state[
        "active_ticket_id"
    ]


@async_test
async def test_knowledge_has_citations_and_no_ticket():
    intake = Intake(
        {"kind": "knowledge_chat", "policyVersion": "p1", "question": "Bạn hỏi gì?"},
        {
            "kind": "sufficient",
            "answer": "Mở lúc 8 giờ.",
            "retrievalRunId": "retrieval-1",
            "citations": [{"documentId": "doc", "version": "1", "chunkId": "chunk"}],
        },
    )
    h = harness(intake=intake)
    result = await h.graph.run(REQUEST)
    assert result["status"] == "completed"
    assert result["state"]["reply"] == "Mở lúc 8 giờ."
    assert result["state"]["intake"]["citations"]
    assert not h.calls


@pytest.mark.parametrize(
    "intent,operation",
    [
        ("information", "append_ticket_information"),
        ("cancel", "request_ticket_cancellation"),
        ("status", "get_ticket_status"),
        ("new_incident", None),
    ],
)
@async_test
async def test_active_ticket_branches(intent, operation):
    h = harness(model=[INFORMATION, turn(intent, description="Bổ sung")])
    first = waiting(await h.graph.run(REQUEST))
    result = await h.graph.resume(resident_resume(first))
    assert result["status"] in ("completed", "interrupted"), result
    assert result["state"]["active_ticket_id"] == first["state"]["active_ticket_id"]
    ops = [c["operation"] for c in h.calls]
    assert ops.count("create_ticket_draft") == 1
    if operation:
        assert operation in ops
    else:
        assert len(h.calls) == 7
    if intent == "cancel":
        assert result["state"]["phase"] != "terminal"


@async_test
async def test_supervisor_completion_requires_backend_confirmation():
    h = harness()
    result = waiting(await h.graph.run(REQUEST))
    event, resume = event_fixture(result, "completed")
    set_event(h, event)
    unconfirmed = waiting(await h.graph.resume(resume))
    assert unconfirmed["state"]["phase"] != "terminal"
    event, resume = event_fixture(unconfirmed, "completed", "event-2")
    set_event(h, event)
    h.mutable.update(status="closed", confirmed=True)
    confirmed = await h.graph.resume(resume)
    assert confirmed["status"] == "completed", confirmed
    assert confirmed["state"]["phase"] == "terminal"


@async_test
async def test_pending_interaction_answers_use_version():
    h = harness(
        model=[INFORMATION, turn("information", answers={"access_time": "9 giờ"})]
    )
    first = waiting(await h.graph.run(REQUEST))
    event, resume = event_fixture(first, "waiting_for_customer")
    event["interaction_revision"] = 2
    event["payload"]["requested_information"] = {
        "interaction_id": "interaction-test",
        "questions": [
            {
                "field_id": "access_time",
                "question": "Khi nào có thể vào căn hộ?",
                "required": True,
            }
        ],
    }
    set_event(h, event)
    asking = waiting(await h.graph.resume(resume))
    result = waiting(await h.graph.resume(resident_resume(asking)))
    call = next(
        c for c in h.calls if c["operation"] == "respond_supervisor_interaction"
    )
    assert call["input"]["interaction_revision"] == 2
    assert call["input"]["answers"] == {"access_time": "9 giờ"}
    assert result["state"]["pending_interaction"] is None


@pytest.mark.parametrize(
    "field,bad",
    [
        ("bindingId", "other"),
        ("ticketId", "other"),
        ("generation", 1),
        ("aggregateVersion", 0),
    ],
)
@async_test
async def test_invalid_notification_does_not_consume_interrupt(field, bad):
    h = harness()
    first = waiting(await h.graph.run(REQUEST))
    _, resume = event_fixture(first)
    resume["source"]["event"][field] = bad
    result = await h.graph.resume(resume)
    assert result["status"] == "failed"
    state = await h.graph.compiled.aget_state(h.graph._config(REQUEST["context"]))
    assert state.tasks[0].interrupts[0].id == first["interrupts"][0]["id"]
    assert len(h.calls) == 7


@async_test
async def test_duplicate_and_stale_events():
    h = harness()
    first = waiting(await h.graph.run(REQUEST))
    event, resume = event_fixture(first)
    set_event(h, event)
    current = waiting(await h.graph.resume(resume))
    resume["interruptId"] = current["interrupts"][0]["id"]
    resume["source"]["event"]["interruptId"] = resume["interruptId"]
    assert (await h.graph.resume(resume))["code"] == "EVENT_STALE_OR_MISMATCH"


@async_test
async def test_context_and_python_checkpoint_isolation():
    h = harness()
    await h.graph.run(REQUEST)
    wrong = deepcopy(REQUEST["context"])
    wrong["tenantId"] = "other"
    with pytest.raises(Exception, match="CONTEXT_MISMATCH"):
        await h.graph.read(wrong)
    saved = await h.graph.read(REQUEST["context"])
    saved["workflow_version"] = "pd-workflow-1"
    await h.graph.compiled.aupdate_state(
        h.graph._config(REQUEST["context"]), {"data": saved}
    )
    with pytest.raises(Exception, match="WORKFLOW_MIGRATION_REQUIRED"):
        await h.graph.read(REQUEST["context"])


@async_test
async def test_stream_and_no_silent_restart():
    h = harness()
    events = [e async for e in h.graph.stream(REQUEST)]
    assert [e["type"] for e in events] == ["text_delta", "result"]
    assert (await h.graph.run(REQUEST))["code"] == "RESUME_REQUIRED"


@async_test
async def test_repeated_resident_delivery_is_not_reapplied():
    h = harness(model=[INFORMATION, turn("information", description="Bổ sung")])
    first = waiting(await h.graph.run(REQUEST))
    req = resident_resume(first)
    current = waiting(await h.graph.resume(req))
    count = len(h.calls)
    req["interruptId"] = current["interrupts"][0]["id"]
    duplicate = await h.graph.resume(req)
    assert duplicate["state"]["reply"] == ""
    assert len(h.calls) == count
    req["source"]["message"]["text"] = "changed"
    assert (await h.graph.resume(req))["code"] == "OPERATION_PAYLOAD_CONFLICT"
