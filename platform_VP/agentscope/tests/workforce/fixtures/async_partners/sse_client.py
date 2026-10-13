"""
TEST ONLY SSE/history catch-up consumer with per-ticket cursor and dedupe.
"""

import json


async def parse_sse(lines):
    """
    Parse comments and multiline data; incomplete frames wait for reconnect.
    """
    event_id, event_type, data = None, "message", []
    first = True
    async for line in lines:
        if first:
            line = line.removeprefix("\ufeff")
            first = False
        if not line:
            if data:
                yield {
                    "event_id": event_id,
                    "event_type": event_type,
                    "data": json.loads("\n".join(data)),
                }
            event_id, event_type, data = None, "message", []
            continue
        if line.startswith(":"):
            continue
        field, separator, val = line.partition(":")
        if separator and val.startswith(" "):
            val = val[1:]
        if field == "id" and "\x00" not in val:
            event_id = val
        elif field == "event":
            event_type = val
        elif field == "data":
            data.append(val)


class TicketEventClient:
    """
    Advance a cursor only after successful processing; never compare UUID
    order.
    """

    def __init__(self, binding, external_user_id):
        self.binding, self.external_user_id = dict(binding), external_user_id
        self.cursor = None
        self.events, self.messages = set(), set()
        self.messages.update(
            m["message_id"] for m in binding.get("messages", [])
        )

    async def process(self, event, handler):
        for key in (
            "conversation_id",
            "workflow_id",
            "external_ticket_id",
            "external_conversation_id",
        ):
            if event.get(key) != self.binding[key]:
                raise AssertionError("Cross-ticket public event")
        if event.get("external_user_id") != self.external_user_id:
            raise AssertionError("Cross-audience public event")
        event_id = event["event_id"]
        if event_id in self.events:
            return False
        message_id = (
            event.get("payload", {}).get("message_id")
            if event["event_type"] == "assistant.message"
            else None
        )
        duplicate_message = (
            message_id is not None and message_id in self.messages
        )
        if not duplicate_message:
            await handler(event)
        self.events.add(event_id)
        if message_id:
            self.messages.add(message_id)
        self.cursor = event_id
        return not duplicate_message

    async def read_stream(self, client, headers, handler, max_events=None):
        """
        Reuse one consumer per conversation; disconnect does not close
        workflow.
        """
        headers = dict(headers)
        if self.cursor:
            headers["Last-Event-ID"] = self.cursor
        conversation_id = self.binding["conversation_id"]
        url = f"/workforce/v1/partner/conversations/{conversation_id}/events"
        async with client.stream(
            "GET",
            url,
            headers=headers,
            params={"external_user_id": self.external_user_id},
        ) as response:
            response.raise_for_status()
            delivered = 0
            async for frame in parse_sse(response.aiter_lines()):
                if frame["event_id"] != frame["data"]["event_id"]:
                    raise AssertionError("SSE envelope ID mismatch")
                await self.process(frame["data"], handler)
                delivered += 1
                if max_events is not None and delivered >= max_events:
                    break

    async def catch_up(self, client, headers, handler):
        conversation_id = self.binding["conversation_id"]
        url = (
            f"/workforce/v1/partner/conversations/{conversation_id}"
            "/event-history"
        )
        while True:
            params = {"external_user_id": self.external_user_id, "limit": 100}
            if self.cursor:
                params["after_cursor"] = self.cursor
            response = await client.get(url, headers=headers, params=params)
            if response.status_code == 410:
                snapshot = await client.get(
                    url.removesuffix("/event-history"),
                    headers=headers,
                    params={"external_user_id": self.external_user_id},
                )
                snapshot.raise_for_status()
                body = snapshot.json()
                if body["conversation_id"] != self.binding["conversation_id"]:
                    raise AssertionError("Cross-conversation snapshot")
                await handler({"event_type": "snapshot", "payload": body})
                self.cursor = body["snapshot_cursor"]
                self.messages.update(
                    m["message_id"] for m in body.get("messages", [])
                )
                return
            response.raise_for_status()
            body = response.json()
            before = self.cursor
            for event in body["items"]:
                await self.process(event, handler)
            if not body["has_more"]:
                return
            if before == self.cursor:
                raise AssertionError("History pagination made no progress")
