# -*- coding: utf-8 -*-
"""Cases saved from conversations and replayed with their real results.

A scripted model stands in for the provider; nothing calls a real model.
"""
import asyncio
import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from service_team_tools_test import _AgentInviteTestBase

from agentscope.app._router import _agent_eval as router
from agentscope.app._service import _agent_eval as agent_eval
from agentscope.app._service import _builder_eval as builder_eval
from agentscope.message import Msg, TextBlock, ToolCallBlock, ToolResultBlock
from agentscope.model import ChatResponse


class _ScriptedModel:
    """Tool calls and answers from a script; the judge always passes."""

    def __init__(self, chat, verdict=True):
        self.chat = list(chat)
        self.verdict = verdict
        self.seen_tool_results: list[str] = []

    async def generate_structured_output(self, messages, structured_model, **kwargs):
        if structured_model is builder_eval._Fixture:
            raise AssertionError("a recorded result must be used, not a generated fixture")
        return SimpleNamespace(content={
            "criteria": [{"name": n, "passed": self.verdict, "reason": "ok"} for n in builder_eval.CRITERIA],
            "summary": "ok",
        })

    async def __call__(self, messages, tools=None, **kwargs):
        for message in messages:
            for block in message.get_content_blocks():
                if isinstance(block, ToolResultBlock):
                    self.seen_tool_results.append(block.output[0].text)
        return self.chat.pop(0)


def _tool(name, args):
    return ChatResponse(content=[ToolCallBlock(id=f"c-{name}", name=name, input=json.dumps(args))], is_last=True)


def _text(text):
    return ChatResponse(content=[TextBlock(text=text)], is_last=True)


def _turn(flights_id: str) -> list[Msg]:
    def call(mid, name, output, state="success"):
        return [ToolCallBlock(id=mid, name=name, input="{}"),
                ToolResultBlock(id=mid, name=name, output=output, state=state)]

    return [
        Msg(id="u1", name="user", role="user", content=[TextBlock(text="Bay Hà Nội đi Đà Nẵng 15/11")]),
        Msg(id="r1", name="Chuyên viên chuyến bay", role="assistant",
            metadata={"team_agent_id": flights_id},
            content=[*call("a", "mcp__Travelling__search_flights", '{"items": ["QH118"]}'),
                     *call("b", "mcp__Travelling__check_flight_availability", "boom", "error"),
                     *call("c", "TeamSay", "delivered")]),
        Msg(id="r2", name="Leader", role="assistant", content=[TextBlock(text="Có chuyến QH118")]),
    ]


class CaseFromTurnTest(TestCase):
    def test_takes_the_customer_message_and_the_agents_successful_reads(self):
        scenario, recorded = agent_eval.case_from_turn(_turn("flights"), "r2", "flights", "leader")
        self.assertEqual(scenario, "Bay Hà Nội đi Đà Nẵng 15/11")
        self.assertEqual(recorded, {"search_flights": ['{"items": ["QH118"]}']})

    def test_another_agent_gets_no_recorded_data(self):
        _, recorded = agent_eval.case_from_turn(_turn("flights"), "r2", "hotel", "leader")
        self.assertEqual(recorded, {})

    def test_compare_marks_better_worse_and_new_cases(self):
        older = {"tests": [{"case_id": "a", "status": "passed"}, {"case_id": "b", "status": "failed"}]}
        newer = {"tests": [{"case_id": "a", "scenario": "x", "status": "failed"},
                           {"case_id": "b", "scenario": "y", "status": "passed"},
                           {"case_id": "c", "scenario": "z", "status": "passed"}]}
        self.assertEqual([r["change"] for r in agent_eval.compare_runs(older, newer)], ["worse", "better", "new"])


class RecordedReplayTest(TestCase):
    def test_a_recorded_read_is_replayed_instead_of_generated(self):
        model = _ScriptedModel([_tool("search_flights", {"to": "Đà Nẵng"}), _text("Có chuyến QH118")])
        agent = builder_eval.EvalAgent(name="F", system_prompt="Bạn tra chuyến bay.", tools=[
            {"tool_name": "search_flights", "description": "", "input_schema": {"type": "object"}},
        ])
        case = builder_eval.EvalCase(scenario="Bay đi Đà Nẵng", expected="Tra cứu")
        outcome = asyncio.run(builder_eval.score_case(
            model, agent, case, recorded={"search_flights": ['{"items": ["QH118"]}']},
        ))
        self.assertEqual(outcome["status"], "passed")
        self.assertEqual(outcome["result"]["tool_calls"], [{"name": "search_flights", "mode": "recorded"}])
        self.assertEqual(model.seen_tool_results, ['{"items": ["QH118"]}'])


