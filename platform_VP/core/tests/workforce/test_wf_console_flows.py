"""The owner's flows of the console (B3), driven without a browser: each test makes the calls the page makes for one
flow, in the page's order, through `consolekit.Page` (only endpoints of app.js's own table, the key in the header, the
bodies the forms send). What is proven is that the API sequences behind the screens work end to end; that the page's
JavaScript makes them is what the browser check of the slice shows (docs/WORKFORCE_V1_QUYET_DINH.md, B3).

(a) Kho tool: add an MCP server, enable it (discovery against the fake MCP partner), activate a proposed tool.
(b) Agent: builder chat, overlap warning, apply, the draft exists.
(c) Agent: publish refused without an evaluation, evaluate, publish, roll back.
(d) Vận hành: list workflows, look at one, resolve it.
(e) The same with a manager's key, which sees and changes only its own scope.
"""
from __future__ import annotations

import time

import evalkit as ek
import pytest
from conftest import ADM, EVENT_SCHEMA
from consolekit import Page, eval_case, tool_action, tool_lookup
from enginekit import world
from fake_llm import MODE
from partnerkit import SECRET, Partner

READ_ONLY = {"lookup_ticket", "repair_status"}
PARKING = {"key": "parking", "name": "Parking desk", "mission": "books visitor parking slots for residents.",
           "handles": ["visitor parking", "parking slots"], "refuses": ["fines"], "tools_allow": []}
PLAIN = {**ek.TECH, "refuses": [], "tools_allow": []}


class Shop(Partner):
    """The fake partner, with a tool a test can take away while the server runs."""

    def build(self):
        self.mcp = super().build()
        return self.mcp


@pytest.fixture
def shop():
    with Shop() as p:
        yield p


def bearer(headers: dict) -> str:
    return headers["Authorization"].removeprefix("Bearer ")


def names(tools: list[dict], status: str) -> set[str]:
    return {t["name"] for t in tools if t["status"] == status}


def tool_store_flow(page: Page, rid: str, shop, integration: str | None) -> None:
    """Screen 1 for one route, as an admin or as the route's manager."""
    assert page.ok("mcpList", rid) == {"servers": []} and page.ok("toolList", rid) == {"tools": []}
    # the form "Thêm MCP server": the server is stored switched off, and its header value never comes back
    added = page.call("mcpAdd", rid, body={"name": "bql", "url": shop.url, "timeout": 8, "headers": {"Authorization": f"Bearer {SECRET}"}})
    assert added.status_code == 201 and added.json()["enabled"] is False and added.json()["header_names"] == ["Authorization"]
    assert SECRET not in added.text and shop.rpc == []
    again = page.call("mcpAdd", rid, body={"name": "bql", "url": shop.url, "timeout": 8, "headers": {}})
    assert again.status_code == 409 and "already has a server" in again.json()["detail"]  # the 409 body the page shows
    # "Bật": discovery; what the page shows as the result, then the reloaded lists
    report = page.ok("mcpEnable", rid, "bql")
    assert report["server"]["enabled"] is True and report["rejected"] == [] and report["gone"] == [] and report["changed"] == []
    assert READ_ONLY < set(report["added"]) and "book_repair" in report["added"]
    [server] = page.ok("mcpList", rid)["servers"]
    assert server["enabled"] is True and server["last_discovered_at"] and server["last_error"] is None
    tools = page.ok("toolList", rid)["tools"]
    assert names(tools, "active") == READ_ONLY and "book_repair" in names(tools, "proposed") and names(tools, "gone") == set()
    book = next(t for t in tools if t["name"] == "book_repair")
    assert (book["kind"], book["requires_consent"], book["source"]) == ("action", True, "discovered")
    assert "client_reference" in book["schema"]["input_schema"]["properties"]  # what the form offers as the reference argument
    # the activation form: a waiver without its reason is the API's 422, shown as it is
    r = page.call("toolPatch", rid, "book_repair", body=tool_action(tracking="none", ask=False, waiver=None))
    assert r.status_code == 422 and "consent_waiver" in r.json()["detail"]
    r = page.call("toolPatch", rid, "book_repair", body=tool_action(tracking="events"))
    assert r.status_code == 422 and "client_reference_arg" in r.json()["detail"]
    assert names(page.ok("toolList", rid)["tools"], "proposed") >= {"book_repair"}  # nothing was activated by a refusal
    done = page.ok("toolPatch", rid, "book_repair", body=tool_action(
        tracking="events", reference="client_reference", integration=integration, summary="Đặt lịch sửa chữa lúc {slot}"))
    assert (done["status"], done["tracking"], done["client_reference_arg"], done["requires_consent"], done["consent_summary"],
            done["integration_id"]) == ("active", "events", "client_reference", True, "Đặt lịch sửa chữa lúc {slot}", integration)
    # an action that runs unasked: the typed reason is kept
    waived = page.ok("toolPatch", rid, "book_hotel", body=tool_action(ask=False, waiver="cư dân đã yêu cầu rõ", reference="client_reference"))
    assert (waived["status"], waived["requires_consent"], waived["consent_waiver"]) == ("active", False, "cư dân đã yêu cầu rõ")
    # a tool the server does not call read-only becomes a look-up only with a reason
    r = page.call("toolPatch", rid, "lookup_no_hint", body=tool_lookup())
    assert r.status_code == 422 and "read-only" in r.json()["detail"]
    looked = page.ok("toolPatch", rid, "lookup_no_hint", body=tool_lookup(waiver="chỉ đọc theo tài liệu của đối tác"))
    assert (looked["status"], looked["kind"], looked["read_only"]) == ("active", "lookup", True)
    tools = page.ok("toolList", rid)["tools"]
    assert names(tools, "active") == READ_ONLY | {"book_repair", "book_hotel", "lookup_no_hint"}
    # "Sửa" (the same form, no activation) and "Ngưng dùng"
    edited = page.ok("toolPatch", rid, "book_hotel", body=tool_action(ask=True, reference="client_reference", activate=False))
    assert (edited["status"], edited["requires_consent"], edited["consent_waiver"]) == ("active", True, None)
    assert page.ok("toolPatch", rid, "book_hotel", body={"status": "proposed"})["status"] == "proposed"
    # "Làm mới": a tool the server dropped is shown as gone, and stays listed
    shop.mcp.remove_tool("book_hotel")
    report = page.ok("mcpRefresh", rid, "bql")
    assert report["gone"] == ["book_hotel"] and report["added"] == []
    assert names(page.ok("toolList", rid)["tools"], "gone") == {"book_hotel"}
    r = page.call("toolPatch", rid, "book_hotel", body=tool_action(reference="client_reference"))
    assert r.status_code == 409 and "no longer offers" in r.json()["detail"]
    # "Tắt": the rows stay, the server is off
    assert page.ok("mcpDisable", rid, "bql")["server"]["enabled"] is False
    assert names(page.ok("toolList", rid)["tools"], "active") == READ_ONLY | {"book_repair", "lookup_no_hint"}
    assert page.call("mcpEnable", rid, "nobody").status_code == 404


