# -*- coding: utf-8 -*-
"""The case file of a customer turn: evidence and token cost."""
import json
import os
from unittest import TestCase
from unittest.mock import patch

from fastapi import HTTPException
from service_team_tools_test import _AgentInviteTestBase

from agentscope.app._router._session import get_case_file
from agentscope.app._service._case_file import build_case_file, load_turn_messages, model_prices
from agentscope.message import Msg, TextBlock, ToolCallBlock, ToolResultBlock, Usage


def _customer(mid: str, text: str) -> Msg:
    return Msg(id=mid, name="user", role="user", content=[TextBlock(text=text)])


def _reply(mid: str, name: str, agent_id: str | None, *, usage=(0, 0, 0), tools=(), text="") -> Msg:
    content = [TextBlock(text=text)] if text else []
    for index, (tool, args, output, state) in enumerate(tools):
        call_id = f"{mid}-call-{index}"
        content.append(ToolCallBlock(id=call_id, name=tool, input=json.dumps(args)))
        content.append(ToolResultBlock(id=call_id, name=tool, output=output, state=state))
    metadata = {"team_agent_id": agent_id, "team_session_id": f"{agent_id}-session"} if agent_id else {}
    return Msg(
        id=mid, name=name, role="assistant", content=content, metadata=metadata,
        usage=Usage(input_tokens=usage[0], output_tokens=usage[1], cache_input_tokens=usage[2]),
    )


def _conversation() -> list[Msg]:
    return [
        _customer("u1", "Tìm chuyến bay"),
        _reply("old", "Leader", None, usage=(500, 50, 0)),
        _customer("u2", "Đi Đà Nẵng 15/11"),
        _reply("flights-start", "Chuyên viên chuyến bay", "flights"),  # start copy
        _reply("leader-1", "Leader", None, usage=(1000, 100, 400), tools=[
            ("TeamSay", {"to": "Chuyên viên chuyến bay"}, "delivered", "success"),
        ]),
        _reply("flights-start", "Chuyên viên chuyến bay", "flights", usage=(2000, 200, 0), tools=[
            ("mcp__Travelling__search_flights", {"destination": "Đà Nẵng"}, '{"count": 1}', "success"),
            ("mcp__Travelling__check_flight_availability", {"flight_id": "QH118"}, "boom", "error"),
        ]),
        _reply("answer", "Leader", None, usage=(1500, 300, 1000), text="Có chuyến QH118"),
        _customer("u3", "Cảm ơn"),
        _reply("later", "Leader", None, usage=(100, 10, 0)),
    ]


class BuildCaseFileTest(TestCase):
    def _build(self, message_id="answer", prices=None, models=None):
        return build_case_file(
            _conversation(), message_id, leader_agent_id="leader",
            models=models or {"leader": "gpt-6-luna", "flights": "gpt-6-luna"},
            prices=prices or {},
        )

    def test_turn_runs_from_its_customer_message_to_the_next(self):
        case = self._build()
        self.assertEqual(case["turn"]["customer_message_id"], "u2")
        self.assertEqual(case["turn"]["customer_text"], "Đi Đà Nẵng 15/11")
        self.assertEqual({a["agent_id"] for a in case["agents"]}, {"leader", "flights"})
        # Any message of the turn gives the same case file.
        self.assertEqual(self._build("u2")["totals"], case["totals"])

    def test_tokens_are_summed_per_agent_and_a_stored_twice_reply_counts_once(self):
        case = self._build()
        leader = next(a for a in case["agents"] if a["agent_id"] == "leader")
        flights = next(a for a in case["agents"] if a["agent_id"] == "flights")
        self.assertEqual((leader["replies"], leader["input_tokens"], leader["output_tokens"]), (2, 2500, 400))
        self.assertEqual((flights["replies"], flights["input_tokens"]), (1, 2000))
        self.assertEqual(case["totals"]["input_tokens"], 4500)
        self.assertEqual(case["totals"]["cache_input_tokens"], 1400)

    def test_evidence_lists_business_lookups_but_not_team_messages(self):
        evidence = self._build()["evidence"]
        self.assertEqual(
            [(e["tool"], e["state"], e["agent_name"]) for e in evidence],
            [
                ("mcp__Travelling__search_flights", "success", "Chuyên viên chuyến bay"),
                ("mcp__Travelling__check_flight_availability", "error", "Chuyên viên chuyến bay"),
            ],
        )
        self.assertEqual(evidence[0]["arguments"], {"destination": "Đà Nẵng"})
        self.assertEqual(evidence[0]["result"], '{"count": 1}')

    def test_cost_needs_a_configured_price_and_never_guesses(self):
        unpriced = self._build()
        self.assertFalse(unpriced["totals"]["priced"])
        self.assertIsNone(unpriced["totals"]["cost_usd"])

        priced = self._build(prices={"gpt-6-luna": {"input": 2.0, "cached_input": 0.5, "output": 10.0}})
        leader = next(a for a in priced["agents"] if a["agent_id"] == "leader")
        # (2500 - 1400) uncached * 2 + 1400 cached * 0.5 + 400 output * 10, per 1M.
        self.assertAlmostEqual(leader["cost_usd"], (1100 * 2 + 1400 * 0.5 + 400 * 10) / 1e6)
        self.assertTrue(priced["totals"]["priced"])

        partly = self._build(models={"leader": "gpt-6-luna", "flights": "unknown-model"},
                             prices={"gpt-6-luna": {"input": 2.0, "output": 10.0}})
        self.assertFalse(partly["totals"]["priced"])

    def test_unknown_message_gives_none(self):
        self.assertIsNone(self._build("missing"))

    def test_prices_come_from_the_environment(self):
        with patch.dict(os.environ, {"WORKFORCE_MODEL_PRICES": '{"m": {"input": 1, "output": 2}, "bad": {}}'}):
            self.assertEqual(model_prices(), {"m": {"input": 1.0, "output": 2.0}})
        with patch.dict(os.environ, {"WORKFORCE_MODEL_PRICES": "not json"}):
            self.assertEqual(model_prices(), {})


class CaseFileEndpointTest(_AgentInviteTestBase):
    async def test_endpoint_reads_the_session_and_pages_back_to_the_turn_start(self):
        for message in _conversation():
            await self.storage.upsert_message(self.user_id, self.leader_session.id, message)
        with patch("agentscope.app._service._case_file._PAGE_SIZE", 2):
            loaded = await load_turn_messages(self.storage, self.user_id, self.leader_session.id, "answer")
            self.assertIn("u2", [m.id for m in loaded])
            case = await get_case_file(
                session_id=self.leader_session.id, agent_id=self.leader_agent.id,
                message_id="answer", user_id=self.user_id, storage=self.storage,
            )
        self.assertEqual(case["turn"]["customer_message_id"], "u2")
        self.assertEqual(len(case["evidence"]), 2)

    async def test_other_users_and_unknown_messages_get_404(self):
        with self.assertRaises(HTTPException) as error:
            await get_case_file(
                session_id=self.leader_session.id, agent_id=self.leader_agent.id,
                message_id="answer", user_id="someone-else", storage=self.storage,
            )
        self.assertEqual(error.exception.status_code, 404)
        with self.assertRaises(HTTPException) as error:
            await get_case_file(
                session_id=self.leader_session.id, agent_id=self.leader_agent.id,
                message_id="missing", user_id=self.user_id, storage=self.storage,
            )
        self.assertEqual(error.exception.status_code, 404)
