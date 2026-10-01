import asyncio
from copy import deepcopy

import pytest
from src.graph.budget import CancellationToken
from workflow_fixture import (
    INFORMATION,
    REQUEST,
    async_test,
    event_fixture,
    harness,
    resident_resume,
    set_event,
    turn,
    waiting,
)


@async_test
async def test_lost_draft_response_reconciles_original_key():
    def override(call, value):
        if call["operation"] == "create_ticket_draft":
            return {
                "kind": "failure",
                "code": "LOST",
                "retryable": False,
                "outcome": "unknown",
            }

    h = harness(override=override)
    first = waiting(await h.graph.run(REQUEST))
    assert not first["state"].get("active_ticket_id")
    key = first["state"]["pending"]["idempotencyKey"]
    req = {
        "context": REQUEST["context"],
        "operationId": "reconcile",
        "interruptId": first["interrupts"][0]["id"],
        "source": {
            "kind": "backend",
            "event": {
                "eventId": "event-reconcile",
                "aggregateVersion": 1,
                "generation": 0,
                "bindingId": REQUEST["context"]["bindingId"],
                "interruptId": first["interrupts"][0]["id"],
            },
        },
    }
    recreated = h.factory.create(h.dependencies)
    final = waiting(await recreated.resume(req))
    assert final["state"]["active_ticket_id"] == "ticket-synthetic"
    assert h.reconciliations[0]["idempotencyKey"] == key
    assert sum(c["operation"] == "create_ticket_draft" for c in h.calls) == 1


@async_test
async def test_timeout_keeps_plan_without_mutation_retry():
    async def override(call, value):
        if call["operation"] == "create_ticket_draft":
            await asyncio.Event().wait()

    h = harness(override=override, timeout_ms=30)
    result = waiting(await h.graph.run(REQUEST))
    assert result["state"]["phase"] == "waiting_operation"
    assert result["state"]["pending"]["operation"] == "create_ticket_draft"
    assert len(h.calls) == 1


@async_test
async def test_cancel_mid_mutation_recovers_checkpointed_plan():
    token = CancellationToken()

    async def override(call, value):
        if call["operation"] == "create_ticket_draft":
            token.abort()
            await asyncio.Event().wait()

    h = harness(override=override)
    assert (await h.graph.run({**REQUEST, "signal": token}))["status"] == "cancelled"
    data = await h.graph.read(REQUEST["context"])
    assert data["pending"]["operation"] == "create_ticket_draft"
    recreated = h.factory.create(h.dependencies)
    final = waiting(
        await recreated.recover(
            {"context": REQUEST["context"], "operationId": "recovery"}
        )
    )
    assert final["state"]["active_ticket_id"] == "ticket-synthetic"
    assert len([c for c in h.calls if c["operation"] == "create_ticket_draft"]) == 1


@async_test
async def test_missing_reconciliation_keeps_interrupt_and_key():
    h = harness(
        override=lambda c, v: (
            {"kind": "accepted", "operationId": "op"}
            if c["operation"] == "create_ticket_draft"
            else None
        ),
        reconcile=None,
    )
    first = waiting(await h.graph.run(REQUEST))
    req = {
        "context": REQUEST["context"],
        "operationId": "event",
        "interruptId": first["interrupts"][0]["id"],
        "source": {"kind": "backend", "event": {}},
    }
    assert (await h.graph.resume(req))["code"] == "RECONCILIATION_UNAVAILABLE"
    assert (await h.graph.read(REQUEST["context"]))["pending"] == first["state"][
        "pending"
    ]


@pytest.mark.parametrize(
    "payload",
    [
        turn("information", workspace_id="forged"),
        turn("information", file_ids=["forged"]),
        turn("information", operation="create_ticket_draft"),
        turn(
            "information",
            facts=[
                {
                    "key": "unit",
                    "value": "fake",
                    "source": "staff_verified",
                    "source_message_id": "message-1",
                }
            ],
        ),
        turn(
            "information",
            facts=[
                {
                    "key": "unit",
                    "value": "fake",
                    "source": "customer_report",
                    "source_message_id": "other",
                }
            ],
        ),
    ],
)
@async_test
async def test_injection_cannot_supply_authority(payload):
    h = harness(model=[payload])
    result = waiting(await h.graph.run(REQUEST))
    assert result["state"]["phase"] == "review"
    assert [c["operation"] for c in h.calls] == [
        "create_ticket_draft",
        "get_verified_resident_context",
    ]


