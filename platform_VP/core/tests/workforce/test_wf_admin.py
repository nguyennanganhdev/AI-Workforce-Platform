"""Admin API under /platform/v1/wf: lifecycle, validation, tenant isolation, no leaked secrets."""
import copy
import json
import re

import pytest
from cryptography.fernet import Fernet

from awp.app import build_app
from awp.config import Settings
from awp.providers import ModelCatalog
from awp.workforce.crypto import Sealer, SecretKeyMissing
from conftest import ADM, ADM_B, ALL_CUSTOMER, EVENT_SCHEMA, OLD_SVC, SECRET_KEY, key_headers

W = "/platform/v1/wf"


def secrets_in(text: str, *plain: str):
    for p in plain:
        assert p not in text


# ---- access --------------------------------------------------------------
def test_admin_api_needs_an_admin_bearer_key(env):
    assert env.http.get(f"{W}/clients").status_code == 401
    assert env.http.get(f"{W}/clients", headers=OLD_SVC).status_code == 401  # a connector key is not an admin key (the platform no longer has them)
    assert env.http.get(f"{W}/clients", headers=ADM).status_code == 200


# ---- clients ---------------------------------------------------------------
def test_create_client_takes_tenant_from_the_principal(env):
    r = env.http.post(f"{W}/clients", headers=ADM, json={"name": "Acme Partner", "domain": "homes",
                                                         "environment": "sandbox", "capabilities": ["attach_asset"]})
    assert r.status_code == 201
    body = r.json()
    assert body["client_id"].startswith("client_") and body["status"] == "active"
    assert body["capabilities"] == ["attach_asset"] and body["created_at"].endswith("Z")
    (row,) = env.sql("select tenant, domain, environment from wf_clients where id = ?", (body["client_id"],))
    assert row == ("ta", "homes", "sandbox")
    assert "tenant" not in body
    r = env.http.post(f"{W}/clients", headers=ADM_B, json={"name": "B", "domain": "d", "environment": "production"})
    (row,) = env.sql("select tenant from wf_clients where id = ?", (r.json()["client_id"],))
    assert row == ("tb",)
    # the body cannot name a tenant
    bad = {"name": "x", "domain": "d", "environment": "sandbox", "tenant": "tb"}
    assert env.http.post(f"{W}/clients", headers=ADM, json=bad).status_code == 422


@pytest.mark.parametrize("body", [
    {"name": "", "domain": "d", "environment": "sandbox"},
    {"name": "n", "domain": "has space", "environment": "sandbox"},
    {"name": "n", "domain": "d", "environment": "prod"},
    {"name": "n", "domain": "d", "environment": "sandbox", "capabilities": ["fly"]},
    {"name": "n" * 121, "domain": "d", "environment": "sandbox"},
    {"domain": "d", "environment": "sandbox"},
])
def test_client_input_is_validated(env, body):
    assert env.http.post(f"{W}/clients", headers=ADM, json=body).status_code == 422


# ---- keys --------------------------------------------------------------------
def test_key_secret_is_shown_once_and_never_listed(env):
    c = env.client()
    k = env.key(c["client_id"], operations=["reply", "read_result"])
    assert re.fullmatch(r"dp_[0-9a-f]{16}\.[A-Za-z0-9_-]{43}", k["api_key"])
    assert k["key_id"] == k["api_key"][3:19] and k["operations"] == ["reply", "read_result"]
    assert k["routes"] == ["*"] and k["status"] == "active"
    secret = k["api_key"].split(".", 1)[1]

    listing = env.http.get(f"{W}/clients/{c['client_id']}/keys", headers=ADM)
    assert listing.status_code == 200
    assert [x["key_id"] for x in listing.json()["keys"]] == [k["key_id"]]
    secrets_in(listing.text, secret, "secret_hash", "api_key")
    assert set(listing.json()["keys"][0]) == {"key_id", "kind", "client_id", "integration_id", "operations",
                                              "routes", "status", "expires_at", "created_at", "revoked_at"}
    r = env.http.post(f"{W}/clients/{c['client_id']}/keys", headers=ADM, json={"operations": ["reply"]})
    assert r.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("body", [
    {"operations": []},
    {"operations": ["reply", "reply"]},
    {"operations": ["publish_job_event"]},  # a provider operation
    {"operations": ["teleport"]},
    {"operations": ["reply"], "routes": []},
    {"operations": ["reply"], "routes": ["*", "route_x"]},
    {"operations": ["reply"], "routes": ["route_not_mine"]},
    {"operations": ["reply"], "expires_at": "2001-01-01T00:00:00Z"},
    {"operations": ["reply"], "expires_at": "tomorrow"},
    {"operations": ["reply"], "client_id": "other"},
])
def test_key_input_is_validated(env, body):
    c = env.client()
    assert env.http.post(f"{W}/clients/{c['client_id']}/keys", headers=ADM, json=body).status_code == 422


