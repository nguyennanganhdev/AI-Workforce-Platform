"""FastAPI factory for customer request, result, history, snapshot and SSE."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import ValidationError

from ..contracts import ActorContext, CloseWorkflowCommand
from ..execution._utils import ExecutionError
from ._ingress import receipt_http_status
from .partner_events import EventCursorExpired
from .workflows import (
    WorkflowBindingMismatch,
    WorkflowClosed,
    WorkflowConflict,
    WorkflowTicketAlreadyBound,
)


def create_router(
    ingress: Any,
    conversation_events: Any,
    customer_dependency: Any,
    *,
    bounded_wait_seconds: float = 8.0,
    max_customer_bytes: int = 262_144,
    metric_sink: Any = None,
) -> Any:
    """Build routes only; C7 owns mounting and application composition."""
    if bounded_wait_seconds < 0:
        raise ValueError("bounded_wait_seconds must not be negative")
    if max_customer_bytes < 1:
        raise ValueError("max_customer_bytes must be positive")

    from fastapi import APIRouter, Depends, Header, Query, Request
    from fastapi.responses import JSONResponse, StreamingResponse

    from ..foundation.event_delivery import (
        SSE_CONNECTIONS,
        SSE_REPLAYS,
        NullMetricSink,
    )

    globals()["Request"] = Request
    router = APIRouter(prefix="/workforce/v1", tags=["workforce-orchestration"])
    customer_principal = Depends(customer_dependency)
    metrics = metric_sink or NullMetricSink()

    def actor(value: Any) -> ActorContext:
        if isinstance(value, dict) and "actor" in value:
            value = value["actor"]
        return ActorContext.model_validate(value)

    def customer(value: Any, external_user_id: str) -> ActorContext:
        verified = actor(value)
        if verified.external_user_id != external_user_id:
            raise PermissionError("external user does not match credential")
        return verified

    async def json_body(request: Request) -> Any:
        raw = bytearray()
        async for chunk in request.stream():
            raw.extend(chunk)
            if len(raw) > max_customer_bytes:
                raise _PayloadTooLarge
        return json.loads(raw)

    async def respond(action):
        try:
            return await action()
        except ExecutionError as error:
            return JSONResponse(error.public(), status_code=error.status)
        except EventCursorExpired:
            return JSONResponse(
                {
                    "error": {
                        "code": "EVENT_CURSOR_EXPIRED",
                        "message": "Reload the conversation snapshot.",
                    }
                },
                status_code=410,
            )
        except WorkflowBindingMismatch:
            return JSONResponse(
                {"error": {"code": "WORKFLOW_BINDING_MISMATCH"}},
                status_code=409,
            )
        except WorkflowTicketAlreadyBound:
            return JSONResponse(
                {"error": {"code": "TICKET_ALREADY_BOUND"}},
                status_code=409,
            )
        except PermissionError:
            return JSONResponse(
                {"error": {"code": "AUTHORIZATION_DENIED"}},
                status_code=403,
            )
        except KeyError:
            return JSONResponse(
                {"error": {"code": "RESOURCE_NOT_FOUND"}},
                status_code=404,
            )
        except _PayloadTooLarge:
            return JSONResponse(
                {"error": {"code": "PAYLOAD_TOO_LARGE"}}, status_code=413
            )
        except (WorkflowClosed, WorkflowConflict):
            return JSONResponse(
                {
                    "error": {
                        "code": "WORKFLOW_CONFLICT",
                        "message": "The workflow state changed; reload and retry.",
                    }
                },
                status_code=409,
            )
        except (ValidationError, ValueError, TypeError):
            return JSONResponse(
                {"error": {"code": "REQUEST_BODY_INVALID"}},
                status_code=422,
            )

    @router.post("/partner/requests")
    async def submit_request(
        request: Request,
        principal: Any = customer_principal,
    ) -> Any:
        async def action():
            verified = actor(principal)
            receipt = await ingress.accept(verified, await json_body(request))
            if receipt_http_status(receipt) == 202 and bounded_wait_seconds:
                receipt = await ingress.wait_for_result(
                    verified,
                    receipt.request_id,
                    verified.external_user_id,
                    datetime.now(UTC) + timedelta(seconds=bounded_wait_seconds),
                )
            return JSONResponse(
                receipt.model_dump(mode="json"),
                status_code=receipt_http_status(receipt),
            )

        return await respond(action)

    @router.get("/partner/requests/{request_id}")
    async def request_result(
        request_id: str,
        external_user_id: str = Query(min_length=1),
        principal: Any = customer_principal,
    ) -> Any:
        return await respond(
            lambda: ingress.read_result(actor(principal), request_id, external_user_id)
        )

    @router.get("/partner/conversations/{conversation_id}")
    async def conversation_snapshot(
        conversation_id: str,
        external_user_id: str = Query(min_length=1),
        principal: Any = customer_principal,
    ) -> Any:
        return await respond(
            lambda: conversation_events.snapshot(
                customer(principal, external_user_id), conversation_id
            )
        )

    @router.get("/partner/conversations/{conversation_id}/event-history")
    async def event_history(
        conversation_id: str,
        external_user_id: str = Query(min_length=1),
        after_cursor: str | None = None,
        limit: int = Query(default=100, ge=1, le=500),
        principal: Any = customer_principal,
    ) -> Any:
        return await respond(
            lambda: conversation_events.list_after(
                customer(principal, external_user_id),
                conversation_id,
                after_cursor,
                limit,
            )
        )

    @router.get("/partner/conversations/{conversation_id}/events")
    async def event_stream(
        conversation_id: str,
        external_user_id: str = Query(min_length=1),
        after_cursor: str | None = None,
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
        principal: Any = customer_principal,
    ) -> Any:
        async def action():
            if (
                after_cursor is not None
                and last_event_id is not None
                and after_cursor != last_event_id
            ):
                raise ValueError("cursor sources disagree")
            cursor = last_event_id or after_cursor
            verified = customer(principal, external_user_id)
            # Fail auth/expired cursor before Starlette sends SSE headers.
            await conversation_events.list_after(verified, conversation_id, cursor, 1)
            metrics.increment(
                SSE_CONNECTIONS,
                labels={"result": "accepted"},
            )
            if cursor is not None:
                metrics.increment(
                    SSE_REPLAYS,
                    labels={
                        "cursor_source": ("last_event_id" if last_event_id else "query")
                    },
                )
            return StreamingResponse(
                conversation_events.stream(verified, conversation_id, cursor),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Content-Encoding": "identity",
                    "X-Accel-Buffering": "no",
                },
            )

        return await respond(action)

    @router.post("/partner/workflows/{workflow_id}/close")
    async def close_workflow(
        workflow_id: str,
        request: Request,
        principal: Any = customer_principal,
    ) -> Any:
        async def action():
            verified = actor(principal)
            command = CloseWorkflowCommand.model_validate(await json_body(request))
            original = await ingress.requests.resolve_workflow_request(
                verified, workflow_id, command.external_user_id
            )
            receipt = await ingress.close_workflow(
                verified, original.scope, workflow_id, command
            )
            return JSONResponse(receipt.model_dump(mode="json"), status_code=200)

        return await respond(action)

    return router


__all__ = ["create_router"]


class _PayloadTooLarge(ValueError):
    pass
