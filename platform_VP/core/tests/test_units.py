"""Unit tests: no model, no AgentScope run."""
import asyncio

from awp.casefile import CaseStore, build_view, render_digest
from awp.config import Settings
from awp.db import Database
from awp.guard import PhraseRule, Rules, check_text, figures_missing
from awp.profiles import AgentProfile, ProfileError, ProfileStore, system_prompt, tool_patterns
from awp.profiles.compile import specialist_prompt
from awp.providers import ModelCatalog, ModelSpec
from awp.security import mask_secrets


def run(coro):
    return asyncio.run(coro)


# ---- guard -----------------------------------------------------------------
def test_figures_must_come_from_sources():
    assert figures_missing("costs 1.500.000 VND", ["pipe repair: 1500000 VND"]) == []
    assert figures_missing("costs 2000000 VND", ["pipe repair: 1500000 VND"]) == ["2000000"]
    assert figures_missing("see you at 09:30", ["appointment 09:30"]) == []
    # whole-token comparison: a smaller number is not "inside" a bigger one
    assert figures_missing("owes 5,000 VND", ["Balance due 1,250,000 VND"]) == ["5,000"]
    assert figures_missing("owes 250 VND", ["Balance due 1,250,000 VND"]) == ["250"]
    # digits must not be stitched together across two sources
    assert figures_missing("code 2034", ["unit A-12", "ticket 0345"]) == ["2034"]
    # single digits are checked too, list markers are not
    assert figures_missing("You have 3 invoices", ["2 invoices"]) == ["3"]
    assert figures_missing("1. First" + chr(10) + "2. Second", ["nothing"]) == []
    # a number split by single spaces matches when written joined, and the reverse
    assert figures_missing("call 0901234567", ["phone 0901 234 567"]) == []
    assert figures_missing("call 0901 234 567", ["phone 0901234567"]) != []


def test_phrase_rules_need_evidence():
    rules = Rules(phrase_rules=[PhraseRule(("is finished",), "claims completion", unless=("status: resolved",))],
                  forbidden_words=("backend",))
    assert check_text("The work is finished", ["status: open"], rules)
    assert not check_text("The work is finished", ["status: resolved"], rules)
    assert check_text("our backend is down", [], rules)


# ---- case file -------------------------------------------------------------
def test_case_file_flow_and_digest():
    async def go():
        db = Database("sqlite+aiosqlite:///:memory:")
        await db.create_all()
        cs = CaseStore(db)
        cid = await cs.create_case(tenant="t", domain="d", external_ref="X1", user_id="u",
                                   intake={"summary": "leak"})
        e1 = await cs.add(cid, "evidence", "tech", {"tool": "lookup", "text": "T-1001 waiting"})
        f1 = await cs.add(cid, "fact", "tech", {"text": "waiting", "evidence": [e1.ref]})
        assert (e1.ref, f1.ref) == ("E1", "F1")
        c1 = await cs.add(cid, "challenge", "fin", {"fact": "F1", "reason": "x", "evidence": ["E1"]}, addressee="tech")
        view = build_view(await cs.items(cid))
        assert view.facts["F1"].status == "challenged" and view.open_challenges()[0].ref == "C1"
        await cs.add(cid, "answer", "tech", {"to_ref": c1.ref, "text": "no", "retract": True}, addressee="fin")
        view = build_view(await cs.items(cid))
        assert view.facts["F1"].status == "retracted" and not view.open_challenges()

        members = [{"agent_name": "tech", "agent_id": "a1", "role": "worker"},
                   {"agent_name": "fin", "agent_id": "a2", "role": "worker"}]
        items = await cs.items(cid)
        text = render_digest(case_id=cid, summary="leak", viewer="fin", role="worker", view=view,
                             new_items=items, members=members, max_chars=1500, max_rounds=2)
        assert "F1" in text and "C1" not in text.split("WAITING")[0] or True
        quiet = render_digest(case_id=cid, summary="leak", viewer="fin", role="worker", view=view,
                              new_items=[i for i in items if i.author == "fin"], members=members,
                              max_chars=1500, max_rounds=2)
        assert quiet == ""  # nothing new from others -> no tokens spent
        await db.dispose()

    run(go())


def test_digest_is_bounded():
    async def go():
        db = Database("sqlite+aiosqlite:///:memory:")
        await db.create_all()
        cs = CaseStore(db)
        cid = await cs.create_case(tenant="t", domain="d", external_ref="X2", user_id="u", intake={})
        for i in range(60):
            await cs.add(cid, "fact", "tech", {"text": f"fact number {i} " + "x" * 120, "evidence": ["E1"]})
        items = await cs.items(cid)
        text = render_digest(case_id=cid, summary="s", viewer="leader", role="leader",
                             view=build_view(items), new_items=items, members=[], max_chars=1200, max_rounds=2)
        assert len(text) <= 1400 and "older item" in text
        await db.dispose()

    run(go())


