"""GET request, conversation snapshot and event history (contract 9.3-9.5, 6.3)."""
import json
import threading
import time

import pytest

from conftest import key_headers
from fake_engine import Plan
from test_wf_errors import assert_envelope


def seed_messages(env, conversation_id, workflow_id, n, first_sequence=1000):
    con = env.raw()
    try:
        con.executemany(
            "insert into wf_messages (id, conversation_id, workflow_id, request_id, sender, text, asset_ids, "
            "sequence, created_at) values (?, ?, ?, NULL, 'assistant', ?, '[]', ?, ?)",
            [(f"msg_seed{first_sequence + i:06d}", conversation_id, workflow_id, f"line {i}",
              first_sequence + i, 1000.0 + i) for i in range(n)])
    finally:
        con.close()


def seed_events(env, conversation_id, workflow_id, n):
    con = env.raw()
    try:
        [(last,)] = con.execute("select last_sequence from wf_conversations where id=?", (conversation_id,))
        con.executemany(
            "insert into wf_events (event_id, conversation_id, sequence, event_type, workflow_id, payload, "
            "occurred_at, recorded_at) values (?, ?, ?, 'workflow.status_changed', ?, '{}', 1.0, 1.0)",
            [(f"evt_seed{last + i + 1:06d}", conversation_id, last + i + 1, workflow_id) for i in range(n)])
        con.execute("update wf_conversations set last_sequence=? where id=?", (last + n, conversation_id))
    finally:
        con.close()


# ---- GET request (9.3) -----------------------------------------------------------------------------------------
def test_get_request_is_the_9_3_view_of_the_frozen_result(sf):
    r, body = sf.start()
    post = r.json()
    g = sf.request(post["request_id"])
    assert g.status_code == 200
    j = g.json()
    assert list(j) == ["request_id", "request_status", "external_ticket_id", "conversation_id", "workflow_id",
                       "workflow_state", "next_action", "workflow_revision", "ticket_id", "result", "error",
                       "accepted_at", "completed_at", "last_event_id"]
    same = {k: v for k, v in post.items() if k in j}
    assert {k: v for k, v in j.items() if k != "last_event_id"} == same  # message ids and text as in the POST
    last = sf.history(post["conversation_id"]).json()["items"][-1]["event_id"]
    assert j["last_event_id"] == last
    sf.reply(body, post)  # the conversation moves on
    again = sf.request(post["request_id"]).json()
    # the result, error and times are frozen; the state, revision and next step are the workflow's now
    assert {k: again[k] for k in ("result", "error", "accepted_at", "completed_at")} ==         {k: j[k] for k in ("result", "error", "accepted_at", "completed_at")}
    assert again["workflow_revision"] >= j["workflow_revision"]
    assert again["last_event_id"] == sf.history(post["conversation_id"]).json()["items"][-1]["event_id"]


def test_get_request_on_a_pending_request_shows_the_live_state(sf):
    sf.engine.paused = True
    with sf.waiting(0.3):
        post = sf.start()[0].json()
    j = sf.request(post["request_id"]).json()
    assert (j["request_status"], j["workflow_state"], j["next_action"]) == ("queued", "accepted", "watch_request")
    assert j["result"] is None and j["completed_at"] is None and j["error"] is None
    assert j["last_event_id"] == sf.history(post["conversation_id"]).json()["items"][-1]["event_id"]


def test_the_get_reads_for_the_audience_only(sf):
    post = sf.start()[0].json()
    rid, cid = post["request_id"], post["conversation_id"]
    for call in (lambda u: sf.request(rid, user=u), lambda u: sf.snapshot(cid, user=u),
                 lambda u: sf.history(cid, user=u)):
        assert_envelope(call("resident-999"), 404, "NOT_FOUND")
        assert call("resident-123").status_code == 200
    assert_envelope(sf.request("req_nope"), 404, "NOT_FOUND")
    assert_envelope(sf.snapshot("conv_nope"), 404, "NOT_FOUND")
    assert_envelope(sf.history("conv_nope"), 404, "NOT_FOUND")
    # the answer for a stranger is the answer for a missing id
    a, b = sf.request(rid, user="resident-999"), sf.request("req_nope")
    assert a.json()["error"]["message"] == b.json()["error"]["message"] and a.json()["error"]["details"] == b.json()["error"]["details"]


def test_the_audience_query_is_required_and_is_no_grant(sf):
    post = sf.start()[0].json()
    for call in (lambda: sf.request(post["request_id"], user=None), lambda: sf.snapshot(post["conversation_id"], user=None),
                 lambda: sf.history(post["conversation_id"], user=None)):
        assert call().status_code == 422
    assert_envelope(sf.http.get(f"/workforce/v1/partner/requests/{post['request_id']}",
                                params={"external_user_id": ""}, headers=sf.h), 422, "VALIDATION_FAILED")


