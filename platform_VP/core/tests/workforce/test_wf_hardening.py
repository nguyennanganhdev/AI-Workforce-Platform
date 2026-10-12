"""Slice S1 review fixes: wire strictness, atomic lifecycle changes, route isolation, pre-auth checks."""
import logging
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from conftest import ADM, ALL_CUSTOMER, just_before, key_headers
from test_wf_errors import assert_envelope

W = "/platform/v1/wf"
RES = "/workforce/v1/partner/residences"
JSON = {"content-type": "application/json"}


def par(fn, n=8):
    with ThreadPoolExecutor(n) as ex:
        return [f.result() for f in [ex.submit(fn, i) for i in range(n)]]


def confirm_url(route):
    return f"/workforce/v1/partner/routes/{route['route_id']}/confirm"


def put(env, api_key, rid="S1-0205", ref="BQL-OP1-A", user="resident-123", **over):
    body = {"schema_version": "1", "external_user_id": user, "external_management_ref": ref,
            "status": "active", **over}
    return env.http.put(f"{RES}/{rid}", json=body, headers=key_headers(api_key))


def route_row(env, route_id):
    return env.http.get(f"{W}/routes/{route_id}", headers=ADM).json()


# ---- wire format ------------------------------------------------------------------
def test_deeply_nested_json_is_400_not_500(world):
    env, c, k, route = world
    r = env.http.post(confirm_url(route), content=b"[" * 200000,
                      headers={**key_headers(k["api_key"]), **JSON})
    err = assert_envelope(r, 400, "INVALID_REQUEST")
    assert err["retryable"] is False


@pytest.mark.parametrize("value", ["1", True, 1.0, None])
def test_expected_revision_must_be_an_integer(env, value):
    c = env.client()
    k = env.key(c["client_id"])
    route = env.route(c["client_id"])
    r = env.http.post(confirm_url(route), headers=key_headers(k["api_key"]), json={
        "schema_version": "1", "external_management_ref": "BQL-OP1-A", "expected_revision": value})
    assert_envelope(r, 422, "VALIDATION_FAILED")
    assert route_row(env, route["route_id"])["status"] == "pending"


@pytest.mark.parametrize("value", ["1", True, 1.0])
def test_residence_expected_revision_must_be_an_integer(world, value):
    env, c, k, _ = world
    assert put(env, k["api_key"], expected_revision=value).status_code == 422
    assert env.sql("select count(*) from wf_residences") == [(0,)]


@pytest.mark.parametrize("config", [{"wait_seconds": "5"}, {"wait_seconds": True},
                                    {"policy": {"approval_ttl_seconds": "600"}},
                                    {"policy": {"auto_close_read_only": "yes"}},
                                    {"residence_required": 1}])
def test_admin_route_config_is_typed_strictly_too(env, config):
    c = env.client()
    r = env.post(f"{W}/clients/{c['client_id']}/routes",
                 {"external_management_ref": "R", "leader_profile": env.leader(), "config": config,
                  "manager_id": env.default_manager(c["client_id"])})
    assert r.status_code == 422, r.text


def test_content_type_must_be_json(world):
    env, c, k, route = world
    good = '{"schema_version":"1","external_management_ref":"OTHER-REF","expected_revision":1}'
    h = key_headers(k["api_key"])
    pending = env.route(c["client_id"], "OTHER-REF")
    url = confirm_url(pending)
    for ct in ("text/plain", "application/x-www-form-urlencoded", "application/json; charset=latin-1", ""):
        r = env.http.post(url, content=good, headers={**h, "content-type": ct} if ct else h)
        assert_envelope(r, 400, "INVALID_REQUEST")
    assert route_row(env, pending["route_id"])["status"] == "pending"
    ok = env.http.post(url, content=good, headers={**h, "content-type": "Application/JSON; charset=UTF-8"})
    assert ok.status_code == 200, ok.text


def test_correlation_id_is_logged_and_cleaned(env, caplog):
    with caplog.at_level(logging.INFO, logger="awp.workforce"):
        r = env.http.get("/workforce/v1/nope", headers={"X-Correlation-Id": "trace-42\x07" + "x" * 300})
    line = next(m for m in caplog.messages if "correlation=trace-42" in m)
    assert "\x07" not in line and len(line) < 400
    assert r.status_code == 404


@pytest.mark.parametrize("path", ["/workforce", "/workforce/", "/workforce/v1", "/workforce/v1/",
                                  "/workforce/v2/partner/requests"])
