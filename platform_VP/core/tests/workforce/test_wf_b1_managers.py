"""Management accounts (M6): a route belongs to one manager, and a manager's operator key sees and operates only what
hangs off its own routes. The owner's case is two managers in one area under one client: neither may see or touch the
other's work, and the tenant's admin sees both. No model (the scripted engine of the request tests)."""
from __future__ import annotations

import hashlib
import json

import pytest
from conftest import ADM, ADM_B, EVENT_SCHEMA, build, key_headers

W = "/platform/v1/wf"


def get(env, path, headers):
    return env.http.get(W + path, headers=headers)


def post(env, path, headers, body=None):
    return env.http.post(W + path, headers=headers, json=body or {})


class Area:
    """One client, two managers (A and B), each with its own ref, route and one workflow."""

    def __init__(self, flow) -> None:
        self.flow, self.env = flow, flow.env
        env, cid = flow.env, flow.client["client_id"]
        self.cid = cid
        self.a = flow.route["manager_id"]  # the fixture's route (ref BQL-OP1-A) belongs to the client's default manager
        self.b = env.manager(cid, "Block B management")["manager_id"]
        self.route_a = flow.route["route_id"]
        self.route_b = env.active_route(cid, flow.key["api_key"], ref="BQL-OP1-B", manager_id=self.b)["route_id"]
        self.key_a, self.key_b = env.manager_key(self.a), env.manager_key(self.b)
        self.start_a, self.wf_a = flow.begin()
        self.start_b, self.wf_b = flow.begin(external_management_ref="BQL-OP1-B")
        self.wid_a, self.wid_b = self.wf_a["workflow_id"], self.wf_b["workflow_id"]

    def seed(self, wid: str, route_id: str, tag: str, integration: str) -> dict:
        """An operation, an approval and a provider receipt of a workflow, as rows."""
        sql, conv = self.env.sql, self.env.sql("select conversation_id from wf_workflows where id=?", (wid,))[0][0]
        sql("insert into wf_operations (id, workflow_id, route_id, tool_name, args_hash, client_reference, status, created_at, "
            "updated_at) values (?, ?, ?, 'book', 'h', ?, 'unknown', 1, 1)", (f"op_{tag}", wid, route_id, f"cr_{tag}"))
        sql("insert into wf_approvals (id, workflow_id, conversation_id, client_id, external_user_id, session_id, agent_id, "
            "tool_call_id, tool_name, arguments, arguments_hash, summary, status, workflow_revision, created_at) "
            "values (?, ?, ?, ?, 'resident-123', 's', 'a', ?, 'book', '{}', 'sha256:x', '{}', 'rejected', 1, 1)",
            (f"appr_{tag}", wid, conv, self.cid, f"call_{tag}"))
        sql("insert into wf_provider_inbox (receipt_id, integration_id, external_event_id, payload_hash, event_type, payload, "
            "operation_id, workflow_id, ingestion_status, received_at) values (?, ?, ?, 'h', 'repair.assigned', '{}', ?, ?, "
            "'applied', 1)", (f"rcpt_{tag}", integration, f"ev_{tag}", f"op_{tag}", wid))
        return {"operation": f"op_{tag}", "approval": f"appr_{tag}", "receipt": f"rcpt_{tag}"}


@pytest.fixture
def area(flow):
    return Area(flow)


# ---- the account and its keys -------------------------------------------------------------------------------------------
def test_a_manager_is_made_listed_and_switched_off_by_the_admin_only(env):
    c = env.client()
    m = env.manager(c["client_id"], "North block")
    assert m["manager_id"].startswith("mgr_") and m["status"] == "active" and m["client_id"] == c["client_id"]
    assert get(env, f"/managers/{m['manager_id']}", ADM).json() == m
    assert [x["manager_id"] for x in get(env, f"/managers?client_id={c['client_id']}", ADM).json()["managers"]] == [m["manager_id"]]
    assert post(env, f"/managers/{m['manager_id']}/disable", ADM).json()["status"] == "disabled"
    assert post(env, f"/managers/{m['manager_id']}/keys", ADM).status_code == 409  # no new key for an account that is off
    assert post(env, f"/managers/{m['manager_id']}/enable", ADM).json()["status"] == "active"
    assert post(env, f"/clients/{c['client_id']}/managers", ADM, {"name": ""}).status_code == 422
    assert post(env, "/clients/client_nobody/managers", ADM, {"name": "x"}).status_code == 404


