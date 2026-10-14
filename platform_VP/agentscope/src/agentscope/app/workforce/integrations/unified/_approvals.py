"""Partner approvals of unified mode (decision D1: the end user decides).

A partner-session tool that needs consent parks its call (the chat consent
machinery). The runner turns each parked call into an approval and publishes
``approval.required`` with what the partner must send back (contract 9.8).
The partner's decision wakes the workflow with an approval cause; the runner
then resumes the parked call with that decision.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy import insert, select, update

from ...contracts import ActorContext
from ._tables import approvals

DEFAULT_TTL_SECONDS = 86_400


def _now() -> datetime:
    return datetime.now(UTC)


def arguments_hash(tool_name: str, arguments: Any) -> str:
    canonical = json.dumps(
        {"tool": tool_name, "arguments": arguments},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class DecisionBody(BaseModel):
    schema_version: str = Field(pattern="^1$")
    external_request_id: str = Field(min_length=1, max_length=200)
    external_user_id: str = Field(min_length=1, max_length=200)
    external_ticket_id: str | None = Field(default=None, max_length=200)
    external_conversation_id: str = Field(min_length=1, max_length=400)
    workflow_id: str = Field(min_length=1, max_length=255)
    decision: Literal["approve", "reject"]
    expected_revision: int = Field(ge=1)
    arguments_hash: str = Field(min_length=1, max_length=200)
    quote_ref: str | None = Field(default=None, max_length=200)


class ApprovalError(Exception):
    def __init__(self, status: int, code: str, details: dict | None = None) -> None:
        super().__init__(code)
        self.status, self.code, self.details = status, code, details or {}


class CaseApprovals:
    """Approval rows of partner workflows and their public events."""

    def __init__(self, uows: Callable[[], Any], events: Any = None) -> None:
        self._uows = uows
        self._events = events

    def attach_events(self, events: Any) -> None:
        self._events = events

    @staticmethod
    def approval_id(workflow_id: str, tool_call_id: str) -> str:
        return "ap_" + hashlib.sha256(f"{workflow_id}|{tool_call_id}".encode()).hexdigest()[:32]

    async def get(self, approval_id: str) -> dict | None:
        async with self._uows() as uow:
            row = (
                await uow.execute(select(approvals).where(approvals.c.approval_id == approval_id))
            ).mappings().first()
        return dict(row) if row else None

    async def open(
        self,
        workflow: Any,
        actions: list[Any],
        *,
        expected_revision: int,
        ttl_seconds: int,
        describe: Callable[[str], str],
    ) -> list[str]:
        """One approval per parked call; publishes ``approval.required`` once."""

        ids: list[str] = []
        for action in actions:
            call = action.tool_call
            approval_id = self.approval_id(workflow.workflow_id, call.id)
            ids.append(approval_id)
            if await self.get(approval_id) is not None:
                continue
            try:
                arguments = json.loads(call.input or "{}")
            except ValueError:
                arguments = {"raw": call.input}
            now = _now()
            expires_at = now + timedelta(seconds=ttl_seconds or DEFAULT_TTL_SECONDS)
            summary = {"text": describe(call.name)}
            row = {
                "approval_id": approval_id,
                "workflow_id": workflow.workflow_id,
                "session_id": action.session_id,
                "agent_id": action.agent_id,
                "tool_call_id": call.id,
                "tool_name": call.name,
                "arguments": arguments,
                "arguments_hash": arguments_hash(call.name, arguments),
                "expected_revision": expected_revision,
                "summary": summary,
                "status": "pending",
                "expires_at": expires_at,
                "decided_at": None,
                "created_at": now,
            }
            async with self._uows() as uow:
                await uow.execute(insert(approvals).values(**row))
                if self._events is not None:
                    await self._events.write(
                        workflow,
                        "approval.required",
                        {
                            "approval_id": approval_id,
                            "summary": summary,
                            "expires_at": expires_at.isoformat(),
                            "arguments_hash": row["arguments_hash"],
                            "expected_revision": expected_revision,
                        },
                        uow,
                        approval_id,
                    )
                await uow.commit()
        return ids

    async def decide(
        self,
        approval_id: str,
        body: DecisionBody,
        actor: ActorContext,
        *,
        workflow: Any,
        requests: Any,
        workflows: Any,
        trigger_ids: Callable[[], str],
    ) -> dict:
        """Record the partner's decision and wake the workflow (one transaction)."""

        audience = workflow.audience
        if (
            body.external_conversation_id != audience.external_conversation_id
            or body.external_ticket_id != audience.external_ticket_id
            or body.external_user_id != audience.external_user_id
        ):
            raise ApprovalError(403, "AUTHORIZATION_DENIED")
        row = await self.get(approval_id)
        if row is None or row["workflow_id"] != body.workflow_id:
            raise ApprovalError(404, "RESOURCE_NOT_FOUND")
        status = "approved" if body.decision == "approve" else "rejected"
        answer = {
            "approval_id": approval_id,
            "status": status,
            "external_ticket_id": audience.external_ticket_id,
            "workflow_id": body.workflow_id,
        }
        if row["status"] == status:
            return {**answer, "accepted_at": (row["decided_at"] or _now()).isoformat()}
        if row["status"] != "pending":
            raise ApprovalError(409, "APPROVAL_NOT_PENDING", {"status": row["status"]})
        expires_at = row["expires_at"]
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= _now():
            raise ApprovalError(409, "APPROVAL_EXPIRED")
        if body.arguments_hash != row["arguments_hash"]:
            raise ApprovalError(409, "APPROVAL_MISMATCH")
        if body.expected_revision != row["expected_revision"]:
            raise ApprovalError(
                409,
                "REVISION_CONFLICT",
                {"current_revision": row["expected_revision"]},
            )
        now = _now()
        payload_hash = hashlib.sha256(
            json.dumps([approval_id, status], separators=(",", ":")).encode()
        ).hexdigest()
        async with self._uows() as uow:
            moved = await uow.execute(
                update(approvals)
                .where(approvals.c.approval_id == approval_id, approvals.c.status == "pending")
                .values(status=status, decided_at=now),
            )
            if moved.rowcount != 1:
                raise ApprovalError(409, "APPROVAL_NOT_PENDING")
            claim = await requests.claim_or_read(
                actor,
                body.external_request_id,
                "approval_decision",
                body.workflow_id,
                payload_hash,
                uow,
            )
            if self._events is not None:
                await self._events.write(
                    workflow,
                    "approval.resolved",
                    {"approval_id": approval_id, "status": status},
                    uow,
                    approval_id,
                )
            await workflows.enqueue_trigger(
                workflow.scope,
                {
                    "trigger_id": trigger_ids(),
                    "workflow_id": body.workflow_id,
                    "cause": {
                        "kind": "approval",
                        "request_id": claim.request_id,
                        "approval_id": approval_id,
                    },
                },
                uow,
            )
            await uow.commit()
        return {**answer, "accepted_at": now.isoformat()}


__all__ = ["ApprovalError", "CaseApprovals", "DecisionBody", "arguments_hash"]