@pytest.mark.parametrize(
    "operation,mutate",
    [
        (
            "resolve_management_destination",
            lambda v: v["route"].update(building_id="other"),
        ),
        (
            "resolve_management_destination",
            lambda v: v["route"].update(ticket_version="old"),
        ),
        ("handoff_ticket", lambda v: v.update(persisted=False)),
        ("handoff_ticket", lambda v: v.update(enqueued=False)),
        ("handoff_ticket", lambda v: v.update(correlation_id="other")),
        ("create_ticket_draft", lambda v: v.update(ticket_generation=True)),
    ],
)
@async_test
async def test_backend_output_requires_verified_scope_and_ack(operation, mutate):
    def override(call, value):
        if call["operation"] == operation:
            mutate(value)
            return {"kind": "success", "value": value}

    h = harness(override=override)
    result = waiting(await h.graph.run(REQUEST))
    assert result["state"]["pending"]["operation"] == operation
    assert result["state"]["phase"] == "waiting_operation"
    assert "register_supervisor_wait" not in [c["operation"] for c in h.calls]


@async_test
async def test_scope_change_invalidates_route_and_reloads_profile():
    def override(call, value):
        if call["operation"] == "append_ticket_information":
            value["scope_changed"] = True
            return {"kind": "success", "value": value}

    h = harness(
        model=[INFORMATION, turn("information", description="Cập nhật")],
        override=override,
    )
    first = waiting(await h.graph.run(REQUEST))
    final = waiting(await h.graph.resume(resident_resume(first)))
    ops = [c["operation"] for c in h.calls]
    assert ops.count("get_verified_resident_context") == 2
    assert ops.count("resolve_management_destination") == 2
    assert final["state"]["active_ticket_id"] == first["state"]["active_ticket_id"]


@pytest.mark.parametrize("status", ["conflict", "expired"])
@async_test
async def test_interaction_rejection_requires_review(status):
    def override(call, value):
        if call["operation"] == "respond_supervisor_interaction":
            value["status"] = status
            return {"kind": "success", "value": value}

    h = harness(
        model=[INFORMATION, turn("interaction_answer", answers={"time": "9 giờ"})],
        override=override,
    )
    first = waiting(await h.graph.run(REQUEST))
    event, resume = event_fixture(first, "waiting_for_customer")
    event["interaction_revision"] = 1
    event["payload"]["requested_information"] = {
        "interaction_id": "interaction",
        "questions": [{"field_id": "time", "question": "Giờ nào?", "required": True}],
    }
    set_event(h, event)
    asking = waiting(await h.graph.resume(resume))
    final = waiting(await h.graph.resume(resident_resume(asking)))
    assert final["state"]["phase"] == "review"
    assert "đã được hệ thống tiếp nhận" not in final["state"]["reply"]


@async_test
async def test_unresolved_route_and_repeated_questions_stop():
    h = harness(
        override=lambda c, v: (
            {"kind": "success", "value": {"kind": "unresolved"}}
            if c["operation"] == "resolve_management_destination"
            else None
        )
    )
    result = waiting(await h.graph.run(REQUEST))
    assert result["state"]["last_error"] == "ROUTING_UNRESOLVED"
    h = harness(
        override=lambda c, v: (
            {
                "kind": "success",
                "value": {"kind": "missing", "questions": ["Căn hộ nào?"]},
            }
            if c["operation"] == "get_verified_resident_context"
            else None
        )
    )
    first = waiting(await h.graph.run(REQUEST))
    result = waiting(await h.graph.resume(resident_resume(first)))
    assert result["state"]["last_error"] == "UNANSWERED_FIELDS_REVIEW"