# ---- (a) and screen 3: an admin sets a partner up, then fills its tool store ----------------------------------------------
def test_a_an_admin_sets_up_a_partner_and_fills_the_tool_store(make_env, shop):
    with make_env(mcp_allow_private=True) as env:
        page = Page(env, "adm-a")
        assert page.ok("me")["role"] == "admin"
        assert page.ok("clients") == {"clients": []} and page.ok("routes") == {"routes": []}  # the empty states
        # screen 3, in the order its forms are used
        client = page.ok("clientAdd", body={"name": "Đối tác A", "domain": "homes", "environment": "sandbox"})
        cid = client["client_id"]
        q = {"client_id": cid}
        assert page.ok("keys", cid) == {"keys": []} and page.ok("managers", query=q) == {"managers": []}
        key = page.call("keyAdd", cid, body={"operations": ["submit_request", "reply", "read_result", "confirm_route"], "routes": ["*"]})
        assert key.status_code == 201 and key.headers["cache-control"] == "no-store" and key.json()["api_key"].startswith("dp_")
        secret = key.json()["api_key"]
        assert secret not in page.call("keys", cid).text  # shown exactly once: the list never has it again
        manager = page.ok("managerAdd", cid, body={"name": "Ban quản lý tòa A"})
        mkey = page.call("managerKeyAdd", manager["manager_id"])
        assert mkey.status_code == 201 and mkey.headers["cache-control"] == "no-store" and mkey.json()["api_key"].startswith("mk_")
        assert mkey.json()["api_key"] not in page.call("managerKeys", manager["manager_id"]).text
        env.leader("desk")  # an agent leader exists (made on screen 2); the route form offers it
        assert {p["key"] for p in page.ok("profiles")["profiles"] if p["profile"]["role"] == "leader"} == {"desk"}
        body = {"external_management_ref": "BQL-OP1-A", "manager_id": manager["manager_id"], "leader_profile": "desk",
                "config": {"ticket_binding_mode": "required", "residence_required": False, "timezone": "Asia/Ho_Chi_Minh",
                           "rules": {"safe_reply": "Ban quản lý sẽ liên hệ lại với bạn."}}}
        route = page.call("routeAdd", cid, body=body)
        assert route.status_code == 201 and route.json()["status"] == "pending" and route.json()["revision"] == 1
        route = route.json()
        bad = page.call("routeAdd", cid, body={**body, "external_management_ref": "X", "leader_profile": "nobody"})
        assert bad.status_code == 422 and "not a leader profile" in bad.json()["detail"]
        # "Gửi đối tác": what the dialog shows is exactly what the partner sends to confirm, with its own key
        confirm = env.http.post(f"/workforce/v1/partner/routes/{route['route_id']}/confirm", headers={"Authorization": f"ApiKey {secret}"},
                                json={"schema_version": "1", "expected_revision": route["revision"],
                                      "external_management_ref": route["external_management_ref"]})
        assert confirm.status_code == 200 and confirm.json()["status"] == "active"
        [listed] = page.ok("routes", query=q)["routes"]
        assert (listed["status"], listed["revision"], listed["manager_id"]) == ("active", 2, manager["manager_id"])
        # integration, its schema and its provider keys (secrets shown once)
        integ = page.ok("integrationAdd", cid, body={"event_schema": EVENT_SCHEMA})["integration_id"]
        refused = page.call("integrationAdd", cid, body={"event_schema": {"version": "1"}})
        assert refused.status_code == 422 and isinstance(refused.json()["detail"], list)  # a validation list: the page shows loc + msg
        [shown] = page.ok("integrations", query=q)["integrations"]
        assert shown["integration_id"] == integ and set(shown["event_schema"]["events"]) == set(EVENT_SCHEMA["events"])
        pkey = page.call("providerKeyAdd", integ, body={})
        assert pkey.status_code == 201 and pkey.headers["cache-control"] == "no-store"
        made = pkey.json()
        assert made["api_key"].startswith("dp_") and made["signing_key"]["secret"]
        full = page.ok("integration", integ)
        assert [s["key_id"] for s in full["signing_keys"]] == [made["signing_key"]["key_id"]] and made["signing_key"]["secret"] not in str(full)
        assert [k["key_id"] for k in page.ok("providerKeys", integ)["keys"]] == [made["key_id"]]
        extra = page.ok("signingKeyAdd", integ)["signing_key"]
        assert page.ok("signingKeyRevoke", integ, extra["key_id"]) == {"key_id": extra["key_id"], "status": "revoked"}
        # (a) screen 1 on that route
        tool_store_flow(page, route["route_id"], shop, integ)
        # keys: rotate (a new secret, once) and revoke; manager: off and on; route: suspend, replace
        rotated = page.call("keyRotate", key.json()["key_id"])
        assert rotated.status_code == 201 and rotated.json()["api_key"] != secret and rotated.json()["replaces"] == key.json()["key_id"]
        assert page.ok("keyRevoke", rotated.json()["key_id"])["status"] == "revoked"
        assert [k["status"] for k in page.ok("keys", cid)["keys"]] == ["revoked", "revoked"]
        assert page.call("keyRotate", rotated.json()["key_id"]).status_code == 409
        assert page.ok("managerKeyRevoke", manager["manager_id"], mkey.json()["key_id"])["status"] == "revoked"
        assert page.ok("managerDisable", manager["manager_id"])["status"] == "disabled"
        assert page.ok("managerEnable", manager["manager_id"])["status"] == "active"
        replaced = page.call("routeReplace", route["route_id"], body={"external_management_ref": "BQL-OP1-B"})
        assert replaced.status_code == 201 and replaced.json()["route"]["status"] == "pending"
        new = replaced.json()["route"]
        assert names(page.ok("toolList", new["route_id"])["tools"], "active") >= {"book_repair"}  # the store came along
        assert page.ok("routeSuspend", new["route_id"])["status"] == "suspended"
        assert page.call("routeSuspend", route["route_id"]).status_code == 409  # the replaced one: the 409 the page shows
        assert not any("adm-a" in u or secret in u for u in page.urls)


