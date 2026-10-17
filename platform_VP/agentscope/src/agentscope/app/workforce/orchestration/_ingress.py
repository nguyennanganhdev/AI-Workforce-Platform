"""Partner ingress, idempotency, immutable routing, and bounded wait."""

import asyncio
import json
from datetime import UTC, datetime
from hashlib import sha256
from time import monotonic
from typing import Protocol
from urllib.parse import quote

from ..contracts import (
    CloseWorkflowCommand,
    InboundReceipt,
    InboundRequest,
    PartnerAudience,
    PartnerCommandType,
    PartnerOperation,
    PartnerRequestEnvelope,
    PublicError,
    RequestResult,
    RequestStatus,
    WorkforceModel,
)
from .workflows import WorkflowBindingMismatch, WorkflowConflict, next_action
from .workflows._models import parse_aggregate, raw_value, require_binding
from .workflows.phase_a import CommandClaimResult

PENDING_REQUESTS = {
    RequestStatus.ACCEPTED,
    RequestStatus.QUEUED,
    RequestStatus.RUNNING,
}


def _observe_task(task: asyncio.Task) -> None:
    if not task.cancelled():
        task.exception()


class RequestView(WorkforceModel):
    request: InboundRequest
    result: RequestResult | None = None
    error: PublicError | None = None


class RequestRepository(Protocol):
    """Request/result view sharing the command-ledger unit of work."""

    async def attach(self, request: InboundRequest, uow) -> None: ...

    async def read(
        self,
        actor,
        request_id: str,
        external_user_id: str,
        uow=None,
    ) -> RequestView: ...

    async def resolve_workflow_request(
        self,
        actor,
        workflow_id: str,
        external_user_id: str,
        uow=None,
    ) -> InboundRequest:
        """Return the immutable first accepted request for this workflow."""
        ...


