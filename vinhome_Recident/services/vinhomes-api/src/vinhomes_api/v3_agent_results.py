"""Transport metadata only; no model calls, tool selection, or agent decisions."""

from pydantic import BaseModel, ConfigDict, Field


class AgentContinuation(BaseModel):
    """Factual call metadata alongside the endpoint's unchanged business payload."""

    operation: str
    facts: dict[str, object] = Field(default_factory=dict)
    missingFields: list[str] = Field(default_factory=list)
    resourceContext: dict[str, object] = Field(default_factory=dict)
    source: str = "business_api"


class AgentBusinessResponse(BaseModel):
    """Preserve endpoint fields and document the factual agentContext object."""

    model_config = ConfigDict(extra="allow")
    agentContext: AgentContinuation


def agent_blocked(
    message: str, blockers: list[str], resource: dict[str, object]
) -> dict[str, object]:
    """Return failed server-side checks as data; do not advise or select a next step."""
    return {
        "message": message,
        "validation": {"failedChecks": blockers, "resourceContext": resource},
        "agentContext": AgentContinuation(
            operation="technical.submit_executor_result",
            resourceContext=resource,
        ).model_dump(),
    }


def agent_result(
    operation: str, result: dict[str, object], resource: dict[str, object] | None = None
) -> dict[str, object]:
    """Add only identifiers and status fields already present in the response."""
    fact_fields = (
        "id",
        "code",
        "status",
        "version",
        "ready",
        "creationOutcome",
        "reportId",
        "jobId",
        "totalTickets",
        "fileId",
        "uploadId",
        "added",
        "managementUnitId",
        "buildingId",
        "domainId",
        "serviceCategoryId",
        "interval",
    )
    facts = {key: result[key] for key in fact_fields if key in result}
    missing_fields = result.get("missingFields", [])
    if not isinstance(missing_fields, list):
        missing_fields = []
    context = dict(resource or {})
    return {
        **result,
        "agentContext": AgentContinuation(
            operation=operation,
            facts=facts,
            missingFields=missing_fields,
            resourceContext=context,
        ).model_dump(),
    }
