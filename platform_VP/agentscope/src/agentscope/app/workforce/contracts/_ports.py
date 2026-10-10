# -*- coding: utf-8 -*-
"""Public dependency-inversion ports shared by Workforce modules.

This module intentionally describes boundaries only. Concrete persistence,
runtime and transport adapters live in the folder owned by the corresponding
team member.
"""

from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timedelta
from typing import Any, Protocol, runtime_checkable

from ._base import JsonObject, OpaqueId
from ._batch import AgentBuildBatch, BuildItem
from ._catalog import McpConnection, ToolBinding, ToolDescriptor
from ._conversation import (
    InboundReceipt,
    PartnerRequestEnvelope,
    RequestResult,
    TicketConversationBinding,
    WorkflowRecord,
)
from ._evaluation import EvaluationCaseResult, EvaluationSnapshot
from ._events import ConversationEvent, EventHistoryPage
from ._execution import (
    AsyncProtocolSnapshotRef,
    ExternalOperation,
    NormalizedJobEvent,
    ProviderEventEnvelope,
    ProviderEventReceipt,
)
from ._identity import ActorContext, CredentialPurpose, PartnerAudience, Scope
from ._manifest import AgentManifest, BusinessProfile
from ._partner_routing import PartnerOperation, ResolvedPartnerRoute
from ._reuse import ReuseCheck, ReuseDecision


@runtime_checkable
class UnitOfWork(Protocol):
    """Transaction boundary; ports must not commit an injected unit of work."""

    async def __aenter__(self) -> "UnitOfWork": ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: Any,
    ) -> bool | None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...

    def add_after_commit(self, callback: Any) -> None: ...


class UnitOfWorkFactory(Protocol):
    def __call__(self) -> AbstractAsyncContextManager[UnitOfWork]: ...


@runtime_checkable
class IdentityPort(Protocol):
    async def resolve_manager(
        self,
        authenticated_principal: object,
    ) -> Scope: ...

    async def check_scope_active(
        self,
        scope: Scope,
        uow: UnitOfWork | None = None,
    ) -> None: ...


@runtime_checkable
class PartnerRoutingPort(Protocol):
    async def resolve(
        self,
        partner_actor: ActorContext,
        routing_input: Mapping[str, object],
    ) -> ResolvedPartnerRoute: ...

    async def revalidate(
        self,
        scope: Scope,
        route_id: OpaqueId,
        expected_revision: int,
        actor: ActorContext,
        audience: PartnerAudience,
        operation: PartnerOperation,
        uow: UnitOfWork | None = None,
    ) -> ResolvedPartnerRoute: ...


@runtime_checkable
class RegistryPort(Protocol):
    async def list_available_tools(
        self,
        scope: Scope,
        query: str | None = None,
        capabilities: Sequence[str] = (),
        cursor: OpaqueId | None = None,
    ) -> tuple[tuple[ToolDescriptor, ...], OpaqueId | None]: ...

    async def get_tool_snapshot(
        self,
        scope: Scope,
        tool_version_id: OpaqueId,
    ) -> ToolDescriptor: ...

    async def check_bindings(
        self,
        scope: Scope,
        bindings: Sequence[ToolBinding],
    ) -> None: ...

    async def resolve_connection(
        self,
        scope: Scope,
        connection_id: OpaqueId,
    ) -> McpConnection: ...


@runtime_checkable
class DraftPort(Protocol):
    async def create_draft(
        self,
        scope: Scope,
        manifest: AgentManifest,
        reuse_decision: ReuseDecision,
        batch_id: OpaqueId | None = None,
    ) -> object: ...

    async def get_draft(self, scope: Scope, draft_id: OpaqueId) -> object: ...

    async def update_draft(
        self,
        scope: Scope,
        draft_id: OpaqueId,
        expected_revision: int,
        manifest: AgentManifest,
        reuse_decision: ReuseDecision,
    ) -> object: ...

    async def validate_draft(
        self,
        scope: Scope,
        draft_id: OpaqueId,
    ) -> object: ...


@runtime_checkable
class BuildBatchPort(Protocol):
    async def create_batch(
        self,
        scope: Scope,
        build_session_id: OpaqueId,
        items: Sequence[BuildItem],
    ) -> AgentBuildBatch: ...

    async def get_batch(
        self,
        scope: Scope,
        batch_id: OpaqueId,
    ) -> AgentBuildBatch: ...

    async def attach_draft(
        self,
        scope: Scope,
        batch_id: OpaqueId,
        item_id: OpaqueId,
        draft_id: OpaqueId,
        expected_revision: int,
    ) -> AgentBuildBatch: ...

    async def publish_selected(
        self,
        scope: Scope,
        batch_id: OpaqueId,
        expected_revision: int,
        selections: Sequence[Mapping[str, object]],
    ) -> AgentBuildBatch: ...


