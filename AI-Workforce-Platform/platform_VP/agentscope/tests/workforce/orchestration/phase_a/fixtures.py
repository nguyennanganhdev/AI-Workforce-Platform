# -*- coding: utf-8 -*-
"""Deterministic review samples, not fake service implementations."""

from copy import deepcopy


NOW = "2026-10-10T09:00:00Z"


def phase_a_samples() -> dict:
    scope = dict(
        tenant_id="tenant-1",
        domain_id="domain-1",
        area_id="area-1",
        manager_account_id="manager-1",
    )
    audience = dict(
        partner_client_id="partner-1",
        external_user_id="user-1",
        external_conversation_id="chat-A",
        external_ticket_id="ticket-A",
    )
    workflow = dict(
        workflow_id="workflow-A",
        scope=scope,
        audience=audience,
        conversation_id="conversation-A",
        ticket_id=None,
        route_id="route-1",
        route_revision=1,
        state="active",
        revision=1,
        group_id="group-A",
        checkpoint_ref="checkpoint-A-1",
        version_pins=["agent-version-1"],
        pending_waits=[],
        last_applied_event_id=None,
        created_at=NOW,
        updated_at=NOW,
    )
    binding = dict(
        scope=scope,
        **audience,
        workflow_id="workflow-A",
        conversation_id="conversation-A",
        group_id="group-A",
        route_id="route-1",
        route_revision=1,
        status="active",
        created_at=NOW,
        updated_at=NOW,
    )
    protocol = dict(
        protocol_id="repair",
        protocol_version="1",
        schema_hash="sha256:fixture",
        tool_version_id="tool-version-1",
        provider_integration_id="provider-1",
        capabilities=["create", "receive_status"],
    )
    trigger = dict(
        trigger_id="trigger-A-1",
        workflow_id="workflow-A",
        cause=dict(kind="request", request_id="request-A"),
        expected_state_revision=1,
    )
    checkpoint = dict(
        schema_version="phh-phase-a-1",
        workflow_id="workflow-A",
        state_revision=1,
        session_refs=["session-A"],
        agent_version_pins=[
            dict(agent_id="agent-1", version_id="agent-version-1")
        ],
        protocol_pins=[protocol],
        shared_state_ref="state-A-1",
        pending_task_ids=[],
        pending_question_ids=[],
        pending_approval_ids=[],
        operation_refs=["operation-A"],
        last_processed_causes=[],
        used_budget=dict(
            model_turns=0, tool_calls=0, input_tokens=0, output_tokens=0
        ),
    )
    result = dict(
        messages=[
            dict(
                message_id="message-A",
                workflow_id="workflow-A",
                sender="assistant",
                text="Đã tiếp nhận yêu cầu.",
                created_at=NOW,
            )
        ],
        data={},
    )
    event = dict(
        schema_version="1",
        event_id="event-A-1",
        sequence=1,
        event_type="assistant.message",
        occurred_at=NOW,
        recorded_at=NOW,
        conversation_id="conversation-A",
        external_ticket_id="ticket-A",
        external_conversation_id="chat-A",
        external_user_id="user-1",
        workflow_id="workflow-A",
        ticket_id=None,
        causation_id="request-A",
        payload=dict(message_id="message-A", text="Đã tiếp nhận yêu cầu."),
    )
    receipt = dict(
        request_id="request-A",
        request_status="completed",
        external_ticket_id="ticket-A",
        conversation_id="conversation-A",
        workflow_id="workflow-A",
        ticket_id=None,
        workflow_state="awaiting_user",
        next_action="submit_reply",
        workflow_revision=1,
        result=result,
        error=None,
        accepted_at=NOW,
        completed_at=NOW,
        status_url="/workforce/v1/partner/requests/request-A",
        conversation_url="/workforce/v1/partner/conversations/conversation-A",
        event_stream_url=(
            "/workforce/v1/partner/conversations/conversation-A/events"
        ),
    )
    candidate = deepcopy(checkpoint)
    candidate.update(
        state_revision=2,
        shared_state_ref="state-A-2",
        last_processed_causes=[deepcopy(trigger["cause"])],
    )
    samples = {
        "WorkflowRecord": workflow,
        "TicketConversationBinding": binding,
        "ConversationEvent": event,
        "EventHistoryPage": dict(
            items=[event], next_cursor="event-A-1", has_more=False
        ),
        "InboundReceipt": receipt,
        "PartnerRequestEnvelope": dict(
            schema_version="1",
            command_type="start_workflow",
            external_request_id="external-request-A",
            external_management_ref="management-1",
            external_user_id="user-1",
            external_ticket_id="ticket-A",
            external_conversation_id="chat-A",
            message=dict(type="text", text="Cần hỗ trợ."),
        ),
        "CloseWorkflowCommand": dict(
            schema_version="1",
            external_request_id="close-A",
            external_user_id="user-1",
            external_ticket_id="ticket-A",
            external_conversation_id="chat-A",
            expected_revision=1,
            reason="Đã hoàn tất",
            stop_tracking_only=False,
        ),
        "RequestResult": result,
        "AsyncProtocolSnapshotRef": protocol,
        "WorkflowTrigger": trigger,
        "WorkflowCheckpoint": checkpoint,
        "CommandClaimResult": dict(
            request_id="request-A",
            is_new=False,
            status="completed",
            result=result,
        ),
        "PinnedRuntimeContext": dict(workflow=workflow, checkpoint=checkpoint),
        "RuntimeTurnResult": dict(
            trigger_id="trigger-A-1",
            expected_state_revision=1,
            checkpoint=candidate,
            result=result,
        ),
    }
    payloads = {
        "request.accepted": dict(request_id="request-A"),
        "workflow.status_changed": dict(
            state="waiting_external_event", revision=2
        ),
        "ticket.created": dict(ticket_id="legacy-ticket-A", status="open"),
        "ticket.status_changed": dict(
            status="in_progress", public_details="Đang xử lý"
        ),
        "assistant.message": deepcopy(event["payload"]),
        "approval.required": dict(
            approval_id="approval-A",
            summary="Xác nhận chi phí",
            expires_at=NOW,
        ),
        "approval.resolved": dict(approval_id="approval-A", status="approved"),
        "operation.status_changed": dict(
            operation_type="hotel_booking",
            status_schema="hotel_booking.v1",
            status="confirmed",
            external_reference="BOOKING-A",
        ),
        "workflow.awaiting_user": dict(
            reason="Cần thêm thông tin", revision=2
        ),
        "workflow.needs_attention": dict(
            reason_code="PROVIDER_STATUS_UNKNOWN"
        ),
        "workflow.closed": dict(
            state="closed", revision=3, reason="Đã hoàn tất", closed_at=NOW
        ),
    }
    triggers = [deepcopy(trigger)]
    for index, cause in enumerate(
        [
            dict(
                kind="approval",
                request_id="approval-request-A",
                approval_id="approval-A",
            ),
            dict(
                kind="external_event",
                cause_event_id="inbox-A",
                operation_id="operation-A",
            ),
            dict(kind="timer", timer_id="timer-A"),
        ],
        2,
    ):
        triggers.append(
            dict(
                trigger_id=f"trigger-A-{index}",
                workflow_id="workflow-A",
                cause=cause,
                expected_state_revision=1,
            )
        )
    patterns = {}
    for name, state, action in (
        ("response_only", "closed", "none"),
        ("interactive", "awaiting_user", "submit_reply"),
        ("external_tracking", "waiting_external_event", "watch_events"),
    ):
        patterns[name] = deepcopy(receipt)
        patterns[name].update(workflow_state=state, next_action=action)
    ticket_b = deepcopy(samples["PinnedRuntimeContext"])
    ticket_b["workflow"].update(
        workflow_id="workflow-B",
        conversation_id="conversation-B",
        group_id="group-B",
        checkpoint_ref="checkpoint-B-1",
    )
    ticket_b["workflow"]["audience"].update(
        external_conversation_id="chat-B", external_ticket_id="ticket-B"
    )
    ticket_b["checkpoint"].update(
        workflow_id="workflow-B",
        session_refs=["session-B"],
        shared_state_ref="state-B-1",
        operation_refs=["operation-B"],
    )
    return dict(
        models=samples,
        public_payloads=payloads,
        triggers=triggers,
        patterns=patterns,
        ticket_contexts=[deepcopy(samples["PinnedRuntimeContext"]), ticket_b],
    )
