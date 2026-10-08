"""Synthetic PH16 consumer fixtures; not claims about the real backend API."""

from copy import deepcopy

CONTEXT = {
    "tenantId": "tenant-synthetic",
    "principalId": "principal-synthetic",
    "bindingId": "binding-synthetic",
    "runId": "run-synthetic",
    "requestId": "request-synthetic",
}
REF = {"ticket_id": "ticket-synthetic", "ticket_generation": 0, "ticket_version": "v1"}
TICKET = {
    **REF,
    "ticket_code": "SYN-1",
    "aggregate_version": 1,
    "created_at": "2026-10-01T00:00:00Z",
}
FACT = {
    "key": "location",
    "value": "bếp mẫu",
    "source": "customer_report",
    "source_message_id": "message-synthetic",
}
INCIDENT = {
    "title": "Rò nước",
    "description": "Vòi bếp mẫu bị rò.",
    "facts": [FACT],
    "file_ids": ["file-1", "file-2"],
}
MESSAGE = {
    "id": "message-synthetic",
    "text": "Cư dân bổ sung thông tin mẫu.",
    "fileIds": [],
}
PROFILE = {
    "resident_id": "resident-synthetic",
    "resident_name": "Cư dân mẫu",
    "phone_number": "synthetic-phone",
    "unit_id": "unit-synthetic",
    "unit_number": "Căn mẫu",
    "building_id": "building-synthetic",
    "building_code": "TEST",
    "building_name": "Tòa mẫu",
    "domain_id": "domain-synthetic",
    "domain_name": "Domain mẫu",
    "location_scope_id": "scope-synthetic",
}
TRIAGE = {
    "status": "applied",
    "policy_version": "policy-v1",
    "triage_decision_id": "triage-synthetic",
    "request_kind": "incident",
    "priority": "normal",
    "severity": "minor",
    "is_emergency": False,
}
ROUTE = {
    "destination_id": "destination-synthetic",
    "workspace_id": "workspace-synthetic",
    "team_id": "team-synthetic",
    "route_revision": 1,
    "coordination_binding_id": "coordination-synthetic",
    "building_id": "building-synthetic",
    "domain_id": "domain-synthetic",
    "ticket_version": "v1",
}
EVENT = {
    "event_id": "event-synthetic",
    "aggregate_version": 1,
    "binding_id": CONTEXT["bindingId"],
    "payload": {
        **REF,
        "schema_version": "2.0",
        "message_id": "supervisor-message-synthetic",
        "correlation_id": "correlation-synthetic",
        "sent_at": "2026-10-01T00:01:00+07:00",
        "message_type": "in_progress",
        "message": "Đang xử lý mẫu.",
        "tenant_id": CONTEXT["tenantId"],
        "workspace_id": ROUTE["workspace_id"],
        "team_id": ROUTE["team_id"],
        "ticket_code": "SYN-1",
        "supervisor_run_id": "supervisor-run-synthetic",
    },
}
PROCEDURE = {
    "approved": True,
    "eligible": True,
    "policy_version": "policy-v1",
    "version": "procedure-v1",
    "expires_at": "2099-10-01T00:00:00Z",
    "steps": ["Bước thử nghiệm đã duyệt."],
    "stop_conditions": ["Dừng khi có dấu hiệu nguy hiểm."],
    "retrievalRunId": "retrieval-synthetic",
    "citations": [
        {
            "documentId": "document-synthetic",
            "version": "1",
            "chunkId": "chunk-synthetic",
        }
    ],
}
APPEND = {
    **REF,
    "source_message_id": MESSAGE["id"],
    "message": MESSAGE["text"],
    "facts": [FACT],
    "file_ids": ["file-1"],
}
CASES = {
    "create_ticket_draft": (
        {"channel_id": "channel-synthetic", "handoff_reason": "needs_staff"},
        TICKET,
    ),
    "get_verified_resident_context": (
        {**REF, "resident_response": MESSAGE},
        {"kind": "verified", "profile": PROFILE},
    ),
    "update_ticket_incident": (
        {**REF, "incident": INCIDENT},
        {"ticket": TICKET, "incident": INCIDENT, "missing_fields": []},
    ),
    "submit_ticket_assessment": (
        {**REF, "facts": [FACT]},
        {"ticket": TICKET, "triage": TRIAGE},
    ),
    "resolve_management_destination": (REF, {"kind": "resolved", "route": ROUTE}),
    "handoff_ticket": (
        {
            **REF,
            "correlation_id": "correlation-synthetic",
            "handoff_reason": "needs_staff",
        },
        {
            **REF,
            "schema_version": "2.0",
            "persisted": True,
            "enqueued": True,
            "correlation_id": "correlation-synthetic",
            "operation_id": "handoff-synthetic",
        },
    ),
    "register_supervisor_wait": (
        {**REF, "correlation_id": "correlation-synthetic"},
        {**REF, "registered": True, "correlation_id": "correlation-synthetic"},
    ),
    "get_supervisor_event": (
        {
            **REF,
            "event_id": EVENT["event_id"],
            "aggregate_version": 1,
            "correlation_id": "correlation-synthetic",
        },
        EVENT,
    ),
    "append_ticket_information": (
        APPEND,
        {
            "ticket": TICKET,
            "delivered": True,
            "scope_changed": False,
            "linked_file_ids": ["file-1"],
        },
    ),
    "respond_supervisor_interaction": (
        {**APPEND, "message_type": "information_provided"},
        {"ticket": TICKET, "status": "accepted", "linked_file_ids": ["file-1"]},
    ),
    "request_ticket_cancellation": (
        {**REF, "reason": "Yêu cầu hủy mẫu.", "source_message_id": MESSAGE["id"]},
        {"ticket": TICKET, "status": "accepted"},
    ),
    "get_ticket_status": (
        REF,
        {
            "ticket": TICKET,
            "status": "in_progress",
            "completion_confirmed": False,
            "scope_changed": False,
        },
    ),
    "process_self_help": (
        {
            "channel_id": "channel-synthetic",
            "reception_session_id": "session-synthetic",
            "source_message": MESSAGE,
            "policy_version": "policy-v1",
            "attempt": None,
        },
        {
            "status": "offered",
            "policy_version": "policy-v1",
            "attempt_id": "attempt-synthetic",
            "procedure": PROCEDURE,
        },
    ),
    "escalate_emergency": (
        {
            "channel_id": "channel-synthetic",
            "reception_session_id": "session-synthetic",
            "source_message": MESSAGE,
            "policy_version": "policy-v1",
        },
        {
            "persisted": True,
            "enqueued": True,
            "operation_id": "emergency-synthetic",
            "policy_version": "policy-v1",
        },
    ),
}


def case(operation):
    value, output = CASES[operation]
    return deepcopy(value), deepcopy(output)


def request(operation, value=None):
    return {
        "operation": operation,
        "input": case(operation)[0] if value is None else value,
        "context": deepcopy(CONTEXT),
        "idempotencyKey": "stable-key",
    }


def success(value):
    return {"kind": "success", "value": value}