def test_another_tenant_sees_and_changes_nothing_of_a_manager(env):
    c = env.client()
    m = env.manager(c["client_id"])["manager_id"]
    key = post(env, f"/managers/{m}/keys", ADM).json()
    assert get(env, "/managers", ADM_B).json() == {"managers": []}
    for path in (f"/managers/{m}", f"/managers/{m}/keys"):
        assert get(env, path, ADM_B).status_code == 404, path
    for path in (f"/clients/{c['client_id']}/managers", f"/managers/{m}/disable", f"/managers/{m}/keys",
                 f"/managers/{m}/keys/{key['key_id']}/revoke"):
        assert post(env, path, ADM_B, {"name": "x"} if path.endswith("/managers") else None).status_code == 404, path
    assert env.sql("select status from wf_managers") == [("active",)]
    assert env.sql("select status from wf_manager_keys") == [("active",)]


def test_a_manager_key_is_shown_once_and_only_its_hash_is_kept(env):
    c = env.client()
    m = env.manager(c["client_id"])["manager_id"]
    r = post(env, f"/managers/{m}/keys", ADM)
    assert r.status_code == 201 and r.headers["cache-control"] == "no-store"
    made = r.json()
    key_id, secret = made["api_key"][len("mk_"):].split(".", 1)
    assert made["api_key"].startswith("mk_") and key_id == made["key_id"]
    assert env.sql("select secret_hash from wf_manager_keys") == [(hashlib.sha256(secret.encode()).hexdigest(),)]
    assert secret not in env.dump()
    listed = get(env, f"/managers/{m}/keys", ADM)
    assert [k["key_id"] for k in listed.json()["keys"]] == [key_id] and "api_key" not in listed.text and secret not in listed.text


def test_a_key_that_is_wrong_revoked_expired_or_of_a_disabled_account_opens_nothing(env):
    c = env.client()
    m = env.manager(c["client_id"])["manager_id"]
    made = post(env, f"/managers/{m}/keys", ADM).json()
    good = {"Authorization": f"Bearer {made['api_key']}"}
    assert get(env, "/routes", good).status_code == 200
    key_id, secret = made["api_key"][3:].split(".", 1)
    for bad in (f"mk_{key_id}.{secret[:-1]}x", f"mk_{'0' * 16}.{secret}", "mk_", "mk_x.y", f"mk_{key_id}"):
        assert get(env, "/routes", {"Authorization": f"Bearer {bad}"}).status_code == 401, bad
    post(env, f"/managers/{m}/disable", ADM)
    assert get(env, "/routes", good).status_code == 401
    post(env, f"/managers/{m}/enable", ADM)
    assert get(env, "/routes", good).status_code == 200
    env.sql("update wf_manager_keys set expires_at=1 where key_id=?", (key_id,))
    assert get(env, "/routes", good).status_code == 401
    env.sql("update wf_manager_keys set expires_at=null where key_id=?", (key_id,))
    r = post(env, f"/managers/{m}/keys/{key_id}/revoke", ADM)
    assert r.status_code == 200 and r.json()["status"] == "revoked" and r.json()["revoked_at"]
    assert get(env, "/routes", good).status_code == 401
    env.sql("update wf_manager_keys set status='active' where key_id=?", (key_id,))
    env.sql("update wf_clients set status='disabled'")
    assert get(env, "/routes", good).status_code == 401  # the client is off: so are its managers


