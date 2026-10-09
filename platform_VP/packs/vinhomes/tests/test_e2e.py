"""One ticket from the domain's inbox to its result, through the real core with a scripted model.

This proves the plumbing (inbox -> case -> tools -> guard -> outbox -> result). It does not say
how a real model would handle a Vietnamese repair ticket.
"""
import json
import re
import time

import httpx
import pytest
from fastapi.testclient import TestClient

import fake_llm
from awp.app import build_app
from awp.config import ServiceKey, Settings
from awp.providers import ModelCatalog, ModelSpec
from awp_vinhomes import VinhomesClient, VinhomesPack
from fake_llm import FakeServer
from fake_vinhomes import NAME, PHONE, TEAM, TICKET, State, make_app, submitted

ADM = {"Authorization": "Bearer adm-key"}
SEEN: list[str] = []  # everything the model was shown


def _text(m):
    c = m.get("content")
    return c if isinstance(c, str) else " ".join(p.get("text", "") for p in c or [] if isinstance(p, dict))


def script(msgs, tools):
    """The leader reads the ticket, first claims the work is done (the guard refuses), then answers
    with what the ticket said."""
    SEEN.append(json.dumps(msgs, ensure_ascii=False))
    system = next((_text(m) for m in msgs if m.get("role") in ("system", "developer")), "")
    if 'key="vinhomes_supervisor"' not in system:
        return "ok"
    names = [t["function"]["name"] for t in tools or []]
    called = lambda n: sum(1 for m in msgs for tc in (m.get("tool_calls") or []) if tc["function"]["name"] == n)  # noqa: E731
    if called("get_ticket") == 0:
        assert {"get_ticket", "propose_plan", "search_knowledge", "CaseFinalize"} <= set(names), names
        return [("get_ticket", {})]
    ids = [tc["id"] for m in msgs for tc in (m.get("tool_calls") or []) if tc["function"]["name"] == "get_ticket"]
    seen = " ".join(_text(m) for m in msgs if m.get("role") == "tool" and m.get("tool_call_id") in ids)
    evidence = re.findall(r"\[evidence (E\d+)\]", seen)
    tries = [_text(m) for m in msgs if m.get("role") == "tool" and "Not accepted" in _text(m)]
    if not tries:
        return [("CaseFinalize", {"answer": "Yêu cầu VH-0001 đã sửa xong.", "outcome": "resolved", "cites": evidence[:1]})]
    if called("CaseFinalize") < 2:
        return [("CaseFinalize", {"answer": "Yêu cầu VH-0001 đang được xử lý, phiên bản 7.",
                                  "outcome": "resolved", "cites": evidence[:1]})]
    return "Xong."


@pytest.fixture()
def stack(tmp_path, monkeypatch):
    monkeypatch.setattr(fake_llm, "policy", script)
    SEEN.clear()
    state = State()
    state.messages = [submitted(1)]
    client = VinhomesClient("http://vinhomes.test", state.secret, transport=httpx.ASGITransport(app=make_app(state)))
    pack = VinhomesPack(client, cursor_file=tmp_path / "cursor.json", poll_seconds=0.2, start_delay=1.0)
    with FakeServer() as fake:
        settings = Settings(
            db_url=f"sqlite+aiosqlite:///{(tmp_path / 'awp.db').as_posix()}",
            agentscope_db_url=f"sqlite+aiosqlite:///{(tmp_path / 'as.db').as_posix()}",
            workspace_dir=str(tmp_path / "ws"),
            service_keys={"svc-key": ServiceKey("t1", "vinhomes")}, admin_keys={"adm-key": "t1"})
        catalog = ModelCatalog([
            ModelSpec(id="strong", provider="openai_compatible", model="fake-strong", tier="strong",
                      base_url=fake.base_url, api_key_env="FAKE_KEY", price_in=2.0, price_out=8.0),
            ModelSpec(id="cheap", provider="openai_compatible", model="fake-cheap", tier="cheap",
                      base_url=fake.base_url, api_key_env="FAKE_KEY", price_in=0.5, price_out=2.0),
        ], env={"FAKE_KEY": "x"})
        app = build_app(settings, packs=[pack], catalog=catalog, deliver_every=0.3)
        with TestClient(app) as http:
            yield http, state, pack


def wait_for(cond, what, timeout=40, why=lambda: ""):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return
        time.sleep(0.2)
    raise AssertionError(f"timed out waiting for {what}. {why()}")


def where_it_stopped(http, state, pack):
    cases = http.get("/platform/v1/cases", headers=ADM).json()["cases"]
    items = [i for c in cases for i in http.get(f"/platform/v1/cases/{c['id']}/items", headers=ADM).json()["items"]]
    return f"cursor={pack.cursor} cases={cases} results={state.results} items={[(i['ref'], i['data']) for i in items][-6:]}"


def test_a_ticket_goes_in_and_a_grounded_result_comes_out(stack):
    http, state, pack = stack
    wait_for(lambda: any(r["message_type"] == "in_progress" for r in state.results), "the result",
             why=lambda: where_it_stopped(http, state, pack))

    # the receipt came first, then the answer, both accepted by the strict contract
    kinds = [r["message_type"] for r in state.results]
    assert kinds[0] == "accepted" and kinds.count("in_progress") == 1
    done = next(r for r in state.results if r["message_type"] == "in_progress")
    assert done["message"] == "Yêu cầu VH-0001 đang được xử lý, phiên bản 7."
    assert (done["team_id"], done["ticket_id"], done["ticket_version"], done["ticket_generation"]) == (TEAM, TICKET, "7", 0)
    assert done["correlation_id"] == "corr-1" and done["supervisor_run_id"].startswith("case_")

    # the case exists once, under the ticket, with the leader of the pack
    cases = http.get("/platform/v1/cases", headers=ADM).json()
    assert len(cases["cases"]) == 1 and cases["cases"][0]["external_ref"] == TICKET
    items = http.get(f"/platform/v1/cases/{cases['cases'][0]['id']}/items", headers=ADM).json()["items"]
    # "đã sửa xong" was refused because the ticket is not resolved
    attempts = [i for i in items if i["kind"] == "note" and i["data"].get("type") == "final_attempt"]
    assert len(attempts) == 1 and "chưa xác nhận" in str(attempts[0]["data"]["problems"])
    # the ticket text became evidence the answer cites
    assert any("Trạng thái yêu cầu: open" in i["data"].get("text", "") for i in items if i["kind"] == "evidence")

    # the model never saw the resident's name or number
    shown = " ".join(SEEN)
    assert "Vòi bếp rò nước" in shown and NAME not in shown and PHONE not in shown

    # reading the inbox again changes nothing: one case, one answer
    state.messages.append(submitted(2, "information_provided", message="Nhà có người ở nhà cả ngày"))
    wait_for(lambda: pack.cursor == "c2", "the second message")
    assert len(http.get("/platform/v1/cases", headers=ADM).json()["cases"]) == 1
