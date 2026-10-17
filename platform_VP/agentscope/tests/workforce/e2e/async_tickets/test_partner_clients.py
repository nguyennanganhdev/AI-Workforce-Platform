"""
Contract tests of reusable customer/provider/SSE clients, not platform E2E.
"""

import asyncio
import json

import httpx
import pytest

from async_partners import CustomerBackend, TicketEventClient, parse_sse


def test_customer_two_chats_preserve_binding_and_next_action():
    async def scenario():
        seen = []

        async def transport(request):
            body = json.loads(request.content)
            seen.append(body)
            suffix = body["external_ticket_id"][-1]
            state, action = (
                ("closed", "none")
                if suffix == "A"
                else ("awaiting_user", "submit_reply")
            )
            return httpx.Response(
                200,
                json={
                    "request_id": body["external_request_id"],
                    "external_ticket_id": body["external_ticket_id"],
                    "conversation_id": "conv-" + suffix,
                    "workflow_id": "wf-" + suffix,
                    "workflow_revision": len(seen),
                    "workflow_state": state,
                    "next_action": action,
                    "result": {"messages": []},
                },
            )

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(transport), base_url="http://fixture"
        ) as client:
            customer = CustomerBackend(
                client, {"Authorization": "TEST-ONLY"}, "same-user", "ref-A"
            )
            await customer.start("TICKET-A", "CHAT-A", "read-only", "A1")
            await customer.start("TICKET-B", "CHAT-B", "plan", "B1")
            # Client binding test uses canned responses; closed-workflow
            # rejection
            # belongs to the real Orchestration acceptance gate below.
            await customer.reply("TICKET-A", "A context", "A2")
            await customer.reply("TICKET-B", "B context", "B2")
            assert [b["external_request_id"] for b in seen] == [
                "A1",
                "B1",
                "A2",
                "B2",
            ]
            assert (
                seen[2]["workflow_id"] == "wf-A"
                and seen[3]["workflow_id"] == "wf-B"
            )
            assert all(b["external_user_id"] == "same-user" for b in seen)
            assert not customer.tracking_required(
                "TICKET-A"
            ) and not customer.tracking_required("TICKET-B")
            assert all(
                "group_id" not in b and "manager_account_id" not in b
                for b in seen
            )

    asyncio.run(scenario())


def test_sse_dedupe_cursors_and_handler_failure():
    async def scenario():
        binding_a = {
            "conversation_id": "conv-A",
            "workflow_id": "wf-A",
            "external_ticket_id": "TICKET-A",
            "external_conversation_id": "CHAT-A",
            "messages": [{"message_id": "message-1"}],
        }
        a, b = (
            TicketEventClient(binding_a, "same-user"),
            TicketEventClient(
                {
                    **binding_a,
                    "conversation_id": "conv-B",
                    "workflow_id": "wf-B",
                    "external_ticket_id": "TICKET-B",
                    "external_conversation_id": "CHAT-B",
                    "messages": [],
                },
                "same-user",
            ),
        )
        event = {
            **{k: v for k, v in binding_a.items() if k != "messages"},
            "external_user_id": "same-user",
            "event_id": "event-1",
            "event_type": "assistant.message",
            "payload": {"message_id": "message-1"},
        }
        delivered = []

        async def handler(event):
            delivered.append(event)

        assert not await a.process(event, handler)
        assert a.cursor == "event-1" and b.cursor is None and delivered == []
        event2 = {
            **event,
            "event_id": "event-2",
            "payload": {"message_id": "message-2"},
        }

        async def failure(event):
            raise RuntimeError("client offline before processing")

        with pytest.raises(RuntimeError):
            await a.process(event2, failure)
        assert a.cursor == "event-1"
        assert await a.process(event2, handler)
        assert not await a.process(event2, handler)
        with pytest.raises(AssertionError, match="Cross-ticket"):
            await b.process(event, handler)
        assert len(delivered) == 1

        async def lines():
            for line in [
                ": heartbeat",
                "",
                "id: event-2",
                "event: assistant.message",
                "data: " + json.dumps(event2),
                "",
                "id: incomplete",
                "data: {}",
            ]:
                yield line

        frames = [frame async for frame in parse_sse(lines())]
        assert len(frames) == 1 and frames[0]["event_id"] == "event-2"

    asyncio.run(scenario())