def test_key_routes_must_belong_to_the_client(env):
    a, b = env.client(), env.client(domain="other")
    rb = env.route(b["client_id"])
    ra = env.route(a["client_id"])
    r = env.http.post(f"{W}/clients/{a['client_id']}/keys", headers=ADM,
                      json={"operations": ["reply"], "routes": [rb["route_id"]]})
    assert r.status_code == 422
    ok = env.http.post(f"{W}/clients/{a['client_id']}/keys", headers=ADM,
                       json={"operations": ["reply"], "routes": [ra["route_id"]]})
    assert ok.status_code == 201 and ok.json()["routes"] == [ra["route_id"]]


def test_key_with_expiry_records_it(env):
    c = env.client()
    k = env.key(c["client_id"], expires_at="2999-05-06T07:08:09Z")
    assert k["expires_at"] == "2999-05-06T07:08:09Z"


def test_revoke_key_is_idempotent_and_final(env):
    c = env.client()
    k = env.key(c["client_id"])
    first = env.post(f"{W}/keys/{k['key_id']}/revoke")
    assert first.status_code == 200 and first.json()["status"] == "revoked" and first.json()["revoked_at"]
    again = env.post(f"{W}/keys/{k['key_id']}/revoke")
    assert again.status_code == 200 and again.json() == first.json()
    assert "api_key" not in first.text
    assert env.post(f"{W}/keys/{k['key_id']}/rotate").status_code == 409  # a revoked key cannot be rotated


def test_rotate_key_issues_a_new_secret_and_retires_the_old(env):
    c = env.client()
    ra = env.route(c["client_id"])
    old = env.key(c["client_id"], operations=["reply", "confirm_route"], routes=[ra["route_id"]])
    r = env.post(f"{W}/keys/{old['key_id']}/rotate")
    assert r.status_code == 201
    new = r.json()
    assert new["key_id"] != old["key_id"] and new["replaces"] == old["key_id"]
    assert new["operations"] == ["reply", "confirm_route"] and new["routes"] == [ra["route_id"]]
    assert env.confirm(old["api_key"], ra).status_code == 401  # old key is dead
    assert env.confirm(new["api_key"], ra).status_code == 200  # new key works
    keys = env.http.get(f"{W}/clients/{c['client_id']}/keys", headers=ADM).json()["keys"]
    assert {x["key_id"]: x["status"] for x in keys} == {old["key_id"]: "revoked", new["key_id"]: "active"}


def test_rotate_keeps_a_future_expiry_and_refuses_an_expired_one(env):
    c = env.client()
    k = env.key(c["client_id"], expires_at="2999-01-01T00:00:00Z")
    assert env.post(f"{W}/keys/{k['key_id']}/rotate").json()["expires_at"] == "2999-01-01T00:00:00Z"
    k2 = env.key(c["client_id"], expires_at="2999-01-01T00:00:00Z")
    env.sql("update wf_keys set expires_at = 1 where key_id = ?", (k2["key_id"],))
    assert env.post(f"{W}/keys/{k2['key_id']}/rotate").status_code == 422
    r = env.post(f"{W}/keys/{k2['key_id']}/rotate", {"expires_at": "2998-01-01T00:00:00Z"})
    assert r.status_code == 201 and r.json()["expires_at"] == "2998-01-01T00:00:00Z"


