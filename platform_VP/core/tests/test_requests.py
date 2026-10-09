"""Work that goes through people outside the platform: field staff and the requester."""
import asyncio
import json
import time
from types import SimpleNamespace

from awp.intake.service import IntakeService
from awp.protocol.tools import CaseFinalize, CaseRequest
from awp.requests import RequestKind
from awp.runtime import Binding

from fake_llm import MODE
from support import ADM, SVC, DemoPack, make_stack
from test_e2e import intake_body, wait_for
from test_review_fixes import make_rt, open_case, text_of


def run(coro):
    return asyncio.run(coro)


def kinds():
    return {k.key: k for k in DemoPack().request_kinds()}


# ---- a case waiting for people is not a stalled case ---------------------------
def test_case_waiting_20_minutes_for_a_reply_is_not_closed(tmp_path, monkeypatch):
    async def go():
        rt = await make_rt(tmp_path, case_stall_seconds=900)
        intake = IntakeService(rt, SimpleNamespace(aclose=lambda: asyncio.sleep(0)))
        waiting, _ = await open_case(rt, "WAITING")
        await rt.cases.add(waiting, "request", "boss", {"kind": "work_request", "fields": {}, "expects_reply": True})
        idle, _ = await open_case(rt, "IDLE")  # no request: nothing explains the silence

        real = time.time
        monkeypatch.setattr(time, "time", lambda: real() + 20 * 60)
        assert await intake.expire_stalled() == 1
        assert (await rt.cases.get_case(waiting))["status"] == "open"
        assert (await rt.cases.get_case(idle))["status"] == "failed"

        # a reply that never comes ends as needs_human, once the request timeout is over
        monkeypatch.setattr(time, "time", lambda: real() + 73 * 3600)
        assert await intake.expire_stalled() == 1
        closed = await rt.cases.get_case(waiting)
        assert closed["status"] == "finalized" and closed["result"]["outcome"] == "needs_human"
        await rt.db.dispose()

    run(go())


# ---- sending a request ------------------------------------------------------------
def test_request_is_checked_before_it_leaves(tmp_path):
    async def go():
        rt = await make_rt(tmp_path)
        rt.request_kinds["d"] = kinds()
        cid, ev = await open_case(rt)
        b = Binding(cid, "s1", "a1", "boss", "leader", "u")
        tool = CaseRequest(rt, b, kinds())

        bad_shape = await tool.call(kind="work_request", fields={"unit": "A-12-05"}, evidence=[ev])
        assert "not valid" in text_of(bad_shape)
        wrong_total = await tool.call(kind="cost_confirmation", fields={"total": "600000"}, evidence=[ev])
        assert "figures not found" in text_of(wrong_total)  # 600000 is not in the evidence
        assert "Unknown kind" in text_of(await tool.call(kind="refund", fields={}))
        async with rt.db.engine.connect() as conn:
            from sqlalchemy import func, select

            from awp import db as dbm
            assert (await conn.execute(select(func.count()).select_from(dbm.outbox))).scalar_one() == 0

        ok = await tool.call(kind="cost_confirmation", fields={"total": "1500000"}, evidence=[ev])
        assert "T1 sent" in text_of(ok)
        notice = await tool.call(kind="progress_update", fields={"status": "technician on the way"})
        assert "T2 sent" in text_of(notice) and "Wait" not in text_of(notice)  # no reply expected
        async with rt.db.engine.connect() as conn:
            rows = (await conn.execute(select(dbm.outbox.c.kind, dbm.outbox.c.payload))).all()
        assert [r[0] for r in rows] == ["request", "request"]
        assert rows[0][1]["external_ref"] == "X" and rows[0][1]["expects_reply"] is True
        await rt.db.dispose()

    run(go())