def test_an_unknown_manager_key_is_never_the_dev_user(tmp_path):
    with build(tmp_path, dev_open=True, admin_keys={}) as env:
        assert env.http.get(f"{W}/routes").status_code == 200  # dev mode lets a keyless call in as tenant dev
        assert env.http.get(f"{W}/routes", headers={"Authorization": "Bearer mk_0123456789abcdef.nothing-like-a-real-secret"}
                            ).status_code == 401


# ---- a route belongs to exactly one manager ---------------------------------------------------------------------------
def test_a_route_needs_a_manager_of_its_own_client(env):
    c, other = env.client(), env.client(domain="other")
    mine, theirs = env.manager(c["client_id"])["manager_id"], env.manager(other["client_id"])["manager_id"]
    body = {"external_management_ref": "R", "leader_profile": env.leader()}
    url = f"/clients/{c['client_id']}/routes"
    assert post(env, url, ADM, body).status_code == 422  # manager_id is required
    for bad in (theirs, "mgr_nobody"):
        r = post(env, url, ADM, {**body, "manager_id": bad})
        assert r.status_code == 422 and "manager" in r.text, r.text
    post(env, f"/managers/{mine}/disable", ADM)
    assert post(env, url, ADM, {**body, "manager_id": mine}).status_code == 422
    post(env, f"/managers/{mine}/enable", ADM)
    made = post(env, url, ADM, {**body, "manager_id": mine})
    assert made.status_code == 201 and made.json()["manager_id"] == mine
    assert env.sql("select count(*) from wf_routes") == [(1,)]


def test_one_ref_belongs_to_one_manager_and_a_replacement_stays_with_it(env):
    c = env.client()
    k = env.key(c["client_id"])
    a, b = env.manager(c["client_id"], "A")["manager_id"], env.manager(c["client_id"], "B")["manager_id"]
    route = env.active_route(c["client_id"], k["api_key"], ref="AREA-1", manager_id=a)
    r = post(env, f"/clients/{c['client_id']}/routes", ADM,
             {"external_management_ref": "AREA-1", "leader_profile": env.leader(), "manager_id": b})
    assert r.status_code == 409 and "another manager" in r.text
    new = post(env, f"/routes/{route['route_id']}/replace", ADM).json()["route"]
    assert new["manager_id"] == a
    assert [x["route_id"] for x in get(env, f"/routes?manager_id={a}", ADM).json()["routes"]] == [route["route_id"], new["route_id"]]
    assert get(env, f"/routes?manager_id={b}", ADM).json() == {"routes": []}


# ---- two managers, one area, one client ---------------------------------------------------------------------------------
def test_each_ref_starts_its_workflow_on_its_own_managers_route(area):
    rows = dict(area.env.sql("select id, route_id from wf_workflows"))
    assert rows == {area.wid_a: area.route_a, area.wid_b: area.route_b}
    # a request under B's ref made nothing on A's route: no conversation, no case, no job
    assert area.env.sql("select count(*) from wf_conversations where route_id=?", (area.route_a,)) == [(1,)]
    assert area.env.sql("select count(*) from wf_jobs where workflow_id=?", (area.wid_a,)) == [(1,)]
    r, _ = area.flow.reply(area.start_b, area.wf_b, external_management_ref="BQL-OP1-A")  # B's workflow under A's ref
    assert r.status_code == 409 and r.json()["error"]["code"] == "WORKFLOW_BINDING_MISMATCH"
    assert dict(area.env.sql("select id, route_id from wf_workflows")) == rows