# ---- routes ---------------------------------------------------------------------
def test_create_route_is_pending_revision_1_with_filled_config(env):
    c = env.client()
    r = env.http.post(f"{W}/clients/{c['client_id']}/routes", headers=ADM, json={
        "external_management_ref": "BQL-OP1-A", "leader_profile": env.leader(), "manager_id": env.default_manager(c["client_id"]),
        "config": {"ticket_binding_mode": "required", "residence_required": True, "timezone": "Asia/Ho_Chi_Minh",
                   "wait_seconds": 5, "rules": {"safe_reply": "A person will follow up.",
                                                "phrase_rules": [{"phrases": ["is fixed"], "reason": "claims done",
                                                                  "unless": ["status: done"]}]},
                   "policy": {"auto_close_read_only": False, "approval_ttl_seconds": 600}}})
    assert r.status_code == 201
    body = r.json()
    assert body["route_id"].startswith("route_") and body["revision"] == 1 and body["status"] == "pending"
    assert body["config"]["timezone"] == "Asia/Ho_Chi_Minh" and body["config"]["wait_seconds"] == 5
    assert body["config"]["policy"] == {"auto_close_read_only": False, "approval_ttl_seconds": 600}
    assert body["config"]["rules"]["phrase_rules"][0]["unless"] == ["status: done"]
    got = env.http.get(f"{W}/routes/{body['route_id']}", headers=ADM).json()
    assert got == body


def test_route_defaults_come_from_settings(make_env):
    with make_env(wf_wait_seconds=7.5, approval_ttl_seconds=900) as env:
        c = env.client()
        cfg = env.route(c["client_id"])["config"]
        assert cfg["wait_seconds"] == 7.5 and cfg["policy"]["approval_ttl_seconds"] == 900
        assert cfg["ticket_binding_mode"] == "required" and cfg["residence_required"] is False
        assert cfg["timezone"] == "UTC" and cfg["policy"]["auto_close_read_only"] is True


@pytest.mark.parametrize("patch", [
    {"external_management_ref": ""},
    {"external_management_ref": "x" * 129},
    {"external_management_ref": "tab\there"},
    {"leader_profile": "has space"},
    {"leader_profile": ""},
    {"config": {"timezone": "Mars/Base"}},
    {"config": {"ticket_binding_mode": "sometimes"}},
    {"config": {"wait_seconds": -1}},
    {"config": {"wait_seconds": 500}},
    {"config": {"unknown_setting": 1}},
    {"config": {"policy": {"approval_ttl_seconds": 5}}},
    {"config": {"rules": {"phrase_rules": [{"phrases": [], "reason": "x"}]}}},
    {"client_id": "c"},
])
def test_route_input_is_validated(env, patch):
    c = env.client()
    good = {"external_management_ref": "R", "leader_profile": env.leader(), "manager_id": env.default_manager(c["client_id"])}
    assert env.http.post(f"{W}/clients/{c['client_id']}/routes", headers=ADM, json={**good, **patch}).status_code == 422
    assert env.http.post(f"{W}/clients/{c['client_id']}/routes", headers=ADM, json=good).status_code == 201  # only the patch was wrong


def test_list_and_filter_routes(env):
    a, b = env.client(), env.client(domain="b")
    r1, r2, r3 = env.route(a["client_id"], "A"), env.route(a["client_id"], "B"), env.route(b["client_id"], "C")
    env.post(f"{W}/routes/{r2['route_id']}/suspend")
    allr = env.http.get(f"{W}/routes", headers=ADM).json()["routes"]
    assert {x["route_id"] for x in allr} == {r1["route_id"], r2["route_id"], r3["route_id"]}
    only_a = env.http.get(f"{W}/routes?client_id={a['client_id']}", headers=ADM).json()["routes"]
    assert {x["route_id"] for x in only_a} == {r1["route_id"], r2["route_id"]}
    susp = env.http.get(f"{W}/routes?status=suspended", headers=ADM).json()["routes"]
    assert [x["route_id"] for x in susp] == [r2["route_id"]]


def test_suspend_route(env):
    c = env.client()
    k = env.key(c["client_id"])
    r = env.active_route(c["client_id"], k["api_key"])
    s = env.post(f"{W}/routes/{r['route_id']}/suspend")
    assert s.status_code == 200 and s.json()["status"] == "suspended" and s.json()["revision"] == r["revision"] + 1
    again = env.post(f"{W}/routes/{r['route_id']}/suspend")
    assert again.json() == s.json()  # idempotent, revision not bumped twice
    # a suspended route cannot be confirmed again
    assert env.confirm(k["api_key"], s.json(), revision=s.json()["revision"]).status_code == 409