# ---- closing needs the people to have answered -------------------------------------
def test_resolved_needs_replies_and_the_requesters_confirmation(tmp_path):
    async def go():
        rt = await make_rt(tmp_path)
        rt.request_kinds["d"] = kinds()
        cid, ev = await open_case(rt)
        await rt.cases.update_case(cid, intake={"confirm_with": "cost_confirmation"})
        b = Binding(cid, "s1", "a1", "boss", "leader", "u")
        final = CaseFinalize(rt, b)
        args = {"answer": "Repair costs 1500000 VND", "outcome": "resolved", "cites": [ev]}

        req = await rt.cases.add(cid, "request", "boss", {"kind": "cost_confirmation", "fields": {}, "expects_reply": True})
        assert "still waiting for replies to T1" in text_of(await final.call(**args))

        await rt.cases.add(cid, "reply", "external", {"to_ref": req.ref, "kind": "cost_confirmation",
                                                      "data": {"confirmed": False}})
        assert "has not confirmed" in text_of(await final.call(**args))  # a "no" is not a confirmation

        req2 = await rt.cases.add(cid, "request", "boss", {"kind": "cost_confirmation", "fields": {}, "expects_reply": True})
        await rt.cases.add(cid, "reply", "external", {"to_ref": req2.ref, "kind": "cost_confirmation",
                                                      "data": {"confirmed": True}})
        assert "finalized as resolved" in text_of(await final.call(**args))
        # none of the refusals above used up the leader's attempts
        assert not [n for n in await rt.cases.items(cid, kinds=("note",)) if n.data.get("type") == "final_attempt"]
        await rt.db.dispose()

    run(go())


def test_calc_sum_adds_exactly_and_its_result_is_citable():
    from awp.protocol.calc import calc_sum

    out = run(calc_sum().call(label="materials", values=["300,000", "250000", "0.1", "0.2"]))
    assert "sum of materials: 550000.3" in out.content[0].text
    assert "is not a number" in run(calc_sum().call(label="x", values=["abc"])).content[0].text


# ---- the whole repair, through the real service ---------------------------------------
def wait_until(check, timeout=60, what="condition"):
    end = time.time() + timeout
    while time.time() < end:
        if check():
            return
        time.sleep(0.2)
    raise AssertionError(f"timed out waiting for {what}")


def test_repair_goes_through_staff_and_closes_only_when_the_resident_confirms(tmp_path):
    with make_stack(tmp_path, case_stall_seconds=3) as (client, pack, rt):
        MODE["scenario"] = "repair"
        body = intake_body(external_ref="R-1", message_id="r-1", confirm_with="cost_confirmation")
        case_id = client.post("/platform/v1/intake", headers=SVC, json=body).json()["case_id"]

        def sent(kind):
            return [r for r in pack.requests if r["kind"] == kind]

        def status():
            return client.get(f"/platform/v1/cases/{case_id}", headers=SVC).json()["status"]

        def reply(request_ref, data, msg_id):
            r = client.post("/platform/v1/cases/by-ref/R-1/messages", headers=SVC, json={
                "message_id": msg_id, "kind": "reply", "reply_to": request_ref, "data": data})
            assert r.status_code == 202, r.text

        # 1. an agent asks field staff to do the work
        wait_until(lambda: sent("work_request"), what="the work request")
        # the case waits longer than the stall limit and is not closed for it
        time.sleep(5)
        assert status() == "open"

        # 2. staff answer with costs (a reply that does not match the form is refused)
        work = sent("work_request")[0]
        bad = client.post("/platform/v1/cases/by-ref/R-1/messages", headers=SVC, json={
            "message_id": "r-1-bad", "kind": "reply", "reply_to": work["request_ref"], "data": {"cost_items": []}})
        assert bad.status_code == 422
        reply(work["request_ref"], {"cost_items": [{"label": "pipe", "amount": 300000},
                                                   {"label": "seal", "amount": 250000}]}, "r-1-cost")

        # 3. the first cost sheet had a wrong total and never left; the right one goes to the resident
        wait_until(lambda: sent("cost_confirmation"), what="the cost sheet for the resident")
        assert len(sent("cost_confirmation")) == 1
        assert sent("cost_confirmation")[0]["fields"]["total"] == "550000"
        assert not any("600000" in json.dumps(r) for r in pack.requests)

        # 4. nothing closes the case until the resident confirms
        time.sleep(5)
        assert status() == "open"
        reply(sent("cost_confirmation")[0]["request_ref"], {"confirmed": True}, "r-1-ok")
        case = wait_for(client, case_id)
        assert case["result"]["outcome"] == "resolved" and "550000" in case["result"]["answer"]

        items = client.get(f"/platform/v1/cases/{case_id}/items", headers=ADM).json()["items"]
        assert [i["kind"] for i in items].count("reply") == 2