def test_another_partner_cannot_read_a_request_or_a_conversation(sf):
    post = sf.start()[0].json()
    other = sf.env.client(domain="travel", name="Other")
    k = sf.env.key(other["client_id"])
    sf.env.active_route(other["client_id"], k["api_key"])
    h = key_headers(k["api_key"])
    assert sf.request(post["request_id"], headers=h).status_code == 404
    assert sf.snapshot(post["conversation_id"], headers=h).status_code == 404
    assert sf.history(post["conversation_id"], headers=h).status_code == 404


def test_reads_need_their_operations(sf):
    post = sf.start()[0].json()
    no_read = key_headers(sf.env.key(sf.client["client_id"], operations=["submit_request", "receive_events"])["api_key"])
    no_events = key_headers(sf.env.key(sf.client["client_id"], operations=["read_result"])["api_key"])
    assert_envelope(sf.request(post["request_id"], headers=no_read), 403, "PERMISSION_DENIED")
    assert_envelope(sf.snapshot(post["conversation_id"], headers=no_read), 403, "PERMISSION_DENIED")
    assert_envelope(sf.history(post["conversation_id"], headers=no_read), 403, "PERMISSION_DENIED")
    assert sf.request(post["request_id"], headers=no_events).status_code == 200
    assert sf.snapshot(post["conversation_id"], headers=no_events).status_code == 200
    assert_envelope(sf.history(post["conversation_id"], headers=no_events), 403, "PERMISSION_DENIED")  # history needs both
    assert_envelope(sf.request(post["request_id"], headers={}), 401, "UNAUTHENTICATED")


def test_a_key_that_does_not_cover_the_route_reads_nothing(sf):
    post = sf.start()[0].json()
    other = sf.env.route(sf.client["client_id"], "ELSEWHERE")
    narrow = key_headers(sf.env.key(sf.client["client_id"], routes=[other["route_id"]])["api_key"])
    assert sf.request(post["request_id"], headers=narrow).status_code == 404
    assert sf.snapshot(post["conversation_id"], headers=narrow).status_code == 404


# ---- snapshot (9.4) -----------------------------------------------------------------------------------------------
def test_snapshot_has_the_fields_of_contract_9_4(sf):
    sf.engine.plan = Plan(say=("one", "two"), state="waiting_external_event")
    r, body = sf.start()
    post = r.json()
    s = sf.snapshot(post["conversation_id"])
    assert s.status_code == 200
    j = s.json()
    assert list(j) == ["conversation_id", "external_ticket_id", "external_conversation_id", "external_user_id",
                       "workflows", "messages", "has_more_messages", "approvals", "snapshot_cursor"]
    assert j["external_conversation_id"] == body["external_conversation_id"] and j["external_user_id"] == "resident-123"
    assert j["workflows"] == [{"workflow_id": post["workflow_id"], "external_ticket_id": body["external_ticket_id"],
                               "ticket_id": None, "state": "waiting_external_event", "next_action": "watch_events",
                               "revision": post["workflow_revision"]}]
    assert [(m["sender"], m["text"]) for m in j["messages"]] == [
        ("user", body["message"]["text"]), ("assistant", "one"), ("assistant", "two")]
    assert j["approvals"] == [] and j["has_more_messages"] is False
    assert j["snapshot_cursor"] == sf.history(post["conversation_id"]).json()["items"][-1]["event_id"]
    # the same messages with the same ids as the POST answer
    assert [m["message_id"] for m in j["messages"][1:]] == [m["message_id"] for m in post["result"]["messages"]]


def test_snapshot_cursor_is_null_before_any_event(sf):
    post = sf.start()[0].json()
    sf.env.sql("insert into wf_conversations (id, client_id, route_id, external_user_id, external_conversation_id, "
               "last_sequence, purged_through, created_at) values ('conv_empty', ?, ?, 'resident-123', 'CHAT-EMPTY', 0, 0, 1.0)",
               (sf.client["client_id"], sf.route["route_id"]))
    j = sf.snapshot("conv_empty").json()
    assert j["snapshot_cursor"] is None and j["workflows"] == [] and j["messages"] == []
    assert sf.history("conv_empty").json() == {"items": [], "next_cursor": None, "has_more": False}
    assert post["conversation_id"] != "conv_empty"