def test_a_manager_lists_only_its_own_and_the_admin_sees_both(area):
    env = area.env
    integ = post(env, f"/clients/{area.cid}/integrations", ADM, {"event_schema": EVENT_SCHEMA}).json()["integration_id"]
    mine, theirs = area.seed(area.wid_a, area.route_a, "a", integ), area.seed(area.wid_b, area.route_b, "b", integ)
    env.sql("insert into wf_provider_inbox (receipt_id, integration_id, external_event_id, payload_hash, event_type, payload, "
            "ingestion_status, received_at) values ('rcpt_loose', ?, 'ev_loose', 'h', 'repair.assigned', '{}', 'quarantined', 1)",
            (integ,))

    def ids(headers) -> dict:
        return {
            "routes": {x["route_id"] for x in get(env, "/routes", headers).json()["routes"]},
            "workflows": {x["workflow_id"] for x in get(env, "/workflows", headers).json()["workflows"]},
            "operations": {x["operation_id"] for x in get(env, "/operations", headers).json()["operations"]},
            "approvals": {x["approval_id"] for x in get(env, "/approvals", headers).json()["approvals"]},
            "receipts": {x["receipt_id"] for x in get(env, "/receipts", headers).json()["receipts"]}}

    assert ids(area.key_a) == {"routes": {area.route_a}, "workflows": {area.wid_a}, "operations": {mine["operation"]},
                               "approvals": {mine["approval"]}, "receipts": {mine["receipt"]}}
    assert ids(area.key_b) == {"routes": {area.route_b}, "workflows": {area.wid_b}, "operations": {theirs["operation"]},
                               "approvals": {theirs["approval"]}, "receipts": {theirs["receipt"]}}
    assert ids(ADM) == {"routes": {area.route_a, area.route_b}, "workflows": {area.wid_a, area.wid_b},
                        "operations": {mine["operation"], theirs["operation"]},
                        "approvals": {mine["approval"], theirs["approval"]},
                        "receipts": {mine["receipt"], theirs["receipt"], "rcpt_loose"}}  # an unmatched event is the admin's
    # a filter that names the other manager's rows finds nothing, it does not widen the view
    assert get(env, f"/workflows?route_id={area.route_b}", area.key_a).json() == {"workflows": []}
    assert get(env, f"/operations?workflow_id={area.wid_b}", area.key_a).json() == {"operations": []}
    assert get(env, f"/approvals?workflow_id={area.wid_b}", area.key_a).json() == {"approvals": []}
    assert get(env, f"/receipts?workflow_id={area.wid_b}", area.key_a).json() == {"receipts": []}
    assert get(env, f"/routes?manager_id={area.b}", area.key_a).json() == {"routes": []}


def test_the_other_managers_rows_answer_404_and_resolve_does_too(area):
    env = area.env
    integ = post(env, f"/clients/{area.cid}/integrations", ADM, {"event_schema": EVENT_SCHEMA}).json()["integration_id"]
    theirs = area.seed(area.wid_b, area.route_b, "b", integ)
    env.sql("update wf_workflows set state='needs_attention', attention_reason='operation_unknown' where id=?", (area.wid_b,))
    reads = [f"/workflows/{area.wid_b}", f"/operations/{theirs['operation']}", f"/receipts/{theirs['receipt']}",
             f"/routes/{area.route_b}", f"/routes/{area.route_b}/mcp", f"/routes/{area.route_b}/tools"]
    for path in reads:
        assert get(env, path, area.key_a).status_code == 404, path
        assert get(env, path, area.key_b).status_code == 200, path
        assert get(env, path, ADM).status_code == 200, path
    for action in ("resume", "close"):
        r = post(env, f"/workflows/{area.wid_b}/resolve", area.key_a, {"action": action})
        assert r.status_code == 404, r.text
    assert env.sql("select state from wf_workflows where id=?", (area.wid_b,)) == [("needs_attention",)]
    assert env.sql("select count(*) from wf_jobs where workflow_id=? and kind='operator'", (area.wid_b,)) == [(0,)]
    done = post(env, f"/workflows/{area.wid_b}/resolve", area.key_b, {"action": "close"})  # its own manager may
    assert done.status_code == 200 and done.json()["state"] == "closed"
    env.sql("update wf_workflows set state='needs_attention' where id=?", (area.wid_a,))
    assert post(env, f"/workflows/{area.wid_a}/resolve", ADM, {"action": "close"}).json()["state"] == "closed"  # the superuser


