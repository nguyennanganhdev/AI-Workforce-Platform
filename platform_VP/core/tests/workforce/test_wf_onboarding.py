"""Contract 8: confirm a route, sync a residence."""
import re

import pytest

import dbtest

from conftest import ADM, ALL_CUSTOMER, key_headers
from test_wf_errors import assert_envelope

W = "/platform/v1/wf"
RUNTIME = ["submit_request", "reply", "read_result", "receive_events", "submit_consent", "close_workflow"]


def confirm_url(route):
    return f"/workforce/v1/partner/routes/{route['route_id']}/confirm"


def body(route, **over):
    return {"schema_version": "1", "external_management_ref": route["external_management_ref"],
            "expected_revision": route["revision"], **over}


# ---- confirm route -------------------------------------------------------------
def test_confirm_activates_a_pending_route(env):
    c = env.client()
    k = env.key(c["client_id"])
    route = env.route(c["client_id"])
    r = env.http.post(confirm_url(route), json=body(route), headers=key_headers(k["api_key"]))
    assert r.status_code == 200
    assert r.json() == {"route_id": route["route_id"], "external_management_ref": "BQL-OP1-A",
                        "status": "active", "revision": 2, "allowed_operations": RUNTIME}
    # nothing internal leaks: no domain, tenant, client, profile
    assert set(r.json()) == {"route_id", "external_management_ref", "status", "revision", "allowed_operations"}
    assert env.http.get(f"{W}/routes/{route['route_id']}", headers=ADM).json()["status"] == "active"


def test_allowed_operations_is_the_keys_operations_the_route_allows(env):
    c = env.client()
    k = env.key(c["client_id"], operations=["confirm_route", "close_workflow", "reply", "sync_residence"])
    route = env.route(c["client_id"])
    r = env.confirm(k["api_key"], route)
    assert r.json()["allowed_operations"] == ["reply", "close_workflow"]  # onboarding ops are not runtime ops


def test_confirm_is_idempotent_for_the_same_inputs(env):
    c = env.client()
    k = env.key(c["client_id"])
    route = env.route(c["client_id"])
    first = env.confirm(k["api_key"], route)
    again = env.confirm(k["api_key"], route)
    assert again.status_code == 200 and again.json() == first.json() and again.json()["revision"] == 2
    assert env.sql("select revision from wf_routes where id = ?", (route["route_id"],)) == [(2,)]


def test_confirm_with_a_stale_or_wrong_revision_is_409(env):
    c = env.client()
    k = env.key(c["client_id"])
    route = env.route(c["client_id"])
    for wrong in (0, 2, 7):
        err = assert_envelope(env.confirm(k["api_key"], route, revision=wrong), 409, "REVISION_CONFLICT")
        assert err["details"] == {"current_revision": 1}
    assert env.sql("select status from wf_routes where id = ?", (route["route_id"],)) == [("pending",)]
    assert env.confirm(k["api_key"], route).status_code == 200
    # once active, only the confirmation that produced the revision is a replay
    assert_envelope(env.confirm(k["api_key"], route, revision=2), 409, "REVISION_CONFLICT")
    assert_envelope(env.confirm(k["api_key"], route, revision=0), 409, "REVISION_CONFLICT")


def test_another_client_cannot_confirm_the_route(env):
    owner, other = env.client(), env.client(domain="other")
    ko = env.key(other["client_id"])
    route = env.route(owner["client_id"])
    err = assert_envelope(env.confirm(ko["api_key"], route), 403, "ROUTE_NOT_AUTHORIZED")
    assert err["details"] == {}
    assert env.sql("select status from wf_routes where id = ?", (route["route_id"],)) == [("pending",)]
    # a route that does not exist answers the same way, so ids cannot be probed
    ghost = {**route, "route_id": "route_" + "0" * 32}
    err2 = assert_envelope(env.confirm(ko["api_key"], ghost), 403, "ROUTE_NOT_AUTHORIZED")
    assert err2["message"] == err["message"]


def test_confirm_needs_the_confirm_route_operation(env):
    c = env.client()
    k = env.key(c["client_id"], operations=["reply", "sync_residence"])
    route = env.route(c["client_id"])
    err = assert_envelope(env.confirm(k["api_key"], route), 403, "PERMISSION_DENIED")
    assert err["details"] == {"operation": "confirm_route"}


def test_confirm_with_a_different_ref_is_a_route_conflict(env):
    c = env.client()
    k = env.key(c["client_id"])
    route = env.route(c["client_id"])
    err = assert_envelope(env.confirm(k["api_key"], route, ref="BQL-OTHER"), 409, "ROUTE_CONFLICT")
    assert err["details"] == {"reason": "ref_mismatch"}
    assert env.sql("select status from wf_routes where id = ?", (route["route_id"],)) == [("pending",)]