class PartnerIngressService:
    def __init__(
        self,
        workflows,
        commands,
        requests: RequestRepository,
        routing,
        identity,
        events,
        completion_signals,
        *,
        assets=None,
        clock=lambda: datetime.now(UTC),
        wait_slice_seconds: float = 1.0,
    ) -> None:
        if wait_slice_seconds <= 0:
            raise ValueError("wait_slice_seconds must be positive")
        self.workflows = workflows
        self.commands = commands
        self.requests = requests
        self.routing = routing
        self.identity = identity
        self.events = events
        self.completion_signals = completion_signals
        self.assets = assets
        self.clock = clock
        self.wait_slice_seconds = wait_slice_seconds

    @staticmethod
    def _require_customer_actor(actor, external_user_id: str) -> None:
        if (
            actor.kind != "partner"
            or actor.credential_purpose != "customer_api"
            or actor.external_user_id != external_user_id
        ):
            raise PermissionError("verified customer API actor required")

    async def accept(self, partner_actor, envelope):
        envelope = PartnerRequestEnvelope.model_validate(raw_value(envelope))
        self._require_customer_actor(partner_actor, envelope.external_user_id)
        audience = PartnerAudience(
            partner_client_id=partner_actor.partner_client_id,
            external_user_id=envelope.external_user_id,
            external_ticket_id=envelope.external_ticket_id,
            external_conversation_id=envelope.external_conversation_id,
            residence_id=envelope.residence_id,
        )
        route_audience = audience
        binding_mismatch = False
        payload_hash = sha256(
            json.dumps(
                envelope.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        # A valid retry remains bound to its original owner even when the
        # partner route was remapped after the first commit.  Production
        # command ledgers expose this read; Phase-B fakes remain compatible.
        read_existing = getattr(self.commands, "read_existing", None)
        if read_existing is not None:
            existing = await read_existing(
                partner_actor,
                envelope.external_request_id,
                envelope.command_type.value,
                envelope.workflow_id,
                payload_hash,
            )
            if existing is not None:
                claim = CommandClaimResult.model_validate(raw_value(existing))
                return await self.read_result(
                    partner_actor,
                    claim.request_id,
                    envelope.external_user_id,
                )
        if envelope.command_type == PartnerCommandType.START_WORKFLOW:
            route = await self.routing.resolve(
                partner_actor,
                {
                    "external_management_ref": (envelope.external_management_ref),
                    "external_user_id": envelope.external_user_id,
                    "residence_id": envelope.residence_id,
                },
            )
            scope = route.scope
            route_id = route.route_id
            route_revision = route.route_revision
            operation = PartnerOperation.SUBMIT_REQUEST
        else:
            original = InboundRequest.model_validate(
                raw_value(
                    await self.requests.resolve_workflow_request(
                        partner_actor,
                        envelope.workflow_id,
                        envelope.external_user_id,
                    )
                )
            )
            binding_mismatch = (
                original.workflow_id != envelope.workflow_id
                or original.audience != audience
                or original.external_management_ref != envelope.external_management_ref
            )
            route_audience = original.audience
            scope = original.scope
            route_id = original.route_id
            route_revision = original.route_revision
            operation = PartnerOperation.REPLY
        async with self.workflows.uows() as tx:
            await self.identity.check_scope_active(scope, tx)
            await self.routing.revalidate(
                scope,
                route_id,
                route_revision,
                partner_actor,
                route_audience,
                operation,
                tx,
            )
            if binding_mismatch:
                raise WorkflowBindingMismatch(
                    "reply immutable route or ticket mismatch"
                )
            claim = CommandClaimResult.model_validate(
                raw_value(
                    await self.commands.claim_or_read(
                        partner_actor,
                        envelope.external_request_id,
                        envelope.command_type.value,
                        envelope.workflow_id,
                        payload_hash,
                        tx,
                    )
                )
            )
            if claim.is_new:
                message = {
                    "request_id": claim.request_id,
                    "text": envelope.message.text,
                    "asset_ids": tuple(
                        item.asset_id for item in envelope.message.attachments
                    ),
                }
                if envelope.command_type == PartnerCommandType.START_WORKFLOW:
                    message.update(
                        route_id=route_id,
                        route_revision=route_revision,
                    )
                    workflow = await self.workflows.start_with_binding(
                        scope, partner_actor, audience, message, tx
                    )
                else:
                    aggregate = parse_aggregate(
                        await self.workflows.repository.load(
                            scope, envelope.workflow_id, tx
                        )
                    )
                    workflow = require_binding(aggregate, scope, audience)
                    message["expected_revision"] = workflow.revision
                    workflow = await self.workflows.accept_reply(
                        scope,
                        partner_actor,
                        audience,
                        workflow.workflow_id,
                        message,
                        tx,
                    )
                if (
                    workflow.route_id != route_id
                    or workflow.route_revision != route_revision
                ):
                    raise WorkflowConflict(
                        "workflow route differs from authorized route"
                    )
                if message["asset_ids"]:
                    if self.assets is None:
                        raise ValueError("asset capability is not configured")
                    await self.assets.bind_customer_assets(
                        scope,
                        audience,
                        workflow.workflow_id,
                        message["asset_ids"],
                        tx,
                    )
                await self.requests.attach(
                    InboundRequest(
                        request_id=claim.request_id,
                        scope=scope,
                        audience=audience,
                        external_request_id=envelope.external_request_id,
                        external_management_ref=(envelope.external_management_ref),
                        payload_hash=payload_hash,
                        route_id=route_id,
                        route_revision=route_revision,
                        conversation_id=workflow.conversation_id,
                        workflow_id=workflow.workflow_id,
                        group_id=workflow.group_id,
                        status=RequestStatus.ACCEPTED,
                        accepted_at=self.clock(),
                    ),
                    tx,
                )
            await tx.commit()
        return await self.read_result(
            partner_actor, claim.request_id, envelope.external_user_id
        )

    async def read_result(self, partner_actor, request_id, external_user_id):
        self._require_customer_actor(partner_actor, external_user_id)
        view = RequestView.model_validate(
            raw_value(
                await self.requests.read(partner_actor, request_id, external_user_id)
            )
        )
        request = view.request
        if (
            request.request_id != request_id
            or request.audience.partner_client_id != partner_actor.partner_client_id
            or request.audience.external_user_id != external_user_id
        ):
            raise PermissionError("request result audience mismatch")
        await self.identity.check_scope_active(request.scope)
        await self.routing.revalidate(
            request.scope,
            request.route_id,
            request.route_revision,
            partner_actor,
            request.audience,
            PartnerOperation.READ_RESULT,
        )
        aggregate = parse_aggregate(
            await self.workflows.repository.load(request.scope, request.workflow_id)
        )
        workflow = require_binding(aggregate, request.scope, request.audience)
        if (
            workflow.conversation_id != request.conversation_id
            or workflow.group_id != request.group_id
        ):
            raise PermissionError("request binding changed")
        if view.result is not None and any(
            message.workflow_id != workflow.workflow_id
            for message in view.result.messages
        ):
            raise PermissionError("request result contains a foreign workflow")
        status = request.status
        if (status == RequestStatus.COMPLETED) != (view.result is not None):
            raise WorkflowConflict("request result/status is inconsistent")
        terminal_failure = status in {
            RequestStatus.FAILED,
            RequestStatus.BLOCKED,
        }
        if terminal_failure != (view.error is not None):
            raise WorkflowConflict("request error/status is inconsistent")
        if view.error is not None and view.error.request_id != request_id:
            raise PermissionError("public error belongs to another request")
        error = view.error
        if status in PENDING_REQUESTS and workflow.state == "closed":
            status = RequestStatus.BLOCKED
            error = PublicError(
                code="WORKFLOW_CLOSED",
                message="The workflow closed before this request completed.",
                request_id=request_id,
                retryable=False,
            )
        elif status in PENDING_REQUESTS and workflow.state in {
            "blocked_authorization",
            "blocked_route_changed",
            "needs_attention",
        }:
            status = RequestStatus.BLOCKED
            error = PublicError(
                code={
                    "blocked_authorization": "ROUTE_NOT_AUTHORIZED",
                    "blocked_route_changed": "ROUTE_CONFLICT",
                    "needs_attention": "WORKFLOW_NEEDS_ATTENTION",
                }[workflow.state.value],
                message="The workflow requires operator attention.",
                request_id=request_id,
                retryable=False,
            )
        if status in PENDING_REQUESTS:
            action = "watch_request"
        elif (
            status in {RequestStatus.FAILED, RequestStatus.BLOCKED}
            and workflow.state != "closed"
        ):
            action = "resolve_attention"
        else:
            action = next_action(workflow.state)
        request_path = f"/workforce/v1/partner/requests/{quote(request_id, safe='')}"
        conversation = quote(workflow.conversation_id, safe="")
        conversation_path = f"/workforce/v1/partner/conversations/{conversation}"
        return InboundReceipt(
            request_id=request_id,
            request_status=status,
            external_ticket_id=request.audience.external_ticket_id,
            conversation_id=workflow.conversation_id,
            workflow_id=workflow.workflow_id,
            ticket_id=workflow.ticket_id,
            workflow_state=workflow.state,
            next_action=action,
            workflow_revision=workflow.revision,
            result=view.result,
            error=error,
            accepted_at=request.accepted_at,
            completed_at=request.completed_at,
            status_url=request_path,
            conversation_url=conversation_path,
            event_stream_url=f"{conversation_path}/events",
        )

    async def wait_for_result(
        self, partner_actor, request_id, external_user_id, deadline
    ):
        if deadline.tzinfo is None:
            raise ValueError("bounded wait deadline must be timezone-aware")
        budget = max(0.0, (deadline - self.clock()).total_seconds())
        started = monotonic()

        def remaining() -> float:
            return min(
                (deadline - self.clock()).total_seconds(),
                budget - (monotonic() - started),
            )

        while True:
            receipt = await self.read_result(
                partner_actor, request_id, external_user_id
            )
            if receipt.request_status not in PENDING_REQUESTS:
                return receipt
            duration = min(remaining(), self.wait_slice_seconds)
            if duration <= 0:
                return receipt
            view = await self.requests.read(partner_actor, request_id, external_user_id)
            waiter = asyncio.create_task(
                self.completion_signals.wait_for_completion(
                    view.request.scope, request_id, duration
                )
            )
            waiter.add_done_callback(_observe_task)
            slice_started = monotonic()
            try:
                done, _ = await asyncio.wait({waiter}, timeout=duration)
                signaled = False
                if done:
                    signaled = bool(waiter.result())
                if not signaled:
                    delay = min(
                        max(0.0, duration - (monotonic() - slice_started)),
                        max(0.0, remaining()),
                    )
                    if delay:
                        await asyncio.sleep(delay)
            except Exception:
                delay = min(
                    max(0.0, duration - (monotonic() - slice_started)),
                    max(0.0, remaining()),
                )
                if delay:
                    await asyncio.sleep(delay)
            finally:
                if not waiter.done():
                    waiter.cancel()

    async def close_workflow(self, partner_actor, scope, workflow_id, command):
        raw = raw_value(command)
        if not isinstance(raw, dict):
            raise ValueError("close command must be an object")
        if type(raw.get("expected_revision")) is not int:
            raise ValueError("close revision must be a strict integer")
        if type(raw.get("stop_tracking_only", False)) is not bool:
            raise ValueError("close tracking flag must be a strict boolean")
        parsed = CloseWorkflowCommand.model_validate(raw)
        self._require_customer_actor(partner_actor, parsed.external_user_id)
        aggregate = parse_aggregate(
            await self.workflows.repository.load(scope, workflow_id)
        )
        workflow = aggregate.workflow
        expected_audience = PartnerAudience(
            partner_client_id=partner_actor.partner_client_id,
            external_user_id=parsed.external_user_id,
            external_ticket_id=parsed.external_ticket_id,
            external_conversation_id=parsed.external_conversation_id,
            residence_id=workflow.audience.residence_id,
        )
        require_binding(aggregate, scope, expected_audience)
        payload_hash = sha256(
            json.dumps(
                parsed.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        async with self.workflows.uows() as tx:
            await self.identity.check_scope_active(scope, tx)
            await self.routing.revalidate(
                scope,
                workflow.route_id,
                workflow.route_revision,
                partner_actor,
                workflow.audience,
                PartnerOperation.CLOSE_WORKFLOW,
                tx,
            )
            claim = CommandClaimResult.model_validate(
                raw_value(
                    await self.commands.claim_or_read(
                        partner_actor,
                        parsed.external_request_id,
                        "close_workflow",
                        workflow_id,
                        payload_hash,
                        tx,
                    )
                )
            )
            if claim.is_new:
                closed = await self.workflows.close(
                    scope,
                    partner_actor,
                    workflow.audience,
                    {**parsed.model_dump(), "workflow_id": workflow_id},
                    tx,
                )
                await self.requests.attach(
                    InboundRequest(
                        request_id=claim.request_id,
                        scope=scope,
                        audience=workflow.audience,
                        external_request_id=parsed.external_request_id,
                        external_management_ref="bound_close",
                        payload_hash=payload_hash,
                        route_id=workflow.route_id,
                        route_revision=workflow.route_revision,
                        conversation_id=workflow.conversation_id,
                        workflow_id=workflow_id,
                        group_id=workflow.group_id,
                        status=RequestStatus.ACCEPTED,
                        accepted_at=self.clock(),
                    ),
                    tx,
                )
                await self.commands.record_result(
                    claim.request_id,
                    RequestResult(
                        data={
                            "workflow_state": closed.state.value,
                            "workflow_revision": closed.revision,
                            "next_action": "none",
                        }
                    ),
                    tx,
                )
            await tx.commit()
        return await self.read_result(
            partner_actor, claim.request_id, parsed.external_user_id
        )

    async def stream_events(
        self, partner_actor, conversation_id, external_user_id, cursor=None
    ):
        self._require_customer_actor(partner_actor, external_user_id)
        async for event in self.events.subscribe(
            partner_actor, conversation_id, cursor
        ):
            yield event


def receipt_http_status(receipt: InboundReceipt) -> int:
    return 202 if receipt.request_status in PENDING_REQUESTS else 200
