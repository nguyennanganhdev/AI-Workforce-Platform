"""Tests for the deterministic rules engine."""

from __future__ import annotations

import pytest

from dispatcher.contracts import TicketClassification
from dispatcher.errors import DispatcherException
from dispatcher.rules import (
    build_selected_agents,
    check_approval_required,
    filter_eligible_agents,
    resolve_sla,
    validate_resident_agent_request,
)
from tests.dispatcher.fixtures import make_agent, make_incident, make_sla_policy


# ---------------------------------------------------------------------------
# SLA resolution
# ---------------------------------------------------------------------------

class TestResolveSla:
    def test_exact_match_category_and_severity(self) -> None:
        classification = _classification(category="PLUMBING", severity="HIGH")
        policies = [
            make_sla_policy(category="PLUMBING", severity="HIGH", response_minutes=30, resolution_minutes=240),
            make_sla_policy(category="ELECTRICAL", severity="HIGH", response_minutes=30, resolution_minutes=240),
        ]
        sla = resolve_sla(classification, policies, "TK-1", "corr-1", "2026-01-01T00:00:00Z")
        assert sla["severity"] == "HIGH"
        assert sla["response_minutes"] == 30
        assert sla["resolution_minutes"] == 240

    def test_multiple_exact_picks_strictest(self) -> None:
        classification = _classification(category="PLUMBING", severity="MEDIUM")
        policies = [
            make_sla_policy(category="PLUMBING", severity="MEDIUM", response_minutes=120, resolution_minutes=960),
            make_sla_policy(category="PLUMBING", severity="MEDIUM", response_minutes=60, resolution_minutes=480),
        ]
        sla = resolve_sla(classification, policies, "TK-1", "corr-1", "2026-01-01T00:00:00Z")
        assert sla["resolution_minutes"] == 480  # Strictest

    def test_fallback_severity_only(self) -> None:
        classification = _classification(category="OTHER", severity="LOW")
        policies = [
            make_sla_policy(category="PLUMBING", severity="LOW", response_minutes=240, resolution_minutes=1440),
        ]
        sla = resolve_sla(classification, policies, "TK-1", "corr-1", "2026-01-01T00:00:00Z")
        assert sla["severity"] == "LOW"

    def test_no_match_raises(self) -> None:
        classification = _classification(category="PLUMBING", severity="CRITICAL")
        policies = [
            make_sla_policy(category="PLUMBING", severity="LOW"),
        ]
        with pytest.raises(DispatcherException) as exc_info:
            resolve_sla(classification, policies, "TK-1", "corr-1", "2026-01-01T00:00:00Z")
        assert exc_info.value.error["error_code"] == "SLA_POLICY_NOT_FOUND"


# ---------------------------------------------------------------------------
# Agent eligibility
# ---------------------------------------------------------------------------

class TestFilterEligibleAgents:
    def test_keeps_published_agents(self) -> None:
        agents = [
            make_agent(version_id="v1", status="PUBLISHED"),
            make_agent(version_id="v2", status="DRAFT"),
            make_agent(version_id="v3", status="PUBLISHED"),
        ]
        result = filter_eligible_agents(agents, "TK-1", "corr-1")
        assert len(result) == 2
        assert all(a["status"] == "PUBLISHED" for a in result)

    def test_no_published_raises(self) -> None:
        agents = [make_agent(version_id="v1", status="DRAFT")]
        with pytest.raises(DispatcherException) as exc_info:
            filter_eligible_agents(agents, "TK-1", "corr-1")
        assert exc_info.value.error["error_code"] == "NO_ELIGIBLE_AGENTS"


# ---------------------------------------------------------------------------
# @agent validation
# ---------------------------------------------------------------------------

class TestResidentAgentRequest:
    def test_valid_request(self) -> None:
        eligible = [make_agent(version_id="v1"), make_agent(version_id="v2")]
        valid, warnings = validate_resident_agent_request(["v1"], eligible)
        assert valid == ["v1"]
        assert warnings == []

    def test_invalid_request_produces_warning(self) -> None:
        eligible = [make_agent(version_id="v1")]
        valid, warnings = validate_resident_agent_request(["v999"], eligible)
        assert valid == []
        assert len(warnings) == 1
        assert "v999" in warnings[0]

    def test_none_mentioned(self) -> None:
        eligible = [make_agent(version_id="v1")]
        valid, warnings = validate_resident_agent_request(None, eligible)
        assert valid == []
        assert warnings == []


