"""Recover large model inputs without dropping authoritative source data."""

import json
from dataclasses import replace
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from agentscope.agent import Agent
from agentscope.app._shared_context import (
    CollaborationStoppedError,
    SharedContextConfig,
    SharedContextService,
)
from agentscope.app._tool import SharedContextRead
from agentscope.app.message_bus import InMemoryMessageBus, MessageBusKeys
from agentscope.app.middleware import SharedContextIsolationMiddleware
from agentscope.message import ToolCallBlock, ToolCallState, UserMsg
from agentscope.model import ChatResponse
from agentscope.state import AgentState
from agentscope.tool import ToolResponse
from agentscope.model import FinishedReason
from tests.team_shared_context_test import _MeasuredModel, _Storage
from tests.team_say_shared_context_test import _Storage as _TeamStorage
from tests.utils import MockModel


class _PrivateModel(_MeasuredModel):
    async def generate_structured_output(self, **kwargs):
        schema = kwargs["structured_model"]
        fields = (
            schema.get("properties", {})
            if isinstance(schema, dict)
            else schema.model_fields
        )
        if "task_overview" not in fields:
            return await super().generate_structured_output(**kwargs)
        self.summary_calls += 1
        return SimpleNamespace(
            content={key: "Preserved prior work" for key in fields},
            finished_reason=FinishedReason.COMPLETED,
            usage=None,
        )


class _PagingModel(_PrivateModel, MockModel):
    def __init__(self):
        MockModel.__init__(self, context_size=10000)
        _MeasuredModel.__init__(self)

    async def count_tokens(self, messages, tools):
        return await MockModel.count_tokens(self, messages, tools)