def test_snapshot_pages_the_messages_two_hundred_at_a_time(sf):
    post = sf.start()[0].json()
    cid, wid = post["conversation_id"], post["workflow_id"]
    seed_messages(sf.env, cid, wid, 450)
    first = sf.snapshot(cid).json()
    assert len(first["messages"]) == 200 and first["has_more_messages"] is True
    texts = [m["text"] for m in first["messages"]]
    assert texts == [f"line {i}" for i in range(250, 450)]  # the latest 200, oldest first
    second = sf.snapshot(cid, messages_before=first["messages"][0]["message_id"]).json()
    assert [m["text"] for m in second["messages"]] == [f"line {i}" for i in range(50, 250)]
    assert second["has_more_messages"] is True
    third = sf.snapshot(cid, messages_before=second["messages"][0]["message_id"]).json()
    assert len(third["messages"]) == 50 + 2 and third["has_more_messages"] is False  # + the start's two
    assert third["messages"][0]["sender"] == "user"
    ids = [m["message_id"] for page in (third, second, first) for m in page["messages"]]
    assert len(ids) == len(set(ids)) == 452
    assert_envelope(sf.snapshot(cid, messages_before="msg_nope"), 422, "VALIDATION_FAILED")


def test_a_message_of_another_conversation_is_no_page_marker(sf):
    a = sf.start()[0].json()
    b = sf.start()[0].json()
    foreign = sf.snapshot(b["conversation_id"]).json()["messages"][0]["message_id"]
    assert_envelope(sf.snapshot(a["conversation_id"], messages_before=foreign), 422, "VALIDATION_FAILED")


def test_snapshot_shows_the_pending_approvals_the_caller_may_see(sf):
    post = sf.start()[0].json()
    wid, cid, client = post["workflow_id"], post["conversation_id"], sf.client["client_id"]
    other = sf.start()[0].json()
    insert = ("insert into wf_approvals (id, workflow_id, conversation_id, client_id, external_user_id, session_id, "
              "agent_id, tool_call_id, tool_name, arguments, arguments_hash, quote_ref, summary, status, "
              "workflow_revision, expires_at, created_at) values (?, ?, ?, ?, ?, 's', 'a', ?, 'book', '{\"secret\":1}', "
              "'sha256:abc', 'quote_1', '{\"total\":\"1500000\"}', ?, 4, 2000000000.0, ?)")
    sf.env.sql(insert, ("appr_mine", wid, cid, client, "resident-123", "c1", "pending", 1.0))
    sf.env.sql(insert, ("appr_done", wid, cid, client, "resident-123", "c2", "approved", 2.0))
    sf.env.sql(insert, ("appr_other_user", wid, cid, client, "resident-999", "c3", "pending", 3.0))
    sf.env.sql(insert, ("appr_other_chat", other["workflow_id"], other["conversation_id"], client,
                        "resident-123", "c4", "pending", 4.0))
    [a] = sf.snapshot(cid).json()["approvals"]
    assert a == {"approval_id": "appr_mine", "workflow_id": wid, "status": "pending", "tool_name": "book",
                 "summary": {"total": "1500000"}, "arguments_hash": "sha256:abc", "quote_ref": "quote_1",
                 "expected_revision": 4, "expires_at": "2033-05-18T03:33:20Z"}
    assert "secret" not in json.dumps(sf.snapshot(cid).json())  # the raw arguments never leave


def test_a_snapshot_taken_during_writes_is_one_consistent_picture(sf):
    """Every snapshot's workflow revision and assistant messages are exactly those of its own cursor."""
    sf.engine.plan = Plan(say=("a", "b"), state="awaiting_user")
    start, started = sf.begin()
    stop, snaps, problems = threading.Event(), [], []

    def writer():
        for _ in range(12):
            sf.reply(start, started)
        stop.set()

    def reader():
        while not stop.is_set() or len(snaps) < 5:
            snaps.append(sf.snapshot(started["conversation_id"]).json())

    threads = [threading.Thread(target=writer), threading.Thread(target=reader), threading.Thread(target=reader)]
    [th.start() for th in threads]
    [th.join(60) for th in threads]
    items = sf.history(started["conversation_id"], limit=500).json()["items"]
    by_id = {i["event_id"]: i for i in items}
    for snap in snaps:
        cut = by_id[snap["snapshot_cursor"]]["sequence"]
        upto = [i for i in items if i["sequence"] <= cut]
        revision = 1
        for i in upto:
            if i["event_type"].startswith("workflow.") and "revision" in i["payload"]:
                revision = i["payload"]["revision"]
        said = [i["payload"]["message_id"] for i in upto if i["event_type"] == "assistant.message"]
        got = [m["message_id"] for m in snap["messages"] if m["sender"] == "assistant"]
        if snap["workflows"][0]["revision"] != revision or got != said:
            problems.append((cut, snap["workflows"][0]["revision"], revision, len(got), len(said)))
    assert len(snaps) >= 5 and not problems, problems


