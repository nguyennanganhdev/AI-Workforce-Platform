"""Test fixtures shared across dispatcher tests."""

from __future__ import annotations

from dispatcher.contracts import (
    AttachmentRef,
    DomainSubjectRefPy,
    EligibleAgentRef,
    IncidentContext,
    ReportContext,
    SlaPolicyRef,
    TicketReport,
)


def make_report(
    text: str = "Water leaking from ceiling in apartment 1205",
    *,
    facts: dict | None = None,
    attachments: list[AttachmentRef] | None = None,
    mentioned_agents: list[str] | None = None,
) -> ReportContext:
    return ReportContext(
        text=text,
        facts=facts or {"leak_location": "ceiling", "apartment": "1205"},
        attachments=attachments or [
            AttachmentRef(id="att-1", media_type="image/jpeg", file_object_id="file-1"),
        ],
        resident_mentioned_agents=mentioned_agents,
    )


def make_incident(
    *,
    category: str = "PLUMBING",
    severity: str | None = None,
    status: str = "REPORTED",
    location_type: str = "APARTMENT",
) -> IncidentContext:
    return IncidentContext(
        id="inc-001",
        project_id="proj-001",
        category=category,
        severity=severity,
        status=status,
        location_type=location_type,
    )


def make_sla_policy(
    *,
    category: str = "PLUMBING",
    severity: str = "MEDIUM",
    response_minutes: int = 60,
    resolution_minutes: int = 480,
) -> SlaPolicyRef:
    return SlaPolicyRef(
        policy_id=f"sla-{category}-{severity}".lower(),
        code=f"{category}_{severity}",
        category=category,
        severity=severity,  # type: ignore[arg-type]
        response_minutes=response_minutes,
        resolution_minutes=resolution_minutes,
        clock_type="ELAPSED",
    )


def make_agent(
    *,
    agent_id: str = "agent-001",
    version_id: str = "ver-001",
    role: str = "SPECIALIST",
    capabilities: list[str] | None = None,
    status: str = "PUBLISHED",
) -> EligibleAgentRef:
    return EligibleAgentRef(
        agent_id=agent_id,
        agent_version_id=version_id,
        role=role,  # type: ignore[arg-type]
        capabilities=capabilities or ["plumbing", "water"],
        status=status,
    )


def make_ticket(
    *,
    report: ReportContext | None = None,
    incident: IncidentContext | None = None,
    sla_policies: list[SlaPolicyRef] | None = None,
    eligible_agents: list[EligibleAgentRef] | None = None,
) -> TicketReport:
    return TicketReport(
        version=1,
        ticket_id="TK-123",
        tenant_id="tenant-001",
        correlation_id="corr-001",
        trace_id="trace-001",
        incident=incident or make_incident(),
        report=report or make_report(),
        sla_policies=sla_policies or [
            make_sla_policy(severity="LOW", response_minutes=240, resolution_minutes=1440),
            make_sla_policy(severity="MEDIUM"),
            make_sla_policy(severity="HIGH", response_minutes=30, resolution_minutes=240),
            make_sla_policy(severity="CRITICAL", response_minutes=15, resolution_minutes=120),
        ],
        eligible_agents=eligible_agents or [
            make_agent(agent_id="coord-1", version_id="coord-v1", role="COORDINATOR", capabilities=["orchestration"]),
            make_agent(agent_id="plumb-1", version_id="plumb-v1", role="SPECIALIST", capabilities=["plumbing", "water"]),
            make_agent(agent_id="elec-1", version_id="elec-v1", role="SPECIALIST", capabilities=["electrical"]),
            make_agent(agent_id="review-1", version_id="review-v1", role="REVIEWER", capabilities=["quality"]),
        ],
        subject=DomainSubjectRefPy(
            namespace="vinhomes",
            subject_type="incident",
            subject_id="inc-001",
        ),
    )
