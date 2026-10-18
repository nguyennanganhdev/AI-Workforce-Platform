"""Durability, isolation, compaction, and token-budget tests."""

import asyncio
import hashlib
import json
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase

from agentscope.app._shared_context import (
    CollaborationStoppedError,
    ContextDirective,
    SharedContextBudgetError,
    SharedContextConfig,
    SharedContextService,
)
from agentscope.app.message_bus import InMemoryMessageBus, MessageBusKeys
from agentscope.app.middleware import InboxMiddleware, SharedContextIsolationMiddleware
from agentscope.app.storage import (
    ContextDelta,
    SharedContextEvent,
    SharedContextSummary,
    TeamHandoffRecord,
    TeamSharedContextRecord,
)
from agentscope.message import (
    AssistantMsg,
    HintBlock,
    SystemMsg,
    TextBlock,
    ToolCallBlock,
    UserMsg,
)
from agentscope.model import ChatResponse, ChatUsage
from agentscope.state import AgentState


class _Storage:
    def __init__(self) -> None:
        self.records: dict[tuple[str, str], TeamSharedContextRecord] = {}
        self.handoffs: dict[str, TeamHandoffRecord] = {}
        self.sessions: dict[tuple[str, str], object] = {}

    async def get_session(
        self,
        user_id: str,
        _agent_id: str,
        session_id: str,
    ) -> object | None:
        return self.sessions.get((user_id, session_id))

    async def get_team_shared_context(
        self,
        user_id: str,
        team_id: str,
    ) -> TeamSharedContextRecord | None:
        record = self.records.get((user_id, team_id))
        return record.model_copy(deep=True) if record else None

    async def upsert_team_shared_context(
        self,
        user_id: str,
        record: TeamSharedContextRecord,
    ) -> TeamSharedContextRecord:
        self.records[(user_id, record.team_id)] = record.model_copy(deep=True)
        return record

    async def compare_and_swap_team_shared_context(
        self, user_id: str, record: TeamSharedContextRecord, expected_revision: int
    ) -> bool:
        current = self.records.get((user_id, record.team_id))
        if (current.state.revision if current else 0) != expected_revision:
            return False
        self.records[(user_id, record.team_id)] = record.model_copy(deep=True)
        return True

    async def get_team_handoff(
        self,
        user_id: str,
        handoff_record_id: str,
    ) -> TeamHandoffRecord | None:
        record = self.handoffs.get(handoff_record_id)
        return record if record is not None and record.user_id == user_id else None