def test_confirm_conflicts_with_another_active_route_of_the_same_ref(env):
    c = env.client()
    k = env.key(c["client_id"])
    first = env.route(c["client_id"], "SAME")
    second = env.route(c["client_id"], "SAME")
    assert env.confirm(k["api_key"], first).status_code == 200
    assert_envelope(env.confirm(k["api_key"], second), 409, "ROUTE_CONFLICT")
    assert env.sql("select status from wf_routes where id = ?", (second["route_id"],)) == [("pending",)]
    # a different client may use the same ref
    other = env.client(domain="other")
    ko = env.key(other["client_id"])
    assert env.confirm(ko["api_key"], env.route(other["client_id"], "SAME")).status_code == 200


def test_the_database_itself_refuses_two_active_routes_with_one_ref(env):
    c = env.client()
    k = env.key(c["client_id"])
    first = env.route(c["client_id"], "SAME")
    second = env.route(c["client_id"], "SAME")
    env.confirm(k["api_key"], first)
    with pytest.raises(dbtest.IntegrityError):
        env.sql("update wf_routes set status = 'active' where id = ?", (second["route_id"],))


def test_suspended_and_replaced_routes_cannot_be_confirmed(env):
    c = env.client()
    k = env.key(c["client_id"])
    a, b = env.route(c["client_id"], "A"), env.route(c["client_id"], "B")
    env.post(f"{W}/routes/{a['route_id']}/suspend")
    env.post(f"{W}/routes/{b['route_id']}/replace")
    for route, status in ((a, "suspended"), (b, "replaced")):
        err = assert_envelope(env.confirm(k["api_key"], route, revision=2), 409, "ROUTE_CONFLICT")
        assert err["details"] == {"status": status}


def test_confirm_after_replacement_takes_over_the_ref(env):
    c = env.client()
    k = env.key(c["client_id"])
    old = env.active_route(c["client_id"], k["api_key"], "REF")
    new = env.post(f"{W}/routes/{old['route_id']}/replace").json()["route"]
    assert env.confirm(k["api_key"], new).status_code == 200
    states = dict(env.sql("select id, status from wf_routes"))
    assert states[old["route_id"]] == "replaced" and states[new["route_id"]] == "active"


# ---- residences --------------------------------------------------------------------
def put(env, api_key, residence_id="S1-0205", route=None, user="resident-123", **over):
    payload = {"schema_version": "1", "external_user_id": user, "external_management_ref": "BQL-OP1-A",
               "status": "active", **over}
    if route is not None:
        payload["external_management_ref"] = route["external_management_ref"]
    return env.http.put(f"/workforce/v1/partner/residences/{residence_id}", json=payload,
                        headers=key_headers(api_key))


def test_residence_create_is_201_revision_1(world):
    env, c, k, route = world
    r = put(env, k["api_key"])
    assert r.status_code == 201
    out = r.json()
    assert out == {"residence_id": "S1-0205", "external_user_id": "resident-123",
                   "external_management_ref": "BQL-OP1-A", "status": "active", "revision": 1,
                   "updated_at": out["updated_at"]}
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", out["updated_at"])
    assert env.sql("select route_id, revision from wf_residences") == [(route["route_id"], 1)]


def test_residence_expected_revision_zero_also_creates(world):
    env, _, k, _ = world
    r = put(env, k["api_key"], expected_revision=0)
    assert r.status_code == 201 and r.json()["revision"] == 1


def test_residence_same_content_is_idempotent(world):
    env, _, k, _ = world
    first = put(env, k["api_key"])
    for extra in ({}, {"expected_revision": 1}, {"expected_revision": 0}, {"expected_revision": 9}):
        again = put(env, k["api_key"], **extra)
        assert again.status_code == 200, extra
        assert again.json() == {**first.json()}  # same revision, same updated_at
    assert env.sql("select revision from wf_residences") == [(1,)]


def test_residence_update_needs_the_current_revision(world):
    env, _, k, _ = world
    put(env, k["api_key"])
    ok = put(env, k["api_key"], status="inactive", expected_revision=1)
    assert ok.status_code == 200 and ok.json()["revision"] == 2 and ok.json()["status"] == "inactive"
    # a retry of the update that already succeeded changes nothing
    retry = put(env, k["api_key"], status="inactive", expected_revision=1)
    assert retry.status_code == 200 and retry.json()["revision"] == 2
    for attempt in ({}, {"expected_revision": 0}, {"expected_revision": 1}, {"expected_revision": 5}):
        err = assert_envelope(put(env, k["api_key"], status="active", **attempt), 409, "REVISION_CONFLICT")
        assert err["details"] == {"current_revision": 2}
    assert put(env, k["api_key"], status="active", expected_revision=2).json()["revision"] == 3


def test_residence_expected_revision_on_a_new_residence_is_a_conflict(world):
    env, _, k, _ = world
    err = assert_envelope(put(env, k["api_key"], expected_revision=3), 409, "REVISION_CONFLICT")
    assert err["details"] == {"current_revision": 0}
    assert env.sql("select count(*) from wf_residences") == [(0,)]