# ---- (b) builder chat, overlap warning, apply, the draft exists -----------------------------------------------------------
def test_b_a_builder_chat_warns_of_overlap_and_applies_into_a_draft(tmp_path):
    def proposes(*profiles):
        return lambda c: {"reply": "Đây là đề xuất của tôi.", "proposals": [
            {"action": "create", "profile": p, "reason": "chưa có agent nào làm việc này"} for p in profiles]}

    with world(tmp_path, publish=False) as w:
        page = Page(w.env, "adm-a")
        MODE["builder"] = proposes(PARKING)
        sid = page.ok("builderNew")["session_id"]
        said = page.ok("builderSay", sid, body={"text": "Cần một agent đặt chỗ gửi xe cho khách của cư dân."})
        assert [m["role"] for m in said["messages"]] == ["admin", "builder"] and said["messages"][1]["text"] == "Đây là đề xuất của tôi."
        [p] = said["proposals"]
        assert (p["action"], p["gated"], p["overlap"], p["applied"]) == ("create", False, [], None) and p["profile"]["key"] == "parking"
        assert "parking" not in {x["key"] for x in page.ok("profiles")["profiles"]}  # a proposal is not an agent
        done = page.ok("builderApply", sid, body={"items": [{"index": 0}]})
        assert done["results"] == [{"index": 0, "action": "create", "created": True, "key": "parking", "version": 1, "status": "draft"}]
        # the draft exists, is not live, and the reloaded session (a page reload) remembers that it was applied
        made = [x for x in page.ok("profiles")["profiles"] if x["key"] == "parking"]
        assert [(x["version"], x["status"]) for x in made] == [(1, "draft")] and "parking" not in w.rt.templates
        assert page.ok("builderGet", sid)["proposals"][0]["applied"]["key"] == "parking"
        assert page.ok("gate", "parking", 1)["publishable"] is False  # the draft meets the gate like any other

        # a second request for the same work under another name: the platform's warning, and no second agent
        MODE["builder"] = proposes({**PARKING, "key": "car_park", "name": "Car park desk"})
        [p] = page.ok("builderSay", sid, body={"text": "Thêm một agent lo chỗ đỗ xe cho khách."})["proposals"]
        assert (p["action"], p["proposed_action"], p["gated"], p["overlap_with"]) == ("reuse", "create", True, ["parking"])
        [warning] = p["overlap"]
        assert warning["key"] == "parking" and warning["score"] >= 0.5 and "parking" in warning["shared"]
        assert any("overlaps 'parking'" in n for n in p["notes"]) and p["profile"]["key"] == "car_park"
        [kept] = page.ok("builderApply", sid, body={"items": [{"index": 0}]})["results"]
        assert (kept["action"], kept["created"], kept["key"]) == ("reuse", False, "parking")
        assert "car_park" not in {x["key"] for x in page.ok("profiles")["profiles"]}
        # "Vẫn tạo bản nháp (ghi lý do)": the typed reason makes it, and the history keeps the reason
        [forced] = page.ok("builderApply", sid, body={"items": [{"index": 0, "override_reason": "bãi xe tầng hầm là một đội khác"}]})["results"]
        assert (forced["created"], forced["key"], forced["status"], forced["override_reason"]) == (True, "car_park", "draft", "bãi xe tầng hầm là một đội khác")
        [event] = page.ok("history", "car_park")["events"]
        assert event["kind"] == "create" and event["detail"]["override_reason"] == "bãi xe tầng hầm là một đội khác"
        assert page.call("builderGet", "bld_nobody").status_code == 404
        assert Page(w.env, "adm-b").call("builderGet", sid).status_code == 404  # another tenant's chat is not there