class TestBudgetRecovery(IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.storage = _Storage()
        self.bus = InMemoryMessageBus()
        self.model = _PrivateModel()
        self.service = SharedContextService(
            self.storage,
            self.bus,
            SharedContextConfig(
                packet_max_tokens=12000, history_budget_tokens=3000
            ),
        )
        self.task_id = await self.service.active_task_id("u", "ticket-1")

    async def test_over_budget_summary_falls_back_to_readable_sources(self):
        model = _MeasuredModel()
        model.context_size = 100000
        original_summary = model.generate_structured_output

        async def oversized_summary(**kwargs):
            response = await original_summary(**kwargs)
            point = response.content["processed"][0]
            response.content["processed"] = [
                {**point, "text": "lengthy explanation " * 90}
                for _ in range(3)
            ]
            return response

        model.generate_structured_output = oversized_summary
        for kind, content in (
            ("customer_message", "c" * 30000),
            ("result", "r" * 30000),
        ):
            await self.service.append_event(
                user_id="u",
                team_id="ticket-1",
                kind=kind,
                content=content,
            )
        packet, tokens = await self.service.prepare_packet(
            model=model,
            user_id="u",
            team_id="ticket-1",
            allow_source_references=True,
        )
        self.assertLessEqual(tokens, 12000)
        self.assertTrue(json.loads(packet)["source_references"])
        record = await self.storage.get_team_shared_context("u", "ticket-1")
        self.assertEqual(record.state.metrics.compaction_failures, 1)
        self.assertEqual(record.state.metrics.packet_budget_failures, 0)

    def _read_tool(self):
        return SharedContextRead(
            storage=_TeamStorage(),
            message_bus=self.bus,
            workspace_manager=object(),
            user_id="u",
            session_id="leader-session",
            agent_id="leader",
            shared_context_service=self.service,
        )

    async def _paging_agent(self):
        await self.service.append_event(
            user_id="u", team_id="ticket-1", kind="customer_message",
            content="c" * 60000,
        )
        middleware = SharedContextIsolationMiddleware(
            "task", self.service, "u", "ticket-1",
            task_id=self.task_id, allow_source_references=True,
        )
        agent = Agent(
            name="Leader", system_prompt="Review", model=self.model,
            state=AgentState(session_id="leader-session"),
        )
        await middleware._refresh_packet(agent, self.model)
        source_ref = agent.state.middle_context["shared_context_sources"]["references"][0]
        return middleware, agent, source_ref

    async def test_snapshot_remains_readable_until_reply_scope_changes(self):
        middleware, agent, source_ref = await self._paging_agent()
        tool = self._read_tool()
        first = await tool(source_ref, _agent_state=agent.state)
        offset = json.loads(first.content[0].text)["next_offset"]
        await self.service.append_event(
            user_id="u", team_id="ticket-1", kind="result",
            content="New peer result",
        )
        await middleware._refresh_packet(agent, self.model)
        second = await tool(source_ref, offset=offset, _agent_state=agent.state)
        self.assertEqual(second.state, "success", second.content)
        page = json.loads(second.content[0].text)
        self.assertFalse(page["is_current_snapshot"])
        self.assertIn("snapshot_revision", page)
        agent.state.reply_id = "next-reply"
        self.assertEqual(
            (await tool(source_ref, _agent_state=agent.state)).state, "error"
        )
        await middleware._refresh_packet(agent, self.model)
        self.assertNotIn(
            source_ref,
            agent.state.middle_context["shared_context_sources"]["references"],
        )

    async def test_successful_paging_preserves_work_calls_and_counts_all_usage(self):
        middleware, agent, source_ref = await self._paging_agent()
        tool = self._read_tool()
        chunks = []
        offset = 0
        calls = 0
        while offset is not None:
            call = ToolCallBlock(
                id=f"read-{calls}", name="SharedContextRead",
                input=json.dumps({"source_ref": source_ref, "offset": offset}),
            )
            await middleware.on_model_call(
                agent, {**await agent._prepare_model_input(), "current_model": self.model},
                AsyncMock(return_value=ChatResponse(content=[call], is_last=True)),
            )

            async def action(**kwargs):
                result = await tool(source_ref, offset=offset, _agent_state=agent.state)
                yield ToolResponse.model_validate(result.model_dump())

            results = [result async for result in middleware.on_acting(
                agent, {"tool_call": call}, action,
            )]
            self.assertEqual(results[-1].state, "success", results[-1].content)
            page = json.loads(results[-1].content[0].text)
            chunks.append(page["content"])
            offset = page["next_offset"]
            calls += 1
        self.assertGreater(calls, 16)
        self.assertEqual(json.loads("".join(chunks))[0]["text"], "c" * 60000)
        record = await self.storage.get_team_shared_context("u", "ticket-1")
        branch = record.state.tasks[self.task_id].collaboration["leader-session"]
        self.assertEqual(branch.model_calls, calls)
        self.assertEqual(branch.paging_model_calls, calls)
        self.assertGreater(branch.measured_tokens, 0)
        self.assertGreater(branch.active_seconds, 0)
        for _ in range(16):
            await middleware.on_model_call(
                agent, {**await agent._prepare_model_input(), "current_model": self.model},
                AsyncMock(return_value=ChatResponse(content=[], is_last=True)),
            )
        with self.assertRaisesRegex(CollaborationStoppedError, "model call"):
            await middleware.on_model_call(
                agent, {**await agent._prepare_model_input(), "current_model": self.model},
                AsyncMock(return_value=ChatResponse(content=[], is_last=True)),
            )

    async def test_only_new_pages_in_read_only_rounds_receive_credit(self):
        middleware, agent, source_ref = await self._paging_agent()
        tool = self._read_tool()
        for index, (offset, limit, mixed, reference, credits) in enumerate((
            (0, 2000, False, source_ref, 1),
            (0, 2000, False, source_ref, 1),
            (2000, 2000, False, "0" * 64, 1),
            (2000, 2000, True, source_ref, 1),
            (2000, 2000, False, source_ref, 2),
            (4000, 1, False, source_ref, 2),
            (4000, 2000, False, source_ref, 3),
        )):
            call = ToolCallBlock(id=f"page-{index}", name="SharedContextRead", input="{}")
            calls = [call]
            if mixed:
                calls.append(ToolCallBlock(id="work", name="TeamSay", input="{}"))
            await middleware.on_model_call(
                agent, {**await agent._prepare_model_input(), "current_model": self.model},
                AsyncMock(return_value=ChatResponse(content=calls, is_last=True)),
            )

            async def action(**kwargs):
                result = await tool(reference, offset=offset, limit=limit, _agent_state=agent.state)
                yield ToolResponse.model_validate(result.model_dump())

            async for _ in middleware.on_acting(agent, {"tool_call": call}, action):
                pass
            record = await self.storage.get_team_shared_context("u", "ticket-1")
            branch = record.state.tasks[self.task_id].collaboration["leader-session"]
            self.assertEqual(branch.paging_model_calls, credits)
        self.assertEqual(branch.model_calls, 7)
        # Progress and credits survive reload; a new snapshot cannot refund old pages.
        self.service = SharedContextService(self.storage, self.bus, self.service.config)
        await self.service.credit_source_read(
            "u", "ticket-1", "leader-session", paging_call_id="replayed-page",
            task_id=self.task_id, customer_revision=branch.customer_revision,
            source_reads=[{"section": "authoritative_state.items", "offset": 0,
                           "end": 2000, "total_characters": 80000}],
        )
        record = await self.storage.get_team_shared_context("u", "ticket-1")
        self.assertEqual(
            record.state.tasks[self.task_id].collaboration["leader-session"].paging_model_calls,
            3,
        )

    async def test_failed_page_batch_receives_no_credit(self):
        middleware, agent, source_ref = await self._paging_agent()
        tool = self._read_tool()
        calls = [ToolCallBlock(id=reference, name="SharedContextRead", input="{}")
                 for reference in (source_ref, "0" * 64)]
        await middleware.on_model_call(
            agent, {**await agent._prepare_model_input(), "current_model": self.model},
            AsyncMock(return_value=ChatResponse(content=calls, is_last=True)),
        )
        for call in calls:
            async def action(**kwargs):
                result = await tool(call.id, _agent_state=agent.state)
                yield ToolResponse.model_validate(result.model_dump())

            async for _ in middleware.on_acting(agent, {"tool_call": call}, action):
                pass
        record = await self.storage.get_team_shared_context("u", "ticket-1")
        branch = record.state.tasks[self.task_id].collaboration["leader-session"]
        self.assertEqual(branch.model_calls, 1)
        self.assertEqual(branch.paging_model_calls, 0)

    async def test_page_batch_credits_one_round_with_out_of_order_results(self):
        middleware, agent, source_ref = await self._paging_agent()
        tool = self._read_tool()
        calls = [ToolCallBlock(id=str(offset), name="SharedContextRead", input="{}")
                 for offset in (4000, 0, 2000)]
        await middleware.on_model_call(
            agent, {**await agent._prepare_model_input(), "current_model": self.model},
            AsyncMock(return_value=ChatResponse(content=calls, is_last=True)),
        )
        for call in calls:
            async def action(**kwargs):
                result = await tool(source_ref, offset=int(call.id), _agent_state=agent.state)
                yield ToolResponse.model_validate(result.model_dump())

            async for _ in middleware.on_acting(agent, {"tool_call": call}, action):
                pass
        record = await self.storage.get_team_shared_context("u", "ticket-1")
        branch = record.state.tasks[self.task_id].collaboration["leader-session"]
        self.assertEqual(branch.model_calls, 1)
        self.assertEqual(branch.paging_model_calls, 1)
        self.assertEqual(branch.source_read_progress["authoritative_state.items"], (6000, 3))

    async def test_resuming_pending_reply_restores_only_its_iteration_credits(self):
        middleware, agent, source_ref = await self._paging_agent()
        grant = agent.state.middle_context["shared_context_sources"]
        grant["iteration_credits"] = 20
        agent.state.append_context(agent.name, [ToolCallBlock(
            id="awaiting-approval", name="BusinessTool", input="{}",
            state=ToolCallState.ASKING,
        )])
        max_iters = agent.react_config.max_iters

        async def resume(**kwargs):
            yield agent.react_config.max_iters

        self.assertEqual(
            [limit async for limit in middleware.on_reply(agent, {}, resume)],
            [max_iters + 20],
        )
        self.assertEqual(agent.react_config.max_iters, max_iters)
        agent.state.reply_id = "another-reply"
        self.assertEqual(
            [limit async for limit in middleware.on_reply(agent, {}, resume)],
            [max_iters],
        )

    async def test_reference_scope_changes_revoke_previous_snapshot(self):
        middleware, agent, source_ref = await self._paging_agent()
        selected = await self.service.append_event(
            user_id="u", team_id="ticket-1", kind="progress", content="s" * 60000,
        )
        limited = SharedContextIsolationMiddleware(
            "references", self.service, "u", "ticket-1", task_id=self.task_id,
            allow_source_references=True, reference_event_ids=(selected.id,),
        )
        await limited._refresh_packet(agent, self.model)
        self.assertEqual(
            (await self._read_tool()(source_ref, _agent_state=agent.state)).state,
            "error",
        )
        grants = agent.state.middle_context["shared_context_sources"]
        self.assertNotIn(source_ref, grants["references"])
        self.assertEqual(grants["reference_event_ids"], [selected.id])

    async def test_partial_final_page_is_not_credited_again_after_growth(self):
        for index, (offset, end, credits) in enumerate((
            (0, 1999, 1), (1999, 2000, 1), (2000, 4000, 2),
        )):
            await self.service.measure_collaboration(
                "u", "ticket-1", "leader-session", model_call=1,
            )
            await self.service.credit_source_read(
                "u", "ticket-1", "leader-session", paging_call_id=f"read-{index}",
                task_id=self.task_id, customer_revision=0, source_reads=[{
                    "section": "authoritative_state.items", "offset": offset,
                    "end": end, "total_characters": end,
                }],
            )
            record = await self.storage.get_team_shared_context("u", "ticket-1")
            branch = record.state.tasks[self.task_id].collaboration["leader-session"]
            self.assertEqual(branch.paging_model_calls, credits)

    async def test_paging_never_bypasses_token_or_time_limits(self):
        for budget, usage in (("tokens", {"tokens": 2}), ("time", {"active_seconds": 2})):
            with self.subTest(budget=budget):
                await self.asyncSetUp()
                self.service.config = replace(
                    self.service.config, collaboration_max_tokens=1,
                    collaboration_max_active_seconds=1,
                )
                await self.service.measure_collaboration(
                    "u", "ticket-1", "leader-session", model_call=1,
                )
                await self.service.credit_source_read(
                    "u", "ticket-1", "leader-session", paging_call_id="read",
                    task_id=self.task_id, customer_revision=0, source_reads=[{
                        "section": "authoritative_state.items", "offset": 0,
                        "end": 2000, "total_characters": 2000,
                    }],
                )
                with self.assertRaises(CollaborationStoppedError):
                    await self.service.measure_collaboration(
                        "u", "ticket-1", "leader-session", **usage,
                    )

    async def test_oversized_packet_keeps_sources_after_summary_failure(
        self,
    ):
        self.model.context_size = 100000
        self.model.fail_summary = True
        customer = ("Customer constraint " * 1500).strip()
        result = ("Verified result " * 2000).strip()
        for kind, content in (
            ("customer_message", customer),
            ("result", result),
        ):
            await self.service.append_event(
                user_id="u",
                team_id="ticket-1",
                kind=kind,
                content=content,
            )
        packet, tokens = await self.service.prepare_packet(
            model=self.model,
            user_id="u",
            team_id="ticket-1",
            allow_source_references=True,
        )
        value = json.loads(packet)
        self.assertLessEqual(tokens, 12000)
        self.assertTrue(value["source_references"])
        chunks = []
        source_ref = value["authoritative_state"]["items"]["source_ref"]
        offset = 0
        while offset is not None:
            page = await self.service.read_packet_source(
                user_id="u",
                team_id="ticket-1",
                task_id=self.task_id,
                source_ref=source_ref,
                offset=offset,
                limit=1000,
            )
            self.assertLessEqual(len(page["content"]), 1000)
            chunks.append(page["content"])
            offset = page["next_offset"]
        items = json.loads("".join(chunks))
        self.assertTrue(
            {customer, result} == {item["text"] for item in items},
            "Referenced items changed",
        )
        record = await self.storage.get_team_shared_context("u", "ticket-1")
        self.assertTrue(
            [customer, result]
            == [event.content for event in record.state.events],
            "Raw events changed",
        )
        self.assertGreater(record.state.metrics.compaction_failures, 0)
        self.assertEqual(record.state.metrics.packet_budget_failures, 0)

    async def test_packet_growth_lowers_compression_threshold(
        self,
    ):
        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="customer_message",
            content="Review options",
        )
        middleware = SharedContextIsolationMiddleware(
            "task",
            self.service,
            "u",
            "ticket-1",
            task_id=self.task_id,
        )
        state = AgentState(
            session_id="leader-session",
            context=[
                UserMsg(name="user", content="x" * 30000),
            ],
        )
        agent = Agent(
            name="Leader",
            system_prompt="Review",
            model=self.model,
            state=state,
            middlewares=[middleware],
        )
        await agent.compress_context()
        self.assertEqual(self.model.summary_calls, 0)
        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="result",
            content="r" * 6000,
        )
        await agent.compress_context()
        self.assertEqual(self.model.summary_calls, 1)
        self.assertIsNotNone(agent.state.summary)
        downstream = AsyncMock(
            return_value=ChatResponse(content=[], is_last=True)
        )
        await middleware.on_model_call(
            agent,
            {
                **await agent._prepare_model_input(),
                "current_model": self.model,
            },
            downstream,
        )
        downstream.assert_awaited_once()
        measured = await self.model.count_tokens(
            downstream.call_args.kwargs["messages"],
            downstream.call_args.kwargs["tools"],
        )
        self.assertLessEqual(measured + 1000 + 256, self.model.context_size)

    async def test_late_growth_recovers_at_model_call(self):
        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="customer_message",
            content="Review options",
        )
        middleware = SharedContextIsolationMiddleware(
            "task",
            self.service,
            "u",
            "ticket-1",
            task_id=self.task_id,
        )
        agent = Agent(
            name="Leader",
            system_prompt="Review",
            model=self.model,
            state=AgentState(
                session_id="leader-session",
                context=[
                    UserMsg(name="user", content="x" * 30000),
                ],
            ),
            middlewares=[middleware],
        )
        await agent.compress_context()
        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="result",
            content="r" * 6000,
        )
        downstream = AsyncMock(
            return_value=ChatResponse(content=[], is_last=True)
        )
        await middleware.on_model_call(
            agent,
            {
                **await agent._prepare_model_input(),
                "current_model": self.model,
            },
            downstream,
        )
        self.assertEqual(self.model.summary_calls, 1)
        downstream.assert_awaited_once()

    async def test_small_model_receives_references_and_scoped_grants(
        self,
    ):
        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="customer_message",
            content="c" * 60000,
        )
        middleware = SharedContextIsolationMiddleware(
            "task",
            self.service,
            "u",
            "ticket-1",
            task_id=self.task_id,
            allow_source_references=True,
        )
        agent = Agent(
            name="Leader",
            system_prompt="Review",
            model=self.model,
            state=AgentState(session_id="leader-session"),
            middlewares=[middleware],
        )
        downstream = AsyncMock(
            return_value=ChatResponse(content=[], is_last=True)
        )
        await middleware.on_model_call(
            agent,
            {
                **await agent._prepare_model_input(),
                "current_model": self.model,
            },
            downstream,
        )
        downstream.assert_awaited_once()
        grant = agent.state.middle_context["shared_context_sources"]
        self.assertEqual(grant["task_id"], self.task_id)
        self.assertTrue(grant["references"])
        prompt = downstream.call_args.kwargs["messages"]
        self.assertLessEqual(
            await self.model.count_tokens(prompt, []), 10000 - 1000 - 256
        )
        await self.bus.registry_drop(
            MessageBusKeys.team_context_sources("u", "ticket-1", self.task_id)
        )
        await middleware.on_model_call(
            agent,
            {
                **await agent._prepare_model_input(),
                "current_model": self.model,
            },
            downstream,
        )
        self.assertEqual(downstream.await_count, 2)
        for source_ref in grant["references"]:
            page = await self.service.read_packet_source(
                user_id="u",
                team_id="ticket-1",
                task_id=self.task_id,
                source_ref=source_ref,
            )
            self.assertTrue(page["content"])

    async def test_isolated_turn_revokes_source_grants(
        self,
    ):
        team_storage = _TeamStorage()
        for kind, text in (
            ("customer_message", "c" * 30000),
            ("result", "r" * 30000),
        ):
            await self.service.append_event(
                user_id="u",
                team_id="ticket-1",
                kind=kind,
                content=text,
            )
        packet, _ = await self.service.prepare_packet(
            model=self.model,
            user_id="u",
            team_id="ticket-1",
            allow_source_references=True,
        )
        state = AgentState(session_id="leader-session")
        middleware = SharedContextIsolationMiddleware(
            "task", self.service, "u", "ticket-1",
            task_id=self.task_id, allow_source_references=True,
        )
        await middleware._refresh_packet(
            Agent(name="Leader", system_prompt="Review", model=self.model, state=state),
            self.model,
        )
        refs = state.middle_context["shared_context_sources"]["references"]
        tool = SharedContextRead(
            storage=team_storage,
            message_bus=self.bus,
            workspace_manager=object(),
            user_id="u",
            session_id="leader-session",
            agent_id="leader",
            shared_context_service=self.service,
        )
        result = await tool(refs[0], limit=500, _agent_state=state)
        self.assertEqual(result.state, "success", result.content)
        self.assertEqual(
            len(json.loads(result.content[0].text)["content"]), 500
        )
        self.assertEqual(
            (await tool("0" * 64, _agent_state=state)).state, "error"
        )
        self.assertEqual(
            (await tool(refs[0], offset=-1, _agent_state=state)).state, "error"
        )
        with self.assertRaisesRegex(ValueError, "expired"):
            await self.service.read_packet_source(
                user_id="another-owner",
                team_id="ticket-1",
                task_id=self.task_id,
                source_ref=refs[0],
            )
        isolated = SharedContextIsolationMiddleware(
            "isolated", self.service, "u", None
        )
        await isolated._refresh_packet(
            SimpleNamespace(state=state), self.model
        )
        self.assertEqual(
            (await tool(refs[0], _agent_state=state)).state, "error"
        )

    async def test_expired_cache_is_rebuilt_from_retained_sources(self):
        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="customer_message",
            content="c" * 60000,
        )
        kwargs = dict(
            model=self.model,
            user_id="u",
            team_id="ticket-1",
            allow_source_references=True,
        )
        packet, _ = await self.service.prepare_packet(**kwargs)
        source_ref = json.loads(packet)["source_references"][0]
        await self.bus.registry_drop(
            MessageBusKeys.team_context_sources("u", "ticket-1", self.task_id)
        )
        with self.assertRaisesRegex(ValueError, "expired"):
            await self.service.read_packet_source(
                user_id="u",
                team_id="ticket-1",
                task_id=self.task_id,
                source_ref=source_ref,
            )
        await self.service.prepare_packet(**kwargs)
        page = await self.service.read_packet_source(
            user_id="u",
            team_id="ticket-1",
            task_id=self.task_id,
            source_ref=source_ref,
        )
        self.assertTrue(page["content"])

    async def test_reference_mode_pages_only_explicitly_selected_sources(self):
        selected = await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="progress",
            content="s" * 60000,
        )
        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="customer_message",
            content="Unreferenced customer secret",
        )
        packet, tokens = await self.service.prepare_packet(
            model=self.model,
            user_id="u",
            team_id="ticket-1",
            mode="references",
            reference_event_ids=(selected.id,),
            allow_source_references=True,
        )
        self.assertLessEqual(tokens, 12000)
        self.assertNotIn("Unreferenced customer secret", packet)
        source_ref = json.loads(packet)["recent_events"]["source_ref"]
        offset = 0
        chunks = []
        while offset is not None:
            page = await self.service.read_packet_source(
                user_id="u",
                team_id="ticket-1",
                task_id=self.task_id,
                source_ref=source_ref,
                offset=offset,
                limit=4000,
            )
            chunks.append(page["content"])
            offset = page["next_offset"]
        source = "".join(chunks)
        self.assertNotIn("Unreferenced customer secret", source)
        self.assertEqual(
            [event["id"] for event in json.loads(source)], [selected.id]
        )

    async def test_repeated_calls_fit_as_shared_and_private_history_grow(self):
        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="customer_message",
            content="Keep comparing verified options",
        )
        middleware = SharedContextIsolationMiddleware(
            "task",
            self.service,
            "u",
            "ticket-1",
            task_id=self.task_id,
            allow_source_references=True,
        )
        agent = Agent(
            name="Leader",
            system_prompt="Review",
            model=self.model,
            state=AgentState(session_id="leader-session"),
            middlewares=[middleware],
        )
        downstream = AsyncMock(
            return_value=ChatResponse(content=[], is_last=True)
        )
        for index in range(6):
            agent.state.context.append(
                UserMsg(name="user", content="p" * 8000)
            )
            await self.service.append_event(
                user_id="u",
                team_id="ticket-1",
                kind="result",
                content=f"Verified peer result {index}: " + "e" * 10000,
            )
            await agent.compress_context()
            await middleware.on_model_call(
                agent,
                {
                    **await agent._prepare_model_input(),
                    "current_model": self.model,
                },
                downstream,
            )
            measured = await self.model.count_tokens(
                downstream.call_args.kwargs["messages"],
                downstream.call_args.kwargs["tools"],
            )
            self.assertLessEqual(
                measured + 1000 + 256, self.model.context_size
            )
        self.assertEqual(downstream.await_count, 6)
        self.assertGreater(self.model.summary_calls, 0)
        self.assertTrue(
            agent.state.middle_context["shared_context_sources"]["references"]
        )
        record = await self.storage.get_team_shared_context("u", "ticket-1")
        self.assertEqual(len(record.state.events), 7)
        self.assertEqual(record.state.metrics.prompt_budget_failures, 0)
        self.assertEqual(record.state.metrics.packet_budget_failures, 0)