def test_residence_key_is_client_residence_and_user(world):
    env, c, k, _ = world
    assert put(env, k["api_key"], user="resident-1").status_code == 201
    assert put(env, k["api_key"], user="resident-2").status_code == 201  # same flat, another resident
    assert put(env, k["api_key"], residence_id="S1-0206", user="resident-1").status_code == 201
    assert env.sql("select count(*) from wf_residences") == [(3,)]
    # another client has its own namespace
    other = env.client(domain="o")
    ko = env.key(other["client_id"])
    env.active_route(other["client_id"], ko["api_key"])
    assert put(env, ko["api_key"], user="resident-1").status_code == 201
    assert env.sql("select count(*) from wf_residences") == [(4,)]


def test_residence_refused_for_unknown_foreign_or_inactive_routes(env):
    c = env.client()
    k = env.key(c["client_id"])
    pending = env.route(c["client_id"], "PENDING-REF")
    err = assert_envelope(put(env, k["api_key"], route=pending), 403, "ROUTE_NOT_AUTHORIZED")
    assert err["details"] == {"reason": "route_not_active"}
    err = assert_envelope(put(env, k["api_key"], external_management_ref="NO-SUCH-REF"), 403, "ROUTE_NOT_AUTHORIZED")
    assert err["details"] == {}

    other = env.client(domain="o")
    ko = env.key(other["client_id"])
    env.active_route(other["client_id"], ko["api_key"], "THEIRS")
    err = assert_envelope(put(env, k["api_key"], external_management_ref="THEIRS"), 403, "ROUTE_NOT_AUTHORIZED")
    assert err["details"] == {}  # the other client's route looks like one that does not exist

    # suspended after being active
    live = env.active_route(c["client_id"], k["api_key"], "LIVE")
    assert put(env, k["api_key"], external_management_ref="LIVE").status_code == 201
    env.post(f"{W}/routes/{live['route_id']}/suspend")
    err = assert_envelope(put(env, k["api_key"], external_management_ref="LIVE", user="u2"), 403, "ROUTE_NOT_AUTHORIZED")
    assert err["details"] == {"reason": "route_not_active"}
    assert env.sql("select count(*) from wf_residences") == [(1,)]


def test_residence_respects_the_keys_route_scope(env):
    c = env.client()
    k_all = env.key(c["client_id"])
    a = env.active_route(c["client_id"], k_all["api_key"], "A")
    b = env.active_route(c["client_id"], k_all["api_key"], "B")
    scoped = env.key(c["client_id"], routes=[a["route_id"]])
    assert put(env, scoped["api_key"], external_management_ref="A").status_code == 201
    assert_envelope(put(env, scoped["api_key"], external_management_ref="B", user="u2"), 403, "ROUTE_NOT_AUTHORIZED")


def test_residence_moves_to_another_route_with_a_revision_bump(env):
    c = env.client()
    k = env.key(c["client_id"])
    a = env.active_route(c["client_id"], k["api_key"], "A")
    b = env.active_route(c["client_id"], k["api_key"], "B")
    assert put(env, k["api_key"], external_management_ref="A").json()["revision"] == 1
    assert_envelope(put(env, k["api_key"], external_management_ref="B"), 409, "REVISION_CONFLICT")
    moved = put(env, k["api_key"], external_management_ref="B", expected_revision=1)
    assert moved.status_code == 200 and moved.json()["revision"] == 2
    assert moved.json()["external_management_ref"] == "B"
    assert env.sql("select route_id from wf_residences") == [(b["route_id"],)]


def test_residence_needs_the_sync_residence_operation(env):
    c = env.client()
    k = env.key(c["client_id"], operations=["reply", "confirm_route"])
    err = assert_envelope(put(env, k["api_key"]), 403, "PERMISSION_DENIED")
    assert err["details"] == {"operation": "sync_residence"}


@pytest.mark.parametrize("over", [
    {"external_user_id": ""},
    {"external_user_id": "u" * 201},
    {"external_user_id": "bad\nuser"},
    {"external_management_ref": ""},
    {"external_management_ref": "r" * 129},
    {"status": "deleted"},
    {"schema_version": "9"},
    {"expected_revision": -1},
    {"expected_revision": 1.5},
    {"group_id": "internal"},
])
def test_residence_body_is_validated(world, over):
    env, _, k, _ = world
    payload = {"schema_version": "1", "external_user_id": "u", "external_management_ref": "BQL-OP1-A",
               "status": "active", **over}
    r = env.http.put("/workforce/v1/partner/residences/S1", json=payload, headers=key_headers(k["api_key"]))
    assert_envelope(r, 422, "VALIDATION_FAILED")


@pytest.mark.parametrize("rid", ["x" * 201, "bad%00id", "tab%09id"])
def test_residence_id_is_validated(world, rid):
    env, _, k, _ = world
    err = assert_envelope(put(env, k["api_key"], residence_id=rid), 422, "VALIDATION_FAILED")
    assert err["details"]["errors"][0]["field"] == "residence_id"


def test_residence_put_requires_json_object(world):
    env, _, k, _ = world
    r = env.http.put("/workforce/v1/partner/residences/S1", content=b"nope", headers=key_headers(k["api_key"]))
    assert_envelope(r, 400, "INVALID_REQUEST")
