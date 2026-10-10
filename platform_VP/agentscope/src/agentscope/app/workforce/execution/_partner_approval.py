# -*- coding: utf-8 -*-
"""Partner consent uses original audience and shared command idempotency."""

from typing import Any

from ._utils import ExecutionError, digest, timestamp, value


class PartnerApprovalService:
    """
    Requires PartnerCommandPort; cannot substitute a private dedupe table.
    """

    def __init__(self, approvals: Any, commands: Any) -> None:
        self.approvals, self.commands = approvals, commands

    async def decide(self, actor: Any, approval_id: Any, body: Any) -> Any:
        """
        Claim and record consent in the same UOW as the approval mutation.
        """
        actor, body = value(actor), value(body)
        if (
            actor.get("kind") != "partner"
            or actor.get("purpose") != "customer"
        ):
            raise ExecutionError("CUSTOMER_AUTH_REQUIRED", 403)
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
                actor,
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
                return command["result"]
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
                command["request_id"], result, uow=uow
            )
            return result
