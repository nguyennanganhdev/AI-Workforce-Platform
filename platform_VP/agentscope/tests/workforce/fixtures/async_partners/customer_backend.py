"""TEST ONLY customer backend; machine credentials never go to a browser."""

from uuid import uuid4


class CustomerBackend:
    """
    One record and cursor per external ticket, including two chats for one
    user.
    """

    def __init__(
        self, client, headers, external_user_id, external_management_ref
    ):
        self.client, self.headers = client, headers
        self.external_user_id, self.external_management_ref = (
            external_user_id,
            external_management_ref,
        )
        self.tickets = {}

    def _base(self, ticket, conversation, request_id):
        return {
            "schema_version": "1",
            "external_request_id": request_id,
            "external_management_ref": self.external_management_ref,
            "external_user_id": self.external_user_id,
            "external_ticket_id": ticket,
            "external_conversation_id": conversation,
        }

    async def start(self, ticket, conversation, text, request_id=None):
        body = {
            **self._base(ticket, conversation, request_id or str(uuid4())),
            "command_type": "start_workflow",
            "message": {"type": "text", "text": text},
        }
        response = await self.client.post(
            "/workforce/v1/partner/requests", headers=self.headers, json=body
        )
        response.raise_for_status()
        result = response.json()
        self._remember(ticket, conversation, result)
        return response

    def _remember(self, ticket, conversation, result):
        if result["external_ticket_id"] != ticket:
            raise AssertionError("Platform returned the wrong external ticket")
        previous = self.tickets.get(ticket)
        ids = {
            "external_ticket_id": ticket,
            "external_conversation_id": conversation,
            "workflow_id": result["workflow_id"],
            "conversation_id": result["conversation_id"],
        }
        if previous and any(previous[k] != v for k, v in ids.items()):
            raise AssertionError(
                "Platform changed an immutable ticket binding"
            )
        self.tickets[ticket] = {
            **(previous or {}),
            **ids,
            "workflow_revision": result["workflow_revision"],
            "workflow_state": result["workflow_state"],
            "next_action": result["next_action"],
            "request_id": result["request_id"],
            "messages": result.get("result", {}).get("messages", [])
            if result.get("result")
            else [],
        }

    async def reply(self, ticket, text, request_id=None):
        record = self.tickets[ticket]
        body = {
            **self._base(
                ticket,
                record["external_conversation_id"],
                request_id or str(uuid4()),
            ),
            "command_type": "workflow_reply",
            "workflow_id": record["workflow_id"],
            "message": {"type": "text", "text": text},
        }
        response = await self.client.post(
            "/workforce/v1/partner/requests", headers=self.headers, json=body
        )
        response.raise_for_status()
        self._remember(
            ticket, record["external_conversation_id"], response.json()
        )
        return response

    async def approve(
        self, ticket, approval, decision="approve", request_id=None
    ):
        record = self.tickets[ticket]
        body = {
            "schema_version": "1",
            "external_request_id": request_id or str(uuid4()),
            "external_user_id": self.external_user_id,
            "external_ticket_id": ticket,
            "external_conversation_id": record["external_conversation_id"],
            "workflow_id": record["workflow_id"],
            "decision": decision,
            "arguments_hash": approval["arguments_hash"],
            "quote_ref": approval["quote"]["quote_ref"],
            "expected_revision": approval["revision"],
        }
        response = await self.client.post(
            f"/workforce/v1/partner/approvals/{approval['approval_id']}/decision",
            headers=self.headers,
            json=body,
        )
        response.raise_for_status()
        return response

    async def close(self, ticket, stop_tracking_only=False, request_id=None):
        record = self.tickets[ticket]
        body = {
            "schema_version": "1",
            "external_request_id": request_id or str(uuid4()),
            "external_user_id": self.external_user_id,
            "external_ticket_id": ticket,
            "external_conversation_id": record["external_conversation_id"],
            "expected_revision": record["workflow_revision"],
            "stop_tracking_only": stop_tracking_only,
            "reason": "resident_requested_stop_tracking"
            if stop_tracking_only
            else "resident_confirmed_resolved",
        }
        response = await self.client.post(
            f"/workforce/v1/partner/workflows/{record['workflow_id']}/close",
            headers=self.headers,
            json=body,
        )
        response.raise_for_status()
        result = response.json()
        record.update(
            workflow_state=result.get("workflow_state", result.get("state")),
            workflow_revision=result.get(
                "workflow_revision", result.get("revision")
            ),
            next_action=result["next_action"],
        )
        return response

    async def read_request(self, ticket):
        record = self.tickets[ticket]
        response = await self.client.get(
            f"/workforce/v1/partner/requests/{record['request_id']}",
            headers=self.headers,
            params={"external_user_id": self.external_user_id},
        )
        response.raise_for_status()
        self._remember(
            ticket, record["external_conversation_id"], response.json()
        )
        return response

    def tracking_required(self, ticket):
        return self.tickets[ticket]["next_action"] in {
            "watch_request",
            "watch_events",
        }
