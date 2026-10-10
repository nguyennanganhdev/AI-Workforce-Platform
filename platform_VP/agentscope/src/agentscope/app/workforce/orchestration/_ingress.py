# -*- coding: utf-8 -*-
"""Customer POST/result bounded wait, with authenticated routing and dedupe."""

import asyncio
from datetime import datetime, timezone
from hashlib import sha256
import json
from time import monotonic
from typing import Protocol
from urllib.parse import quote, urlencode

from ..contracts import (
    CloseWorkflowCommand,
    InboundReceipt,
    InboundRequest,
    PartnerAudience,
    PartnerOperation,
    PartnerRequestEnvelope,
    PublicError,
    RequestResult,
    RequestStatus,
    WorkforceModel,
)
from .workflows._boundary import (
    WorkflowConflict,
    raw_models,
    require_binding,
    validated_bundle,
)
from .workflows._service import next_action
from .workflows.phase_a import CommandClaimResult


def _consume_signal_result(task):
    """Observe errors from cancelled advisory subscriptions during cleanup."""
    if not task.cancelled():
        task.exception()


class RequestView(WorkforceModel):
    request: InboundRequest
    result: RequestResult | None = None
    error: PublicError | None = None


class RequestRepository(Protocol):
    """Shares command ledger and UOW with PartnerCommandPort.record_result.

    attach persists the immutable request/workflow/binding. read reloads actual
    request status + result + safe public error together and enforces actor
    client/user membership. A failed/blocked request must retain its persisted
    PublicError; filter internal/provider details before constructing it.
    A claim and attach commit together; a retry must never rebuild a group.
    """

    async def attach(self, request: InboundRequest, uow) -> None:
        ...

    async def read(
        self, actor, request_id: str, external_user_id: str, uow=None
    ) -> RequestView:
        ...

    async def resolve_workflow_binding(
        self, actor, workflow_id: str, external_user_id: str, uow=None
    ) -> InboundRequest:
        """Read the original accepted request by authenticated client/user.

        Resolve only within the principal's tenant/client/user namespace.
        Return the immutable first-request route, audience and group binding,
        never a currently remapped route or a request selected by body scope.
        """
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
        clock=lambda: datetime.now(timezone.utc),
        wait_slice_seconds=1.0,
    ):
        if wait_slice_seconds <= 0:
            raise ValueError("wait slice must be positive")
        self.workflows, self.commands, self.requests = (
            workflows,
            commands,
            requests,
        )
        self.routing, self.identity, self.events = routing, identity, events
        self.completion_signals, self.clock = completion_signals, clock
        self.wait_slice_seconds = wait_slice_seconds

    @staticmethod
    def _actor(actor, external_user_id):
        if (
            actor.kind != "partner"
            or actor.credential_purpose != "customer_api"
            or actor.external_user_id != external_user_id
        ):
            raise PermissionError("verified customer actor required")

    async def accept(self, partner_actor, envelope):
        envelope = PartnerRequestEnvelope.model_validate(raw_models(envelope))
        self._actor(partner_actor, envelope.external_user_id)
        audience = PartnerAudience(
            partner_client_id=partner_actor.partner_client_id,
            external_user_id=envelope.external_user_id,
            external_ticket_id=envelope.external_ticket_id,
            external_conversation_id=envelope.external_conversation_id,
            residence_id=envelope.residence_id,
        )
        if envelope.command_type == "start_workflow":
            route = await self.routing.resolve(
                partner_actor,
                {
                    "external_management_ref": (
                        envelope.external_management_ref
                    ),
                    "external_user_id": envelope.external_user_id,
                    "residence_id": envelope.residence_id,
                },
            )
            scope, route_id, route_revision = (
                route.scope,
                route.route_id,
                route.route_revision,
            )
        else:
            original = InboundRequest.model_validate(
                raw_models(
                    await self.requests.resolve_workflow_binding(
                        partner_actor,
                        envelope.workflow_id,
                        envelope.external_user_id,
                    )
                )
            )
            if (
                original.workflow_id != envelope.workflow_id
                or original.audience != audience
                or original.external_management_ref
                != envelope.external_management_ref
            ):
                raise PermissionError(
                    "reply immutable routing/binding mismatch"
                )
            scope, route_id, route_revision = (
                original.scope,
                original.route_id,
                original.route_revision,
            )
        operation = (
            PartnerOperation.SUBMIT_REQUEST
            if envelope.command_type == "start_workflow"
            else PartnerOperation.REPLY
        )
        payload_hash = sha256(
            json.dumps(
                envelope.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        async with self.workflows.uows() as tx:
            await self.identity.check_scope_active(scope, tx)
            await self.routing.revalidate(
                scope,
                route_id,
                route_revision,
                partner_actor,
                audience,
                operation,
                tx,
            )
            raw_claim = await self.commands.claim_or_read(
                partner_actor,
                envelope.external_request_id,
                envelope.command_type.value,
                envelope.workflow_id,
                payload_hash,
                tx,
            )
            claim = CommandClaimResult.model_validate(raw_models(raw_claim))
            if claim.is_new:
                message = dict(
                    request_id=claim.request_id, text=envelope.message.text
                )
                if envelope.command_type == "start_workflow":
                    record = await self.workflows.start_with_binding(
                        scope, partner_actor, audience, message, tx
                    )
                else:
                    bundle = await self.workflows.repository.load(
                        scope, envelope.workflow_id, tx
                    )
                    record = require_binding(bundle, scope, audience)
                    message["expected_revision"] = record.revision
                    record = await self.workflows.accept_reply(
                        scope,
                        partner_actor,
                        audience,
                        record.workflow_id,
                        message,
                        tx,
                    )
                if (
                    record.route_id != route_id
                    or record.route_revision != route_revision
                ):
                    raise WorkflowConflict(
                        "bootstrap/reply route differs from authorized route"
                    )
                await self.requests.attach(
                    InboundRequest(
                        request_id=claim.request_id,
                        scope=scope,
                        audience=audience,
                        external_request_id=envelope.external_request_id,
                        external_management_ref=(
                            envelope.external_management_ref  # Public ref.
                        ),
                        payload_hash=payload_hash,
                        route_id=route_id,
                        route_revision=route_revision,
                        conversation_id=record.conversation_id,
                        workflow_id=record.workflow_id,
                        group_id=record.group_id,
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
        self._actor(partner_actor, external_user_id)
        view = RequestView.model_validate(
            raw_models(
                await self.requests.read(
                    partner_actor, request_id, external_user_id
                )
            )
        )
        request = view.request
        if (
            request.request_id != request_id
            or request.audience.partner_client_id
            != partner_actor.partner_client_id
            or request.audience.external_user_id != external_user_id
        ):
            raise PermissionError("request audience mismatch")
        await self.identity.check_scope_active(request.scope)
        await self.routing.revalidate(
            request.scope,
            request.route_id,
            request.route_revision,
            partner_actor,
            request.audience,
            PartnerOperation.READ_RESULT,
        )
        bundle = validated_bundle(
            await self.workflows.repository.load(
                request.scope, request.workflow_id
            )
        )
        record = require_binding(bundle, request.scope, request.audience)
        if (
            record.conversation_id != request.conversation_id
            or record.group_id != request.group_id
        ):
            raise PermissionError("request immutable binding mismatch")
        if view.result is not None and any(
            m.workflow_id != record.workflow_id for m in view.result.messages
        ):
            raise PermissionError("request result contains foreign workflow")
        status = request.status
        if (status == RequestStatus.COMPLETED) != (view.result is not None):
            raise WorkflowConflict(
                "request status/result are not a consistent read"
            )
        if view.error is not None and view.error.request_id != request_id:
            raise PermissionError("public error belongs to another request")
        failed = status in {RequestStatus.FAILED, RequestStatus.BLOCKED}
        if failed != (view.error is not None):
            raise WorkflowConflict(
                "request status/error are not a consistent read"
            )
        error = view.error
        pending = status in {
            RequestStatus.ACCEPTED,
            RequestStatus.QUEUED,
            RequestStatus.RUNNING,
        }
        if record.state == "closed" and pending:
            status, pending = RequestStatus.BLOCKED, False
            error = PublicError(
                code="WORKFLOW_CLOSED",
                message="The workflow closed before this request completed.",
                request_id=request_id,
                retryable=False,
            )
        action = "watch_request" if pending else next_action(record.state)
        if (
            status in {RequestStatus.FAILED, RequestStatus.BLOCKED}
            and record.state != "closed"
        ):
            action = "resolve_attention"
        query = urlencode({"external_user_id": external_user_id})
        request_path = (
            f"/workforce/v1/partner/requests/{quote(request_id, safe='')}"
        )
        conversation_id = quote(record.conversation_id, safe="")
        conversation_path = (
            f"/workforce/v1/partner/conversations/{conversation_id}"
        )
        return InboundReceipt(
            request_id=request_id,
            request_status=status,
            workflow_state=record.state,
            workflow_revision=record.revision,
            next_action=action,
            external_ticket_id=request.audience.external_ticket_id,
            conversation_id=record.conversation_id,
            workflow_id=record.workflow_id,
            ticket_id=record.ticket_id,
            result=view.result,
            error=error,
            accepted_at=request.accepted_at,
            completed_at=request.completed_at,
            status_url=f"{request_path}?{query}",
            conversation_url=f"{conversation_path}?{query}",
            event_stream_url=f"{conversation_path}/events?{query}",
        )

    async def close_workflow(self, partner_actor, scope, workflow_id, command):
        raw_command = raw_models(command)
        if (
            type(raw_command.get("expected_revision")) is not int
            or type(raw_command.get("stop_tracking_only", False)) is not bool
        ):
            raise ValueError(
                "close requires strict revision and tracking flag"
            )
        command = CloseWorkflowCommand.model_validate(raw_command)
        self._actor(partner_actor, command.external_user_id)
        bundle = await self.workflows.repository.load(scope, workflow_id)
        record = bundle.workflow
        if (
            record.audience.external_user_id != command.external_user_id
            or record.audience.partner_client_id
            != partner_actor.partner_client_id
            or record.audience.external_ticket_id != command.external_ticket_id
            or record.audience.external_conversation_id
            != command.external_conversation_id
        ):
            raise PermissionError("close immutable binding mismatch")
        payload_hash = sha256(
            json.dumps(
                command.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        async with self.workflows.uows() as tx:
            await self.identity.check_scope_active(scope, tx)
            await self.routing.revalidate(
                scope,
                record.route_id,
                record.route_revision,
                partner_actor,
                record.audience,
                PartnerOperation.CLOSE_WORKFLOW,
                tx,
            )
            claim = CommandClaimResult.model_validate(
                dict(
                    await self.commands.claim_or_read(
                        partner_actor,
                        command.external_request_id,
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
                    record.audience,
                    {**command.model_dump(), "workflow_id": workflow_id},
                    tx,
                )
                await self.requests.attach(
                    InboundRequest(
                        request_id=claim.request_id,
                        scope=scope,
                        audience=record.audience,
                        external_request_id=command.external_request_id,
                        external_management_ref="bound_close",
                        payload_hash=payload_hash,
                        route_id=record.route_id,
                        route_revision=record.route_revision,
                        workflow_id=workflow_id,
                        conversation_id=record.conversation_id,
                        group_id=record.group_id,
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
            partner_actor, claim.request_id, command.external_user_id
        )

    async def wait_for_result(
        self, partner_actor, request_id, external_user_id, deadline
    ):
        if deadline.tzinfo is None:
            raise ValueError("bounded wait deadline must be timezone-aware")
        budget = max(0, (deadline - self.clock()).total_seconds())
        started = monotonic()

        def remaining_budget():
            return min(
                (deadline - self.clock()).total_seconds(),
                budget - (monotonic() - started),
            )

        while True:
            receipt = await self.read_result(
                partner_actor, request_id, external_user_id
            )
            if receipt.request_status not in {
                RequestStatus.ACCEPTED,
                RequestStatus.QUEUED,
                RequestStatus.RUNNING,
            }:
                return receipt
            remaining = remaining_budget()
            if remaining <= 0:
                return receipt
            view = await self.requests.read(
                partner_actor, request_id, external_user_id
            )
            duration = min(remaining_budget(), self.wait_slice_seconds)
            if duration <= 0:
                continue
            waiter = asyncio.create_task(
                self.completion_signals.wait_for_completion(
                    view.request.scope, request_id, duration
                )
            )
            waiter.add_done_callback(_consume_signal_result)
            try:
                # asyncio.wait bounds this request independently of a broken
                # signal adapter, even when cancellation cleanup is slow.
                done, _ = await asyncio.wait({waiter}, timeout=duration)
                if done:
                    waiter.result()
            except Exception:
                # Reread durable state after waiting; never busy-loop on error.
                await asyncio.sleep(max(0, min(remaining_budget(), duration)))
            finally:
                if not waiter.done():
                    waiter.cancel()

    async def stream_events(
        self, partner_actor, conversation_id, external_user_id, cursor=None
    ):
        self._actor(partner_actor, external_user_id)
        async for event in self.events.subscribe(
            partner_actor, conversation_id, cursor
        ):
            yield event


def receipt_http_status(receipt: InboundReceipt) -> int:
    """Only a still-pending result at the bounded-wait deadline maps to 202."""
    return (
        202
        if receipt.request_status
        in {
            RequestStatus.ACCEPTED,
            RequestStatus.QUEUED,
            RequestStatus.RUNNING,
        }
        else 200
    )
