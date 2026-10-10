# -*- coding: utf-8 -*-
"""Durable transaction consent, separate from the agent's parked HITL state."""

from typing import Any

from datetime import timedelta

from ._utils import (
    ExecutionError,
    audience_ref,
    digest,
    freeze,
    instant,
    new_id,
    owner,
    require_scope,
    timestamp,
    utc_now,
    value,
)


class ApprovalService:
    """
    Quotes and HITL projection are ports; neither model text nor UI grants
    consent.
    """

    def __init__(
        self,
        repository: Any,
        runtime: Any,
        quotes: Any,
        hitl: Any,
        clock: Any = utc_now,
        ttl_seconds: Any = 900,
    ) -> None:
        self.repo, self.runtime, self.quotes, self.hitl = (
            repository,
            runtime,
            quotes,
            hitl,
        )
        self.clock, self.ttl_seconds = clock, ttl_seconds

    async def verified_quote(
        self, scope: Any, context: Any, request: Any, descriptor: Any
    ) -> Any:
        """
        Ask the provider-specific adapter to validate price, dates and quote
        version.
        """
        quote = freeze(
            await self.quotes.validate(scope, context, request, descriptor)
        )
        required = {
            "quote_ref",
            "quote_version",
            "provider",
            "option",
            "dates",
            "amount",
            "fees",
            "cancellation_terms",
            "expires_at",
        }
        if not required.issubset(quote):
            raise ExecutionError("VERIFIED_QUOTE_REQUIRED", 422)
        if instant(quote["expires_at"]) <= self.clock():
            raise ExecutionError("QUOTE_EXPIRED")
        return quote

    async def create(
        self, scope: Any, context: Any, request: Any, quote: Any, uow: Any
    ) -> Any:
        """Persist consent and the existing HITL event in one transaction."""
        allowed = context.get("allowed_decider")
        if not allowed or allowed.get("kind") not in {"manager", "partner"}:
            raise ExecutionError("CONSENT_POLICY_REQUIRED", 403)
        expires = min(
            instant(quote["expires_at"]),
            self.clock() + timedelta(seconds=self.ttl_seconds),
        )
        record = {
            "id": new_id(),
            "scope": owner(scope),
            "revision": 1,
            "run_id": context["run_id"],
            "workflow_id": context.get("workflow_id"),
            "conversation_id": context["conversation_id"],
            "group_id": context.get("group_id"),
            "call_id": request["call_id"],
            "arguments_hash": digest(request["arguments"]),
            "quote": quote,
            "quote_hash": digest(quote),
            "expires_at": timestamp(expires),
            "status": "pending",
            "allowed_decider": freeze(allowed),
            "audience_ref": audience_ref(context.get("partner_audience")),
            "decision_history": [],
        }
        stored = await self.repo.insert_once(
            "approvals", record, {"call_id": request["call_id"]}, uow, scope
        )
        if stored["id"] == record["id"]:
            await self.hitl.required(scope, stored, context, uow=uow)
        return stored

    async def authorize(
        self, scope: Any, approval: Any, actor: Any, audience: Any, uow: Any
    ) -> Any:
        """
        Revalidate the original route, run and audience before a read or
        decision.
        """
        require_scope(scope, approval)
        actor = value(actor)
        allowed = approval["allowed_decider"]
        if actor.get("kind") != allowed["kind"]:
            raise ExecutionError("APPROVAL_DECIDER_FORBIDDEN", 403)
        for key, expected in allowed.items():
            if actor.get(key) != expected:
                raise ExecutionError("APPROVAL_DECIDER_FORBIDDEN", 403)
        if allowed["kind"] == "partner" and audience_ref(
            audience
        ) != audience_ref(approval["audience_ref"]):
            raise ExecutionError("APPROVAL_AUDIENCE_FORBIDDEN", 403)
        context = value(
            await self.runtime.load(scope, approval["run_id"], uow=uow)
        )
        if (
            context.get("workflow_id") != approval["workflow_id"]
            or context.get("group_id") != approval["group_id"]
            or context.get("conversation_id") != approval["conversation_id"]
            or audience_ref(context.get("partner_audience"))
            != audience_ref(approval["audience_ref"])
        ):
            raise ExecutionError("WORKFLOW_BINDING_MISMATCH")
        await self.runtime.revalidate(
            scope, context, "submit_consent", uow=uow
        )
        return context

    async def decide_in_uow(
        self,
        scope: Any,
        approval_id: Any,
        decision: Any,
        actor: Any,
        audience: Any,
        arguments_hash: Any,
        quote_hash: Any,
        uow: Any,
    ) -> Any:
        """Resolve once; a repeated approved decision never consumes twice."""
        approval = await self.repo.get(
            "approvals", approval_id, uow, scope, lock=True
        )
        context = await self.authorize(scope, approval, actor, audience, uow)
        if decision not in {"approve", "reject"}:
            raise ExecutionError("APPROVAL_DECISION_INVALID", 422)
        if (
            arguments_hash != approval["arguments_hash"]
            or quote_hash != approval["quote_hash"]
        ):
            raise ExecutionError("APPROVAL_CONTENT_CHANGED")
        target = "approved" if decision == "approve" else "rejected"
        if approval["status"] != "pending":
            if approval["status"] == target:
                return approval
            raise ExecutionError("APPROVAL_ALREADY_RESOLVED")
        if instant(approval["expires_at"]) <= self.clock():
            raise ExecutionError("APPROVAL_EXPIRED")
        revision = approval["revision"]
        approval["status"] = target
        approval["decision_actor"] = freeze(value(actor))
        approval["decision_history"].append(
            {
                "decision": decision,
                "actor": freeze(value(actor)),
                "at": timestamp(self.clock()),
            }
        )
        approval = await self.repo.save("approvals", approval, revision, uow)
        await self.hitl.resolved(scope, approval, context, uow=uow)
        return approval

    async def decide_approval(
        self,
        scope: Any,
        approval_id: Any,
        decision: Any,
        actor: Any,
        audience: Any = None,
        *,
        arguments_hash: Any,
        quote_hash: Any,
    ) -> Any:
        """
        Manager entrypoint. Partner commands must use the shared namespace.
        """
        if value(actor).get("kind") != "manager":
            raise ExecutionError("MANAGER_AUTH_REQUIRED", 403)
        async with self.repo.transaction() as uow:
            return await self.decide_in_uow(
                scope,
                approval_id,
                decision,
                actor,
                audience,
                arguments_hash,
                quote_hash,
                uow,
            )

    async def consume(
        self,
        scope: Any,
        approval_id: Any,
        context: Any,
        request: Any,
        quote: Any,
        uow: Any,
    ) -> Any:
        """Lock and consume approval atomically with the execution intent."""
        approval = await self.repo.get(
            "approvals", approval_id, uow, scope, lock=True
        )
        require_scope(scope, approval)
        if (
            approval["run_id"] != context["run_id"]
            or approval["call_id"] != request["call_id"]
            or approval["group_id"] != context.get("group_id")
            or approval["workflow_id"] != context.get("workflow_id")
            or audience_ref(approval["audience_ref"])
            != audience_ref(context.get("partner_audience"))
            or approval["arguments_hash"] != digest(request["arguments"])
            or approval["quote_hash"] != digest(quote)
        ):
            raise ExecutionError("APPROVAL_CONTENT_CHANGED")
        if approval["status"] != "approved":
            raise ExecutionError("APPROVAL_NOT_APPROVED")
        if instant(approval["expires_at"]) <= self.clock():
            raise ExecutionError("APPROVAL_EXPIRED")
        approval["status"] = "consumed"
        await self.repo.save("approvals", approval, approval["revision"], uow)
