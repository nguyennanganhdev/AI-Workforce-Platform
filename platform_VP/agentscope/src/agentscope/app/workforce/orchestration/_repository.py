"""SQL persistence adapters for the Phase-C orchestration slice.

All methods join an injected Foundation unit of work.  No adapter creates a
database, commits an injected transaction, or runs DDL at runtime.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, func, insert, or_, select, update

from ..contracts import (
    AssistantMessage,
    ConversationEvent,
    ConversationSnapshot,
    EventHistoryPage,
    InboundRequest,
    PartnerAudience,
    PublicError,
    RequestResult,
    RequestStatus,
    Scope,
    WorkflowProjection,
)
from ..foundation._identity import _sql_uow
from ._ingress import RequestView
from ._tables import (
    partner_commands,
    partner_requests,
    public_events,
    workflow_bindings,
    workflow_checkpoints,
    workflow_inputs,
    workflows,
)
from .partner_events import ConversationAccess, EventCursorExpired
from .workflows import (
    WorkflowConflict,
    WorkflowLease,
    WorkflowReservation,
    next_action,
)
from .workflows._models import parse_aggregate
from .workflows.phase_a import CommandClaimResult, WorkflowCheckpoint


def _scope_values(scope: Scope) -> dict[str, str]:
    return scope.model_dump(mode="python")


def _scope_where(table: Any, scope: Scope) -> tuple[Any, ...]:
    return tuple(
        table.c[name] == value for name, value in _scope_values(scope).items()
    )


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _json_hash(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _dialect_insert(uow: Any, table: Any, values: dict[str, Any]) -> Any:
    dialect = uow.bind.dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as dialect_insert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as dialect_insert
    else:
        return insert(table).values(**values)
    return dialect_insert(table).values(**values).on_conflict_do_nothing()


class SqlWorkflowRepository:
    """Immutable ticket binding plus workflow CAS and lease fencing."""

    def __init__(
        self,
        uows: Callable[[], Any],
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        ids: Callable[[], str] = lambda: uuid4().hex,
    ) -> None:
        self._uows = uows
        self._clock = clock
        self._ids = ids

    @staticmethod
    def _binding_predicate(scope: Scope, audience: PartnerAudience) -> Any:
        base = (
            workflow_bindings.c.tenant_id == scope.tenant_id,
            workflow_bindings.c.partner_client_id
            == audience.partner_client_id,
            workflow_bindings.c.external_user_id == audience.external_user_id,
        )
        keys = [
            workflow_bindings.c.external_conversation_id
            == audience.external_conversation_id
        ]
        if audience.external_ticket_id is not None:
            keys.append(
                workflow_bindings.c.external_ticket_id
                == audience.external_ticket_id
            )
        return and_(*base, or_(*keys))

    async def reserve(self, aggregate, uow):
        aggregate = parse_aggregate(aggregate)
        tx = _sql_uow(uow)
        record = aggregate.workflow
        statement = select(workflow_bindings).where(
            self._binding_predicate(record.scope, record.audience)
        )
        if tx.bind.dialect.name == "postgresql":
            statement = statement.with_for_update()
        matches = (await tx.execute(statement)).mappings().all()
        if matches:
            workflow_ids = {row["workflow_id"] for row in matches}
            if len(workflow_ids) != 1:
                raise WorkflowConflict("ticket binding indexes disagree")
            row = (
                await tx.execute(
                    select(workflows).where(
                        workflows.c.id == next(iter(workflow_ids))
                    )
                )
            ).mappings().one()
            return WorkflowReservation(
                aggregate=parse_aggregate(row["payload"]), created=False
            )

        now = _aware(self._clock())
        bind_values = {
            "workflow_id": record.workflow_id,
            **_scope_values(record.scope),
            "partner_client_id": record.audience.partner_client_id,
            "external_user_id": record.audience.external_user_id,
            "external_ticket_id": record.audience.external_ticket_id,
            "external_conversation_id": (
                record.audience.external_conversation_id
            ),
            "residence_id": record.audience.residence_id,
            "conversation_id": record.conversation_id,
            "group_id": record.group_id,
            "route_id": record.route_id,
            "route_revision": record.route_revision,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        inserted = await tx.execute(
            _dialect_insert(tx, workflow_bindings, bind_values)
        )
        if inserted.rowcount != 1:
            matches = (
                await tx.execute(
                    select(workflow_bindings).where(
                        self._binding_predicate(record.scope, record.audience)
                    )
                )
            ).mappings().all()
            ids = {row["workflow_id"] for row in matches}
            if len(ids) != 1:
                raise WorkflowConflict("ticket binding conflict")
            existing = (
                await tx.execute(
                    select(workflows).where(workflows.c.id == ids.pop())
                )
            ).mappings().one()
            return WorkflowReservation(
                aggregate=parse_aggregate(existing["payload"]), created=False
            )
        await tx.execute(
            insert(workflows).values(
                id=record.workflow_id,
                **_scope_values(record.scope),
                conversation_id=record.conversation_id,
                group_id=record.group_id,
                state=record.state.value,
                revision=record.revision,
                payload=aggregate.model_dump(mode="json"),
                lease_owner=None,
                lease_expires_at=None,
                fencing_token=0,
                created_at=record.created_at,
                updated_at=record.updated_at,
            )
        )
        return WorkflowReservation(aggregate=aggregate, created=True)

    async def load(self, scope, workflow_id, uow=None):
        scope = Scope.model_validate(scope)
        if uow is None:
            async with self._uows() as owned:
                return await self.load(scope, workflow_id, owned)
        row = (
            await _sql_uow(uow).execute(
                select(workflows).where(
                    workflows.c.id == workflow_id,
                    *_scope_where(workflows, scope),
                )
            )
        ).mappings().first()
        if row is None:
            raise KeyError("workflow not found in owner scope")
        aggregate = parse_aggregate(row["payload"])
        if aggregate.workflow.scope != scope:
            raise PermissionError("workflow payload scope mismatch")
        return aggregate

    async def save(
        self, aggregate, expected_revision, uow, lease=None
    ) -> bool:
        aggregate = parse_aggregate(aggregate)
        record = aggregate.workflow
        clauses = [
            workflows.c.id == record.workflow_id,
            workflows.c.revision == expected_revision,
            *_scope_where(workflows, record.scope),
        ]
        if lease is not None:
            lease = WorkflowLease.model_validate(lease)
            clauses.extend(
                (
                    workflows.c.lease_owner == lease.owner,
                    workflows.c.fencing_token == lease.fencing_token,
                    workflows.c.lease_expires_at.is_not(None),
                    workflows.c.lease_expires_at > self._clock(),
                )
            )
        result = await _sql_uow(uow).execute(
            update(workflows)
            .where(*clauses)
            .values(
                state=record.state.value,
                revision=record.revision,
                payload=aggregate.model_dump(mode="json"),
                updated_at=record.updated_at,
            )
        )
        if result.rowcount == 1 and record.state.value == "closed":
            await _sql_uow(uow).execute(
                update(workflow_bindings)
                .where(workflow_bindings.c.workflow_id == record.workflow_id)
                .values(status="closed", updated_at=record.updated_at)
            )
        return result.rowcount == 1

    async def record_input(
        self, scope, workflow_id, cause_key, text, uow
    ) -> bool:
        await self.load(scope, workflow_id, uow)
        values = {
            "id": self._ids(),
            "workflow_id": workflow_id,
            "cause_kind": cause_key[0],
            "cause_id": cause_key[1],
            "text": text,
            "payload_hash": _json_hash({"text": text}),
            "created_at": _aware(self._clock()),
        }
        result = await _sql_uow(uow).execute(
            _dialect_insert(_sql_uow(uow), workflow_inputs, values)
        )
        return result.rowcount == 1

    async def acquire_lease(
        self, scope, workflow_id, worker_id, duration: timedelta
    ):
        if duration.total_seconds() <= 0:
            raise ValueError("workflow lease must be positive")
        now = _aware(self._clock())
        async with self._uows() as uow:
            row = (
                await uow.execute(
                    select(workflows).where(
                        workflows.c.id == workflow_id,
                        *_scope_where(workflows, scope),
                    )
                )
            ).mappings().first()
            if row is None:
                raise KeyError("workflow not found in owner scope")
            if row["lease_expires_at"] is not None and _aware(
                row["lease_expires_at"]
            ) > now:
                return None
            token = int(row["fencing_token"]) + 1
            expires_at = now + duration
            result = await uow.execute(
                update(workflows)
                .where(
                    workflows.c.id == workflow_id,
                    workflows.c.fencing_token == row["fencing_token"],
                    or_(
                        workflows.c.lease_expires_at.is_(None),
                        workflows.c.lease_expires_at <= now,
                    ),
                )
                .values(
                    lease_owner=worker_id,
                    lease_expires_at=expires_at,
                    fencing_token=token,
                )
            )
            if result.rowcount != 1:
                return None
            await uow.commit()
            return WorkflowLease(
                workflow_id=workflow_id,
                owner=worker_id,
                fencing_token=token,
                expires_at=expires_at,
            )

    async def lease_is_current(self, scope, lease, uow=None):
        lease = WorkflowLease.model_validate(lease)
        if uow is None:
            async with self._uows() as owned:
                return await self.lease_is_current(scope, lease, owned)
        row = (
            await _sql_uow(uow).execute(
                select(workflows.c.id).where(
                    workflows.c.id == lease.workflow_id,
                    *_scope_where(workflows, scope),
                    workflows.c.lease_owner == lease.owner,
                    workflows.c.fencing_token == lease.fencing_token,
                    workflows.c.lease_expires_at.is_not(None),
                    workflows.c.lease_expires_at > self._clock(),
                )
            )
        ).first()
        return row is not None

    async def release_lease(self, scope, lease):
        lease = WorkflowLease.model_validate(lease)
        async with self._uows() as uow:
            await uow.execute(
                update(workflows)
                .where(
                    workflows.c.id == lease.workflow_id,
                    *_scope_where(workflows, scope),
                    workflows.c.lease_owner == lease.owner,
                    workflows.c.fencing_token == lease.fencing_token,
                )
                .values(lease_owner=None, lease_expires_at=None)
            )
            await uow.commit()


class SqlPartnerRequestRepository:
    """Shared partner command ledger and customer request/result projection."""

    def __init__(
        self,
        uows: Callable[[], Any],
        tenant_resolver: Callable[[Any, Any], Any],
        *,
        approval_authorizer: Callable[..., Any] | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        ids: Callable[[], str] = lambda: uuid4().hex,
    ) -> None:
        self._uows = uows
        self._tenant_resolver = tenant_resolver
        self._approval_authorizer = approval_authorizer
        self._clock = clock
        self._ids = ids

    async def read_existing(
        self,
        actor,
        external_request_id,
        command_kind,
        target_ref,
        payload_hash,
    ):
        async with self._uows() as uow:
            tenant_id = await self._resolve_tenant(actor, uow)
            row = await self._command_row(
                uow, tenant_id, actor, external_request_id, lock=False
            )
        if row is None:
            return None
        return self._claim(row, command_kind, target_ref, payload_hash)

    async def claim_or_read(
        self,
        actor,
        external_request_id,
        command_kind,
        target_ref,
        payload_hash,
        uow=None,
    ):
        if uow is None:
            async with self._uows() as owned:
                claim = await self.claim_or_read(
                    actor,
                    external_request_id,
                    command_kind,
                    target_ref,
                    payload_hash,
                    owned,
                )
                await owned.commit()
                return claim
        tx = _sql_uow(uow)
        tenant_id = await self._resolve_tenant(actor, tx)
        now = _aware(self._clock())
        request_id = self._ids()
        values = {
            "id": request_id,
            "tenant_id": tenant_id,
            "partner_client_id": actor.partner_client_id,
            "external_user_id": actor.external_user_id,
            "external_request_id": external_request_id,
            "command_kind": command_kind,
            "target_ref": target_ref,
            "payload_hash": payload_hash,
            "status": RequestStatus.ACCEPTED.value,
            "result": None,
            "error": None,
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
        }
        inserted = await tx.execute(
            _dialect_insert(tx, partner_commands, values)
        )
        row = await self._command_row(
            tx, tenant_id, actor, external_request_id, lock=True
        )
        if row is None:
            raise RuntimeError("command claim was not persisted")
        claim = self._claim(row, command_kind, target_ref, payload_hash)
        return claim.model_copy(update={"is_new": inserted.rowcount == 1})

    async def _resolve_tenant(self, actor, uow) -> str:
        tenant_id = await self._tenant_resolver(actor, uow)
        if not isinstance(tenant_id, str) or not tenant_id:
            raise PermissionError("partner credential tenant is not verified")
        return tenant_id

    async def authorize_approval(self, actor, approval_id, body, uow=None):
        """Delegate approval binding lookup without coupling to Execution tables."""
        if self._approval_authorizer is None:
            raise RuntimeError("approval command authorization is not configured")
        return await self._approval_authorizer(
            actor, approval_id, body, uow=uow
        )

    async def _command_row(
        self, uow, tenant_id, actor, external_request_id, lock
    ):
        statement = select(partner_commands).where(
            partner_commands.c.tenant_id == tenant_id,
            partner_commands.c.partner_client_id == actor.partner_client_id,
            partner_commands.c.external_request_id == external_request_id,
        )
        if lock and uow.bind.dialect.name == "postgresql":
            statement = statement.with_for_update()
        row = (await uow.execute(statement)).mappings().first()
        if row is not None and row["external_user_id"] != actor.external_user_id:
            raise PermissionError("command belongs to another external user")
        return row

    @staticmethod
    def _claim(row, command_kind, target_ref, payload_hash):
        if (
            row["command_kind"] != command_kind
            or row["target_ref"] != target_ref
            or row["payload_hash"] != payload_hash
        ):
            raise WorkflowConflict(
                "idempotency key reused with different command content"
            )
        return CommandClaimResult(
            request_id=row["id"],
            is_new=False,
            status=row["status"],
            result=row["result"],
        )

    async def attach(self, request, uow) -> None:
        request = InboundRequest.model_validate(request)
        values = {
            "id": request.request_id,
            **_scope_values(request.scope),
            "partner_client_id": request.audience.partner_client_id,
            "external_user_id": request.audience.external_user_id,
            "workflow_id": request.workflow_id,
            "conversation_id": request.conversation_id,
            "status": request.status.value,
            "payload": request.model_dump(mode="json"),
            "accepted_at": request.accepted_at,
            "completed_at": request.completed_at,
        }
        result = await _sql_uow(uow).execute(
            _dialect_insert(_sql_uow(uow), partner_requests, values)
        )
        if result.rowcount != 1:
            row = (
                await _sql_uow(uow).execute(
                    select(partner_requests).where(
                        partner_requests.c.id == request.request_id
                    )
                )
            ).mappings().one()
            if InboundRequest.model_validate(row["payload"]) != request:
                raise WorkflowConflict("request id attached to another command")

    async def read(
        self, actor, request_id, external_user_id, uow=None
    ) -> RequestView:
        if uow is None:
            async with self._uows() as owned:
                return await self.read(
                    actor, request_id, external_user_id, owned
                )
        row = (
            await _sql_uow(uow).execute(
                select(
                    partner_requests,
                    partner_commands.c.result,
                    partner_commands.c.error,
                )
                .join(
                    partner_commands,
                    partner_commands.c.id == partner_requests.c.id,
                )
                .where(
                    partner_requests.c.id == request_id,
                    partner_requests.c.partner_client_id
                    == actor.partner_client_id,
                    partner_requests.c.external_user_id == external_user_id,
                )
            )
        ).mappings().first()
        if row is None or actor.external_user_id != external_user_id:
            raise PermissionError("request result audience mismatch")
        request = InboundRequest.model_validate(
            {
                **row["payload"],
                "status": row["status"],
                "completed_at": row["completed_at"],
            }
        )
        return RequestView(
            request=request,
            result=(
                RequestResult.model_validate(row["result"])
                if row["result"] is not None
                else None
            ),
            error=row["error"],
        )

    async def resolve_workflow_request(
        self, actor, workflow_id, external_user_id, uow=None
    ) -> InboundRequest:
        if uow is None:
            async with self._uows() as owned:
                return await self.resolve_workflow_request(
                    actor, workflow_id, external_user_id, owned
                )
        row = (
            await _sql_uow(uow).execute(
                select(partner_requests)
                .where(
                    partner_requests.c.workflow_id == workflow_id,
                    partner_requests.c.partner_client_id
                    == actor.partner_client_id,
                    partner_requests.c.external_user_id == external_user_id,
                )
                .order_by(partner_requests.c.accepted_at)
                .limit(1)
            )
        ).mappings().first()
        if row is None or actor.external_user_id != external_user_id:
            raise PermissionError("workflow request audience mismatch")
        return InboundRequest.model_validate(row["payload"])

    async def resolve_ticket_binding(
        self,
        scope,
        audience,
        external_ticket_id,
        external_conversation_id,
        workflow_id=None,
        uow=None,
    ):
        from ..contracts import TicketConversationBinding

        if uow is None:
            async with self._uows() as owned:
                return await self.resolve_ticket_binding(
                    scope,
                    audience,
                    external_ticket_id,
                    external_conversation_id,
                    workflow_id,
                    owned,
                )
        clauses = [
            *_scope_where(workflow_bindings, scope),
            workflow_bindings.c.partner_client_id
            == audience.partner_client_id,
            workflow_bindings.c.external_user_id == audience.external_user_id,
            workflow_bindings.c.external_ticket_id == external_ticket_id,
            workflow_bindings.c.external_conversation_id
            == external_conversation_id,
        ]
        if workflow_id is not None:
            clauses.append(workflow_bindings.c.workflow_id == workflow_id)
        row = (
            await _sql_uow(uow).execute(
                select(workflow_bindings).where(*clauses)
            )
        ).mappings().first()
        if row is None:
            raise PermissionError("ticket binding not found")
        return TicketConversationBinding(
            scope=scope,
            partner_client_id=row["partner_client_id"],
            external_user_id=row["external_user_id"],
            external_ticket_id=row["external_ticket_id"],
            external_conversation_id=row["external_conversation_id"],
            workflow_id=row["workflow_id"],
            conversation_id=row["conversation_id"],
            group_id=row["group_id"],
            route_id=row["route_id"],
            route_revision=row["route_revision"],
            status=row["status"],
            created_at=_aware(row["created_at"]),
            updated_at=_aware(row["updated_at"]),
        )

    async def record_result(self, request_id, result, uow=None) -> None:
        result = RequestResult.model_validate(result)
        if uow is None:
            async with self._uows() as owned:
                await self.record_result(request_id, result, owned)
                await owned.commit()
                return
        now = _aware(self._clock())
        tx = _sql_uow(uow)
        command = await tx.execute(
            update(partner_commands)
            .where(
                partner_commands.c.id == request_id,
                partner_commands.c.status.in_(
                    (
                        RequestStatus.ACCEPTED.value,
                        RequestStatus.QUEUED.value,
                        RequestStatus.RUNNING.value,
                    )
                ),
            )
            .values(
                status=RequestStatus.COMPLETED.value,
                result=result.model_dump(mode="json"),
                error=None,
                completed_at=now,
                updated_at=now,
            )
        )
        if command.rowcount == 0:
            row = (
                await tx.execute(
                    select(partner_commands).where(
                        partner_commands.c.id == request_id
                    )
                )
            ).mappings().first()
            if row is None or row["result"] != result.model_dump(mode="json"):
                raise WorkflowConflict("request result conflict")
        request_row = (
            await tx.execute(
                select(partner_requests.c.payload).where(
                    partner_requests.c.id == request_id
                )
            )
        ).first()
        if request_row is not None:
            request = InboundRequest.model_validate(request_row[0]).model_copy(
                update={
                    "status": RequestStatus.COMPLETED,
                    "completed_at": now,
                }
            )
            await tx.execute(
                update(partner_requests)
                .where(partner_requests.c.id == request_id)
                .values(
                    status=RequestStatus.COMPLETED.value,
                    completed_at=now,
                    payload=request.model_dump(mode="json"),
                )
            )

    async def mark_running(self, request_id, uow=None) -> None:
        if uow is None:
            async with self._uows() as owned:
                await self.mark_running(request_id, owned)
                await owned.commit()
                return
        tx = _sql_uow(uow)
        now = _aware(self._clock())
        await tx.execute(
            update(partner_commands)
            .where(
                partner_commands.c.id == request_id,
                partner_commands.c.status.in_(
                    (
                        RequestStatus.ACCEPTED.value,
                        RequestStatus.QUEUED.value,
                    )
                ),
            )
            .values(status=RequestStatus.RUNNING.value, updated_at=now)
        )
        await self._update_request_status(
            tx, request_id, RequestStatus.RUNNING, None
        )

    async def record_failure(
        self, request_id, code="WORKFLOW_EXECUTION_FAILED", uow=None
    ) -> None:
        if uow is None:
            async with self._uows() as owned:
                await self.record_failure(request_id, code, owned)
                await owned.commit()
                return
        tx = _sql_uow(uow)
        now = _aware(self._clock())
        error = PublicError(
            code=code,
            message="The workflow could not complete this request.",
            request_id=request_id,
            retryable=False,
        )
        result = await tx.execute(
            update(partner_commands)
            .where(
                partner_commands.c.id == request_id,
                partner_commands.c.status.in_(
                    (
                        RequestStatus.ACCEPTED.value,
                        RequestStatus.QUEUED.value,
                        RequestStatus.RUNNING.value,
                    )
                ),
            )
            .values(
                status=RequestStatus.FAILED.value,
                error=error.model_dump(mode="json"),
                updated_at=now,
                completed_at=now,
            )
        )
        if result.rowcount:
            await self._update_request_status(
                tx, request_id, RequestStatus.FAILED, now
            )

    @staticmethod
    async def _update_request_status(
        tx, request_id, status: RequestStatus, completed_at
    ) -> None:
        row = (
            await tx.execute(
                select(partner_requests.c.payload).where(
                    partner_requests.c.id == request_id
                )
            )
        ).first()
        if row is None:
            return
        request = InboundRequest.model_validate(row[0]).model_copy(
            update={"status": status, "completed_at": completed_at}
        )
        await tx.execute(
            update(partner_requests)
            .where(partner_requests.c.id == request_id)
            .values(
                status=status.value,
                completed_at=completed_at,
                payload=request.model_dump(mode="json"),
            )
        )


class SqlCheckpointRepository:
    """Immutable workflow checkpoint store used by the runtime adapter."""

    def __init__(
        self,
        uows: Callable[[], Any],
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._uows = uows
        self._clock = clock

    async def persist(self, scope, workflow_id, checkpoint, uow=None) -> str:
        checkpoint = WorkflowCheckpoint.model_validate(checkpoint)
        if checkpoint.workflow_id != workflow_id:
            raise PermissionError("checkpoint workflow mismatch")
        if uow is None:
            async with self._uows() as owned:
                ref = await self.persist(
                    scope, workflow_id, checkpoint, owned
                )
                await owned.commit()
                return ref
        payload = checkpoint.model_dump(mode="json")
        digest = _json_hash(payload)
        ref = f"checkpoint:{workflow_id}:{checkpoint.state_revision}:{digest[:16]}"
        tx = _sql_uow(uow)
        await tx.execute(
            _dialect_insert(
                tx,
                workflow_checkpoints,
                {
                    "id": ref,
                    **_scope_values(scope),
                    "workflow_id": workflow_id,
                    "state_revision": checkpoint.state_revision,
                    "payload_hash": digest,
                    "payload": payload,
                    "created_at": _aware(self._clock()),
                },
            )
        )
        row = (
            await tx.execute(
                select(workflow_checkpoints).where(
                    workflow_checkpoints.c.workflow_id == workflow_id,
                    workflow_checkpoints.c.state_revision
                    == checkpoint.state_revision,
                    *_scope_where(workflow_checkpoints, scope),
                )
            )
        ).mappings().one()
        if row["payload_hash"] != digest:
            raise WorkflowConflict("checkpoint revision content conflict")
        return row["id"]

    async def load(self, scope, checkpoint_ref, uow=None):
        if uow is None:
            async with self._uows() as owned:
                return await self.load(scope, checkpoint_ref, owned)
        row = (
            await _sql_uow(uow).execute(
                select(workflow_checkpoints).where(
                    workflow_checkpoints.c.id == checkpoint_ref,
                    *_scope_where(workflow_checkpoints, scope),
                )
            )
        ).mappings().first()
        if row is None:
            raise KeyError("checkpoint not found in owner scope")
        if row["payload_hash"] != _json_hash(row["payload"]):
            raise RuntimeError("checkpoint integrity check failed")
        return WorkflowCheckpoint.model_validate(row["payload"])


class SqlEventRepository:
    """Conversation-scoped event append, replay and snapshot projection."""

    def __init__(self, uows: Callable[[], Any]) -> None:
        self._uows = uows

    async def access(self, conversation_id, uow=None):
        if uow is None:
            async with self._uows() as owned:
                return await self.access(conversation_id, owned)
        row = (
            await _sql_uow(uow).execute(
                select(workflow_bindings).where(
                    workflow_bindings.c.conversation_id == conversation_id
                )
            )
        ).mappings().first()
        if row is None:
            raise KeyError("conversation binding not found")
        return ConversationAccess(
            scope=Scope(
                tenant_id=row["tenant_id"],
                domain_id=row["domain_id"],
                area_id=row["area_id"],
                manager_account_id=row["manager_account_id"],
            ),
            audience=PartnerAudience(
                partner_client_id=row["partner_client_id"],
                external_user_id=row["external_user_id"],
                external_ticket_id=row["external_ticket_id"],
                external_conversation_id=row["external_conversation_id"],
                residence_id=row["residence_id"],
            ),
            conversation_id=row["conversation_id"],
            workflow_id=row["workflow_id"],
            ticket_id=(
                await self._workflow(row["workflow_id"], uow)
            ).workflow.ticket_id,
        )

    async def _workflow(self, workflow_id, uow):
        row = (
            await _sql_uow(uow).execute(
                select(workflows.c.payload).where(workflows.c.id == workflow_id)
            )
        ).first()
        if row is None:
            raise KeyError("workflow not found")
        return parse_aggregate(row[0])

    async def append(self, access, event, uow):
        event = ConversationEvent.model_validate(event)
        tx = _sql_uow(uow)
        existing = (
            await tx.execute(
                select(public_events).where(public_events.c.id == event.event_id)
            )
        ).mappings().first()
        if existing is not None:
            stored = ConversationEvent.model_validate(existing["payload"])
            if stored.model_dump(exclude={"sequence"}) != event.model_dump(
                exclude={"sequence"}
            ):
                raise WorkflowConflict("public event id content conflict")
            return stored
        maximum = await tx.scalar(
            select(func.max(public_events.c.sequence)).where(
                public_events.c.conversation_id == access.conversation_id
            )
        )
        stored = event.model_copy(update={"sequence": int(maximum or 0) + 1})
        await tx.execute(
            insert(public_events).values(
                id=stored.event_id,
                **_scope_values(access.scope),
                conversation_id=stored.conversation_id,
                workflow_id=stored.workflow_id,
                sequence=stored.sequence,
                event_type=stored.event_type,
                causation_id=stored.causation_id,
                payload=stored.model_dump(mode="json"),
                occurred_at=stored.occurred_at,
                recorded_at=stored.recorded_at,
            )
        )
        return stored

    async def list_after(self, access, cursor, limit):
        async with self._uows() as uow:
            start = 0
            if cursor is not None:
                cursor_row = (
                    await uow.execute(
                        select(public_events.c.sequence).where(
                            public_events.c.id == cursor,
                            public_events.c.conversation_id
                            == access.conversation_id,
                        )
                    )
                ).first()
                if cursor_row is None:
                    raise EventCursorExpired(cursor)
                start = cursor_row[0]
            rows = (
                await uow.execute(
                    select(public_events)
                    .where(
                        public_events.c.conversation_id
                        == access.conversation_id,
                        public_events.c.sequence > start,
                        *_scope_where(public_events, access.scope),
                    )
                    .order_by(public_events.c.sequence)
                    .limit(limit + 1)
                )
            ).mappings().all()
        items = tuple(
            ConversationEvent.model_validate(row["payload"])
            for row in rows[:limit]
        )
        return EventHistoryPage(
            items=items,
            next_cursor=items[-1].event_id if items else cursor,
            has_more=len(rows) > limit,
        )

    async def snapshot(self, access):
        async with self._uows() as uow:
            aggregate = await self._workflow(access.workflow_id, uow)
            rows = (
                await uow.execute(
                    select(public_events)
                    .where(
                        public_events.c.conversation_id
                        == access.conversation_id,
                        *_scope_where(public_events, access.scope),
                    )
                    .order_by(public_events.c.sequence)
                )
            ).mappings().all()
        events = tuple(
            ConversationEvent.model_validate(row["payload"]) for row in rows
        )
        record = aggregate.workflow
        messages = tuple(
            AssistantMessage(
                message_id=event.payload["message_id"],
                workflow_id=record.workflow_id,
                text=event.payload["text"],
                created_at=event.occurred_at,
            )
            for event in events
            if event.event_type == "assistant.message"
        )
        return ConversationSnapshot(
            conversation_id=record.conversation_id,
            external_conversation_id=(
                record.audience.external_conversation_id
            ),
            external_user_id=record.audience.external_user_id,
            workflows=(
                WorkflowProjection(
                    workflow_id=record.workflow_id,
                    external_ticket_id=record.audience.external_ticket_id,
                    ticket_id=record.ticket_id,
                    state=record.state,
                    next_action=next_action(record.state),
                    revision=record.revision,
                ),
            ),
            messages=messages,
            pending_approvals=tuple(
                {
                    "workflow_id": record.workflow_id,
                    "approval_id": approval_id,
                    "status": "pending",
                }
                for approval_id in aggregate.checkpoint.pending_approval_ids
            ),
            snapshot_cursor=events[-1].event_id if events else None,
        )


__all__ = [
    "SqlCheckpointRepository",
    "SqlEventRepository",
    "SqlPartnerRequestRepository",
    "SqlWorkflowRepository",
]