def test_replace_route_marks_old_replaced_and_starts_a_new_pending_one(env):
    c = env.client()
    k = env.key(c["client_id"])
    old = env.active_route(c["client_id"], k["api_key"], timezone="Asia/Tokyo")
    r = env.post(f"{W}/routes/{old['route_id']}/replace", {"leader_profile": env.leader("supervisor_v2")})
    assert r.status_code == 201
    new = r.json()["route"]
    assert r.json()["replaced"] == old["route_id"]
    assert new["route_id"] != old["route_id"] and new["status"] == "pending" and new["revision"] == 1
    assert new["leader_profile"] == "supervisor_v2" and new["external_management_ref"] == old["external_management_ref"]
    assert new["config"]["timezone"] == "Asia/Tokyo"  # config carries over unless replaced
    after = env.http.get(f"{W}/routes/{old['route_id']}", headers=ADM).json()
    assert after["status"] == "replaced" and after["revision"] == old["revision"] + 1
    assert env.post(f"{W}/routes/{old['route_id']}/replace").status_code == 409
    assert env.post(f"{W}/routes/{old['route_id']}/suspend").status_code == 409
    # the new route can take over the ref once the partner confirms it
    assert env.confirm(k["api_key"], new).status_code == 200


def test_replace_route_can_change_ref_and_config(env):
    c = env.client()
    old = env.route(c["client_id"], "OLD")
    r = env.post(f"{W}/routes/{old['route_id']}/replace",
                 {"external_management_ref": "NEW", "config": {"residence_required": True}})
    new = r.json()["route"]
    assert new["external_management_ref"] == "NEW" and new["config"]["residence_required"] is True
    assert env.post(f"{W}/routes/{old['route_id']}/replace", {"config": {"timezone": "Nope"}}).status_code in (409, 422)


# ---- integrations and provider keys ---------------------------------------------------
def test_create_integration_validates_and_stores_the_event_schema(env):
    c = env.client()
    r = env.http.post(f"{W}/clients/{c['client_id']}/integrations", headers=ADM, json={"event_schema": EVENT_SCHEMA})
    assert r.status_code == 201
    body = r.json()
    assert body["integration_id"].startswith("intg_") and body["status"] == "active"
    stored = body["event_schema"]
    assert stored["events"]["repair.completed"]["terminal"] is True and stored["events"]["repair.completed"]["wake"] is True
    assert stored["events"]["repair.assigned"]["public_fields"] == ["worker_name"]
    assert env.http.get(f"{W}/integrations/{body['integration_id']}", headers=ADM).json()["event_schema"] == stored
    assert [x["integration_id"] for x in env.http.get(f"{W}/integrations", headers=ADM).json()["integrations"]] == [
        body["integration_id"]]


def _schema(**patch_event):
    s = copy.deepcopy(EVENT_SCHEMA)
    s["events"]["repair.assigned"].update(patch_event)
    return s


def _top(**patch):
    s = copy.deepcopy(EVENT_SCHEMA)
    s.update(patch)
    return s


@pytest.mark.parametrize("schema", [
    _top(version_mode="stream"),
    _top(version=""),
    _top(events={}),
    _top(extra=1),
    _top(events={"Bad Type": {"status": "x", "rank": 1}}),
    _top(events={"a.b": {"status": "x"}}),  # rank is required
    _top(events={"a.b": {"status": "x", "rank": -1}}),
    _top(events={"a.b": {"status": "x", "rank": "high"}}),
    _top(events={"a.b": {"rank": 1}}),  # status is required
    _top(events={"a.b": {"status": "x", "rank": 1, "wake": "maybe"}}),
    _top(events={"a.b": {"status": "x", "rank": 1, "surprise": True}}),
    _schema(message="Hello {unlisted}"),  # placeholder not in public_fields
    _schema(message="Hello {worker_name.upper}"),
    _schema(message="Hello {worker_name!r}"),
    _schema(message="Hello {}"),
    _schema(public_fields=["worker_name", "worker_name"]),
    _schema(public_fields=["not an identifier"]),
])
def test_event_schema_shape_is_validated(env, schema):
    c = env.client()
    r = env.http.post(f"{W}/clients/{c['client_id']}/integrations", headers=ADM, json={"event_schema": schema})
    assert r.status_code == 422, r.text