def test_a_manager_configures_the_tool_store_of_its_own_route_only(area):
    env = area.env
    server = {"name": "p", "url": "http://93.184.216.34/mcp"}
    tool = {"name": "partner_lookup", "server": "p", "mcp_tool": "lookup_ticket", "kind": "lookup", "read_only": True}
    own, other = f"/routes/{area.route_a}", f"/routes/{area.route_b}"
    assert env.http.put(W + own + "/mcp", headers=area.key_a, json={"servers": [server]}).status_code == 200
    assert env.http.put(W + own + "/tools", headers=area.key_a, json={"tools": [tool]}).status_code == 200
    r = env.http.patch(W + own + "/tools/partner_lookup", headers=area.key_a, json={"description_override": "Look a ticket up"})
    assert r.status_code == 200 and r.json()["description_override"] == "Look a ticket up"
    assert post(env, own + "/mcp/p/disable", area.key_a).json()["server"]["enabled"] is False
    for method, path, body in (("put", "/mcp", {"servers": [server]}), ("put", "/tools", {"tools": []}),
                               ("post", "/mcp", {**server, "name": "q"}), ("post", "/mcp/p/enable", {}),
                               ("post", "/mcp/p/refresh", {}), ("post", "/mcp/p/disable", {}),
                               ("patch", "/tools/partner_lookup", {"status": "proposed"})):
        r = env.http.request(method.upper(), W + other + path, headers=area.key_a, json=body)
        assert r.status_code == 404, (method, path, r.text)
        r = env.http.request(method.upper(), W + own + path, headers=area.key_b, json=body)  # and the other way round
        assert r.status_code == 404, (method, path, r.text)
    assert env.sql("select route_id, name from wf_mcp_servers") == [(area.route_a, "p")]
    assert env.sql("select route_id, name, status from wf_tools") == [(area.route_a, "partner_lookup", "active")]


def test_a_manager_key_reaches_nothing_but_its_own_corner(area):
    """Not the tenant's administration (clients, keys, managers, routes that change), not the profiles' writes, not the
    cases, and never the AgentScope API or the partner API."""
    env, key = area.env, area.key_a
    admin_only_posts = [
        ("/clients", {"name": "x", "domain": "d", "environment": "sandbox"}),
        (f"/clients/{area.cid}/keys", {"operations": ["reply"]}),
        (f"/clients/{area.cid}/managers", {"name": "x"}),
        (f"/clients/{area.cid}/routes", {"external_management_ref": "R2", "leader_profile": "supervisor", "manager_id": area.a}),
        (f"/clients/{area.cid}/integrations", {"event_schema": EVENT_SCHEMA}),
        (f"/managers/{area.a}/keys", {}), (f"/managers/{area.b}/disable", {}),
        (f"/routes/{area.route_a}/suspend", {}), (f"/routes/{area.route_a}/replace", {}),
        (f"/keys/{area.flow.key['key_id']}/revoke", {}), (f"/keys/{area.flow.key['key_id']}/rotate", {})]
    for path, body in admin_only_posts:
        assert post(env, path, key, body).status_code == 403, path
    for path in ("/clients", f"/clients/{area.cid}", f"/clients/{area.cid}/keys", "/managers", f"/managers/{area.a}",
                 f"/managers/{area.a}/keys", "/integrations"):
        assert get(env, path, key).status_code == 403, path
    assert env.sql("select count(*) from wf_clients") == [(1,)] and env.sql("select count(*) from wf_managers") == [(2,)]
    assert env.sql("select status from wf_routes where id=?", (area.route_a,)) == [("active",)]
    assert env.sql("select status from wf_keys") == [("active",)]
    platform = "/platform/v1"
    for path in ("/cases", "/cost", "/models", "/metrics", "/jev"):
        assert env.http.get(platform + path, headers=key).status_code == 403, path
    profile = {"key": "mine", "name": "Mine", "mission": "x"}
    assert env.http.post(platform + "/profiles", headers=key, json=profile).status_code == 403
    assert env.http.post(platform + "/profiles/supervisor/versions/1/publish", headers=key).status_code == 403
    assert env.http.post(platform + "/profiles/supervisor/retire", headers=key).status_code == 403
    assert env.http.put(platform + "/profiles/supervisor/versions/1", headers=key, json=profile).status_code == 403
    for path in ("/agent/", "/sessions/", "/credential/", "/chat/", "/workspace/mcp"):  # AgentScope's own API
        assert env.http.get(path, headers=key).status_code == 403, path
        assert env.http.post(path, headers=key, json={}).status_code == 403, path
    assert env.http.get("/agent/", headers=ADM).status_code == 200  # the path is real: the admin gets there
    # the partner API takes ApiKey credentials only
    r = area.flow.post(area.flow.start_body(), headers=key)
    assert r.status_code == 401 and r.json()["error"]["code"] == "UNAUTHENTICATED"
    r = env.http.get(f"{W}/routes", headers=key_headers(area.flow.key["api_key"]))  # and a partner key is no manager key
    assert r.status_code == 401