# ---- (c) the gate refuses, the evaluation passes, publish, roll back ---------------------------------------------------------
def evaluate(page: Page, key: str, version: int) -> dict:
    """"Chạy đánh giá": start with a short wait, then poll the list as the page does until the run ended."""
    r = page.call("evalRun", key, version, body={"wait_seconds": 20})
    assert r.status_code in (200, 202), r.text
    end = time.monotonic() + 120
    while True:
        latest = page.ok("evalRuns", key, version)["runs"][0]
        if latest["status"] != "running":
            return latest
        assert time.monotonic() < end, "the evaluation did not end"
        time.sleep(0.5)


def test_c_publish_is_refused_until_the_evaluation_passed_and_a_rollback_brings_the_old_version_back(tmp_path):
    with world(tmp_path, publish=False) as w:
        env, page = w.env, Page(w.env, "adm-a")
        ek.agents(tech=ek.careful)
        ek.draft(env, PLAIN)  # the draft a builder session leaves
        [rec] = [x for x in page.ok("profiles")["profiles"] if x["key"] == "tech"]
        assert (rec["version"], rec["status"], rec["published_at"]) == (1, "draft", None)
        # the Publish button is disabled with this reason, and pressing through answers the same
        gate = page.ok("gate", "tech", 1)
        assert gate["publishable"] is False and "not been evaluated" in gate["refusal"]["message"]
        refused = page.call("publish", "tech", 1)
        assert refused.status_code == 409 and refused.json()["detail"]["code"] == "EVAL_REQUIRED"
        assert page.ok("evalRuns", "tech", 1) == {"runs": []}
        # the case editor: the platform's cases are listed read-only, one of the tenant's is added, changed
        listed = page.ok("evalCases", "tech")["cases"]
        assert listed and all(c["platform"] and c["id"] is None for c in listed)
        bad = page.call("evalCaseAdd", "tech", body=eval_case("empty", "Hello"))
        assert bad.status_code == 422  # a case with no check: the validation list the page shows
        case = page.ok("evalCaseAdd", "tech", body=eval_case("no invented fee", "How much is the repair?", must_not_contain=["VND"]))
        case = page.ok("evalCaseSet", "tech", case["id"], body=eval_case("no invented fee", "How much is the repair?",
                                                                       must_not_contain=["VND"], must_not_call=["price_list"], grounded=True))
        assert [c["name"] for c in page.ok("evalCases", "tech")["cases"] if not c["platform"]] == ["no invented fee"]
        # run, read the per-case results, and the gate opens
        run = evaluate(page, "tech", 1)
        assert run["status"] == "passed" and run["score"] == 1.0 and run["started_by"].startswith("admin:")
        by_name = {r["name"]: r for r in run["results"]}
        assert len(by_name) == len(listed) + 1 and all(r["passed"] and r["checks"] for r in by_name.values())
        assert {c["check"] for c in by_name["no invented fee"]["checks"]} == {"must_not_contain", "must_not_call", "grounded"}
        assert page.ok("gate", "tech", 1) == {"key": "tech", "version": 1, "status": "draft", "publishable": True, "refusal": None}
        # a case changed after the run closes the gate again, with the reason; removing it does not reopen it
        extra = page.ok("evalCaseAdd", "tech", body=eval_case("says hello", "Hello", must_record_gap=True))
        gate = page.ok("gate", "tech", 1)
        assert gate["publishable"] is False and "cases of this agent changed" in gate["refusal"]["message"]
        assert gate["refusal"]["latest_run"]["status"] == "passed"
        assert page.ok("evalCaseDrop", "tech", extra["id"]) == {"deleted": extra["id"]}
        assert page.ok("gate", "tech", 1)["publishable"] is True  # the cases are again the ones that ran
        out = page.ok("publish", "tech", 1)
        assert (out["status"], out["version"], out["warnings"]) == ("published", 1, []) and out["published_by"].startswith("admin:")
        assert "tech" in w.rt.templates and page.ok("gate", "tech", 1)["publishable"] is False  # nothing left to publish
        # version 2: evaluated and published; version 1 is retired
        assert ek.draft(env, {**PLAIN, "mission": "a technician, second version."})["version"] == 2
        assert page.call("publish", "tech", 2).status_code == 409
        assert evaluate(page, "tech", 2)["status"] == "passed"
        assert page.ok("publish", "tech", 2)["status"] == "published"
        assert [(x["version"], x["status"]) for x in page.ok("profiles")["profiles"] if x["key"] == "tech"] == [(1, "retired"), (2, "published")]
        # "Rollback về v1"
        back = page.ok("rollback", "tech", body={"to_version": 1})
        assert (back["version"], back["status"]) == (1, "published")
        assert [(x["version"], x["status"]) for x in page.ok("profiles")["profiles"] if x["key"] == "tech"] == [(1, "published"), (2, "retired")]
        assert w.rt.templates["tech"].description == PLAIN["mission"]  # who is brought in from now on: version 1
        assert page.call("rollback", "tech", body={"to_version": 1}).status_code == 409  # already the live one
        # "Phát hành không qua đánh giá": the typed reason is recorded
        assert ek.draft(env, {**PLAIN, "mission": "a technician, third version."})["version"] == 3
        assert page.call("publish", "tech", 3).status_code == 409
        assert page.ok("publish", "tech", 3, body={"override_reason": "sửa lỗi chính tả gấp"})["status"] == "published"
        events = page.ok("history", "tech")["events"]
        kinds = [(e["kind"], e["version"]) for e in events]
        assert kinds[:8] == [("create", 1), ("eval", 1), ("publish", 1), ("create", 2), ("eval", 2), ("publish", 2), ("rollback", 1),
                             ("create", 3)]
        assert kinds[8:] == [("override", 3), ("publish", 3)]  # that it went past the gate, then the release
        [override] = [e for e in events if e["kind"] == "override"]
        assert override["detail"]["reason"] == "sửa lỗi chính tả gấp" and all(e["actor"].startswith("admin:") for e in events)