def test_every_path_under_workforce_answers_in_the_envelope(env, path):
    r = env.http.get(path, follow_redirects=False)
    assert_envelope(r, 404, "NOT_FOUND")


def test_unauthenticated_call_is_refused_before_the_body_is_read(env):
    url = "/workforce/v1/partner/routes/x/confirm"
    big = b"a" * 300_000  # over the 256 KiB default limit
    for headers in ({"Authorization": "ApiKey nope"}, {}):
        r = env.http.post(url, content=big, headers={**headers, **JSON})
        assert_envelope(r, 401, "UNAUTHENTICATED")


# ---- parallel and interleaved requests ----------------------------------------------
def test_parallel_identical_confirms_all_succeed(env):
    c = env.client()
    k = env.key(c["client_id"])
    route = env.route(c["client_id"])
    res = par(lambda i: env.confirm(k["api_key"], route))
    assert [x.status_code for x in res] == [200] * 8, [x.text for x in res if x.status_code != 200]
    assert {x.json()["revision"] for x in res} == {2}


def test_confirm_replays_when_a_parallel_request_wins_between_read_and_write(env, monkeypatch):
    c = env.client()
    k = env.key(c["client_id"])
    route = env.route(c["client_id"])
    won = just_before(monkeypatch, env, "UPDATE wf_routes",
                      "update wf_routes set status='active', revision=2 where id=?", (route["route_id"],))
    r = env.confirm(k["api_key"], route)
    assert won and r.status_code == 200 and r.json()["revision"] == 2
    # a stale revision is still a conflict, and it names the real revision
    err = assert_envelope(env.confirm(k["api_key"], route, revision=5), 409, "REVISION_CONFLICT")
    assert err["details"] == {"current_revision": 2}


def test_the_test_kit_refuses_a_bare_database_call_from_inside_the_apps_loop(env):
    """The three tests around this one used to write from a patched function inside the app's loop; one of them failed
    with "database is locked" in a full run. The kit now refuses that every time instead of once in some dozens."""
    with pytest.raises(AssertionError, match="event loop"):
        env.http.portal.call(env.sql, "select 1")
    assert env.sql("select 1") == [(1,)]  # from the test's own thread, as always


def test_parallel_identical_residence_create_is_one_201_and_the_rest_200(world):
    env, c, k, _ = world
    res = par(lambda i: put(env, k["api_key"]))
    assert sorted(x.status_code for x in res) == [200] * 7 + [201]
    assert {x.json()["revision"] for x in res} == {1}
    assert env.sql("select count(*) from wf_residences") == [(1,)]


def test_residence_create_that_loses_the_race_is_judged_on_the_committed_row(world, monkeypatch):
    env, c, k, route = world
    won = just_before(
        monkeypatch, env, "INSERT INTO wf_residences",
        "insert into wf_residences (client_id, residence_id, route_id, external_user_id, status, revision, updated_at)"
        " values (?,?,?,?,?,?,?)", (c["client_id"], "S1-0205", route["route_id"], "resident-123", "active", 1, time.time()))
    r = put(env, k["api_key"])
    assert won and r.status_code == 200 and r.json()["revision"] == 1  # the same content: idempotent
    monkeypatch.undo()
    err = assert_envelope(put(env, k["api_key"], status="inactive"), 409, "REVISION_CONFLICT")
    assert err["details"] == {"current_revision": 1}


def test_parallel_rotate_leaves_exactly_one_live_successor(env):
    c = env.client()
    k = env.key(c["client_id"])
    res = par(lambda i: env.post(f"{W}/keys/{k['key_id']}/rotate"))
    assert sorted(x.status_code for x in res) == [201] + [409] * 7
    assert env.sql("select count(*) from wf_keys where status='active' and client_id=?",
                   (c["client_id"],)) == [(1,)]


def test_rotate_does_not_resurrect_a_key_revoked_after_it_was_read(env, monkeypatch):
    c = env.client()
    k = env.key(c["client_id"], expires_at="2099-01-01T00:00:00Z")
    # rotate has read the key as active and is about to retire it
    revoked = just_before(monkeypatch, env, "UPDATE wf_keys",
                          "update wf_keys set status='revoked', revoked_at=1 where key_id=?", (k["key_id"],))
    r = env.post(f"{W}/keys/{k['key_id']}/rotate")
    assert revoked and r.status_code == 409, r.text
    assert env.sql("select count(*) from wf_keys where status='active' and client_id=?",
                   (c["client_id"],)) == [(0,)]