class _MeasuredModel:
    context_size = 10_000

    def __init__(
        self,
        *,
        fail_summary: bool = False,
    ) -> None:
        self.fail_summary = fail_summary
        self.count_calls = 0
        self.summary_calls = 0

    async def count_tokens(self, messages: list, tools: object) -> int:
        del tools
        self.count_calls += 1
        text = "".join(msg.get_text_content() or "" for msg in messages)
        return max(1, len(text.encode("utf-8")) // 4)

    async def generate_structured_output(self, **kwargs: object) -> object:
        self.summary_calls += 1
        if self.fail_summary:
            raise RuntimeError("summarizer unavailable")
        return SimpleNamespace(
            content={
                "processed": [
                    {
                        "text": "Earlier shared work was completed",
                    },
                ],
                "important_results": [],
                "requirement_changes": [],
                "open_points": [],
            },
        )


class TestSharedContextService(IsolatedAsyncioTestCase):
    async def test_stream_usage_is_charged_and_new_peer_evidence_refreshes_packet(self):
        self.service.config = SharedContextConfig()
        task_id = await self.service.active_task_id("u", "ticket-1")
        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="customer_message",
            content="Compare options",
        )
        state = AgentState(session_id="leader-session")
        agent = SimpleNamespace(state=state, name="Leader")
        captured = []

        async def next_handler(**kwargs):
            captured.append(kwargs["messages"][0].get_text_content())

            async def response():
                yield ChatResponse(
                    content=[TextBlock(text="Verified response")],
                    is_last=True,
                    usage=ChatUsage(input_tokens=10, output_tokens=13, time=0),
                )

            return response()

        middleware = SharedContextIsolationMiddleware(
            "task", self.service, "u", "ticket-1", task_id=task_id
        )
        kwargs = {
            "messages": [SystemMsg(name="system", content="Coordinate")],
            "tools": [],
            "current_model": self.model,
        }
        for n in range(2):
            if n:
                await self.service.append_event(
                    user_id="u",
                    team_id="ticket-1",
                    kind="external_event",
                    content="new-provider-evidence",
                    source_session_id="peer-session",
                )
            stream = await middleware.on_model_call(agent, kwargs, next_handler)
            self.assertEqual(1, len([chunk async for chunk in stream]))
        self.assertNotIn("new-provider-evidence", captured[0])
        self.assertIn("new-provider-evidence", captured[1])
        record = await self.storage.get_team_shared_context("u", "ticket-1")
        branch = record.state.tasks[task_id].collaboration["leader-session"]
        self.assertEqual(2, branch.model_calls)
        self.assertEqual(
            record.state.metrics.total_measured_prompt_tokens + 26,
            branch.measured_tokens,
        )

    async def test_slow_model_is_cancelled_at_active_budget(self):
        self.service.config = SharedContextConfig(collaboration_max_active_seconds=0.01)
        state = AgentState(session_id="worker-session")
        middleware = SharedContextIsolationMiddleware(
            "task", self.service, "u", "ticket-1"
        )

        async def slow(**kwargs):
            await asyncio.sleep(1)
            self.fail("The runtime failed to cancel a slow model")

        with self.assertRaises(CollaborationStoppedError):
            await middleware.on_model_call(
                SimpleNamespace(state=state, name="Worker"),
                {
                    "messages": [SystemMsg(name="system", content="Work")],
                    "tools": [],
                    "current_model": self.model,
                },
                slow,
            )
        record = await self.storage.get_team_shared_context("u", "ticket-1")
        self.assertEqual(
            "stopped",
            record.state.tasks[record.state.active_task_id]
            .collaboration["worker-session"]
            .status,
        )

    async def test_leader_question_survives_late_worker_result(self):
        await self.service.append_event(
            user_id="u",
            team_id="t",
            kind="customer_message",
            content="help",
            source_session_id="leader",
        )
        await self.service.append_event(
            user_id="u",
            team_id="t",
            kind="requires_user_input",
            content="Which location?",
            source_session_id="leader",
        )
        await self.service.append_event(
            user_id="u",
            team_id="t",
            kind="result",
            content="late report",
            source_session_id="worker",
        )
        self.assertEqual(
            await self.service.pending_user_question("u", "t"), "Which location?"
        )
        self.assertTrue(
            (
                await self.service.team_evidence_status(
                    "u", "t", leader_session_id="leader"
                )
            )[-1]
        )
        await self.service.append_event(
            user_id="u",
            team_id="t",
            kind="customer_message",
            content="location A",
            source_session_id="leader",
        )
        self.assertIsNone(await self.service.pending_user_question("u", "t"))

    def test_compact_mcp_facts_preserves_sources_and_business_ids(self):
        items = []
        for index in range(20):
            items.append(
                {
                    "id": f"item-{index}",
                    "task_id": "task",
                    "kind": "fact",
                    "authority": "tool_verified",
                    "source_event_ids": [f"event-{index}"],
                    "text": json.dumps(
                        {
                            "state": "success",
                            "tool_call": {
                                "id": f"call-{index}",
                                "name": "mcp__x__get",
                                "input": '{"ticket_id":"external-1"}',
                            },
                            "tool_result": {
                                "output": [
                                    {
                                        "type": "text",
                                        "id": f"block-{index}",
                                        "text": '{"id":"external-1","created_at":"today","status":"not found"}',
                                    }
                                ]
                            },
                        }
                    ),
                }
            )
        original = json.dumps(items)
        projected = self.service._compact_tool_facts(items)
        self.assertEqual(len(projected), 1)
        self.assertEqual(len(projected[0]["source_event_ids"]), 20)
        self.assertEqual(len(projected[0]["equivalent_item_ids"]), 20)
        self.assertIn("external-1", projected[0]["text"])
        self.assertIn("created_at", projected[0]["text"])
        self.assertEqual(json.dumps(items), original)
        changed = {**items[0], "text": items[0]["text"].replace("not found", "found")}
        self.assertEqual(len(self.service._compact_tool_facts([*items, changed])), 2)
        other_task = {**items[0], "task_id": "different"}
        self.assertEqual(len(self.service._compact_tool_facts([*items, other_task])), 2)

    def test_packet_projects_events_already_in_authoritative_items(self):
        events = [
            SharedContextEvent(
                id="customer-1",
                revision=1,
                task_id="task",
                kind="customer_message",
                content="Need a hotel",
            ),
            SharedContextEvent(
                id="tool-1",
                revision=2,
                task_id="task",
                kind="external_event",
                content='{"raw":"tool envelope"}',
            ),
            SharedContextEvent(
                id="question-1",
                revision=3,
                task_id="task",
                kind="question",
                content="Which hotel is available?",
            ),
        ]
        items = [
            {
                "id": "constraint-1",
                "task_id": "task",
                "kind": "constraint",
                "authority": "customer_confirmed",
                "source_event_ids": ["customer-1"],
                "text": "Need a hotel",
            },
            {
                "id": "fact-1",
                "task_id": "task",
                "kind": "fact",
                "authority": "tool_verified",
                "source_event_ids": ["tool-1"],
                "text": "verified hotel result",
            },
        ]

        recent, represented = self.service._project_represented_events(
            events,
            items,
        )

        self.assertEqual([event.id for event in recent], ["question-1"])
        self.assertEqual(
            [event.id for event in represented],
            ["customer-1", "tool-1"],
        )

    async def test_booking_receipt_is_authoritative_and_same_call_is_reused(self):
        customer = await self.service.append_event(
            user_id="u",
            team_id="booking-team",
            kind="customer_message",
            content="Book the selected flight",
        )
        call = ToolCallBlock(
            id="booking-call",
            name="mcp__travel__book_flight",
            input='{"flight_id":"VN131"}',
        )
        exact = json.dumps(
            {
                "tool_call": call.model_dump(mode="json"),
                "tool_result": {
                    "id": "booking-call",
                    "name": call.name,
                    "output": [
                        {
                            "type": "text",
                            "text": '{"booking_id":"FB-1","status":"confirmed"}',
                        },
                    ],
                    "state": "success",
                    "metadata": {},
                },
                "state": "success",
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        await self.service.append_event(
            user_id="u",
            team_id="booking-team",
            task_id=customer.task_id,
            kind="external_event",
            content=exact,
            delta=ContextDelta(add_confirmed_facts=(exact,)),
        )
        await self.service.append_event(
            user_id="u",
            team_id="booking-team",
            task_id=customer.task_id,
            kind="result",
            content="Booking FB-1 confirmed.",
            source_session_id="booking-agent",
        )

        packet, _ = await self.service.prepare_packet(
            model=self.model,  # type: ignore[arg-type]
            user_id="u",
            team_id="booking-team",
            task_id=customer.task_id,
        )
        data = json.loads(packet)
        self.assertIn("FB-1", json.dumps(data["authoritative_state"]))
        self.assertNotIn("FB-1", json.dumps(data["recent_events"]))

        middleware = SharedContextIsolationMiddleware(
            "task",
            self.service,
            "u",
            "booking-team",
            task_id=customer.task_id,
        )
        executed = False

        async def execute(**_kwargs):
            nonlocal executed
            executed = True
            if False:
                yield None

        agent = SimpleNamespace(
            state=AgentState(session_id="booking-session"),
            name="Booking Agent",
        )
        reused = [
            result
            async for result in middleware.on_acting(
                agent,
                {"tool_call": call},
                execute,
            )
        ]
        self.assertFalse(executed)
        self.assertTrue(reused[0].metadata["reused_authoritative_result"])
        self.assertIn("FB-1", reused[0].content[0].text)

        await self.service.append_event(
            user_id="u",
            team_id="booking-team",
            task_id=customer.task_id,
            kind="customer_message",
            content="Check the booking again now",
        )
        self.assertIsNone(
            await self.service.successful_tool_result(
                "u",
                "booking-team",
                customer.task_id,
                call.name,
                call.input,
            ),
        )

    def setUp(self) -> None:
        self.storage = _Storage()
        self.bus = InMemoryMessageBus()
        self.model = _MeasuredModel()
        self.service = SharedContextService(
            self.storage,  # type: ignore[arg-type]
            self.bus,
            SharedContextConfig(
                packet_max_tokens=900,
                history_budget_tokens=400,
                summary_trigger_ratio=0.8,
                recent_history_ratio=0.1,
                summary_max_ratio=0.25,
                summary_attempts=2,
            ),
        )

    async def test_worker_report_is_not_semantically_validated(self):
        customer = await self.service.append_event(
            user_id="u",
            team_id="claim-team",
            kind="customer_message",
            content="Find a hotel for 2 people with a 3 million VND budget",
            source_session_id="leader-session",
        )
        await self.service.append_event(
            user_id="u",
            team_id="claim-team",
            task_id=customer.task_id,
            kind="external_event",
            content="Verified Hotel costs 1500000 VND and is available",
            source_session_id="worker-session",
        )

        receipt = await self.service.coordinate_handoff(
            user_id="u",
            team_id="claim-team",
            task_id=customer.task_id,
            sender="worker-session",
            recipients=("leader-session",),
            owner="leader-session",
            handoff_id="unchecked-report",
            kind="result",
            content="Imaginary Resort costs 1500000 VND and is available",
        )

        record = await self.storage.get_team_shared_context("u", "claim-team")
        branch = record.state.tasks[customer.task_id].collaboration.get(
            "worker-session"
        )
        self.assertIn("unchecked-report", branch.receipts)
        self.assertEqual("result", receipt["kind"])
        self.assertIn("Imaginary Resort", receipt["content"])

    async def test_worker_progress_is_not_semantically_validated(self):
        customer = await self.service.append_event(
            user_id="u",
            team_id="progress-claim-team",
            kind="customer_message",
            content="Plan a beach trip",
            source_session_id="leader-session",
        )

        receipt = await self.service.coordinate_handoff(
            user_id="u",
            team_id="progress-claim-team",
            task_id=customer.task_id,
            sender="worker-session",
            recipients=("leader-session",),
            owner="leader-session",
            handoff_id="unchecked-progress",
            kind="progress",
            content="I will add Imaginary Resort to the itinerary",
        )
        self.assertEqual("progress", receipt["kind"])

    async def test_worker_and_coordinator_preserve_reference_chain(self):
        customer = await self.service.append_event(
            user_id="u",
            team_id="claim-chain",
            kind="customer_message",
            content="Find a hotel for 2 people with a 3 million VND budget",
            source_session_id="leader-session",
        )
        tool = await self.service.append_event(
            user_id="u",
            team_id="claim-chain",
            task_id=customer.task_id,
            kind="external_event",
            content="Verified Hotel costs 1500000 VND and is available",
            source_session_id="provider-session",
        )
        provider_receipt = await self.service.coordinate_handoff(
            user_id="u",
            team_id="claim-chain",
            task_id=customer.task_id,
            sender="provider-session",
            recipients=("leader-session",),
            owner="leader-session",
            handoff_id="provider-report",
            kind="result",
            content="Verified Hotel costs 1,500,000 VND and is available",
        )
        self.assertEqual("review", provider_receipt["status"])
        provider = await self.service.append_event(
            user_id="u",
            team_id="claim-chain",
            task_id=customer.task_id,
            event_id="provider-report",
            kind="result",
            content="Verified Hotel costs 1,500,000 VND and is available",
            source_session_id="provider-session",
            reference_event_ids=(tool.id,),
        )
        coordinator = await self.service.coordinate_handoff(
            user_id="u",
            team_id="claim-chain",
            task_id=customer.task_id,
            sender="planner-session",
            recipients=("leader-session",),
            owner="leader-session",
            handoff_id="planner-report",
            kind="result",
            content="Choose Verified Hotel at 1,500,000 VND for 2 people",
            references=(provider.id,),
        )
        self.assertEqual([provider.id], coordinator["reference_event_ids"])

        unchecked = await self.service.coordinate_handoff(
            user_id="u",
            team_id="claim-chain",
            task_id=customer.task_id,
            sender="planner-session-2",
            recipients=("leader-session",),
            owner="leader-session",
            handoff_id="planner-unchecked",
            kind="result",
            content=(
                "Choose Verified Hotel at 1,500,000 VND and visit "
                "Imaginary Cafe"
            ),
            references=(provider.id,),
        )
        self.assertIn("Imaginary Cafe", unchecked["content"])

    async def test_latest_worker_result_supersedes_older_packet_snapshot(self):
        customer = await self.service.append_event(
            user_id="u",
            team_id="result-snapshot",
            kind="customer_message",
            content="Compare current options",
        )
        for event_id, content in (
            ("old-result", "Old complete result"),
            ("new-result", "New complete result"),
        ):
            await self.service.append_event(
                user_id="u",
                team_id="result-snapshot",
                task_id=customer.task_id,
                event_id=event_id,
                kind="result",
                content=content,
                source_session_id="worker-session",
            )

        record = await self.storage.get_team_shared_context("u", "result-snapshot")
        outputs = [item for item in record.state.items if item.kind == "output"]
        self.assertEqual(["superseded", "active"], [item.status for item in outputs])
        packet, _ = await self.service.prepare_packet(
            model=self.model,  # type: ignore[arg-type]
            user_id="u",
            team_id="result-snapshot",
        )
        self.assertIn("New complete result", packet)
        self.assertNotIn("Old complete result", packet)

    async def test_verified_worker_report_projects_covered_raw_tool_payload(self):
        customer = await self.service.append_event(
            user_id="u",
            team_id="reported-tool-fact",
            kind="customer_message",
            content="Find a verified option",
        )
        await self.service.append_event(
            user_id="u",
            team_id="reported-tool-fact",
            task_id=customer.task_id,
            event_id="tool-event",
            kind="external_event",
            source_session_id="worker-session",
            content=json.dumps(
                {
                    "state": "success",
                    "tool_call": {
                        "name": "mcp__demo__search",
                        "input": "{}",
                    },
                    "tool_result": {
                        "output": [
                            {
                                "type": "text",
                                "text": json.dumps(
                                    {
                                        "name": "Verified Place",
                                        "secret_detail": "raw-only-value",
                                    }
                                ),
                            }
                        ]
                    },
                }
            ),
        )
        await self.service.append_event(
            user_id="u",
            team_id="reported-tool-fact",
            task_id=customer.task_id,
            event_id="worker-result",
            kind="result",
            source_session_id="worker-session",
            content="Verified Place is available.",
        )

        packet, _ = await self.service.prepare_packet(
            model=self.model,  # type: ignore[arg-type]
            user_id="u",
            team_id="reported-tool-fact",
        )
        self.assertIn("Verified Place is available", packet)
        self.assertNotIn("raw-only-value", packet)

    def test_worker_report_is_trusted_without_tool_evidence(self):
        report = SharedContextEvent(
            id="worker-report",
            revision=2,
            task_id="task-1",
            kind="answer",
            content="Flight details supplied to the Leader",
            source_session_id="flight-agent",
        )

        self.assertEqual(
            {report.id},
            self.service._trusted_event_ids({report.id: report}),
        )

    async def test_summary_retry_requires_only_concise_structured_text(self) -> None:
        prompts = []
        schemas = []

        class Model(_MeasuredModel):
            async def generate_structured_output(model, **kwargs):
                prompts.append(kwargs["messages"][0].get_text_content())
                schemas.append(kwargs["structured_model"].model_json_schema())
                return SimpleNamespace(
                    content=(
                        {}
                        if len(prompts) == 1
                        else {
                            "processed": [
                                {"text": "User selected an option"},
                            ]
                        }
                    ),
                )

        event = SharedContextEvent(
            id="actual-event",
            revision=3,
            task_id="task",
            kind="customer_message",
            content="An unrelated id nested-message-id appears in the text",
        )
        prior = SharedContextSummary(
            text="Old context [sources: old-event-id]",
            source_event_ids=("old-event-id",),
            covered_through_revision=2,
            input_tokens=10,
            output_tokens=5,
        )
        text, _, _, attempts, calls = await self.service._summarize(
            Model(), prior, [event]
        )
        self.assertEqual((attempts, calls), (2, 2))
        self.assertIn("Previous validation error", prompts[1])
        self.assertIn("User selected an option", text)
        self.assertNotIn("source_event_ids", str(schemas[0]))

    async def test_summary_does_not_require_per_event_citations(self) -> None:
        class Model(_MeasuredModel):
            async def generate_structured_output(model, **kwargs):
                return SimpleNamespace(
                    content={
                        "processed": [
                            {"text": "Two customer requests were condensed"},
                        ]
                    }
                )

        events = [
            SharedContextEvent(
                id=f"e{i}",
                revision=i,
                task_id="task",
                kind="customer_message",
                content="text",
            )
            for i in (1, 2)
        ]
        text, _input, _output, attempts, calls = await self.service._summarize(
            Model(), None, events
        )
        self.assertIn("Two customer requests were condensed", text)
        self.assertNotIn("sources:", text)
        self.assertEqual((attempts, calls), (1, 1))

    async def test_summary_may_omit_transient_internal_question(self) -> None:
        class Model(_MeasuredModel):
            async def generate_structured_output(model, **kwargs):
                del kwargs
                return SimpleNamespace(
                    content={
                        "processed": [
                            {"text": "Customer requirement preserved"},
                        ]
                    }
                )

        events = [
            SharedContextEvent(
                id="customer",
                revision=1,
                task_id="task",
                kind="customer_message",
                content="Plan the trip",
            ),
            SharedContextEvent(
                id="peer-question",
                revision=2,
                task_id="task",
                kind="question",
                content="Provide the hotel price",
            ),
        ]

        text, _input, _output, attempts, calls = await self.service._summarize(
            Model(), None, events
        )

        self.assertIn("Customer requirement preserved", text)
        self.assertNotIn("Provide the hotel price", text)
        self.assertEqual((attempts, calls), (1, 1))

    async def test_summary_may_omit_raw_tool_event_kept_as_authoritative_fact(
        self,
    ) -> None:
        class Model(_MeasuredModel):
            async def generate_structured_output(model, **kwargs):
                del kwargs
                return SimpleNamespace(
                    content={
                        "processed": [
                            {"text": "Customer requirement preserved"},
                        ]
                    }
                )

        events = [
            SharedContextEvent(
                id="customer",
                revision=1,
                task_id="task",
                kind="customer_message",
                content="Find a verified option",
            ),
            SharedContextEvent(
                id="provider-call",
                revision=2,
                task_id="task",
                kind="external_event",
                content="Raw provider envelope retained in authoritative state",
            ),
        ]

        text, _input, _output, attempts, calls = await self.service._summarize(
            Model(), None, events
        )

        self.assertIn("Customer requirement preserved", text)
        self.assertNotIn("Raw provider envelope", text)
        self.assertEqual((attempts, calls), (1, 1))

    def test_legacy_single_summary_migrates_to_active_task(self) -> None:
        record = TeamSharedContextRecord.model_validate(
            {
                "id": "ticket-legacy",
                "user_id": "u",
                "team_id": "ticket-legacy",
                "state": {
                    "active_task_id": "task-legacy",
                    "tasks": {
                        "task-legacy": {
                            "id": "task-legacy",
                            "objective": "Continue old ticket",
                        },
                    },
                    "summary": {
                        "text": "Old shared history",
                        "source_event_ids": ["event-old"],
                        "covered_through_revision": 1,
                        "input_tokens": 10,
                        "output_tokens": 4,
                    },
                },
            },
        )

        self.assertIn("task-legacy", record.state.summaries)
        self.assertEqual(
            record.state.summaries["task-legacy"].text,
            "Old shared history",
        )

    async def test_cross_agent_packet_contains_customer_and_result(self) -> None:
        customer = await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="customer_message",
            content="Check-in 17/10, check-out 18/10, two adults.",
            event_id="customer-1",
            source_agent_id="leader",
        )
        result = await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="result",
            content="Hotel A is available above two million VND.",
            event_id="agent-a-result",
            source_agent_id="agent-a",
        )

        packet, measured = await self.service.prepare_packet(
            model=self.model,  # type: ignore[arg-type]
            user_id="u",
            team_id="ticket-1",
        )

        self.assertIn(customer.content, packet)
        self.assertIn(result.content, packet)
        self.assertGreater(measured, 0)
        record = await self.storage.get_team_shared_context("u", "ticket-1")
        self.assertEqual(record.state.metrics.last_packet_tokens, measured)
        self.assertGreater(self.model.count_calls, 0)

    async def test_idempotent_event_retry_does_not_duplicate_state(self) -> None:
        kwargs = {
            "user_id": "u",
            "team_id": "ticket-1",
            "kind": "customer_message",
            "content": "One room for two adults",
            "event_id": "same-message",
        }
        first = await self.service.append_event(**kwargs)
        second = await self.service.append_event(**kwargs)
        record = await self.storage.get_team_shared_context("u", "ticket-1")

        self.assertEqual(first.id, second.id)
        self.assertEqual(len(record.state.events), 1)
        self.assertEqual(len(record.state.items), 1)
        self.assertEqual(record.state.revision, 1)

    async def test_late_agent_reply_is_recorded_but_not_promoted(self) -> None:
        first = await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="customer_message",
            content="Initial requirement",
            event_id="customer-1",
        )
        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="customer_message",
            content="Changed requirement",
            event_id="customer-2",
            task_id=first.task_id,
        )

        late = await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="customer_reply",
            content="Answer based on the initial requirement",
            event_id="assistant-late",
            task_id=first.task_id,
            based_on_revision=first.revision,
        )

        record = await self.storage.get_team_shared_context("u", "ticket-1")
        self.assertTrue(late.stale)
        self.assertFalse(
            any(
                item.text == late.content and item.kind == "output"
                for item in record.state.items
            ),
        )

    async def test_next_partner_style_message_links_the_only_pending_question(
        self,
    ) -> None:
        question = await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="requires_user_input",
            content="Which option do you prefer?",
            event_id="question-1",
        )

        answer = await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="customer_message",
            content="I prefer the second option.",
            event_id="customer-answer-1",
            task_id=question.task_id,
        )

        record = await self.storage.get_team_shared_context("u", "ticket-1")
        self.assertEqual(question.id, answer.in_reply_to)
        self.assertEqual(
            (),
            record.state.tasks[question.task_id].pending_question_ids,
        )

    async def test_out_of_order_partner_projection_cannot_rewind_state(self) -> None:
        newest = await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            task_id="workflow-1",
            kind="customer_message",
            content="Newest committed workflow input",
            event_id="workflow-event-3",
            source_workflow_revision=3,
        )
        older = await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            task_id="workflow-1",
            kind="customer_message",
            content="Late projection from an older workflow revision",
            event_id="workflow-event-2",
            source_workflow_revision=2,
        )

        record = await self.storage.get_team_shared_context("u", "ticket-1")
        task = record.state.tasks["workflow-1"]
        self.assertFalse(newest.stale)
        self.assertTrue(older.stale)
        self.assertEqual(3, task.latest_workflow_revision)
        self.assertFalse(
            any(item.source_event_ids == (older.id,) for item in record.state.items),
        )

    async def test_idempotency_key_reuse_with_new_payload_is_rejected(self) -> None:
        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="result",
            content="Original output",
            event_id="stable-id",
        )
        with self.assertRaisesRegex(ValueError, "different payload"):
            await self.service.append_event(
                user_id="u",
                team_id="ticket-1",
                kind="result",
                content="Mutated output",
                event_id="stable-id",
            )

        record = await self.storage.get_team_shared_context("u", "ticket-1")
        self.assertEqual(len(record.state.events), 1)
        self.assertEqual(record.state.events[0].content, "Original output")

    async def test_references_and_isolated_modes_do_not_leak_history(self) -> None:
        first = await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="result",
            content="Private-reference-one",
        )
        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="result",
            content="Unreferenced-result-two",
        )

        references, _ = await self.service.prepare_packet(
            model=self.model,  # type: ignore[arg-type]
            user_id="u",
            team_id="ticket-1",
            mode="references",
            reference_event_ids=(first.id,),
        )
        isolated, tokens = await self.service.prepare_packet(
            model=self.model,  # type: ignore[arg-type]
            user_id="u",
            team_id="ticket-1",
            mode="isolated",
        )

        self.assertIn("Private-reference-one", references)
        self.assertNotIn("Unreferenced-result-two", references)
        self.assertEqual((isolated, tokens), ("", 0))

    async def test_packet_exposes_customer_source_message_id(self) -> None:
        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="customer_message",
            content="Two adults, no special preference",
            event_id="customer-event-1",
            source_message_id="customer-message-1",
        )

        packet, _ = await self.service.prepare_packet(
            model=self.model,  # type: ignore[arg-type]
            user_id="u",
            team_id="ticket-1",
        )
        data = json.loads(packet)
        customer_item = next(
            item
            for item in data["authoritative_state"]["items"]
            if item["authority"] == "customer_confirmed"
        )

        self.assertEqual(
            ["customer-message-1"],
            customer_item["source_message_ids"],
        )

    async def test_reference_can_target_an_event_from_another_task(self) -> None:
        referenced = await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            task_id="task-b",
            kind="result",
            content="Cross-task evidence",
            delta=ContextDelta(add_outputs=("Structured cross-task output",)),
        )
        packet, _ = await self.service.prepare_packet(
            model=self.model,  # type: ignore[arg-type]
            user_id="u",
            team_id="ticket-1",
            mode="references",
            task_id="task-a",
            reference_event_ids=(referenced.id,),
        )

        self.assertIn("Cross-task evidence", packet)
        self.assertIn("Structured cross-task output", packet)

    async def test_summary_keeps_raw_sources_and_recent_events(self) -> None:
        for index in range(12):
            await self.service.append_event(
                user_id="u",
                team_id="ticket-1",
                kind="progress",
                content=f"progress-{index} " + ("detail " * 20),
                event_id=f"event-{index}",
            )

        packet, _ = await self.service.prepare_packet(
            model=self.model,  # type: ignore[arg-type]
            user_id="u",
            team_id="ticket-1",
        )
        record = await self.storage.get_team_shared_context("u", "ticket-1")

        task_id = record.state.active_task_id
        self.assertIn(task_id, record.state.summaries)
        self.assertEqual(len(record.state.events), 12)
        self.assertEqual(record.state.metrics.compactions, 1)
        self.assertEqual(record.state.metrics.compaction_failures, 0)
        self.assertGreater(record.state.metrics.last_summary_input_tokens, 0)
        self.assertGreater(record.state.metrics.last_summary_output_tokens, 0)
        self.assertIn('"summary"', packet)
        self.assertIn("progress-11", packet)

    async def test_summary_failure_preserves_sources_and_reports_metric(self) -> None:
        failing = _MeasuredModel(fail_summary=True)
        for index in range(8):
            await self.service.append_event(
                user_id="u",
                team_id="ticket-1",
                kind="progress",
                content=f"event-{index} " + ("x " * 30),
            )

        packet, measured = await self.service.prepare_packet(
            model=failing,  # type: ignore[arg-type]
            user_id="u",
            team_id="ticket-1",
        )
        record = await self.storage.get_team_shared_context("u", "ticket-1")

        self.assertTrue(packet)
        self.assertLessEqual(measured, self.service.config.packet_max_tokens)
        self.assertNotIn('"summary_failed_packet_fallback"', packet)
        self.assertIn(record.state.active_task_id, record.state.summaries)
        self.assertIn("Deterministic conversation summary", packet)
        self.assertEqual(len(record.state.events), 8)
        self.assertEqual(record.state.metrics.compactions, 1)
        self.assertEqual(record.state.metrics.compaction_failures, 1)
        self.assertEqual(failing.summary_calls, 2)
        self.assertEqual(record.state.metrics.last_summary_attempts, 2)
        self.assertEqual(record.state.metrics.summary_model_calls, 2)

    async def test_concurrent_workers_share_one_successful_compaction(self) -> None:
        class SlowModel(_MeasuredModel):
            async def generate_structured_output(model, **kwargs):
                await asyncio.sleep(0.01)
                return await super().generate_structured_output(**kwargs)

        model = SlowModel()
        for index in range(8):
            await self.service.append_event(
                user_id="u",
                team_id="ticket-1",
                kind="progress",
                content=f"progress-{index} " + "text " * 25,
            )
        await asyncio.gather(
            *[
                self.service.prepare_packet(
                    model=model, user_id="u", team_id="ticket-1"
                )
                for _ in range(4)
            ]
        )
        self.assertEqual(model.summary_calls, 1)
        record = await self.storage.get_team_shared_context("u", "ticket-1")
        self.assertEqual(len(record.state.events), 8)

    async def test_customer_append_during_summary_is_in_the_returned_snapshot(
        self,
    ) -> None:
        service = self.service

        class InterleavedModel(_MeasuredModel):
            async def generate_structured_output(model, **kwargs):
                await service.append_event(
                    user_id="u",
                    team_id="ticket-1",
                    kind="customer_message",
                    content="A new requirement arrived",
                    event_id="newest-customer",
                )
                return await super().generate_structured_output(**kwargs)

        for index in range(8):
            await service.append_event(
                user_id="u",
                team_id="ticket-1",
                kind="progress",
                content="old progress " * 15,
            )
        packet, _ = await service.prepare_packet(
            model=InterleavedModel(), user_id="u", team_id="ticket-1"
        )
        data = json.loads(packet)
        visible_source_ids = {
            source_id
            for item in data["authoritative_state"]["items"]
            for source_id in item["source_event_ids"]
        } | {event["id"] for event in data["recent_events"]}
        self.assertIn("newest-customer", visible_source_ids)
        record = await self.storage.get_team_shared_context("u", "ticket-1")
        newest_revision = next(
            event.revision
            for event in record.state.events
            if event.id == "newest-customer"
        )
        self.assertGreaterEqual(
            data["revision"],
            newest_revision,
        )

    def test_repeated_events_are_deduped_before_summary(self) -> None:
        events = [
            SharedContextEvent(
                id=f"result-{index}",
                revision=index,
                task_id="task",
                kind="result",
                content="Same flight result",
            )
            for index in (1, 2)
        ]

        deduped = self.service._dedupe_summary_events(events)

        self.assertEqual(["result-2"], [event.id for event in deduped])

    async def test_required_state_over_budget_fails_instead_of_truncating(self) -> None:
        service = SharedContextService(
            self.storage,  # type: ignore[arg-type]
            self.bus,
            SharedContextConfig(
                packet_max_tokens=80,
                history_budget_tokens=60,
                summary_trigger_ratio=0.8,
                recent_history_ratio=0.1,
                summary_max_ratio=0.25,
            ),
        )
        await service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="customer_message",
            content="mandatory-customer-state " * 80,
        )

        with self.assertRaises(SharedContextBudgetError):
            await service.prepare_packet(
                model=self.model,  # type: ignore[arg-type]
                user_id="u",
                team_id="ticket-1",
            )
        record = await self.storage.get_team_shared_context("u", "ticket-1")
        self.assertIn("mandatory-customer-state", record.state.items[0].text)
        self.assertGreater(record.state.metrics.last_required_state_tokens, 80)
        self.assertEqual(record.state.metrics.packet_budget_failures, 1)

    async def test_explicit_reference_over_budget_is_not_silently_dropped(self) -> None:
        service = SharedContextService(
            self.storage,  # type: ignore[arg-type]
            self.bus,
            SharedContextConfig(
                packet_max_tokens=80,
                history_budget_tokens=60,
                summary_trigger_ratio=0.8,
                recent_history_ratio=0.1,
                summary_max_ratio=0.25,
            ),
        )
        event = await service.append_event(
            user_id="u",
            team_id="ticket-1",
            task_id="side-task",
            kind="progress",
            content="explicit-reference " * 100,
        )

        with self.assertRaises(SharedContextBudgetError):
            await service.prepare_packet(
                model=self.model,  # type: ignore[arg-type]
                user_id="u",
                team_id="ticket-1",
                mode="references",
                reference_event_ids=(event.id,),
            )

    async def test_important_result_over_budget_is_not_silently_dropped(self) -> None:
        service = SharedContextService(
            self.storage,  # type: ignore[arg-type]
            self.bus,
            SharedContextConfig(
                packet_max_tokens=80,
                history_budget_tokens=60,
                summary_trigger_ratio=0.8,
                recent_history_ratio=0.1,
                summary_max_ratio=0.25,
            ),
        )
        await service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="result",
            content="important-result " * 100,
        )

        with self.assertRaises(SharedContextBudgetError):
            await service.prepare_packet(
                model=self.model,  # type: ignore[arg-type]
                user_id="u",
                team_id="ticket-1",
            )

    async def test_summaries_are_isolated_per_task(self) -> None:
        for task_id, marker in (("task-a", "alpha"), ("task-b", "bravo")):
            for index in range(10):
                await self.service.append_event(
                    user_id="u",
                    team_id="ticket-1",
                    task_id=task_id,
                    kind="progress",
                    content=f"{marker}-{index} " + ("detail " * 20),
                    event_id=f"{task_id}-{index}",
                )
            packet, _ = await self.service.prepare_packet(
                model=self.model,  # type: ignore[arg-type]
                user_id="u",
                team_id="ticket-1",
                task_id=task_id,
            )
            self.assertIn(marker, packet)

        record = await self.storage.get_team_shared_context("u", "ticket-1")
        self.assertEqual(set(record.state.summaries), {"task-a", "task-b"})
        packet_a, _ = await self.service.prepare_packet(
            model=self.model,  # type: ignore[arg-type]
            user_id="u",
            team_id="ticket-1",
            task_id="task-a",
        )
        self.assertNotIn("bravo", packet_a)

    async def test_existing_customer_history_bootstrap_is_idempotent(self) -> None:
        messages = [
            UserMsg(id="old-user", name="user", content="Old requirement"),
            AssistantMsg(
                id="old-reply",
                name="leader",
                content="Old customer-visible result",
            ),
            UserMsg(id="old-user", name="user", content="Old requirement"),
        ]
        first = await self.service.bootstrap_customer_history(
            user_id="u",
            team_id="ticket-1",
            messages=messages,
        )
        second = await self.service.bootstrap_customer_history(
            user_id="u",
            team_id="ticket-1",
            messages=messages,
        )
        record = await self.storage.get_team_shared_context("u", "ticket-1")

        self.assertEqual((first, second), (2, 0))
        self.assertEqual(len(record.state.events), 2)
        self.assertTrue(record.state.customer_history_bootstrapped)
        self.assertEqual(record.state.metrics.bootstrap_events, 2)

    async def test_customer_history_bootstrap_is_atomic_across_workers(
        self,
    ) -> None:
        messages = [
            UserMsg(id="customer-1", name="user", content="Newest request"),
            AssistantMsg(id="reply-1", name="leader", content="Earlier reply"),
        ]

        results = await asyncio.gather(
            *(
                self.service.bootstrap_customer_history(
                    user_id="u",
                    team_id="ticket-atomic",
                    messages=messages,
                    source_session_id="leader-session",
                    reply_owner_agent_id="leader-agent",
                )
                for _ in range(8)
            ),
        )
        record = await self.storage.get_team_shared_context(
            "u",
            "ticket-atomic",
        )

        self.assertEqual(sum(results), 2)
        self.assertEqual(len(record.state.events), 2)
        self.assertEqual(record.state.metrics.bootstrap_events, 2)
        self.assertTrue(record.state.customer_history_bootstrapped)
        self.assertTrue(
            all(
                event.source_session_id == "leader-session"
                for event in record.state.events
            ),
        )

    async def test_worker_report_is_evidence_only_after_durable_delivery(
        self,
    ) -> None:
        customer = await self.service.append_event(
            user_id="u",
            team_id="ticket-evidence",
            kind="customer_message",
            content="Find an available hotel",
            event_id="customer-evidence",
            source_session_id="leader-session",
        )
        report = await self.service.append_event(
            user_id="u",
            team_id="ticket-evidence",
            task_id=customer.task_id,
            kind="result",
            content="Verified result",
            event_id="worker-report",
            source_agent_id="worker-agent",
            source_session_id="worker-session",
        )

        before = await self.service.team_evidence_status(
            "u",
            "ticket-evidence",
            leader_session_id="leader-session",
        )
        record_id = hashlib.sha256(
            f"{report.id}\0leader-session".encode(),
        ).hexdigest()
        self.storage.handoffs[record_id] = TeamHandoffRecord(
            id=record_id,
            user_id="u",
            team_id="ticket-evidence",
            handoff_id=report.id,
            task_id=customer.task_id,
            kind="result",
            source_agent_id="worker-agent",
            source_session_id="worker-session",
            recipient_agent_id="leader-agent",
            recipient_session_id="leader-session",
            idempotency_key=report.id,
            payload={},
            delivery_status="delivered",
        )
        after = await self.service.team_evidence_status(
            "u",
            "ticket-evidence",
            leader_session_id="leader-session",
        )

        self.assertEqual(before[0], 0)
        self.assertEqual(after[0], 1)

    async def test_concurrent_writers_have_monotonic_unique_revisions(self) -> None:
        await asyncio.gather(
            *(
                self.service.append_event(
                    user_id="u",
                    team_id="ticket-1",
                    kind="progress",
                    content=f"update-{index}",
                    event_id=f"id-{index}",
                )
                for index in range(30)
            ),
        )
        record = await self.storage.get_team_shared_context("u", "ticket-1")
        self.assertEqual(len(record.state.events), 30)
        self.assertEqual(
            [event.revision for event in record.state.events],
            list(range(1, 31)),
        )

    async def test_tenant_and_ticket_isolation(self) -> None:
        await self.service.append_event(
            user_id="u1",
            team_id="ticket-a",
            kind="result",
            content="tenant-one-secret",
        )
        await self.service.append_event(
            user_id="u2",
            team_id="ticket-b",
            kind="result",
            content="tenant-two-result",
        )
        packet, _ = await self.service.prepare_packet(
            model=self.model,  # type: ignore[arg-type]
            user_id="u2",
            team_id="ticket-b",
        )
        self.assertNotIn("tenant-one-secret", packet)
        self.assertIn("tenant-two-result", packet)

    async def test_workforce_scope_binding_is_immutable(self) -> None:
        await self.service.bind_scope(
            "manager-1",
            "group-1",
            tenant_id="tenant-1",
            domain_id="domain-1",
            area_id="area-1",
            manager_account_id="manager-1",
            workflow_id="workflow-1",
        )

        with self.assertRaises(PermissionError):
            await self.service.bind_scope(
                "manager-1",
                "group-1",
                tenant_id="tenant-1",
                domain_id="domain-1",
                area_id="area-1",
                manager_account_id="manager-1",
                workflow_id="workflow-2",
            )

    async def test_thread_hop_is_derived_from_durable_history(self) -> None:
        root = await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            task_id="task-1",
            event_id="handoff-root",
            kind="handoff",
            content="Start a generic peer thread",
        )
        hop, thread_id = await self.service.validate_handoff_link(
            "u",
            "ticket-1",
            "task-1",
            root.id,
        )
        self.assertEqual((2, root.id), (hop, thread_id))
        second = await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            task_id="task-1",
            event_id="handoff-second",
            kind="answer",
            content="Continue the peer thread",
            thread_id=thread_id,
            in_reply_to=root.id,
            hop_count=hop,
        )

        hop, resolved_thread = await self.service.validate_handoff_link(
            "u",
            "ticket-1",
            "task-1",
            None,
            thread_id,
        )

        self.assertEqual(3, hop)
        self.assertEqual(root.id, resolved_thread)
        self.assertEqual(2, second.hop_count)
        terminal = await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            task_id="task-1",
            event_id="handoff-terminal",
            kind="answer",
            content="Reached the bounded end of this peer chain",
            thread_id=root.id,
            in_reply_to=second.id,
            hop_count=12,
        )
        with self.assertRaisesRegex(ValueError, "hop limit"):
            await self.service.validate_handoff_link(
                "u",
                "ticket-1",
                "task-1",
                terminal.id,
            )

    async def test_directive_survives_until_explicit_consumption(self) -> None:
        directive = ContextDirective(
            handoff_id="handoff-1",
            mode="references",
            task_id="task-1",
            reference_event_ids=("event-1",),
        )
        await self.service.register_directive("session-b", directive)
        mode, task_id, refs = await self.service.resolve_mode("session-b")
        self.assertEqual((mode, task_id, refs), ("references", "task-1", ("event-1",)))
        await self.service.consume_directive("session-b", "handoff-1")
        self.assertEqual(await self.service.pending_directives("session-b"), [])

    async def test_directive_priority_uses_task_id_from_selected_mode(self) -> None:
        await self.service.register_directive(
            "session-b",
            ContextDirective(
                handoff_id="task-handoff",
                mode="task",
                task_id="task-correct",
            ),
        )
        await self.service.register_directive(
            "session-b",
            ContextDirective(
                handoff_id="isolated-handoff",
                mode="isolated",
                task_id="task-must-not-win",
            ),
        )

        mode, task_id, refs = await self.service.resolve_mode("session-b")
        self.assertEqual((mode, task_id, refs), ("task", "task-correct", ()))

    async def test_inbox_acknowledges_directive_only_with_decoded_handoff(self) -> None:
        directive = ContextDirective(handoff_id="handoff-1", mode="task")
        await self.service.register_directive("session-b", directive)
        hint = HintBlock(
            hint="work",
            source='{"handoff_id":"handoff-1"}',
        )
        await self.bus.queue_push(
            MessageBusKeys.inbox("session-b"),
            hint.model_dump(mode="json"),
        )
        state = AgentState(session_id="session-b")
        state.reply_id = "reply-1"
        agent = SimpleNamespace(state=state, name="agent-b")

        async def next_handler(**_: object):
            if False:
                yield None

        middleware = InboxMiddleware(self.bus)
        events = [
            event
            async for event in middleware.on_reasoning(
                agent,  # type: ignore[arg-type]
                {},
                next_handler,
            )
        ]
        self.assertEqual(len(events), 1)
        self.assertEqual(await self.service.pending_directives("session-b"), [])

    async def test_context_delta_supersedes_old_fact_without_deleting_source(
        self,
    ) -> None:
        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="result",
            content="Initial result",
            delta=ContextDelta(add_confirmed_facts=("Budget is 10 million",)),
        )
        record = await self.storage.get_team_shared_context("u", "ticket-1")
        fact_id = next(item.id for item in record.state.items if item.kind == "fact")
        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="context_update",
            content="Customer changed the budget",
            delta=ContextDelta(
                add_confirmed_facts=("Budget is 20 million",),
                supersede_item_ids=(fact_id,),
            ),
        )
        record = await self.storage.get_team_shared_context("u", "ticket-1")
        old = next(item for item in record.state.items if item.id == fact_id)
        self.assertEqual(old.status, "superseded")
        self.assertEqual(len(record.state.events), 2)

    async def test_agent_delta_cannot_self_promote_authority(self) -> None:
        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="result",
            content="Agent-proposed state",
            delta=ContextDelta(
                add_constraints=("Customer supposedly chose A",),
                add_confirmed_facts=("Tool supposedly verified B",),
                add_decisions=("Payment supposedly approved",),
            ),
        )
        record = await self.storage.get_team_shared_context("u", "ticket-1")
        self.assertEqual(
            {item.authority for item in record.state.items},
            {"agent_reported"},
        )

        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="external_event",
            content="Verified tool response",
            delta=ContextDelta(add_confirmed_facts=("Tool verified C",)),
        )
        record = await self.storage.get_team_shared_context("u", "ticket-1")
        verified = next(item for item in record.state.items if item.text.endswith("C"))
        self.assertEqual(verified.authority, "tool_verified")

    async def test_pending_operations_are_structured_and_resolved_by_id(self) -> None:
        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="external_event",
            content="Two operations need an external result",
            delta=ContextDelta(
                status="waiting_external",
                add_pending_operation_ids=("operation-1", "operation-2"),
            ),
        )
        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="external_event",
            content="First operation completed",
            delta=ContextDelta(
                status="running",
                resolve_pending_operation_ids=("operation-1",),
            ),
        )
        record = await self.storage.get_team_shared_context("u", "ticket-1")
        task = record.state.tasks[record.state.active_task_id]
        self.assertEqual(task.status, "waiting_external")
        self.assertEqual(task.pending_operation_ids, ("operation-2",))

        await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="external_event",
            content="Second operation completed",
            delta=ContextDelta(
                status="running",
                resolve_pending_operation_ids=("operation-2",),
            ),
        )
        record = await self.storage.get_team_shared_context("u", "ticket-1")
        task = record.state.tasks[record.state.active_task_id]
        self.assertEqual(task.status, "running")
        self.assertEqual(task.pending_operation_ids, ())

    async def test_initial_direct_turn_is_measured_without_creating_a_team(self):
        agent = SimpleNamespace(state=AgentState(session_id="direct-session"))
        middleware = SharedContextIsolationMiddleware("task", self.service, "u", None)
        captured = {}

        async def next_handler(**kwargs):
            captured.update(kwargs)
            return ChatResponse(content=[], is_last=True)

        messages = [SystemMsg(name="system", content="direct chat")]
        await middleware.on_model_call(
            agent,
            {
                "messages": messages,
                "tools": [],
                "current_model": self.model,
            },
            next_handler,
        )
        self.assertEqual(captured["messages"], messages)
        self.assertIsNone(
            await self.storage.get_team_shared_context("u", "direct-session")
        )

    async def test_initial_leader_middleware_adopts_team_created_mid_run(self):
        event = await self.service.append_event(
            user_id="u",
            team_id="ticket-1",
            kind="customer_message",
            content="Plan a verified trip",
        )
        self.storage.sessions[("u", "leader-session")] = SimpleNamespace(
            team_id="ticket-1",
        )
        agent = SimpleNamespace(
            state=AgentState(session_id="leader-session"),
            name="Leader",
        )
        captured = {}

        async def next_handler(**kwargs):
            captured.update(kwargs)
            return ChatResponse(content=[], is_last=True)

        middleware = SharedContextIsolationMiddleware(
            "task",
            self.service,
            "u",
            None,
        )
        await middleware.on_model_call(
            agent,
            {
                "messages": [SystemMsg(name="system", content="Coordinate")],
                "tools": [],
                "current_model": self.model,
            },
            next_handler,
        )

        system_text = captured["messages"][0].get_text_content() or ""
        self.assertIn("Plan a verified trip", system_text)
        self.assertEqual(
            event.revision,
            await self.service.session_revision(
                "leader-session",
                team_id="ticket-1",
                task_id=event.task_id,
            ),
        )

    async def test_model_call_is_measured_after_isolation_filter(self) -> None:
        state = AgentState(session_id="session-b")
        state.reply_id = "current-reply"
        old_private = UserMsg(
            id="old-private",
            name="user",
            content="old private context",
        )
        state.context = [old_private.model_copy(deep=True)]
        current_input = UserMsg(
            id="current-input",
            name="user",
            content="isolated handoff",
        )
        state.context.append(current_input)
        agent = SimpleNamespace(state=state, name="worker")
        captured: dict = {}

        async def next_handler(**kwargs: object) -> object:
            captured.update(kwargs)
            return ChatResponse(content=[], is_last=True)

        middleware = SharedContextIsolationMiddleware(
            "isolated",
            self.service,
            "u",
            "ticket-1",
            [old_private],
        )
        messages = [
            SystemMsg(name="system", content="system"),
            UserMsg(name="user", content="old private summary"),
            *state.context,
        ]
        await middleware.on_model_call(
            agent,  # type: ignore[arg-type]
            {
                "messages": messages,
                "tools": [],
                "tool_choice": None,
                "current_model": self.model,
            },
            next_handler,
        )

        self.assertEqual(
            [msg.id for msg in captured["messages"]],
            [messages[0].id, "current-input"],
        )
        self.assertNotIn("old private summary", captured["messages"])
        record = await self.storage.get_team_shared_context("u", "ticket-1")
        self.assertEqual(record.state.metrics.model_calls_measured, 1)
        self.assertGreater(record.state.metrics.last_total_prompt_tokens, 0)
        self.assertEqual(
            record.state.metrics.total_measured_prompt_tokens,
            record.state.metrics.last_total_prompt_tokens,
        )
        self.assertEqual(
            record.state.metrics.last_total_prompt_tokens,
            record.state.metrics.last_tool_schema_tokens
            + record.state.metrics.last_system_prompt_tokens
            + record.state.metrics.last_conversation_tokens,
        )
        self.assertGreater(record.state.metrics.last_reserved_output_tokens, 0)
        self.assertEqual(
            record.state.metrics.last_preflight_margin_tokens,
            self.service.config.preflight_margin_tokens,
        )

    async def test_isolated_inbox_keeps_only_new_block_on_old_message(self) -> None:
        old_message = AssistantMsg(
            id="old-assistant",
            name="agent-b",
            content="old private answer",
        )
        live_message = old_message.model_copy(deep=True)
        handoff = HintBlock(
            id="current-handoff",
            source="team",
            hint="only this handoff is current",
        )
        live_message.content.append(handoff)
        state = AgentState(session_id="session-b", context=[live_message])
        state.reply_id = "new-reply"
        agent = SimpleNamespace(state=state, name="worker")
        captured: dict = {}

        async def next_handler(**kwargs: object) -> object:
            captured.update(kwargs)
            return ChatResponse(content=[], is_last=True)

        middleware = SharedContextIsolationMiddleware(
            "isolated",
            self.service,
            "u",
            "ticket-1",
            [old_message],
        )
        await middleware.on_model_call(
            agent,  # type: ignore[arg-type]
            {
                "messages": [
                    SystemMsg(name="system", content="system"),
                    live_message,
                ],
                "tools": [],
                "tool_choice": None,
                "current_model": self.model,
            },
            next_handler,
        )

        visible = captured["messages"]
        self.assertEqual([msg.id for msg in visible], [visible[0].id, "old-assistant"])
        self.assertNotIn("old private answer", visible[1].get_text_content() or "")
        self.assertEqual(visible[1].content, [handoff])

    async def test_model_call_budget_reserves_output_and_fails_loudly(self) -> None:
        model = _MeasuredModel()
        model.context_size = 20
        state = AgentState(session_id="session-b")
        state.reply_id = "current-reply"
        agent = SimpleNamespace(state=state, name="worker")
        middleware = SharedContextIsolationMiddleware(
            "task",
            self.service,
            "u",
            "ticket-1",
        )

        async def next_handler(**_: object) -> object:
            self.fail("over-budget prompt must not call the model")

        with self.assertRaises(SharedContextBudgetError):
            await middleware.on_model_call(
                agent,  # type: ignore[arg-type]
                {
                    "messages": [
                        SystemMsg(name="system", content="x" * 200),
                    ],
                    "tools": [],
                    "tool_choice": None,
                    "current_model": model,
                },
                next_handler,
            )
        record = await self.storage.get_team_shared_context("u", "ticket-1")
        self.assertEqual(record.state.metrics.prompt_budget_failures, 1)

    async def test_shared_packet_is_injected_only_at_model_call(self) -> None:
        state = AgentState(session_id="session-b")
        current = UserMsg(id="current-input", name="user", content="continue")
        state.context = [current]
        agent = SimpleNamespace(state=state, name="worker")
        captured: dict = {}

        async def next_handler(**kwargs: object) -> object:
            captured.update(kwargs)
            return ChatResponse(content=[], is_last=True)

        middleware = SharedContextIsolationMiddleware(
            "task",
            self.service,
            "u",
            "ticket-1",
            [],
            "<shared-context-packet>shared state</shared-context-packet>",
        )
        original_system = SystemMsg(name="system", content="private system")
        await middleware.on_model_call(
            agent,  # type: ignore[arg-type]
            {
                "messages": [original_system, current],
                "tools": [],
                "tool_choice": None,
                "current_model": self.model,
            },
            next_handler,
        )

        visible_system = captured["messages"][0].get_text_content() or ""
        self.assertIn("private system", visible_system)
        self.assertIn("shared state", visible_system)
        self.assertNotIn("shared state", original_system.get_text_content() or "")
