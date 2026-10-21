# -*- coding: utf-8 -*-
"""Provider calls get a deadline, and a lock heartbeat survives one
failed renewal."""
import asyncio
import os
from typing import Any
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import patch

import fakeredis.aioredis

from agentscope.app._service._model import _timeout_kwargs
from agentscope.app.message_bus import RedisMessageBus
from agentscope.model import AnthropicChatModel, GeminiChatModel, OpenAIChatModel


class ModelTimeoutTest(TestCase):

    def test_sdk_clients_get_a_deadline_except_gemini(self) -> None:
        self.assertEqual(_timeout_kwargs(OpenAIChatModel), {"client_kwargs": {"timeout": 300.0}})
        self.assertEqual(_timeout_kwargs(AnthropicChatModel), {"client_kwargs": {"timeout": 300.0}})
        self.assertEqual(_timeout_kwargs(GeminiChatModel), {})

    def test_the_deadline_is_configurable(self) -> None:
        with patch.dict(os.environ, {"MODEL_CALL_TIMEOUT_SECONDS": "90"}):
            self.assertEqual(_timeout_kwargs(OpenAIChatModel)["client_kwargs"]["timeout"], 90.0)


class LockHeartbeatTest(IsolatedAsyncioTestCase):

    async def test_one_failed_renewal_does_not_end_the_heartbeat(self) -> None:
        redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

        class _Bus(RedisMessageBus):
            async def __aenter__(self) -> Any:
                self._client = redis
                return self

        bus = await _Bus().__aenter__()
        original = redis.eval
        calls = {"n": 0}

        async def flaky_eval(*args: Any) -> Any:
            calls["n"] += 1
            if calls["n"] == 1:
                raise ConnectionError("blip")
            return await original(*args)

        with patch.object(redis, "eval", flaky_eval):
            async with bus.acquire_lock("k", ttl_secs=2):
                await asyncio.sleep(3.5)
                # Dead after the 1 s failure, the 2 s lease would be gone by now.
                self.assertGreaterEqual(calls["n"], 2)
                self.assertTrue(await redis.exists("k"))