# ---------------------------------------------------------------------------
# Approval rules
# ---------------------------------------------------------------------------

class TestApprovalRequired:
    def test_high_severity_requires_approval(self) -> None:
        classification = _classification(severity="HIGH")
        required, reason = check_approval_required(classification, make_incident())
        assert required is True
        assert reason is not None

    def test_critical_severity_requires_approval(self) -> None:
        classification = _classification(severity="CRITICAL")
        required, _ = check_approval_required(classification, make_incident())
        assert required is True

    def test_low_severity_no_approval(self) -> None:
        classification = _classification(severity="LOW")
        required, reason = check_approval_required(classification, make_incident())
        assert required is False
        assert reason is None

    def test_safety_category_requires_approval(self) -> None:
        classification = _classification(category="FIRE_SAFETY", severity="MEDIUM")
        required, reason = check_approval_required(classification, make_incident())
        assert required is True
        assert "safety" in reason.lower()


# ---------------------------------------------------------------------------
# Agent selection
# ---------------------------------------------------------------------------

class TestBuildSelectedAgents:
    def test_includes_coordinator(self) -> None:
        agents = [
            make_agent(version_id="coord-1", role="COORDINATOR", capabilities=["orchestration"]),
            make_agent(version_id="spec-1", role="SPECIALIST", capabilities=["plumbing"]),
        ]
        classification = _classification(category="PLUMBING", severity="MEDIUM")
        result = build_selected_agents(agents, classification, [])
        roles = [a["role"] for a in result]
        assert "COORDINATOR" in roles

    def test_includes_specialist_matching_category(self) -> None:
        agents = [
            make_agent(version_id="spec-plumb", role="SPECIALIST", capabilities=["plumbing"]),
            make_agent(version_id="spec-elec", role="SPECIALIST", capabilities=["electrical"]),
        ]
        classification = _classification(category="PLUMBING")
        result = build_selected_agents(agents, classification, [])
        ids = [a["agent_version_id"] for a in result]
        assert "spec-plumb" in ids

    def test_includes_reviewer_for_high_severity(self) -> None:
        agents = [
            make_agent(version_id="spec-1", role="SPECIALIST", capabilities=["plumbing"]),
            make_agent(version_id="rev-1", role="REVIEWER", capabilities=["quality"]),
        ]
        classification = _classification(severity="HIGH")
        result = build_selected_agents(agents, classification, [])
        roles = [a["role"] for a in result]
        assert "REVIEWER" in roles

    def test_no_reviewer_for_low_severity(self) -> None:
        agents = [
            make_agent(version_id="spec-1", role="SPECIALIST", capabilities=["plumbing"]),
            make_agent(version_id="rev-1", role="REVIEWER", capabilities=["quality"]),
        ]
        classification = _classification(severity="LOW")
        result = build_selected_agents(agents, classification, [])
        roles = [a["role"] for a in result]
        assert "REVIEWER" not in roles

    def test_includes_resident_requested_agent(self) -> None:
        agents = [
            make_agent(version_id="spec-1", role="SPECIALIST", capabilities=["plumbing"]),
            make_agent(version_id="spec-2", role="SPECIALIST", capabilities=["electrical"]),
        ]
        classification = _classification(category="PLUMBING")
        result = build_selected_agents(agents, classification, ["spec-2"])
        ids = [a["agent_version_id"] for a in result]
        assert "spec-2" in ids


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _classification(
    *,
    category: str = "PLUMBING",
    severity: str = "MEDIUM",
    urgency: str = "MEDIUM",
    complexity: str = "MODERATE",
) -> TicketClassification:
    return TicketClassification(
        category=category,
        severity=severity,  # type: ignore[arg-type]
        urgency=urgency,  # type: ignore[arg-type]
        complexity=complexity,  # type: ignore[arg-type]
        confidence=0.85,
        method="LLM",
    )