def test_a_manager_reads_the_profiles_its_routes_use_and_no_others(env):
    c = env.client()
    for body in ({"key": "desk", "name": "Desk", "role": "leader", "mission": "leads.", "team": ["plumber"]},
                 {"key": "plumber", "name": "Plumber", "mission": "fixes pipes."},
                 {"key": "other_desk", "name": "Other", "role": "leader", "mission": "leads elsewhere.", "team": ["painter"]},
                 {"key": "painter", "name": "Painter", "mission": "paints."}):
        assert env.post("/platform/v1/profiles", body).status_code == 201
    a, b = env.manager(c["client_id"], "A")["manager_id"], env.manager(c["client_id"], "B")["manager_id"]
    env.route(c["client_id"], "A", manager_id=a, leader="desk")
    env.route(c["client_id"], "B", manager_id=b, leader="other_desk")
    seen = lambda headers: sorted(p["key"] for p in env.http.get("/platform/v1/profiles", headers=headers).json()["profiles"])  # noqa: E731
    assert seen(env.manager_key(a)) == ["desk", "plumber"]
    assert seen(env.manager_key(b)) == ["other_desk", "painter"]
    assert seen(ADM) == ["desk", "other_desk", "painter", "plumber"]


def test_a_manager_of_one_tenant_reaches_nothing_of_another(make_env):
    with make_env() as env:
        ca, cb = env.client(), env.client(headers=ADM_B)
        ma = env.manager(ca["client_id"])["manager_id"]
        mb = env.manager(cb["client_id"], headers=ADM_B)["manager_id"]
        ra = env.route(ca["client_id"], manager_id=ma)
        rb = env.route(cb["client_id"], headers=ADM_B, manager_id=mb, leader="supervisor_b")
        key_a = env.manager_key(ma)
        assert {x["route_id"] for x in get(env, "/routes", key_a).json()["routes"]} == {ra["route_id"]}
        for path in (f"/routes/{rb['route_id']}", f"/routes/{rb['route_id']}/tools", f"/routes/{rb['route_id']}/mcp"):
            assert get(env, path, key_a).status_code == 404, path
        # a row that names tenant A's manager on tenant B's route (it cannot be made through the API) still opens nothing
        env.sql("update wf_routes set manager_id=? where id=?", (ma, rb["route_id"]))
        assert get(env, f"/routes/{rb['route_id']}", key_a).status_code == 404
        assert json.loads(get(env, "/routes", key_a).text)["routes"][0]["route_id"] == ra["route_id"]
        assert len(get(env, "/routes", key_a).json()["routes"]) == 1