@runtime_checkable
class AgentReusePort(Protocol):
    async def find_candidates(
        self,
        scope: Scope,
        business_profile: BusinessProfile,
        include_drafts: bool = True,
    ) -> ReuseCheck: ...

    async def get_candidate(
        self,
        scope: Scope,
        agent_id: OpaqueId,
        version_id: OpaqueId | None = None,
    ) -> object: ...

    async def validate_decisions(
        self,
        scope: Scope,
        requirements: Sequence[BusinessProfile],
        reuse_decisions: Sequence[ReuseDecision],
        expected_catalog_revision: int,
    ) -> None: ...


@runtime_checkable
class PublishedCatalogPort(Protocol):
    async def list_candidates(
        self,
        scope: Scope,
        capabilities: Sequence[str],
    ) -> tuple[object, ...]: ...

    async def get_version(
        self,
        scope: Scope,
        version_id: OpaqueId,
    ) -> object: ...

    async def get_deployment(
        self,
        scope: Scope,
        deployment_id: OpaqueId,
    ) -> object: ...


@runtime_checkable
class EvaluationRunnerPort(Protocol):
    async def run_case(
        self,
        scope: Scope,
        version_snapshot: EvaluationSnapshot,
        test_case: Mapping[str, object],
        execution_mode: str,
    ) -> EvaluationCaseResult: ...

    async def cancel_case(
        self,
        scope: Scope,
        case_run_id: OpaqueId,
    ) -> None: ...


@runtime_checkable
class PartnerIngressPort(Protocol):
    async def accept(
        self,
        partner_actor: ActorContext,
        envelope: PartnerRequestEnvelope,
    ) -> InboundReceipt: ...

    async def wait_for_result(
        self,
        partner_actor: ActorContext,
        request_id: OpaqueId,
        external_user_id: OpaqueId,
        deadline: datetime,
    ) -> InboundReceipt: ...

    async def read_result(
        self,
        partner_actor: ActorContext,
        request_id: OpaqueId,
        external_user_id: OpaqueId,
    ) -> InboundReceipt: ...

    def stream_events(
        self,
        partner_actor: ActorContext,
        conversation_id: OpaqueId,
        external_user_id: OpaqueId,
        cursor: OpaqueId | None = None,
    ) -> AsyncIterator[ConversationEvent]: ...


@runtime_checkable
class JobPort(Protocol):
    async def enqueue(
        self,
        scope: Scope,
        job_type: str,
        payload: JsonObject,
        idempotency_key: str,
        uow: UnitOfWork | None = None,
        not_before: datetime | None = None,
    ) -> OpaqueId: ...

    async def enqueue_provider(
        self,
        provider_context: Mapping[str, object],
        job_type: str,
        payload: JsonObject,
        idempotency_key: str,
        uow: UnitOfWork | None = None,
        not_before: datetime | None = None,
    ) -> OpaqueId:
        """Enqueue work before an operation has resolved manager scope.

        Implementations must derive ``tenant_id`` and
        ``provider_integration_id`` from a verified provider context. They
        must never accept either namespace from a public event body.
        """
        ...

    async def claim(
        self,
        worker_id: str,
        lease: timedelta,
    ) -> object | None: ...

    async def heartbeat(self, job_id: OpaqueId) -> None: ...

    async def complete(self, job_id: OpaqueId, result: JsonObject) -> None: ...

    async def fail(self, job_id: OpaqueId, error: JsonObject) -> None: ...


@runtime_checkable
class ProviderAuthPort(Protocol):
    async def authenticate(
        self,
        raw_body: bytes,
        headers: Mapping[str, str],
    ) -> ActorContext: ...

    async def authorize_integration(
        self,
        principal: ActorContext,
        operation: PartnerOperation,
        uow: UnitOfWork | None = None,
    ) -> None: ...

    async def require_purpose(
        self,
        principal: ActorContext,
        purpose: CredentialPurpose,
    ) -> None: ...


@runtime_checkable
class AsyncProtocolPort(Protocol):
    async def get_snapshot(
        self,
        scope: Scope,
        tool_version_id: OpaqueId,
    ) -> AsyncProtocolSnapshotRef: ...

    async def normalize_verified_event(
        self,
        provider_context: ActorContext,
        protocol_snapshot: AsyncProtocolSnapshotRef,
        envelope: ProviderEventEnvelope,
    ) -> NormalizedJobEvent: ...

    async def validate_capability_coverage(
        self,
        protocol_snapshot: AsyncProtocolSnapshotRef,
        required_capabilities: Sequence[str],
    ) -> None: ...


@runtime_checkable
class ExternalOperationPort(Protocol):
    async def prepare(
        self,
        scope: Scope,
        run_context: Mapping[str, object],
        call: Mapping[str, object],
        protocol: AsyncProtocolSnapshotRef,
        uow: UnitOfWork | None = None,
    ) -> ExternalOperation: ...

    async def bind_result(
        self,
        scope: Scope,
        operation_id: OpaqueId,
        result: Mapping[str, object],
        uow: UnitOfWork | None = None,
    ) -> ExternalOperation: ...

    async def get_for_workflow(
        self,
        scope: Scope,
        workflow_id: OpaqueId,
    ) -> tuple[ExternalOperation, ...]: ...