# ---- (d) workflows: list, look, resolve -----------------------------------------------------------------------------------------
def seed(env, wid: str, route_id: str, client_id: str, tag: str, integration: str) -> None:
    """An operation whose result is unknown, an approval and a provider receipt of a workflow, as rows."""
    conv = env.sql("select conversation_id from wf_workflows where id=?", (wid,))[0][0]
    env.sql("insert into wf_operations (id, workflow_id, route_id, tool_name, args_hash, client_reference, status, created_at, "
            "updated_at) values (?, ?, ?, 'book', 'h', ?, 'unknown', 1, 1)", (f"op_{tag}", wid, route_id, f"cr_{tag}"))
    env.sql("insert into wf_approvals (id, workflow_id, conversation_id, client_id, external_user_id, session_id, agent_id, "
            "tool_call_id, tool_name, arguments, arguments_hash, summary, status, workflow_revision, created_at) "
            "values (?, ?, ?, ?, 'resident-123', 's', 'a', ?, 'book', '{}', 'sha256:x', '{}', 'rejected', 1, 1)",
            (f"appr_{tag}", wid, conv, client_id, f"call_{tag}"))
    env.sql("insert into wf_provider_inbox (receipt_id, integration_id, external_event_id, payload_hash, event_type, payload, "
            "operation_id, workflow_id, ingestion_status, received_at) values (?, ?, ?, 'h', 'repair.assigned', '{}', ?, ?, "
            "'applied', 1)", (f"rcpt_{tag}", integration, f"ev_{tag}", f"op_{tag}", wid))


