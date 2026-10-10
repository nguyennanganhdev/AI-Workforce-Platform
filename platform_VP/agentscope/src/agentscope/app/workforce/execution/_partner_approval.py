# -*- coding: utf-8 -*-
"""Partner consent uses original audience and shared command idempotency."""

from typing import Any

from ..contracts import (
    ActorContext,
    CredentialPurpose,
    PartnerApprovalDecision,
    RequestResult,
)
from ._utils import ExecutionError, digest, timestamp, value


class PartnerApprovalService:
    """
    Requires PartnerCommandPort; cannot substitute a private dedupe table.
    """

    def __init__(self, approvals: Any, commands: Any) -> None:
        self.approvals, self.commands = approvals, commands

    async def decide(
        self,
        actor: ActorContext | dict[str, Any],
        approval_id: str,
        body: PartnerApprovalDecision | dict[str, Any],
    ) -> Any:
        """
        Claim and record consent in the same UOW as the approval mutation.
        """
        try:
            actor = ActorContext.model_validate(actor)
        except ValueError:
            raise ExecutionError("CUSTOMER_AUTH_REQUIRED", 403) from None
        if (
            actor.kind != "partner"
            or actor.credential_purpose != CredentialPurpose.CUSTOMER_API
        ):
            raise ExecutionError("CUSTOMER_AUTH_REQUIRED", 403)
        try:
            # Do not let Pydantic coerce bool/float revisions at this boundary.
            if type(value(body).get("expected_revision")) is not int:
                raise ValueError
            body = PartnerApprovalDecision.model_validate(body)
        except ValueError:
            raise ExecutionError("APPROVAL_DECISION_INVALID", 422) from None
        actor_context = actor
        actor, body = value(actor), value(body)
        async with self.approvals.repo.transaction() as uow:
            # The command port resolves owner/audience from the stored approval
            # reference and checks binding before it exposes a cached result.
            resolved = await self.commands.authorize_approval(
                actor, approval_id, body, uow=uow
            )
            scope, audience = resolved["scope"], resolved["audience"]
            approval = await self.approvals.repo.get(
                "approvals", approval_id, uow, scope
            )
            await self.approvals.authorize(
                scope, approval, actor, audience, uow
            )
            command = await self.commands.claim_or_read(
                actor_context,
                body["external_request_id"],
                "approval_decision",
                approval_id,
                digest(
                    {
                        "command_kind": "approval_decision",
                        "target_ref": approval_id,
                        "audience": audience,
                        "body": body,
                    }
                ),
                uow=uow,
            )
            if not command["is_new"]:
                cached = command["result"]
                if isinstance(cached, RequestResult):
                    return cached.data
                cached = value(cached)
                if set(cached) == {"messages", "data"}:
                    return RequestResult.model_validate(cached).data
                # Pre-Phase-A command rows contain the direct response.
                return cached
            if body["expected_revision"] != approval["revision"]:
                raise ExecutionError("REVISION_CONFLICT")
            if body["quote_ref"] != approval["quote"]["quote_ref"]:
                raise ExecutionError("APPROVAL_CONTENT_CHANGED")
            approval = await self.approvals.decide_in_uow(
                scope,
                approval_id,
                body["decision"],
                actor,
                audience,
                body["arguments_hash"],
                approval["quote_hash"],
                uow,
            )
            result = {
                "approval_id": approval["id"],
                "status": approval["status"],
                "external_ticket_id": audience.get("external_ticket_id"),
                "workflow_id": approval["workflow_id"],
                "accepted_at": timestamp(self.approvals.clock()),
            }
            await self.commands.record_result(
                command["request_id"], RequestResult(data=result), uow=uow
            )
            return result
