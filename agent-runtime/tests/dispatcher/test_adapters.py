"""Unit tests for Dispatcher adapters (GroupChat integration)."""

from __future__ import annotations

import pytest

from dispatcher.adapters.groupchat_adapter import (
    build_groupchat_context,
    map_role,
    to_open_room_payload,
)
from dispatcher.contracts import (
    DecisionReasoning,
    DispatcherDecision,
    IncidentContext,
    ReportContext,
    SelectedAgent,
    SlaBind,
    TicketClassification,
    TicketReport,
    TurnPolicy,
)


def _make_ticket_and_decision() -> tuple[TicketReport, DispatcherDecision]:
    report: ReportContext = {
        "text": "Bị chập điện tầng 12",
        "attachments": [],
        "facts": {"note": "Tòa S1"},
        "resident_mentioned_agents": None,
    }
    incident: IncidentContext = {
        "incident_id": "inc-01",
        "human_reported_severity": None,
        "is_safety_hazard": False,
        "is_recurring": False,
        "property_tier": "STANDARD",
    }
    ticket: TicketReport = {
        "version": 1,
        "ticket_id": "TK-100",
        "tenant_id": "tenant-01",
        "correlation_id": "corr-01",
        "trace_id": "trace-01",
        "subject": {
            "namespace": "vinhomes-p12",
            "subject_type": "apartment",
            "subject_id": "ws-p12",
        },
        "report": report,
        "incident": incident,
        "sla_policies": [],
        "eligible_agents": [],
    }
    sla: SlaBind = {
        "policy_id": "sla-01",
        "severity": "HIGH",
        "response_minutes": 15,
        "resolution_minutes": 120,
        "started_at": "2026-09-30T00:00:00Z",
    }
    selected_agents: list[SelectedAgent] = [
        {
            "agent_version_id": "agent-coord-01",
            "role": "COORDINATOR",
            "capability_scope": {"capabilities": ["GENERAL"]},
            "selection_reason": "Coordinator assigned",
        },
        {
            "agent_version_id": "agent-elec-01",
            "role": "SPECIALIST",
            "capability_scope": {"capabilities": ["ELECTRICAL"]},
            "selection_reason": "Specialist matched",
        },
    ]
    turn_policy: TurnPolicy = {
        "purpose": "TRIAGE",
        "max_turns": 20,
        "max_consecutive_turns": 2,
        "timeout_seconds": 600.0,
        "max_tool_calls": 30,
        "speaker_order": ["agent-coord-01", "agent-elec-01"],
        "strategy": "ROSTER_ORDER",
        "allow_resident_agent_request": False,
    }
    classification: TicketClassification = {
        "category": "ELECTRICAL",
        "severity": "HIGH",
        "urgency": "HIGH",
        "complexity": "MODERATE",
        "confidence": 0.95,
        "method": "LLM",
    }
    reasoning: DecisionReasoning = {
        "classification_evidence": ["Chập điện"],
        "sla_match_evidence": ["Matched sla-01"],
        "agent_selection_evidence": ["Selected 2 agents"],
        "warnings": [],
    }
    decision: DispatcherDecision = {
        "version": 1,
        "decision_id": "dec-01",
        "ticket_id": "TK-100",
        "correlation_id": "corr-01",
        "classification": classification,
        "selected_agents": selected_agents,
        "turn_policy": turn_policy,
        "sla": sla,
        "requires_approval": False,
        "approval_reason": None,
        "prediction_signals": {
            "model_version": "v1.0",
            "predicted_urgency": "HIGH",
            "urgency_confidence": 0.9,
            "predicted_resolution_hours": 2.5,
            "resolution_confidence": 0.85,
            "predicted_complexity": "MODERATE",
            "sla_breach_risk": 0.25,
        },
        "reasoning": reasoning,
        "groupchat_context": None,
    }
    return ticket, decision


def test_map_role() -> None:
    assert map_role("COORDINATOR") == "coordinator"
    assert map_role("SPECIALIST") == "specialist"
    assert map_role("REVIEWER") == "reviewer"
    assert map_role("CUSTOM") == "custom"


def test_build_groupchat_context() -> None:
    ticket, decision = _make_ticket_and_decision()
    ctx = build_groupchat_context(ticket, decision)
    assert ctx["tenant_id"] == "tenant-01"
    assert ctx["domain_id"] == "vinhomes-p12"
    assert ctx["workspace_id"] == "ws-p12"
    assert ctx["ticket_id"] == "TK-100"
    assert ctx["ticket_generation"] == 0
    assert ctx["binding_id"] == "dec-01"


def test_to_open_room_payload() -> None:
    ticket, decision = _make_ticket_and_decision()
    result = to_open_room_payload(ticket, decision)

    assert "context" in result
    assert "payload" in result
    payload = result["payload"]

    assert payload["groupchat_version_id"] == "v2"
    assert len(payload["participants"]) == 2
    assert payload["participants"][0]["role"] == "coordinator"
    assert payload["participants"][0]["agent_version_id"] == "agent-coord-01"
    assert payload["turn_policy"]["max_turns"] == 20
    assert payload["turn_policy"]["max_consecutive_turns"] == 2
    assert payload["turn_policy"]["timeout_seconds"] == 600.0