def needs_attention(env, wid: str, reason: str = "operation_unknown") -> None:
    env.sql("update wf_workflows set state='needs_attention', attention_reason=? where id=?", (reason, wid))


def operations_flow(page: Page, env, wid: str, other: str, tag: str) -> None:
    """Screen 4 for one workflow that needs attention (`wid`) and one that is resumed (`other`)."""
    listed = page.ok("workflows", query={"state": "needs_attention", "limit": 200})["workflows"]
    mine = next(x for x in listed if x["workflow_id"] == wid)
    assert (mine["state"], mine["next_action"], mine["attention_reason"]) == ("needs_attention", "resolve_attention", "operation_unknown")
    assert {x["workflow_id"] for x in page.ok("workflows", query={"state": "", "limit": 200})["workflows"]} >= {wid, other}
    # the detail screen: the workflow and what hangs on it
    q = {"workflow_id": wid, "limit": 200}
    assert page.ok("workflow", wid)["attention_reason"] == "operation_unknown"
    [op] = page.ok("operations", query=q)["operations"]
    assert (op["operation_id"], op["status"], op["reviewed"], op["client_reference"]) == (f"op_{tag}", "unknown", False, f"cr_{tag}")
    [approval] = page.ok("approvals", query=q)["approvals"]
    [receipt] = page.ok("receipts", query=q)["receipts"]
    assert (approval["approval_id"], approval["status"]) == (f"appr_{tag}", "rejected")
    assert (receipt["receipt_id"], receipt["ingestion_status"], receipt["operation_id"]) == (f"rcpt_{tag}", "applied", f"op_{tag}")
    # the list tabs with their status filter
    assert [o["operation_id"] for o in page.ok("operations", query={"status": "unknown", "limit": 200})["operations"]] == [f"op_{tag}"]
    assert page.ok("approvals", query={"status": "pending", "limit": 200}) == {"approvals": []}
    assert [x["receipt_id"] for x in page.ok("receipts", query={"status": "applied", "limit": 200})["receipts"]] == [f"rcpt_{tag}"]
    # "Cho leader chạy tiếp (resume)": the unknown operation is marked as seen, the leader gets a job
    resumed = page.ok("resolve", wid, body={"action": "resume"})
    assert (resumed["state"], resumed["attention_reason"]) == ("active", None)
    assert page.ok("operations", query=q)["operations"][0]["reviewed"] is True
    assert env.sql("select count(*) from wf_jobs where workflow_id=? and kind='operator'", (wid,)) == [(1,)]
    # a workflow that does not need attention: the 409 the page shows
    again = page.call("resolve", wid, body={"action": "close"})
    assert again.status_code == 409 and "only needs_attention can be resolved" in again.json()["detail"]
    # "Đóng workflow (close)"
    needs_attention(env, other, "leader_silent")
    closed = page.ok("resolve", other, body={"action": "close"})
    assert (closed["state"], closed["next_action"], closed["close_reason"]) == ("closed", "none", "operator_closed")
    assert page.ok("workflow", other)["closed_at"]
    assert page.call("workflow", "wf_nobody").status_code == 404 and page.call("resolve", "wf_nobody", body={"action": "close"}).status_code == 404
    assert page.call("resolve", other, body={"action": "retry"}).status_code == 422


