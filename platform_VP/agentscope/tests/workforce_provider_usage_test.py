"""Provider usage (including prompt-cache hits) is recorded per agent."""

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase

from agentscope.app._shared_context import SharedContextConfig, SharedContextService
from agentscope.app.message_bus import InMemoryMessageBus
from agentscope.app.middleware import SharedContextIsolationMiddleware
from agentscope.app.storage import TeamSharedContextRecord
from agentscope.message import SystemMsg, TextBlock
from agentscope.model import ChatResponse, ChatUsage
from agentscope.state import AgentState


class _Storage:
    def __init__(self) -> None:
        self.records: dict[tuple[str, str], TeamSharedContextRecord] = {}

    async def get_session(self, user_id, _agent_id, session_id):
        return None

    async def get_team_shared_context(self, user_id, team_id):
        record = self.records.get((user_id, team_id))
        return record.model_copy(deep=True) if record else None

    async def upsert_team_shared_context(self, user_id, record):
        self.records[(user_id, record.team_id)] = record.model_copy(deep=True)
        return record

    async def compare_and_swap_team_shared_context(
        self, user_id, record, expected_revision
    ):
        current = self.records.get((user_id, record.team_id))
        if (current.state.revision if current else 0) != expected_revision:
            return False
        self.records[(user_id, record.team_id)] = record.model_copy(deep=True)
        return True

    async def get_team_handoff(self, user_id, handoff_record_id):
        return None


class _Model:
    context_size = 10_000
    model = "gpt-test-mini"

    async def count_tokens(self, messages, tools):
        del tools
        text = "".join(msg.get_text_content() or "" for msg in messages)
        return max(1, len(text.encode("utf-8")) // 4)


class ProviderUsageTest(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.storage = _Storage()
        self.service = SharedContextService(
            self.storage,  # type: ignore[arg-type]
            InMemoryMessageBus(),
            SharedContextConfig(),
        )

    async def _call(self, middleware, usage, *, stream: bool):
        agent = SimpleNamespace(
            state=AgentState(session_id="worker-session"),
            name="Hotel",
        )

        async def next_handler(**kwargs):
            response = ChatResponse(
                content=[TextBlock(text="ok")],
                is_last=True,
                usage=usage,
            )
            if not stream:
                return response

            async def chunks():
                yield response

            return chunks()

        result = await middleware.on_model_call(
            agent,
            {
                "messages": [SystemMsg(name="system", content="Look up")],
                "tools": [],
                "current_model": _Model(),
            },
            next_handler,
        )
        if stream:
            return [chunk async for chunk in result]
        return result

    async def test_cached_tokens_accumulate_per_agent_for_stream_and_plain_calls(
        self,
    ) -> None:
        task_id = await self.service.active_task_id("u", "ticket-1")
        middleware = SharedContextIsolationMiddleware(
            "task",
            self.service,
            "u",
            "ticket-1",
            task_id=task_id,
            agent_id="agent-hotel",
        )
        await self._call(
            middleware,
            ChatUsage(input_tokens=2000, output_tokens=50, time=0, cache_input_tokens=1536),
            stream=True,
        )
        await self._call(
            middleware,
            ChatUsage(input_tokens=1000, output_tokens=20, time=0),
            stream=False,
        )
        await self._call(middleware, None, stream=False)

        record = await self.storage.get_team_shared_context("u", "ticket-1")
        usage = record.state.metrics.provider_usage["agent-hotel"]
        self.assertEqual("Hotel", usage.agent_name)
        self.assertEqual("gpt-test-mini", usage.model)
        self.assertEqual(3, usage.calls)
        self.assertEqual(2, usage.calls_with_usage)
        self.assertEqual(3000, usage.input_tokens)
        self.assertEqual(1536, usage.cached_input_tokens)
        self.assertEqual(70, usage.output_tokens)
