# -*- coding: utf-8 -*-
"""A reply replaced in place never overwrites a reply another member
pushed in the meantime."""
from typing import Any
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

import fakeredis
import fakeredis.aioredis
from redis.commands.core import ListCommands

from agentscope.app.storage import RedisStorage
from agentscope.message import AssistantMsg


class UpsertMessageRaceTest(IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        server = fakeredis.FakeServer()
        redis = fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)
        self.other = fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)

        class _Storage(RedisStorage):
            async def __aenter__(self) -> Any:
                self._client = redis
                return self

        self.storage = await _Storage().__aenter__()

    async def test_a_reply_pushed_during_the_replace_survives(self) -> None:
        first = AssistantMsg("hotel", "draft")
        await self.storage.upsert_message("u", "s", first)
        intruder = AssistantMsg("flight", "pushed meanwhile")
        key = self.storage._message_key("u", "s")  # pylint: disable=protected-access
        original = ListCommands.lrange
        pushed = []

        async def lrange_then_intrude(client, *args, **kwargs):
            result = await original(client, *args, **kwargs)
            if not pushed:
                pushed.append(True)
                await self.other.rpush(key, intruder.model_dump_json())
            return result

        final = first.model_copy(update={"content": AssistantMsg("hotel", "final").content})
        with patch.object(ListCommands, "lrange", lrange_then_intrude):
            await self.storage.upsert_message("u", "s", final)

        stored, _ = await self.storage.list_messages("u", "s", limit=10)
        texts = {m.id: m.get_text_content() for m in stored}
        self.assertEqual(texts, {first.id: "final", intruder.id: "pushed meanwhile"})
