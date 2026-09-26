"""Draft wire DTOs matching shared/platform/runtime-contracts.ts.

TypedDict is a typing contract, not HTTP input validation.
"""

from __future__ import annotations

from typing import Literal, TypedDict

JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]


class ActorRef(TypedDict):
    kind: Literal["user", "service", "agent"]
    id: str


class RequestContext(TypedDict):
    tenantId: str
    actor: ActorRef
    correlationId: str
    traceId: str


class DomainSubjectRef(TypedDict):
    namespace: str
    subjectType: str
    subjectId: str


class RuntimePlan(TypedDict):
    context: RequestContext
    subject: DomainSubjectRef
    agentVersionId: str
    input: dict[str, JsonValue]


class RuntimeSessionRef(TypedDict):
    tenantId: str
    sessionId: str


class RuntimeStep(TypedDict):
    session: RuntimeSessionRef
    stepId: str
    input: dict[str, JsonValue]


class RuntimeCheckpoint(TypedDict):
    session: RuntimeSessionRef
    checkpointId: str


class RuntimeEvent(TypedDict):
    session: RuntimeSessionRef
    eventId: str
    correlationId: str
    type: Literal["RUN_STARTED", "STEP_COMPLETED", "RUN_COMPLETED", "RUN_FAILED", "RUN_CANCELLED"]
    occurredAt: str
    payload: dict[str, JsonValue]