def test_d_an_admin_lists_workflows_looks_at_one_and_resolves_it(flow):
    env, page = flow.env, Page(flow.env, "adm-a")
    assert page.ok("workflows", query={"limit": 200}) == {"workflows": []}  # the empty state
    _, first = flow.begin()
    _, second = flow.begin()
    integ = env.post(f"/platform/v1/wf/clients/{flow.client['client_id']}/integrations", {"event_schema": EVENT_SCHEMA}).json()["integration_id"]
    seed(env, first["workflow_id"], flow.route["route_id"], flow.client["client_id"], "a", integ)
    needs_attention(env, first["workflow_id"])
    operations_flow(page, env, first["workflow_id"], second["workflow_id"], "a")
    # screen 5 reads: the tenant's cost and its cases (no model ran here: the empty states)
    assert page.ok("cost", query={"since_hours": "24"}) == {"models": []}
    cases = page.ok("cases", query={"limit": 100})["cases"]
    assert len(cases) == 2 and page.ok("caseCost", cases[0]["id"])["totals"]["calls"] == 0
    assert Page(env, "adm-b").ok("workflows", query={"limit": 200}) == {"workflows": []}  # another tenant sees none of it


def test_d_the_cost_screen_shows_what_the_models_cost_by_model_by_case_and_by_agent(tmp_path):
    with world(tmp_path, publish=False) as w:
        page = Page(w.env, "adm-a")
        MODE["builder"] = lambda c: {"reply": "ok", "proposals": [{"action": "clarify", "question": "Việc gì?"}]}
        sid = page.ok("builderNew")["session_id"]
        page.ok("builderSay", sid, body={"text": "Cần một agent."})
        ek.agents(tech=ek.careful)
        ek.draft(w.env, PLAIN)
        run = evaluate(page, "tech", 1)
        models = {m["model"]: m for m in page.ok("cost", query={"since_hours": "24"})["models"]}
        assert models["fake-strong"]["calls"] >= 1 and models["fake-strong"]["cost_usd"] > 0  # the builder's call, on the tenant
        assert sum(m["cost_usd"] for m in models.values()) >= run["cost_usd"] > 0
        cost = page.ok("caseCost", run["results"][0]["case_id"])  # a case's cost: by agent and by model
        assert cost["totals"]["cost_usd"] > 0 and cost["totals"]["calls"] == sum(a["calls"] for a in cost["by_agent"])
        assert {a["agent_name"] for a in cost["by_agent"]} and {m["model"] for m in cost["by_model"]} <= set(models)
        assert page.ok("cost", query={"since_hours": "720"})["models"] and Page(w.env, "adm-b").ok("cost", query={"since_hours": "24"}) == {"models": []}


