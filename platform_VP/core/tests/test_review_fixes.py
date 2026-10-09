"""Regressions for problems found in review: each test names the failure it guards."""
import asyncio
from types import SimpleNamespace

import pytest

from awp.casefile import CaseStore
from awp.config import Settings
from awp.cost import CostService
from awp.db import Database
from awp.guard import Rules
from awp.intake.service import IntakeError, IntakeService, check_callback_url, clamp
from awp.middleware.room import ToolGateMiddleware
from awp.profiles import AgentProfile
from awp.protocol.tools import CaseFact, CaseFinalize
from awp.providers import ModelCatalog
from awp.runtime import Binding, Runtime


def run(coro):
    return asyncio.run(coro)


async def make_rt(tmp_path, **settings):
    db = Database(f"sqlite+aiosqlite:///{(tmp_path / 'r.db').as_posix()}")
    await db.create_all()
    catalog = ModelCatalog([])
    rt = Runtime(settings=Settings(**settings), db=db, cases=CaseStore(db), profiles=None,
                 catalog=catalog, cost=CostService(db, catalog), storage=None, bus=None)
    rt.rules_by_domain["d"] = Rules(safe_reply="A person will follow up.")
    IntakeService(rt, SimpleNamespace(aclose=_noop))
    return rt


async def _noop():
    return None


async def open_case(rt, ref="X"):
    cid = await rt.cases.create_case(tenant="t", domain="d", external_ref=ref, user_id="u", intake={})
    await rt.cases.bind_session(cid, "s1", "a1", "boss", "leader")
    ev = await rt.cases.add(cid, "evidence", "price_list", {"tool": "price_list", "text": "repair: 1500000 VND"})
    return cid, ev.ref


def text_of(chunk):
    return chunk.content[0].text


def test_non_resolved_answers_are_grounded_too(tmp_path):
    async def go():
        rt = await make_rt(tmp_path)
        cid, ev = await open_case(rt)
        b = Binding(cid, "s1", "a1", "boss", "leader", "u")
        out = await CaseFinalize(rt, b).call(
            answer="Your refund of 99,000,000 VND is approved", outcome="needs_human", cites=[ev])
        assert "finalized as needs_human" in text_of(out)
        case = await rt.cases.get_case(cid)
        assert case["result"]["answer"] == "A person will follow up."  # the invented figure never leaves
        assert any("99,000,000" in u for u in case["result"]["unknowns"])
        await rt.db.dispose()

    run(go())


def test_resolved_case_waits_for_peer_reports_and_unanswered_questions(tmp_path):
    async def go():
        rt = await make_rt(tmp_path)
        cid, ev = await open_case(rt)
        await rt.cases.bind_session(cid, "worker-session", "worker-agent", "tech", "worker")
        final = CaseFinalize(rt, Binding(cid, "s1", "a1", "boss", "leader", "u"))
        args = {"answer": "Repair costs 1500000 VND", "outcome": "resolved", "cites": [ev]}
        assert "tech" in text_of(await final.call(**args))
        await rt.cases.add(cid, "report", "tech", {"summary": "Costs verified."})
        question = await rt.cases.add(cid, "question", "boss", {"text": "Is the cost verified?"}, addressee="tech")
        assert question.ref in text_of(await final.call(**args))
        assert (await rt.cases.get_case(cid))["status"] == "open"
        await rt.cases.add(cid, "answer", "tech", {"to_ref": question.ref, "text": "Verified.", "evidence": [ev]})
        assert "finalized as resolved" in text_of(await final.call(**args))
        await rt.db.dispose()
    run(go())


def test_closed_case_accepts_no_more_work_and_closes_once(tmp_path):
    async def go():
        rt = await make_rt(tmp_path)
        cid, ev = await open_case(rt)
        b = Binding(cid, "s1", "a1", "boss", "leader", "u")
        first = await CaseFinalize(rt, b).call(answer="Repair costs 1500000 VND", outcome="resolved", cites=[ev])
        assert "finalized as resolved" in text_of(first)
        again = await CaseFinalize(rt, b).call(answer="Repair costs 1500000 VND", outcome="resolved", cites=[ev])
        assert "closed" in text_of(again)  # not a second result for the domain
        w = Binding(cid, "s2", "a2", "tech", "worker", "u")
        late = await CaseFact(rt, w).call(text="Repair costs 1500000 VND", evidence=[ev])
        assert "closed" in text_of(late)
        async with rt.db.engine.connect() as conn:
            from sqlalchemy import func, select

            from awp import db as dbm
            n = (await conn.execute(select(func.count()).select_from(dbm.outbox))).scalar_one()
        assert n == 1
        await rt.db.dispose()

    run(go())


