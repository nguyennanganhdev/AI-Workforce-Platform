"""What a database that enforces column sizes and a real text type makes of partner input: SQLite stores anything, PostgreSQL
refuses a NUL in text, a value longer than its column, and NaN in JSON. Everything the contract lets a partner send must be
stored, so these run on both and are the real check on PostgreSQL (AWP_TEST_PG_URL)."""
import json

import pytest

from awp.db import dumps
from awp.workforce import tables as t
from dbkit import Lab


def longest(prefix: str, n: int = 200) -> str:
    return (prefix + "-" + "x" * n)[:n]


def test_every_id_at_its_longest_and_a_reason_at_its_longest_are_stored(flow):
    ids = {k: longest(k) for k in ("rq", "user", "ticket", "chat")}
    start, started = flow.begin(external_request_id=ids["rq"], external_user_id=ids["user"], external_ticket_id=ids["ticket"],
                                external_conversation_id=ids["chat"])
    r, reply = flow.reply(start, started, external_request_id=longest("rq2"))
    assert r.status_code in (200, 202), r.text
    snap = flow.get(f"/conversations/{started['conversation_id']}", user=ids["user"])
    assert snap.status_code == 200 and snap.json()["workflows"][0]["external_ticket_id"] == ids["ticket"]
    wf = snap.json()["workflows"][0]
    reason = longest("reason")
    closed, _ = flow.close({"workflow_id": started["workflow_id"], "workflow_revision": wf["revision"]}, start, reason=reason,
                           external_request_id=longest("rq3"))
    assert closed.status_code == 200, closed.text
    [(stored,)] = flow.env.sql("select close_reason from wf_workflows where id=?", (started["workflow_id"],))
    assert stored == reason  # the partner's own words, all 200 characters
    assert flow.env.sql("select user_id from awp_cases where id=(select case_id from wf_workflows where id=?)",
                        (started["workflow_id"],)) == [(ids["user"],)]


def test_a_nul_character_in_a_message_is_dropped_not_a_500(flow):
    start, started = flow.begin(message={"type": "text", "text": "hel" + chr(0) + "lo, my pipe leaks"})
    assert flow.env.sql("select text from wf_messages where workflow_id=? and sender='user'", (started["workflow_id"],)) == [
        ("hello, my pipe leaks",)]
    r, _ = flow.reply(start, started, message={"type": "text", "text": chr(0) * 3})
    assert r.status_code == 422  # nothing is left of it: blank, like any blank message


def test_nan_and_infinity_in_a_json_value_are_stored_as_null(tmp_path):
    assert json.loads(dumps({"a": float("nan"), "b": [float("inf"), 1.5, {"c": float("-inf")}], "d": "x"})) == {
        "a": None, "b": [None, 1.5, {"c": None}], "d": "x"}
    assert dumps({"plain": 1}) == '{"plain": 1}'
    lab = Lab(tmp_path / "nan.db")
    try:
        seed = lab.seed()
        row = dict(id="op_nan", workflow_id=seed["wf"]["id"], route_id="route_1", tool_name="x", args_hash="h", client_reference="cr",
                   status="completed", result={"price": float("nan"), "items": [float("inf")]}, created_at=1.0, updated_at=1.0)

        async def go():
            async with lab.db.engine.begin() as conn:
                await conn.execute(t.operations.insert().values(**row))
        lab.run(go())
        assert lab.one(t.operations, id="op_nan")["result"] == {"price": None, "items": [None]}
    finally:
        lab.close()


def test_a_partner_status_word_longer_than_its_column_is_cut_not_a_failed_write():
    from mcp.types import CallToolResult, TextContent

    from awp.workforce.partner_result import normalize

    res = CallToolResult(content=[TextContent(type="text", text="ok")], structuredContent={"status": "Z" * 300, "job_id": "J-1"},
                         isError=False)
    got = normalize(res, "action", "events")
    assert got.status == "z" * 40  # the partner's word, lower-cased and cut to the 40 characters of wf_operations.normalized_status


def test_long_unicode_text_is_stored_whole(flow):
    text = "Ống nước nhà tôi bị rò rỉ ở tầng 12, phòng 1205. " * 400  # 20000 characters, outside ASCII
    text = text[:20000]
    start, started = flow.begin(message={"type": "text", "text": text})
    [(stored,)] = flow.env.sql("select text from wf_messages where workflow_id=? and sender='user'", (started["workflow_id"],))
    assert stored == text