# ---- (e) a manager's key: the same screens, its own scope only ----------------------------------------------------------------------
def test_e_a_manager_key_runs_the_same_flows_inside_its_own_scope_only(make_flow, shop):
    with make_flow(mcp_allow_private=True) as flow:
        env, cid = flow.env, flow.client["client_id"]
        a = flow.route["manager_id"]
        b = env.manager(cid, "Ban quản lý khối B")["manager_id"]
        route_a = flow.route["route_id"]
        route_b = env.active_route(cid, flow.key["api_key"], ref="BQL-OP1-B", manager_id=b, leader="desk_b")["route_id"]
        page, other = Page(env, bearer(env.manager_key(a))), Page(env, bearer(env.manager_key(b)))
        _, mine1 = flow.begin()
        _, mine2 = flow.begin()
        _, theirs = flow.begin(external_management_ref="BQL-OP1-B")
        integ = env.post(f"/platform/v1/wf/clients/{cid}/integrations", {"event_schema": EVENT_SCHEMA}).json()["integration_id"]
        seed(env, mine1["workflow_id"], route_a, cid, "a", integ)
        seed(env, theirs["workflow_id"], route_b, cid, "b", integ)
        needs_attention(env, mine1["workflow_id"])
        needs_attention(env, theirs["workflow_id"])

        me = page.ok("me")
        assert (me["role"], me["manager_id"], me["tenant"], me["client_id"]) == ("manager", a, "ta", cid) and me["manager_name"]
        # what the page hides from a manager is also closed by the API: partners, cost, the builder
        route_body = {"external_management_ref": "BQL-OP1-C", "manager_id": a, "leader_profile": "supervisor"}
        for name, args, body in (
                ("clients", (), None), ("managers", (), None), ("integrations", (), None), ("keys", (cid,), None), ("cost", (), None),
                ("cases", (), None), ("caseCost", ("case_x",), None), ("managerKeys", (a,), None), ("integration", (integ,), None),
                ("providerKeys", (integ,), None), ("builderNew", (), None), ("builderGet", ("bld_x",), None),
                ("clientAdd", (), {"name": "x", "domain": "homes", "environment": "sandbox"}), ("managerAdd", (cid,), {"name": "x"}),
                ("routeAdd", (cid,), route_body), ("managerKeyAdd", (a,), None), ("managerDisable", (b,), None),
                ("routeSuspend", (route_a,), None), ("routeReplace", (route_a,), {}), ("keyAdd", (cid,), {"operations": ["reply"]}),
                ("keyRevoke", (flow.key["key_id"],), None), ("integrationAdd", (cid,), {"event_schema": EVENT_SCHEMA}),
                ("providerKeyAdd", (integ,), {}), ("signingKeyAdd", (integ,), None)):
            r = page.call(name, *args, body=body)
            assert r.status_code == 403, f"{name}: {r.status_code}"
        assert env.sql("select count(*) from wf_clients") == [(1,)] and env.sql("select status from wf_routes where id=?", (route_a,)) == [("active",)]
        # screen 1: its own route only, and the whole tool-store flow on it
        assert [r["route_id"] for r in page.ok("routes")["routes"]] == [route_a]
        for name in ("mcpList", "toolList"):
            assert page.call(name, route_b).status_code == 404, name
        assert page.call("mcpAdd", route_b, body={"name": "x", "url": shop.url, "timeout": 8, "headers": {}}).status_code == 404
        tool_store_flow(page, route_a, shop, None)
        assert other.ok("toolList", route_b) == {"tools": []} and other.call("toolList", route_a).status_code == 404
        # screen 4: its own workflows only, and the resolve flow on them
        assert {x["workflow_id"] for x in page.ok("workflows", query={"limit": 200})["workflows"]} == {mine1["workflow_id"], mine2["workflow_id"]}
        assert page.call("workflow", theirs["workflow_id"]).status_code == 404
        assert page.call("resolve", theirs["workflow_id"], body={"action": "close"}).status_code == 404
        assert page.ok("operations", query={"workflow_id": theirs["workflow_id"], "limit": 200}) == {"operations": []}
        operations_flow(page, env, mine1["workflow_id"], mine2["workflow_id"], "a")
        assert env.sql("select state from wf_workflows where id=?", (theirs["workflow_id"],)) == [("needs_attention",)]
        assert other.ok("resolve", theirs["workflow_id"], body={"action": "close"})["state"] == "closed"  # its own manager may
        # screen 2: the agents its routes use, their gate and history; never an override, never another account's agent
        assert {p["key"] for p in page.ok("profiles")["profiles"]} == {"supervisor"}
        assert {p["key"] for p in other.ok("profiles")["profiles"]} == {"desk_b"}
        assert page.ok("gate", "supervisor", 1)["publishable"] is False and page.ok("history", "supervisor")["events"][0]["kind"] == "create"
        assert page.ok("evalCases", "supervisor")["cases"] and page.ok("evalRuns", "supervisor", 1) == {"runs": []}
        for name, args, body in (("gate", ("desk_b", 1), None), ("history", ("desk_b",), None), ("evalCases", ("desk_b",), None),
                                 ("publish", ("desk_b", 1), None), ("rollback", ("desk_b",), {"to_version": 1})):
            assert page.call(name, *args, body=body).status_code == 404, name
        r = page.call("publish", "supervisor", 1, body={"override_reason": "cần gấp"})
        assert r.status_code == 403 and "only the tenant's admin" in r.json()["detail"]
        r = page.call("publish", "supervisor", 1)
        assert r.status_code == 409 and r.json()["detail"]["code"] == "EVAL_REQUIRED"
        assert env.sql("select status from awp_profiles where key='supervisor'") == [("draft",)]
        # the admin, on the same screens, sees both accounts
        admin = Page(env, "adm-a")
        assert {r["route_id"] for r in admin.ok("routes")["routes"]} == {route_a, route_b}
        assert len(admin.ok("workflows", query={"limit": 200})["workflows"]) == 3
        assert not any("mk_" in u for u in page.urls + other.urls)
