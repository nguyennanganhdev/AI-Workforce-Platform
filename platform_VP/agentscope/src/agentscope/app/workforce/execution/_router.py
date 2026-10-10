# -*- coding: utf-8 -*-
"""
Execution HTTP factory. Composition injects trusted identity dependencies.
"""

from typing import Any

import json

from ..contracts import PartnerApprovalDecision
from ._utils import ExecutionError, value


def create_router(
    gateway: Any,
    approvals: Any,
    partner_approvals: Any,
    provider_ingress: Any,
    manager_dependency: Any,
    customer_dependency: Any,
    provider_auth: Any,
    max_provider_bytes: Any = 262144,
) -> Any:
    """
    No permissive defaults; authenticate provider raw bytes before parsing.
    """
    from fastapi import APIRouter, Depends, Request
    from fastapi.responses import JSONResponse

    # FastAPI evaluates annotations in the module globals for locally-defined
    # routes.
    globals()["Request"] = Request
    router = APIRouter(prefix="/workforce/v1", tags=["workforce-execution"])

    async def respond(action: Any) -> Any:
        try:
            return await action()
        except ExecutionError as error:
            return JSONResponse(error.public(), status_code=error.status)
        except (ValueError, UnicodeError):
            invalid_error = ExecutionError("REQUEST_BODY_INVALID", 422)
            return JSONResponse(
                invalid_error.public(), status_code=invalid_error.status
            )

    @router.post("/provider/job-events", status_code=202)
    async def provider_events(request: Request) -> Any:
        async def action() -> Any:
            raw = bytearray()
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw) > max_provider_bytes:
                    raise ExecutionError("PAYLOAD_TOO_LARGE", 413)
            principal = await provider_auth.authenticate(
                bytes(raw), dict(request.headers)
            )
            try:
                body = json.loads(raw)
            except (ValueError, UnicodeError):
                raise ExecutionError("PROVIDER_EVENT_INVALID", 422) from None
            return await provider_ingress.accept(principal, body)

        return await respond(action)

    @router.get("/provider/event-receipts/{receipt_id}")
    async def provider_receipt(receipt_id: str, request: Request) -> Any:
        async def action() -> Any:
            principal = await provider_auth.authenticate(
                b"", dict(request.headers)
            )
            return await provider_ingress.read_receipt(principal, receipt_id)

        return await respond(action)

    @router.get("/executions/{call_id}")
    async def execution(
        call_id: str, principal: Any = Depends(manager_dependency)
    ) -> Any:
        async def action() -> Any:
            record = await gateway.get_call(value(principal)["scope"], call_id)
            return {
                k: record.get(k)
                for k in (
                    "call_id",
                    "status",
                    "output",
                    "error",
                    "external_transaction_id",
                    "started_at",
                    "finished_at",
                    "approval_id",
                )
            }

        return await respond(action)

    @router.get("/booking-operations/{operation_id}")
    async def booking(
        operation_id: str, principal: Any = Depends(manager_dependency)
    ) -> Any:
        async def action() -> Any:
            record = await gateway.repo.read(
                "bookings", value(principal)["scope"], operation_id
            )
            return {
                k: record.get(k)
                for k in ("id", "call_id", "status", "external_transaction_id")
            }

        return await respond(action)

    @router.get("/conversations/{conversation_id}/approvals")
    async def list_approvals(
        conversation_id: str, principal: Any = Depends(manager_dependency)
    ) -> Any:
        async def action() -> Any:
            principal_data = value(principal)
            await approvals.runtime.authorize_conversation(
                principal_data["scope"], conversation_id
            )
            async with gateway.repo.transaction() as uow:
                # Conversation is intentionally a JSON payload field; filter by
                # owner in SQL before inspecting its child records.
                rows = await gateway.repo.find(
                    "approvals", {}, uow, principal_data["scope"]
                )
                return {
                    "items": [
                        approval_projection(r)
                        for r in rows
                        if r["conversation_id"] == conversation_id
                    ],
                    "next_cursor": None,
                }

        return await respond(action)

    @router.post("/approvals/{approval_id}/decision")
    async def manager_decision(
        approval_id: str,
        request: Request,
        principal: Any = Depends(manager_dependency),
    ) -> Any:
        async def action() -> Any:
            body = await request.json()
            check_decision(body, partner=False)
            principal_data = value(principal)
            record = await approvals.decide_approval(
                principal_data["scope"],
                approval_id,
                body["decision"],
                principal_data["actor"],
                arguments_hash=body["arguments_hash"],
                quote_hash=body["quote_hash"],
            )
            return approval_projection(record)

        return await respond(action)

    @router.post("/partner/approvals/{approval_id}/decision", status_code=202)
    async def partner_decision(
        approval_id: str,
        request: Request,
        actor: Any = Depends(customer_dependency),
    ) -> Any:
        async def action() -> Any:
            body = await request.json()
            check_decision(body, partner=True)
            decision = PartnerApprovalDecision.model_validate(body)
            return await partner_approvals.decide(actor, approval_id, decision)

        return await respond(action)

    return router


def check_decision(body: Any, partner: Any) -> Any:
    """
    Use the canonical partner DTO; manager view input remains execution-owned.
    """
    required = {"decision", "arguments_hash", "quote_hash"}
    if partner:
        try:
            PartnerApprovalDecision.model_validate(body)
        except ValueError:
            raise ExecutionError("APPROVAL_DECISION_INVALID", 422) from None
        if type(body["expected_revision"]) is not int:
            raise ExecutionError("APPROVAL_DECISION_INVALID", 422)
        return
    if (
        not isinstance(body, dict)
        or set(body) != required
        or any(
            not isinstance(body[k], str) or not body[k]
            for k in required - {"expected_revision"}
        )
        or body["decision"] not in {"approve", "reject"}
    ):
        raise ExecutionError("APPROVAL_DECISION_INVALID", 422)


def approval_projection(record: Any) -> Any:
    """No scope, runtime group, credential or raw actor authentication data."""
    public = {
        "approval_id": record["id"],
        **{
            k: record.get(k)
            for k in (
                "call_id",
                "status",
                "arguments_hash",
                "quote_hash",
                "quote",
                "expires_at",
                "decision_history",
                "allowed_decider",
                "revision",
            )
        },
    }
    public["decision_history"] = [
        {"decision": item["decision"], "at": item["at"]}
        for item in record["decision_history"]
    ]
    return public