def test_requester_words_do_not_prove_a_system_confirmed_something(tmp_path):
    from awp.guard import PhraseRule

    async def go():
        rt = await make_rt(tmp_path)
        rt.rules_by_domain["d"] = Rules(phrase_rules=[
            PhraseRule(("is finished",), "claims completion", unless=("status: resolved",))])
        cid, _ = await open_case(rt)
        typed = await rt.cases.add(cid, "evidence", "intake", {"tool": "intake", "text": "status: resolved (says the resident)"})
        b = Binding(cid, "s1", "a1", "boss", "leader", "u")
        out = await CaseFinalize(rt, b).call(answer="The work is finished", outcome="resolved", cites=[typed.ref])
        assert "Not accepted" in text_of(out) and "claims completion" in text_of(out)
        await rt.db.dispose()

    run(go())


def test_delivery_skips_undeliverable_rows_and_never_blocks_others(tmp_path):
    async def go():
        rt = await make_rt(tmp_path)
        intake = IntakeService(rt, SimpleNamespace(aclose=_noop))
        pull, _ = await open_case(rt, "PULL")
        await rt.cases.update_case(pull, domain="pull")
        push, _ = await open_case(rt, "PUSH")
        sent = []

        async def deliver(case, result):
            sent.append(case["external_ref"])

        intake.deliverers["d"] = deliver
        for cid in (pull, push):
            case = await rt.cases.get_case(cid)
            await rt.cases.close_case(cid, "finalized", {"outcome": "resolved"},
                                      (await intake.result_of(case, {"outcome": "resolved"})).model_dump())
        assert await intake.deliver_pending() == 1
        assert sent == ["PUSH"]
        assert await intake.deliver_pending() == 0  # the skipped row is not retried forever
        await rt.db.dispose()

    run(go())


def test_budget_cannot_be_raised_or_removed_by_a_domain():
    assert clamp(None, 5.0) == 5.0 and clamp(0, 5.0) == 5.0 and clamp(-1, 5.0) == 5.0
    assert clamp(2.0, 5.0) == 2.0 and clamp(50.0, 5.0) == 5.0
    assert clamp(None, 0.0) == 0.0 and clamp(3.0, 0.0) == 3.0


def test_callback_urls_must_be_public_http():
    check_callback_url("https://hooks.example.com/x", allow_private=False)
    for bad in ("ftp://example.com", "http://169.254.169.254/latest", "http://localhost:8000/x",
                "http://10.0.0.5/x", "http://[::1]/x", "not a url"):
        with pytest.raises(IntakeError):
            check_callback_url(bad, allow_private=False)
    check_callback_url("http://10.0.0.5/x", allow_private=True)


def test_leader_cannot_create_another_tenants_specialist():
    from agentscope.message import ToolCallBlock
    from agentscope.permission import PermissionBehavior

    rt = SimpleNamespace(wrap_up=set(), template_tenant={"mine": "t1", "theirs": "t2"},
                         templates={"mine": SimpleNamespace(description="m"),
                                    "theirs": SimpleNamespace(description="SECRET OTHER TENANT")})
    leader = AgentProfile(key="boss", name="B", role="leader", mission="leads.", team=["mine", "theirs"],
                          tools_allow=[])
    gate = ToolGateMiddleware(rt, Binding("c", "s", "a", "B", "leader", "u"), leader, "t1")
    assert gate.creatable() == ["mine"]  # a team entry owned by another tenant does not count

    async def delegated(**_):
        return "delegated"

    async def decide(name, **tool_input):
        call = ToolCallBlock(id="1", name=name, input="{}")
        return await gate.on_check_permission(None, {"tool_call": call, "tool_input": tool_input}, delegated)

    assert run(decide("AgentCreate", subagent_type="theirs")).behavior == PermissionBehavior.DENY
    assert run(decide("AgentCreate", subagent_type="mine")).behavior == PermissionBehavior.ALLOW
    assert run(decide("Bash")).behavior == PermissionBehavior.DENY  # not granted by the profile
    schema = {"type": "function", "function": {"name": "AgentCreate", "parameters": {"properties": {
        "subagent_type": {"enum": ["mine", "theirs", "default"], "description": "lists SECRET OTHER TENANT"}}}}}
    narrowed = gate._narrow_agent_create(schema)["function"]["parameters"]["properties"]["subagent_type"]
    assert narrowed["enum"] == ["mine"] and "SECRET" not in narrowed["description"]