def test_provider_key_comes_with_a_sealed_signing_key(env):
    c = env.client()
    integ = env.post(f"{W}/clients/{c['client_id']}/integrations", {"event_schema": EVENT_SCHEMA}).json()
    r = env.post(f"{W}/integrations/{integ['integration_id']}/keys")
    assert r.status_code == 201 and r.headers["cache-control"] == "no-store"
    body = r.json()
    assert body["kind"] == "provider" and body["integration_id"] == integ["integration_id"]
    assert body["client_id"] is None and body["operations"] == ["publish_job_event", "read_event_receipt"]
    sk = body["signing_key"]
    assert sk["key_id"].startswith("sk_") and len(sk["secret"]) >= 40
    (row,) = env.sql("select secret_enc, status, integration_id from wf_signing_keys where key_id = ?", (sk["key_id"],))
    assert row[0] != sk["secret"] and sk["secret"] not in row[0] and row[1:] == ("active", integ["integration_id"])
    assert Sealer(SECRET_KEY).open(row[0]) == sk["secret"]  # the platform can read it back, nobody else can
    secrets_in(env.dump(), sk["secret"], body["api_key"])

    shown = env.http.get(f"{W}/integrations/{integ['integration_id']}", headers=ADM)
    assert shown.json()["signing_keys"] == [{"key_id": sk["key_id"], "status": "active",
                                             "created_at": shown.json()["signing_keys"][0]["created_at"]}]
    listing = env.http.get(f"{W}/integrations/{integ['integration_id']}/keys", headers=ADM)
    assert [x["key_id"] for x in listing.json()["keys"]] == [body["key_id"]]
    secrets_in(shown.text + listing.text, sk["secret"], "secret_enc", "secret_hash", "api_key")


def test_provider_key_operations_are_validated(env):
    c = env.client()
    integ = env.post(f"{W}/clients/{c['client_id']}/integrations", {"event_schema": EVENT_SCHEMA}).json()
    url = f"{W}/integrations/{integ['integration_id']}/keys"
    assert env.post(url, {"operations": ["reply"]}).status_code == 422
    ok = env.post(url, {"operations": ["publish_job_event"]})
    assert ok.status_code == 201 and ok.json()["operations"] == ["publish_job_event"]


def test_signing_keys_can_be_added_and_revoked(env):
    c = env.client()
    integ = env.post(f"{W}/clients/{c['client_id']}/integrations", {"event_schema": EVENT_SCHEMA}).json()
    iid = integ["integration_id"]
    added = env.post(f"{W}/integrations/{iid}/signing-keys")
    assert added.status_code == 201
    kid = added.json()["signing_key"]["key_id"]
    assert env.post(f"{W}/integrations/{iid}/signing-keys/{kid}/revoke").json() == {"key_id": kid, "status": "revoked"}
    assert env.sql("select status from wf_signing_keys where key_id = ?", (kid,)) == [("revoked",)]
    assert env.post(f"{W}/integrations/{iid}/signing-keys/sk_nope/revoke").status_code == 404


def test_rotating_a_provider_key_keeps_it_a_provider_key(env):
    c = env.client()
    integ = env.post(f"{W}/clients/{c['client_id']}/integrations", {"event_schema": EVENT_SCHEMA}).json()
    old = env.post(f"{W}/integrations/{integ['integration_id']}/keys").json()
    new = env.post(f"{W}/keys/{old['key_id']}/rotate").json()
    assert new["kind"] == "provider" and new["integration_id"] == integ["integration_id"] and new["client_id"] is None
    assert new["operations"] == old["operations"] and "signing_key" not in new


def test_secret_key_is_required_to_store_signing_secrets(make_env):
    with make_env(secret_key="") as env:
        c = env.client()
        integ = env.post(f"{W}/clients/{c['client_id']}/integrations", {"event_schema": EVENT_SCHEMA}).json()
        r = env.post(f"{W}/integrations/{integ['integration_id']}/keys")
        assert r.status_code == 503
        assert env.sql("select count(*) from wf_keys where kind = 'provider'") == [(0,)]  # nothing half-created
        assert env.sql("select count(*) from wf_signing_keys") == [(0,)]
    with make_env(secret_key="", dev_open=True) as env:  # dev mode has a fixed development key
        c = env.client(headers={})
        integ = env.post(f"{W}/clients/{c['client_id']}/integrations", {"event_schema": EVENT_SCHEMA}, {}).json()
        assert env.post(f"{W}/integrations/{integ['integration_id']}/keys", None, {}).status_code == 201


def test_sealer_round_trip_and_refusals():
    s = Sealer(Fernet.generate_key().decode())
    token = s.seal("hmac-secret-value")
    assert token != "hmac-secret-value" and "hmac-secret-value" not in token
    assert s.open(token) == "hmac-secret-value" and s.seal("hmac-secret-value") != token  # fresh IV each time
    with pytest.raises(ValueError):
        Sealer(Fernet.generate_key().decode()).open(token)  # another key cannot open it
    off = Sealer("")
    assert not off.ready
    with pytest.raises(SecretKeyMissing):
        off.seal("x")
    with pytest.raises(SecretKeyMissing):
        off.open(token)
    dev = Sealer("", dev_open=True)
    assert dev.open(dev.seal("abc")) == "abc"
    with pytest.raises(ValueError):
        Sealer("not-a-fernet-key")  # a bad key fails at startup, not at first use