def test_names_longer_than_the_columns_are_cut_where_a_model_chooses_them(tmp_path):
    import asyncio

    import dbtest
    from awp.casefile import CaseStore
    from awp.db import Database

    where = dbtest.one(tmp_path, "names.db")

    async def go():
        db = Database(where.url)
        await db.create_all()
        cs = CaseStore(db)
        cid = await cs.create_case(tenant="t", domain="d", external_ref="X1", user_id="u" * 200, meta={})
        await cs.bind_session(cid, "s1", "a1", "N" * 300, "worker")
        await cs.add(cid, "fact", "A" * 300, {"text": "x"}, addressee="B" * 300)
        out = (await cs.sessions_of_case(cid))[0]["agent_name"], (await cs.items(cid))[0]
        await db.dispose()
        return out

    name, item = asyncio.run(go())
    assert name == "N" * 80 and item.author == "A" * 80 and item.addressee == "B" * 80


def test_epoch_times_keep_their_microseconds_and_ids_differing_only_in_case_stay_apart(flow):
    import time

    stamp = 1_791_663_687.045769  # an epoch with microseconds: a 4-byte float, or a rounded timestamp, would lose them
    start, started = flow.begin(external_conversation_id="Chat-A", external_ticket_id="Ticket-A")
    other, other_started = flow.begin(external_conversation_id="chat-a", external_ticket_id="ticket-a")
    assert started["conversation_id"] != other_started["conversation_id"]  # case is part of the id, as on SQLite
    assert flow.get(f"/conversations/{started['conversation_id']}").json()["workflows"][0]["external_ticket_id"] == "Ticket-A"
    flow.env.sql("update wf_workflows set closed_at=? where id=?", (stamp, started["workflow_id"]))
    assert flow.env.sql("select closed_at from wf_workflows where id=?", (started["workflow_id"],)) == [(stamp,)]
    assert abs(time.time() - flow.env.sql("select created_at from wf_workflows where id=?", (other_started["workflow_id"],))[0][0]) < 600


def test_the_longest_values_of_building_evaluating_and_releasing_are_stored(env):
    """B2 on a database that enforces sizes: the longest profile key, case name, case input (outside ASCII, with a NUL),
    fixture, override reason and error text, and the actor of a manager's key."""
    import asyncio

    P = "/platform/v1/profiles"
    key = "k" + "y" * 40  # the longest key a profile may have
    assert env.post(P, {"key": key, "name": "N" * 80, "mission": "làm việc. " * 300}).status_code == 201
    case = {"name": "c" * 120, "input": ("Ống nước rò rỉ ở tầng 12. " * 800)[:19990] + chr(0) + "hết",
            "fixtures": {"t" * 64: "kết quả " * 2400, "other": {"nested": ["x" * 5000]}},
            "checks": {"must_contain": ["đ" * 500] * 20, "must_call": [{"tool": "t" * 64, "args": {"a": "b" * 500}}], "grounded": True}}
    made = env.post(f"{P}/{key}/eval-cases", case)
    assert made.status_code == 201, made.text
    [(name, text)] = env.sql("select name, input from awp_eval_cases")
    assert name == "c" * 120 and len(text) == 19993 and chr(0) not in text and text.endswith("hết")
    assert env.post(f"{P}/{key}/eval-cases", {**case, "name": "c" * 121}).status_code == 422
    run = env.post(f"{P}/{key}/versions/1/evals", {"wait_seconds": 60})  # no model here: it ends without one, and is stored
    assert run.status_code == 200 and run.json()["status"] in ("failed", "error"), run.text
    store = env.app.state.awp.rt.evals.store

    async def long_error():
        opened = await store.open_run("ta", key, 1, "sha256:" + "f" * 64, "manager:mgr_" + "a" * 32 + "x" * 60, 9e9)
        await store.write_run(opened["id"], status="error", error="e" * 1000)
        return await store.run("ta", opened["id"])

    row = env.http.portal.call(long_error)
    assert len(row["error"]) == 300 and len(row["started_by"]) == 80
    reason = "vì " * 99 + "abc"  # 300 characters
    r = env.post(f"{P}/{key}/versions/1/publish", {"override_reason": reason})
    assert r.status_code == 200, r.text
    events = env.http.get(f"{P}/{key}/history", headers={"Authorization": "Bearer adm-a"}).json()["events"]
    assert [e["kind"] for e in events] == ["create", "eval", "override", "publish"] and events[2]["detail"]["reason"] == reason
    assert asyncio.iscoroutinefunction(store.write_run)