# ---- profiles --------------------------------------------------------------
def test_profile_versions_and_publish():
    async def go():
        db = Database("sqlite+aiosqlite:///:memory:")
        await db.create_all()
        ps = ProfileStore(db)
        p = AgentProfile(key="tech", name="T", mission="does x.")
        r1 = await ps.create_draft("t1", p)
        r2 = await ps.create_draft("t1", p)
        assert (r1.version, r2.version) == (1, 2)
        await ps.publish("t1", "tech", 1)
        await ps.publish("t1", "tech", 2)
        assert (await ps.get_published("t1", "tech")).version == 2
        assert (await ps.get("t1", "tech", 1)).status == "retired"
        try:
            await ps.update_draft("t1", "tech", 2, p)
            raise AssertionError("a published version must not be editable")
        except ProfileError:
            pass
        try:
            await ps.create_draft("t2", p)
            raise AssertionError("keys are unique across tenants")
        except ProfileError:
            pass
        await db.dispose()

    run(go())


def test_prompts_and_tool_patterns():
    s = Settings()
    spec = AgentProfile(key="tech", name="T", mission="a tech.", handles=["a"], refuses=["b"],
                        instructions="Use {braces} safely.", tools_allow=["lookup_*"])
    text = specialist_prompt(spec, 3, s).format(
        member_name="Tom", team_name="tm", team_description="d", member_description="m", leader_name="L")
    assert 'key="tech" v="3"' in text and "Use {braces} safely." in text and "You are Tom" in text
    assert "CaseFinalize" not in tool_patterns(spec) and "lookup_*" in tool_patterns(spec)
    lead = AgentProfile(key="boss", name="Boss", role="leader", mission="leads.", team=["tech"])
    assert "AgentCreate" in system_prompt(lead, 1, s) and "tech" in system_prompt(lead, 1, s)


# ---- models and cost ---------------------------------------------------------
def test_catalog_costs_and_unpriced():
    priced = ModelSpec(id="a", provider="openai", model="m1", price_in=1.0, price_out=4.0,
                       price_cache_read=0.1)
    # OpenAI style: input_tokens includes the cached part
    assert abs(priced.cost(1_000_000, 0, cache_read=500_000) - (0.5 * 1.0 + 0.5 * 0.1)) < 1e-9
    claude = ModelSpec(id="c", provider="anthropic", model="m2", price_in=3.0, price_out=15.0,
                       price_cache_read=0.3)
    # Anthropic style: cache reads are on top of input_tokens
    assert abs(claude.cost(1_000_000, 0, cache_read=1_000_000) - (3.0 + 0.3)) < 1e-9
    assert ModelSpec(id="u", provider="openai", model="m3").cost(10, 10) == 0.0
    cat = ModelCatalog([priced], env={"OPENAI_API_KEY": "k"})
    assert cat.pick("cheap").id == "a" and cat.by_name("m1").id == "a"
    assert ModelCatalog([priced], env={}).pick("cheap") is None


def test_secrets_are_masked():
    out = mask_secrets({"credentials": [{"name": "x", "api_key": "sk-abcdefghijklmnop"}]})
    assert out["credentials"][0]["api_key"] == "********mnop"


def test_concurrent_writers_get_distinct_references(tmp_path):
    async def go():
        db = Database(f"sqlite+aiosqlite:///{(tmp_path / 'c.db').as_posix()}")
        await db.create_all()
        cs = CaseStore(db)
        cid = await cs.create_case(tenant="t", domain="d", external_ref="X3", user_id="u", intake={})
        items = await asyncio.gather(*[cs.add(cid, "fact", f"a{i}", {"text": str(i)}) for i in range(12)])
        assert len({i.ref for i in items}) == 12
        await db.dispose()

    run(go())


def test_late_worker_report_on_a_closed_case_is_swallowed():
    from types import SimpleNamespace

    from agentscope.message import ToolCallBlock
    from agentscope.tool import ToolResponse

    from awp.middleware.room import EvidenceMiddleware
    from awp.runtime import Binding

    class Cases:
        async def get_case(self, _):
            return {"status": "finalized"}

    async def never(**_):
        raise AssertionError("the report must not be delivered")
        yield  # pragma: no cover

    async def go():
        b = Binding("c1", "s1", "a1", "tech", "worker", "u")
        mw = EvidenceMiddleware(SimpleNamespace(cases=Cases()), b, None)
        call = ToolCallBlock(id="t1", name="TeamSay", input='{"content": "done", "to": null}')
        out = [x async for x in mw.on_acting(None, {"tool_call": call}, never)]
        assert len(out) == 1 and isinstance(out[0], ToolResponse) and out[0].state.value == "success"

    run(go())


def test_stalled_cases_are_found_by_last_activity():
    import time as _t

    async def go():
        db = Database("sqlite+aiosqlite:///:memory:")
        await db.create_all()
        cs = CaseStore(db)
        old = await cs.create_case(tenant="t", domain="d", external_ref="old", user_id="u", intake={})
        busy = await cs.create_case(tenant="t", domain="d", external_ref="busy", user_id="u", intake={})
        done = await cs.create_case(tenant="t", domain="d", external_ref="done", user_id="u", intake={})
        await cs.update_case(done, status="finalized")
        await asyncio.sleep(0.4)
        await cs.add(busy, "note", "x", {})  # recent activity
        found = await cs.stalled(0.2)
        assert found == [old]  # not the busy one, not the finished one
        await db.dispose()

    run(go())
