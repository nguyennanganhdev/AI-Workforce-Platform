# -*- coding: utf-8 -*-
"""Pre-network durable intents and atomic consent consumption."""

from typing import Any

from ._effects import SIDE_EFFECTS, classify
from ._utils import (
    ExecutionError,
    audience_ref,
    digest,
    freeze,
    owner,
    timestamp,
    utc_now,
)


class TransactionService:
    """
    A crash after intent commit is recoverable as unknown, never a blind retry.
    """

    def __init__(
        self, repository: Any, approvals: Any, clock: Any = utc_now
    ) -> None:
        self.repo, self.approvals, self.clock = repository, approvals, clock

    @staticmethod
    def fingerprint(request: Any) -> Any:
        """
        Identity includes the key and immutable call/run/version/argument
        tuple.
        """
        return digest(
            {
                **{
                    k: request[k]
                    for k in (
                        "call_id",
                        "run_id",
                        "agent_id",
                        "version_id",
                        "tool_version_id",
                        "arguments",
                    )
                },
                "idempotency_key": request.get("idempotency_key")
                or request["call_id"],
            }
        )

    async def reserve(
        self,
        scope: Any,
        context: Any,
        request: Any,
        descriptor: Any,
        quote: Any,
        uow: Any,
    ) -> Any:
        """
        Return (stored call, may_dispatch); serialize duplicate clicks in DB.
        """
        key = request.get("idempotency_key") or request["call_id"]
        fingerprint = self.fingerprint(request)
        if request.get(
            "arguments_hash", digest(request["arguments"])
        ) != digest(request["arguments"]):
            raise ExecutionError("ARGUMENTS_HASH_MISMATCH", 422)
        record = {
            "id": request["call_id"],
            "call_id": request["call_id"],
            "scope": owner(scope),
            "run_id": request["run_id"],
            "workflow_id": context.get("workflow_id"),
            "group_id": context.get("group_id"),
            "conversation_id": context["conversation_id"],
            "audience_ref": audience_ref(context.get("partner_audience")),
            "idempotency_key": key,
            "fingerprint": fingerprint,
            "request": freeze(request),
            "revision": 1,
            "status": "proposed",
            "effect": classify(descriptor),
            "output": None,
            "error": None,
            "started_at": timestamp(self.clock()),
        }
        stored = await self.repo.insert_once(
            "calls",
            record,
            {"run_id": request["run_id"], "idempotency_key": key},
            uow,
            scope,
        )
        if stored["fingerprint"] != fingerprint:
            raise ExecutionError("IDEMPOTENCY_CONFLICT")
        if (
            stored["workflow_id"] != context.get("workflow_id")
            or stored["group_id"] != context.get("group_id")
            or audience_ref(stored["audience_ref"])
            != audience_ref(context.get("partner_audience"))
        ):
            raise ExecutionError("WORKFLOW_BINDING_MISMATCH")
        if stored["status"] not in {"proposed", "awaiting_approval"}:
            return stored, False
        if stored["effect"] in SIDE_EFFECTS:
            if not request.get("approval_id"):
                approval = await self.approvals.create(
                    scope, context, request, quote, uow
                )
                stored["approval_id"] = approval["id"]
                stored["status"] = "awaiting_approval"
                return await self.repo.save(
                    "calls", stored, stored["revision"], uow
                ), False
            if request["approval_id"] != stored.get("approval_id"):
                raise ExecutionError("APPROVAL_CALL_MISMATCH")
            await self.approvals.consume(
                scope, request["approval_id"], context, request, quote, uow
            )
        stored["status"] = "executing"
        stored["request"] = freeze(request)
        stored = await self.repo.save("calls", stored, stored["revision"], uow)
        if stored["effect"] in SIDE_EFFECTS:
            await self.repo.insert_once(
                "bookings",
                {
                    "id": stored["id"],
                    "scope": owner(scope),
                    "call_id": stored["id"],
                    "revision": 1,
                    "status": "executing",
                    "external_transaction_id": None,
                    "provider_reference": stored["id"],
                    "run_id": context["run_id"],
                    "workflow_id": context.get("workflow_id"),
                    "audience_ref": audience_ref(
                        context.get("partner_audience")
                    ),
                    "tool_version_id": request["tool_version_id"],
                    "quote_ref": quote["quote_ref"],
                },
                {"call_id": stored["id"]},
                uow,
                scope,
            )
        return stored, True

    async def finish(
        self,
        scope: Any,
        call_id: Any,
        status: Any,
        output: Any = None,
        error: Any = None,
        external_transaction_id: Any = None,
        uow: Any = None,
    ) -> Any:
        """
        Record the actual provider outcome even when the run was cancelled.
        """
        if uow is None:
            async with self.repo.transaction() as transaction:
                return await self.finish(
                    scope,
                    call_id,
                    status,
                    output,
                    error,
                    external_transaction_id,
                    transaction,
                )
        call = await self.repo.get("calls", call_id, uow, scope, lock=True)
        if call["status"] != "executing":
            return call
        call.update(
            status=status,
            output=freeze(output),
            error=error,
            external_transaction_id=external_transaction_id,
            finished_at=timestamp(self.clock()),
        )
        call = await self.repo.save("calls", call, call["revision"], uow)
        booking = await self.repo.get(
            "bookings", call_id, uow, scope, lock=True
        )
        if booking:
            booking.update(
                status=status, external_transaction_id=external_transaction_id
            )
            await self.repo.save("bookings", booking, booking["revision"], uow)
        return call

    async def recover_abandoned(self, scope: Any, call_id: Any) -> Any:
        """
        Called only by the fenced worker after its execution lease expires.
        """
        return await self.finish(
            scope, call_id, "unknown", error="EXECUTION_INTERRUPTED"
        )
