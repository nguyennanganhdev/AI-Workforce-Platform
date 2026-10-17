# -*- coding: utf-8 -*-
"""D2 HTTP acceptance for proxy-safe SSE reconnect and replay cursors."""

from __future__ import annotations

import unittest

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from agentscope.app.workforce.contracts import ActorContext
from agentscope.app.workforce.foundation import (
    InMemoryMetricSink,
    SSE_CONNECTIONS,
    SSE_REPLAYS,
)
from agentscope.app.workforce.orchestration import create_router


class _Events:
    def __init__(self) -> None:
        self.replay_calls = []

    async def list_after(
        self, actor, conversation_id, cursor, limit
    ) -> object:
        self.replay_calls.append((actor, conversation_id, cursor, limit))
        return object()

    async def stream(self, actor, conversation_id, cursor):
        del actor, conversation_id, cursor
        yield b"id: cursor-2\nevent: ticket.status_changed\ndata: {}\n\n"


class SseReconnectTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.actor = ActorContext(
            kind="partner",
            actor_id="customer-1",
            partner_client_id="partner-1",
            credential_id="key-1",
            credential_purpose="customer_api",
            external_user_id="resident-1",
            authentication_source="phase-d-test",
        )
        self.events = _Events()
        self.metrics = InMemoryMetricSink()

        async def customer_dependency():
            return self.actor

        app = FastAPI()
        app.include_router(
            create_router(
                object(),
                self.events,
                customer_dependency,
                bounded_wait_seconds=0,
                metric_sink=self.metrics,
            )
        )
        self.client = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="https://platform.test",
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_last_event_id_replays_and_sets_proxy_headers(self) -> None:
        response = await self.client.get(
            "/workforce/v1/partner/conversations/chat-1/events",
            params={"external_user_id": "resident-1"},
            headers={"Last-Event-ID": "cursor-1"},
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual("no-cache", response.headers["cache-control"])
        self.assertEqual("no", response.headers["x-accel-buffering"])
        self.assertEqual("identity", response.headers["content-encoding"])
        self.assertEqual("keep-alive", response.headers["connection"])
        self.assertIn("id: cursor-2", response.text)
        self.assertEqual("cursor-1", self.events.replay_calls[0][2])
        self.assertEqual(
            1,
            self.metrics.value(SSE_CONNECTIONS, result="accepted"),
        )
        self.assertEqual(
            1,
            self.metrics.value(
                SSE_REPLAYS, cursor_source="last_event_id"
            ),
        )

    async def test_disagreeing_reconnect_cursors_fail_before_stream(
        self,
    ) -> None:
        response = await self.client.get(
            "/workforce/v1/partner/conversations/chat-1/events",
            params={
                "external_user_id": "resident-1",
                "after_cursor": "cursor-query",
            },
            headers={"Last-Event-ID": "cursor-header"},
        )
        self.assertEqual(422, response.status_code)
        self.assertEqual([], self.events.replay_calls)
        self.assertEqual(
            0,
            self.metrics.value(SSE_CONNECTIONS, result="accepted"),
        )


if __name__ == "__main__":
    unittest.main()