@runtime_checkable
class ProviderEventIngressPort(Protocol):
    async def accept(
        self,
        verified_principal: ActorContext,
        envelope: ProviderEventEnvelope,
        payload_hash: str,
    ) -> ProviderEventReceipt: ...

    async def read_receipt(
        self,
        principal: ActorContext,
        receipt_id: OpaqueId,
    ) -> ProviderEventReceipt: ...

    async def process(self, receipt_id: OpaqueId) -> ProviderEventReceipt: ...


@runtime_checkable
class PartnerCommandPort(Protocol):
    async def claim_or_read(
        self,
        actor: ActorContext,
        external_request_id: OpaqueId,
        command_kind: str,
        target_ref: OpaqueId | None,
        payload_hash: str,
        uow: UnitOfWork | None = None,
    ) -> object: ...

    async def resolve_ticket_binding(
        self,
        scope: Scope,
        audience: PartnerAudience,
        external_ticket_id: OpaqueId,
        external_conversation_id: OpaqueId,
        workflow_id: OpaqueId | None = None,
        uow: UnitOfWork | None = None,
    ) -> TicketConversationBinding: ...

    async def record_result(
        self,
        request_id: OpaqueId,
        result: RequestResult,
        uow: UnitOfWork | None = None,
    ) -> None: ...


@runtime_checkable
class WorkflowPort(Protocol):
    async def start_with_binding(
        self,
        scope: Scope,
        actor: ActorContext,
        audience: PartnerAudience,
        message: Mapping[str, object],
        uow: UnitOfWork | None = None,
    ) -> WorkflowRecord: ...

    async def accept_reply(
        self,
        scope: Scope,
        actor: ActorContext,
        audience: PartnerAudience,
        workflow_id: OpaqueId,
        message: Mapping[str, object],
        uow: UnitOfWork | None = None,
    ) -> WorkflowRecord: ...

    async def apply_external_event(
        self,
        scope: Scope,
        operation_ref: OpaqueId,
        normalized_event: NormalizedJobEvent,
        uow: UnitOfWork | None = None,
    ) -> WorkflowRecord: ...

    async def enqueue_trigger(
        self,
        scope: Scope,
        trigger: Mapping[str, object],
        uow: UnitOfWork | None = None,
    ) -> OpaqueId: ...

    async def close(
        self,
        scope: Scope,
        actor: ActorContext,
        audience: PartnerAudience,
        command: Mapping[str, object],
        uow: UnitOfWork | None = None,
    ) -> WorkflowRecord: ...


@runtime_checkable
class ConversationEventPort(Protocol):
    async def append(
        self,
        scope: Scope,
        audience: PartnerAudience,
        event: ConversationEvent,
        uow: UnitOfWork | None = None,
    ) -> ConversationEvent: ...

    async def list_after(
        self,
        actor: ActorContext,
        conversation_id: OpaqueId,
        cursor: OpaqueId | None,
        limit: int,
    ) -> EventHistoryPage: ...

    async def snapshot(
        self,
        actor: ActorContext,
        conversation_id: OpaqueId,
    ) -> JsonObject: ...

    def subscribe(
        self,
        actor: ActorContext,
        conversation_id: OpaqueId,
        cursor: OpaqueId | None,
    ) -> AsyncIterator[ConversationEvent]: ...


@runtime_checkable
class PublicEventSignalPort(Protocol):
    async def notify_after_commit(
        self,
        scope: Scope,
        conversation_id: OpaqueId,
        committed_sequence: int,
    ) -> None: ...

    async def wait_for_signal(
        self,
        scope: Scope,
        conversation_id: OpaqueId,
        timeout: float,
    ) -> int | None: ...

    async def health(self) -> bool: ...


@runtime_checkable
class RequestCompletionSignalPort(Protocol):
    """Best-effort wake-up for bounded POST result waiters.

    The persisted request result remains authoritative. A missed signal only
    delays the next database read and must never lose a completed result.
    """

    async def notify_after_commit(
        self,
        scope: Scope,
        request_id: OpaqueId,
    ) -> None: ...

    async def wait_for_completion(
        self,
        scope: Scope,
        request_id: OpaqueId,
        timeout: float,
    ) -> bool: ...

    async def health(self) -> bool: ...


@runtime_checkable
class RuntimeContinuationPort(Protocol):
    async def load_pinned_context(
        self,
        scope: Scope,
        checkpoint: OpaqueId,
    ) -> object: ...

    async def invoke_turn(
        self,
        scope: Scope,
        trigger: Mapping[str, object],
        checkpoint: object,
        execution_guard: object,
    ) -> object: ...

    async def persist_checkpoint(
        self,
        scope: Scope,
        workflow_id: OpaqueId,
        checkpoint: object,
        uow: UnitOfWork | None = None,
    ) -> OpaqueId: ...