def test_parallel_replace_creates_one_pending_route(env):
    c = env.client()
    k = env.key(c["client_id"])
    r = env.active_route(c["client_id"], k["api_key"])
    res = par(lambda i: env.post(f"{W}/routes/{r['route_id']}/replace"), 4)
    assert sorted(x.status_code for x in res) == [201, 409, 409, 409]
    assert env.sql("select count(*) from wf_routes where status='pending' and client_id=?",
                   (c["client_id"],)) == [(1,)]
    assert route_row(env, r["route_id"])["revision"] == 3  # confirmed once (2), replaced once (3)


def test_suspend_racing_replace_never_undoes_the_replacement(env):
    c = env.client()
    k = env.key(c["client_id"])
    for i in range(5):
        r = env.active_route(c["client_id"], k["api_key"], ref=f"R{i}")
        with ThreadPoolExecutor(2) as ex:
            a = ex.submit(lambda: env.post(f"{W}/routes/{r['route_id']}/replace"))
            b = ex.submit(lambda: env.post(f"{W}/routes/{r['route_id']}/suspend"))
            ra, rb = a.result(), b.result()
        assert ra.status_code == 201 and rb.status_code in (200, 409)
        status, revision = env.sql("select status, revision from wf_routes where id=?", (r["route_id"],))[0]
        assert status == "replaced"
        assert revision == 3 + (rb.status_code == 200)  # one bump per transition that happened


def test_suspend_twice_is_idempotent_and_does_not_bump_again(env):
    c = env.client()
    k = env.key(c["client_id"])
    r = env.active_route(c["client_id"], k["api_key"])
    first = env.post(f"{W}/routes/{r['route_id']}/suspend").json()
    again = env.post(f"{W}/routes/{r['route_id']}/suspend").json()
    assert first["status"] == "suspended" and again == first and first["revision"] == 3
    env.post(f"{W}/routes/{r['route_id']}/replace")
    assert env.post(f"{W}/routes/{r['route_id']}/suspend").status_code == 409


# ---- route isolation of residences -------------------------------------------------
def two_routes(env):
    c = env.client()
    full = env.key(c["client_id"])
    ra = env.active_route(c["client_id"], full["api_key"], ref="REF-A")
    rb = env.active_route(c["client_id"], full["api_key"], ref="REF-B")
    assert put(env, full["api_key"], "S1-1", "REF-B").status_code == 201  # lives on route B
    only_a = env.key(c["client_id"], operations=ALL_CUSTOMER, routes=[ra["route_id"]])
    return c, full, only_a, ra, rb


def test_route_scoped_key_cannot_read_or_move_a_residence_of_another_route(env):
    c, full, only_a, ra, rb = two_routes(env)
    r = put(env, only_a["api_key"], "S1-1", "REF-A")
    err = assert_envelope(r, 403, "ROUTE_NOT_AUTHORIZED")
    assert err["details"] == {} and "current_revision" not in r.text
    assert put(env, only_a["api_key"], "S1-1", "REF-A", expected_revision=1).status_code == 403
    assert env.sql("select route_id, revision from wf_residences where residence_id='S1-1'") == [
        (rb["route_id"], 1)]
    # the key that covers both routes may still move it
    assert put(env, full["api_key"], "S1-1", "REF-A", expected_revision=1).status_code == 200


def test_a_key_cannot_tell_whether_a_ref_it_does_not_cover_is_active(env):
    c, full, only_a, ra, rb = two_routes(env)
    pending = env.route(c["client_id"], "REF-P")
    bodies = {}
    for ref in ("REF-B", "REF-P", "REF-NONE"):  # active but uncovered, pending, unknown
        err = assert_envelope(put(env, only_a["api_key"], "S1-9", ref), 403, "ROUTE_NOT_AUTHORIZED")
        bodies[ref] = {k: v for k, v in err.items() if k != "request_id"}
    assert bodies["REF-B"] == bodies["REF-P"] == bodies["REF-NONE"]
    # a key that covers the pending route is told why
    covers = env.key(c["client_id"], operations=ALL_CUSTOMER, routes=[pending["route_id"]])
    err = assert_envelope(put(env, covers["api_key"], "S1-9", "REF-P"), 403, "ROUTE_NOT_AUTHORIZED")
    assert err["details"] == {"reason": "route_not_active"}


def test_several_residents_may_share_a_residence(world):
    """A2: the key is client + residence + user, so a second user on a residence is a new row."""
    env, c, k, _ = world
    assert put(env, k["api_key"], user="resident-123").status_code == 201
    r = put(env, k["api_key"], user="resident-999")
    assert r.status_code == 201 and r.json()["revision"] == 1