def test_a_bad_secret_key_stops_the_app_from_building(tmp_path):
    s = Settings(db_url=f"sqlite+aiosqlite:///{(tmp_path / 'a.db').as_posix()}",
                 agentscope_db_url=f"sqlite+aiosqlite:///{(tmp_path / 'b.db').as_posix()}",
                 secret_key="garbage")
    with pytest.raises(ValueError):
        build_app(s, catalog=ModelCatalog([]))


# ---- tenant isolation --------------------------------------------------------------------
def test_one_tenant_cannot_see_or_touch_anothers(env):
    c = env.client()
    k = env.key(c["client_id"])
    route = env.route(c["client_id"])
    integ = env.post(f"{W}/clients/{c['client_id']}/integrations", {"event_schema": EVENT_SCHEMA}).json()
    pk = env.post(f"{W}/integrations/{integ['integration_id']}/keys").json()
    cid, rid, iid = c["client_id"], route["route_id"], integ["integration_id"]

    b = ADM_B
    assert env.http.get(f"{W}/clients", headers=b).json() == {"clients": []}
    assert env.http.get(f"{W}/routes", headers=b).json() == {"routes": []}
    assert env.http.get(f"{W}/integrations", headers=b).json() == {"integrations": []}
    gets = [f"/clients/{cid}", f"/clients/{cid}/keys", f"/routes/{rid}", f"/integrations/{iid}",
            f"/integrations/{iid}/keys"]
    for path in gets:
        assert env.http.get(W + path, headers=b).status_code == 404, path
    posts = [(f"/clients/{cid}/keys", {"operations": ["reply"]}),
             (f"/clients/{cid}/routes", {"external_management_ref": "R", "leader_profile": "s", "manager_id": route["manager_id"]}),
             (f"/clients/{cid}/integrations", {"event_schema": EVENT_SCHEMA}),
             (f"/keys/{k['key_id']}/revoke", {}), (f"/keys/{k['key_id']}/rotate", {}),
             (f"/keys/{pk['key_id']}/revoke", {}), (f"/keys/{pk['key_id']}/rotate", {}),
             (f"/routes/{rid}/suspend", {}), (f"/routes/{rid}/replace", {}),
             (f"/integrations/{iid}/keys", {}), (f"/integrations/{iid}/signing-keys", {}),
             (f"/integrations/{iid}/signing-keys/{pk['signing_key']['key_id']}/revoke", {})]
    for path, body in posts:
        assert env.http.post(W + path, json=body, headers=b).status_code == 404, path
    # and nothing of tenant A changed
    assert env.http.get(f"{W}/routes/{rid}", headers=ADM).json()["status"] == "pending"
    assert env.http.post(f"{W}/routes/{rid}/suspend", headers=ADM).status_code == 200
    assert env.sql("select status from wf_keys where key_id in (?, ?)", (k["key_id"], pk["key_id"])) == [
        ("active",), ("active",)]


def test_nothing_secret_appears_in_any_admin_read(env):
    c = env.client()
    k = env.key(c["client_id"])
    integ = env.post(f"{W}/clients/{c['client_id']}/integrations", {"event_schema": EVENT_SCHEMA}).json()
    pk = env.post(f"{W}/integrations/{integ['integration_id']}/keys").json()
    env.route(c["client_id"])
    plains = [k["api_key"].split(".", 1)[1], pk["api_key"].split(".", 1)[1], pk["signing_key"]["secret"]]
    reads = ["/clients", f"/clients/{c['client_id']}", f"/clients/{c['client_id']}/keys", "/routes",
             "/integrations", f"/integrations/{integ['integration_id']}",
             f"/integrations/{integ['integration_id']}/keys"]
    for path in reads:
        text = env.http.get(W + path, headers=ADM).text
        secrets_in(text, *plains)
        assert not re.search(r"secret_hash|secret_enc|api_key|\"secret\"", text), path
    revoked = env.post(f"{W}/keys/{k['key_id']}/revoke").text
    secrets_in(revoked, *plains)
    assert "api_key" not in revoked