@async_test
async def test_separate_checkpoint_threads_and_cancel_before_start():
    async def resolve_session(context, signal):
        return {
            "channel_id": "channel-synthetic",
            "reception_session_id": "session:" + context["checkpoint"]["threadId"],
        }

    h = harness(resolve_session=resolve_session)
    first = waiting(await h.graph.run(REQUEST))
    other = deepcopy(REQUEST)
    other["context"]["checkpoint"]["threadId"] = "second"
    second = waiting(await h.graph.run(other))
    assert (
        first["state"]["reception_session_id"]
        != second["state"]["reception_session_id"]
    )
    assert (await h.graph.read(REQUEST["context"])) == first["state"]
    assert len(h.calls) == 14
    token = CancellationToken()
    token.abort()
    assert (await h.graph.run({**REQUEST, "signal": token}))["status"] == "cancelled"


@async_test
async def test_buffered_event_requires_lookup_then_interrupt():
    h = harness()
    initial = waiting(await h.graph.run(REQUEST))
    event, _ = event_fixture(initial)
    delivered = False

    def override(call, value):
        nonlocal delivered
        if call["operation"] == "register_supervisor_wait" and not delivered:
            delivered = True
            return {
                "kind": "success",
                "value": {
                    "registered": True,
                    "buffered_event": {
                        "eventId": event["event_id"],
                        "aggregateVersion": event["aggregate_version"],
                    },
                },
            }

    h2 = harness(override=override)
    set_event(h2, event)
    # Draft fixture starts at v1; the buffered notification corresponds to v4.
    h2.mutable["ticket"].update(ticket_version="1", aggregate_version=1)
    result = waiting(await h2.graph.run(REQUEST))
    assert result["state"]["last_event_version"] == event["aggregate_version"]
    assert result["state"]["processed_event_ids"] == [event["event_id"]]


@async_test
async def test_lost_handoff_ack_reconciles_without_second_send():
    def override(call, value):
        if call["operation"] == "handoff_ticket":
            return {
                "kind": "failure",
                "code": "LOST",
                "retryable": False,
                "outcome": "unknown",
            }

    h = harness(override=override)
    first = waiting(await h.graph.run(REQUEST))
    _, request = event_fixture(first)
    result = waiting(await h.graph.resume(request))
    assert result["state"]["ack"]["persisted"]
    assert sum(c["operation"] == "handoff_ticket" for c in h.calls) == 1
    assert h.reconciliations[0]["input"] == first["state"]["pending"]["input"]


@pytest.mark.parametrize(
    "code", ["forbidden", "stale_version", "expired", "validation_error"]
)
@async_test
async def test_not_applied_backend_error_requires_review(code):
    h = harness(
        override=lambda c, v: (
            {
                "kind": "failure",
                "code": code,
                "retryable": False,
                "outcome": "not_applied",
            }
            if c["operation"] == "create_ticket_draft"
            else None
        )
    )
    result = waiting(await h.graph.run(REQUEST))
    assert result["state"]["phase"] == "review"
    assert result["state"]["pending"] is None
    assert len(h.calls) == 1


@async_test
async def test_emergency_cannot_be_downgraded_before_handoff():
    from workflow_fixture import Intake

    h = harness(
        intake=Intake(
            {"kind": "emergency", "policyVersion": "p", "reason": "synthetic"}
        )
    )
    result = waiting(await h.graph.run(REQUEST))
    assert result["state"]["last_error"] == "EMERGENCY_DOWNGRADE_REVIEW"
    assert "handoff_ticket" not in [c["operation"] for c in h.calls]


@pytest.mark.parametrize(
    "field,bad",
    [
        ("tenant_id", "other"),
        ("workspace_id", "other"),
        ("team_id", "other"),
        ("ticket_code", "other"),
        ("correlation_id", "other"),
    ],
)
@async_test
async def test_authorized_event_payload_must_match_scope(field, bad):
    h = harness()
    first = waiting(await h.graph.run(REQUEST))
    event, request = event_fixture(first)
    event["payload"][field] = bad
    set_event(h, event)
    assert (await h.graph.resume(request))["code"] == "EVENT_STALE_OR_MISMATCH"
    state = await h.graph.compiled.aget_state(h.graph._config(REQUEST["context"]))
    assert state.tasks[0].interrupts[0].id == first["interrupts"][0]["id"]
