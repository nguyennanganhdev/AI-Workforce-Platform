"""Fail-closed Field Operations identity and scope adapter.

The authentication/identity owner injects this resolved authority into trusted
request state. It is never accepted from a request body.
"""

from enum import StrEnum
from typing import Literal
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..request_context import (
    DomainScope,
    RequestContext,
    get_domain_scope,
    get_request_context,
    scope_contains_subject,
)
from ..db.work_order import WorkOrder


class FieldOperationsRole(StrEnum):
    TECHNICIAN = "TECHNICIAN"
    A5_WORKER = "A5_WORKER"
    SECURITY_WORKER = "SECURITY_WORKER"
    CONTRACTOR_WORKER = "CONTRACTOR_WORKER"
    SUPERVISOR = "SUPERVISOR"
    QC = "QC"
    BQL_COORDINATOR = "BQL_COORDINATOR"


class ExecutorRef(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    executor_type: str = Field(alias="executorType", min_length=1, max_length=64)
    executor_id: UUID = Field(alias="executorId")
    incident_id: UUID | None = Field(alias="incidentId", default=None)


class FieldOperationsAuthority(BaseModel):
    """Identity and effective executor grants produced by trusted middleware."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    tenant_id: UUID = Field(alias="tenantId")
    actor_id: str = Field(alias="actorId", min_length=1, max_length=128)
    actor_type: Literal["user", "service", "agent"] = Field(alias="actorType")
    roles: set[FieldOperationsRole] = Field(default_factory=set)
    assignable_executors: list[ExecutorRef] = Field(alias="assignableExecutors", default_factory=list)
    executor_memberships: list[ExecutorRef] = Field(alias="executorMemberships", default_factory=list)

    def can_assign(self, executor_type: str, executor_id: UUID, incident_id: UUID) -> bool:
        return any(
            ref.executor_type == executor_type
            and ref.executor_id == executor_id
            and ref.incident_id == incident_id
            for ref in self.assignable_executors
        )

    def is_executor(self, executor_type: str, executor_id: UUID) -> bool:
        return any(
            ref.executor_type == executor_type and ref.executor_id == executor_id
            for ref in self.executor_memberships
        )

    def require_assign(
        self, work_order: WorkOrder, executor_type: str, executor_id: UUID
    ) -> None:
        if self.actor_type != "user" or not self.roles.intersection(
            {FieldOperationsRole.SUPERVISOR, FieldOperationsRole.BQL_COORDINATOR}
        ):
            raise HTTPException(status_code=403, detail="Supervisor or BQL coordinator role required")
        if not self.can_assign(executor_type, executor_id, work_order.incident_id):
            raise HTTPException(status_code=403, detail="Executor is outside the assigner's team or contract scope")

    def can_read(self, work_order: WorkOrder, scope: DomainScope) -> bool:
        if not scope_contains_subject(
            scope,
            namespace="vinhomes",
            subject_type="incident",
            subject_id=str(work_order.incident_id),
        ):
            return False
        if self.actor_type == "user" and self.roles.intersection(
            {FieldOperationsRole.SUPERVISOR, FieldOperationsRole.BQL_COORDINATOR}
        ):
            return True
        if self.actor_type == "user" and FieldOperationsRole.QC in self.roles:
            return work_order.status.value == "COMPLETED"
        worker_roles = {
            FieldOperationsRole.TECHNICIAN,
            FieldOperationsRole.A5_WORKER,
            FieldOperationsRole.SECURITY_WORKER,
            FieldOperationsRole.CONTRACTOR_WORKER,
        }
        return (
            self.actor_type == "user"
            and bool(self.roles.intersection(worker_roles))
            and work_order.executor_id is not None
            and work_order.executor_id == _actor_uuid(self.actor_id)
            and self.is_executor(work_order.executor_type, work_order.executor_id)
        )

    def require_execute(self, work_order: WorkOrder) -> None:
        if (
            work_order.executor_id is None
            or work_order.executor_id != _actor_uuid(self.actor_id)
            or self.actor_type != "user"
            or not self.roles.intersection(
                {
                    FieldOperationsRole.TECHNICIAN,
                    FieldOperationsRole.A5_WORKER,
                    FieldOperationsRole.SECURITY_WORKER,
                    FieldOperationsRole.CONTRACTOR_WORKER,
                }
            )
            or not self.is_executor(work_order.executor_type, work_order.executor_id)
        ):
            raise HTTPException(status_code=403, detail="Only the assigned executor may update this WorkOrder")


def _actor_uuid(actor_id: str) -> UUID | None:
    try:
        return UUID(actor_id)
    except ValueError:
        return None


async def get_field_operations_authority(
    request: Request,
    context: RequestContext = Depends(get_request_context),
    scope: DomainScope = Depends(get_domain_scope),
) -> FieldOperationsAuthority:
    raw = getattr(request.state, "field_operations_authority", None)
    if raw is None:
        raise HTTPException(status_code=403, detail="Field Operations authority required")
    try:
        authority = FieldOperationsAuthority.model_validate(raw)
    except ValidationError as exc:
        raise HTTPException(status_code=403, detail="Field Operations authority is invalid") from exc
    try:
        context_tenant_id = UUID(context.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Authenticated tenant identifier is invalid") from exc
    if (
        authority.tenant_id != context_tenant_id
        or scope.tenant_id != context.tenant_id
        or authority.actor_id != context.actor.id
        or authority.actor_type != context.actor.kind
    ):
        raise HTTPException(status_code=403, detail="Field Operations authority does not match request context")
    return authority