# ---- event history (9.5) -------------------------------------------------------------------------------------------
def test_history_items_are_the_envelope_of_9_7(sf):
    sf.engine.plan = Plan(say=("hello",), state="awaiting_user")
    r, body = sf.start()
    post = r.json()
    page = sf.history(post["conversation_id"]).json()
    assert list(page) == ["items", "next_cursor", "has_more"] and page["has_more"] is False
    for n, item in enumerate(page["items"], 1):
        assert item["sequence"] == n and item["schema_version"] == "1" and item["event_id"].startswith("evt_")
        assert item["conversation_id"] == post["conversation_id"] and item["workflow_id"] == post["workflow_id"]
        assert item["external_ticket_id"] == body["external_ticket_id"]
        assert item["external_conversation_id"] == body["external_conversation_id"]
        assert item["external_user_id"] == "resident-123" and item["ticket_id"] is None
        assert item["occurred_at"].endswith("Z") and item["recorded_at"].endswith("Z")
    types = [i["event_type"] for i in page["items"]]
    assert types == ["request.accepted", "workflow.status_changed", "assistant.message", "workflow.awaiting_user"]
    [msg] = [i for i in page["items"] if i["event_type"] == "assistant.message"]
    assert msg["payload"] == {"message_id": post["result"]["messages"][0]["message_id"], "text": "hello"}
    assert page["items"][0]["payload"] == {"request_id": post["request_id"]}
    assert page["next_cursor"] == page["items"][-1]["event_id"]


def test_history_default_limit_is_100_and_the_cap_is_500(sf):
    post = sf.start()[0].json()
    cid, wid = post["conversation_id"], post["workflow_id"]
    seed_events(sf.env, cid, wid, 700)
    default = sf.history(cid).json()
    assert len(default["items"]) == 100 and default["has_more"] is True
    capped = sf.history(cid, limit=1000).json()
    assert len(capped["items"]) == 500 and capped["has_more"] is True
    assert len(sf.history(cid, limit=500).json()["items"]) == 500
    assert_envelope(sf.history(cid, limit=0), 422, "VALIDATION_FAILED")
    assert sf.history(cid, limit="many").status_code == 422
    # walking the log in pages of 300 sees every event once, in order
    seen, cursor = [], None
    while True:
        params = {"limit": 300, **({"after_cursor": cursor} if cursor else {})}
        page = sf.history(cid, **params).json()
        seen += [i["sequence"] for i in page["items"]]
        if not page["has_more"]:
            break
        cursor = page["next_cursor"]
    assert seen == list(range(1, 4 + 700 + 1))


def test_history_cursor_errors(sf):
    a = sf.start()[0].json()
    b = sf.start()[0].json()
    foreign = sf.history(b["conversation_id"]).json()["items"][0]["event_id"]
    unknown = sf.history(a["conversation_id"], after_cursor="evt_nothing")
    other = sf.history(a["conversation_id"], after_cursor=foreign)
    assert_envelope(unknown, 422, "VALIDATION_FAILED")
    assert_envelope(other, 422, "VALIDATION_FAILED")
    assert unknown.json()["error"]["details"] == other.json()["error"]["details"]
    # a purged position answers 410 with the way back
    sf.env.sql("insert into wf_event_tombstones (event_id, conversation_id, sequence) values ('evt_gone', ?, 1)",
               (a["conversation_id"],))
    gone = sf.history(a["conversation_id"], after_cursor="evt_gone")
    err = assert_envelope(gone, 410, "EVENT_CURSOR_EXPIRED")
    assert err["details"] == {"snapshot_url": f"/workforce/v1/partner/conversations/{a['conversation_id']}"}
    assert err["retryable"] is False
    # a tombstone of another conversation is not ours to confirm
    assert_envelope(sf.history(b["conversation_id"], after_cursor="evt_gone"), 422, "VALIDATION_FAILED")
    sf.env.sql("update wf_conversations set purged_through=2 where id=?", (b["conversation_id"],))
    assert_envelope(sf.history(b["conversation_id"]), 410, "EVENT_CURSOR_EXPIRED")  # "from the start" is gone too
    resume = sf.snapshot(b["conversation_id"]).json()["snapshot_cursor"]
    assert sf.history(b["conversation_id"], after_cursor=resume).status_code == 200  # the snapshot cursor resumes


def test_history_follows_new_events_from_a_cursor(sf):
    start, started = sf.begin()
    first = sf.history(started["conversation_id"]).json()
    sf.reply(start, started)
    second = sf.history(started["conversation_id"], after_cursor=first["next_cursor"]).json()
    assert [i["sequence"] for i in second["items"]] == list(range(len(first["items"]) + 1, len(first["items"]) + 5))
    assert second["items"][0]["event_type"] == "request.accepted"
    assert sf.history(started["conversation_id"], after_cursor=second["next_cursor"]).json() == {
        "items": [], "next_cursor": second["next_cursor"], "has_more": False}