class AgentEvalRouterTest(_AgentInviteTestBase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        agent_eval._running.clear()
        agent_eval._starts.clear()
        self.agent = self.monday_agent
        self.agent.data.tool_bindings = [
            {"id": "t1", "tool_name": "search_flights", "description": "", "input_schema": {"type": "object"}},
        ]
        await self.storage.upsert_agent(self.user_id, self.agent)
        for message in _turn(self.agent.id):
            await self.storage.upsert_message(self.user_id, self.leader_session.id, message)

    async def _create(self, **body):
        return await router.create_case(
            agent_id=self.agent.id,
            body=router.CreateEvalCaseRequest(**body),
            user_id=self.user_id,
            storage=self.storage,
        )

    async def test_save_from_a_conversation_then_replay_and_compare(self):
        case = await self._create(
            expected="Đưa chuyến QH118", session_id=self.leader_session.id,
            session_agent_id=self.leader_agent.id, message_id="r2",
        )
        self.assertEqual(case["scenario"], "Bay Hà Nội đi Đà Nẵng 15/11")
        self.assertEqual(case["recorded"], {"search_flights": ['{"items": ["QH118"]}']})
        listed = await router.list_cases(agent_id=self.agent.id, user_id=self.user_id, storage=self.storage)
        self.assertEqual([c["id"] for c in listed], [case["id"]])

        runs = []
        for verdict in (True, False):
            model = _ScriptedModel([_tool("search_flights", {}), _text("QH118")], verdict=verdict)
            with (
                patch("agentscope.app._router._workforce_console._model_config",
                      AsyncMock(return_value=SimpleNamespace(model="gpt-6-luna"))),
                patch.object(router, "get_model", AsyncMock(return_value=model)),
            ):
                run = await router.start_run(
                    agent_id=self.agent.id, user_id=self.user_id, storage=self.storage, access=None,
                )
            await agent_eval._running[self.user_id]
            runs.append(run["id"])

        done = await router.get_run(
            agent_id=self.agent.id, run_id=runs[1], compare_to=runs[0],
            user_id=self.user_id, storage=self.storage,
        )
        self.assertEqual(done["status"], "completed")
        self.assertEqual(done["report"]["total"], 1)
        self.assertEqual(done["comparison"]["cases"][0]["change"], "worse")
        self.assertEqual(len(done["version"]), 12)
        newest = await router.list_runs(agent_id=self.agent.id, limit=20, user_id=self.user_id, storage=self.storage)
        self.assertEqual([r["id"] for r in newest], [runs[1], runs[0]])

    async def test_a_case_needs_a_customer_message_and_belongs_to_its_agent(self):
        with self.assertRaises(HTTPException) as error:
            await self._create(expected="x")
        self.assertEqual(error.exception.status_code, 422)
        typed = await self._create(expected="Từ chối", scenario="Viết code giúp tôi")
        with self.assertRaises(HTTPException) as error:
            await router.delete_case(agent_id="other", case_id=typed["id"], user_id=self.user_id, storage=self.storage)
        self.assertEqual(error.exception.status_code, 404)
        await router.delete_case(agent_id=self.agent.id, case_id=typed["id"], user_id=self.user_id, storage=self.storage)
        self.assertEqual(await router.list_cases(agent_id=self.agent.id, user_id=self.user_id, storage=self.storage), [])

    async def test_runs_are_limited_per_user(self):
        agent_eval.reserve_run("u")
        agent_eval._running["u"] = asyncio.get_running_loop().create_future()
        with self.assertRaises(agent_eval.EvalLimitError):
            agent_eval.reserve_run("u")
        agent_eval._running.clear()
        for _ in range(agent_eval.RUNS_PER_DAY - 1):
            agent_eval.reserve_run("u")
        with self.assertRaises(agent_eval.EvalLimitError):
            agent_eval.reserve_run("u")

    async def test_no_cases_means_nothing_to_run(self):
        with self.assertRaises(HTTPException) as error:
            await router.start_run(agent_id=self.agent.id, user_id=self.user_id, storage=self.storage, access=None)
        self.assertEqual(error.exception.status_code, 409)
