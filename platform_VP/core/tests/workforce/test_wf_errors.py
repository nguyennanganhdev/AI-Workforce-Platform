"""Public error model (contract 6.3): envelope, status codes, body limit, the admin API handlers untouched."""
import asyncio
from types import SimpleNamespace

import pytest
from starlette.requests import Request

from awp.workforce import errors
from awp.workforce.errors import WorkforceError, load_body
from conftest import ADM, OLD_SVC, key_headers

ENVELOPE = {"code", "message", "details", "request_id", "retryable"}


def assert_envelope(r, status, code):
    assert r.status_code == status, r.text
    body = r.json()
    assert set(body) == {"error"} and set(body["error"]) == ENVELOPE
    err = body["error"]
    assert err["code"] == code and isinstance(err["message"], str) and isinstance(err["details"], dict)
    assert err["request_id"].startswith("req_") and isinstance(err["retryable"], bool)
    return err


@pytest.fixture
def ready(env):
    c = env.client()
    k = env.key(c["client_id"])
    route = env.route(c["client_id"])
    url = f"/workforce/v1/partner/routes/{route['route_id']}/confirm"
    return env, k, route, url, key_headers(k["api_key"])


def test_error_envelope_and_unique_request_ids(env):
    a = assert_envelope(env.http.get("/workforce/v1/partner/residences/x"), 404, "NOT_FOUND")
    r1 = env.http.post("/workforce/v1/partner/routes/r/confirm", json={})
    e1 = assert_envelope(r1, 401, "UNAUTHENTICATED")
    e2 = assert_envelope(env.http.post("/workforce/v1/partner/routes/r/confirm", json={}), 401, "UNAUTHENTICATED")
    assert len({a["request_id"], e1["request_id"], e2["request_id"]}) == 3


def test_unknown_path_under_workforce_uses_the_envelope(env):
    for method in ("get", "post", "put", "delete"):
        r = getattr(env.http, method)("/workforce/v1/does/not/exist")
        assert_envelope(r, 404, "NOT_FOUND")


def test_bad_json_is_400_invalid_request(ready):
    env, _, _, url, h = ready
    r = env.http.post(url, content=b"{not json", headers={**h, "content-type": "application/json"})
    assert_envelope(r, 400, "INVALID_REQUEST")
    r = env.http.post(url, content=b"\xff\xfe", headers=h)
    assert_envelope(r, 400, "INVALID_REQUEST")
    r = env.http.post(url, content=b"[1, 2]", headers=h)
    assert_envelope(r, 400, "INVALID_REQUEST")
    r = env.http.post(url, content=b"", headers=h)
    assert_envelope(r, 400, "INVALID_REQUEST")


def test_schema_and_value_errors_are_422_validation_failed(ready):
    env, _, route, url, h = ready
    good = {"schema_version": "1", "external_management_ref": "BQL-OP1-A", "expected_revision": 1}
    cases = [
        {k: v for k, v in good.items() if k != "expected_revision"},  # missing field
        {**good, "schema_version": "2"},  # wrong value
        {**good, "expected_revision": -1},
        {**good, "expected_revision": "one"},
        {**good, "external_management_ref": ""},
        {**good, "external_management_ref": "x" * 129},
        {**good, "external_management_ref": "bad\x00ref"},  # control character
        {**good, "route_id": "route_x"},  # fields outside the contract are refused
    ]
    for body in cases:
        err = assert_envelope(env.http.post(url, json=body, headers=h), 422, "VALIDATION_FAILED")
        assert err["details"]["errors"]
    # the submitted value is never echoed back
    err = assert_envelope(env.http.post(url, json={**good, "route_id": "SECRET-VALUE-123"}, headers=h),
                          422, "VALIDATION_FAILED")
    assert "SECRET-VALUE-123" not in str(err)


def test_auth_comes_before_body_errors(ready):
    env, _, _, url, _ = ready
    r = env.http.post(url, content=b"{not json")
    assert_envelope(r, 401, "UNAUTHENTICATED")


def test_declared_oversize_body_is_413(make_env):
    with make_env(wf_body_limit=1000) as env:
        c = env.client()
        k = env.key(c["client_id"])
        url = "/workforce/v1/partner/routes/r1/confirm"
        h = key_headers(k["api_key"])
        r = env.http.post(url, content=b'{"x": "' + b"a" * 2000 + b'"}', headers=h)
        err = assert_envelope(r, 413, "PAYLOAD_TOO_LARGE")
        assert err["details"]["limit_bytes"] == 1000 and err["retryable"] is False
        # at the limit it reaches the handler (and fails there on its own terms)
        r = env.http.post(url, content=b"{" + b" " * 997 + b"}",
                          headers={**h, "content-type": "application/json"})
        assert r.status_code == 422


def test_undeclared_oversize_body_is_413(make_env):
    with make_env(wf_body_limit=1000) as env:
        c = env.client()
        k = env.key(c["client_id"])

        def chunks():  # no Content-Length: sent chunked
            for _ in range(5):
                yield b"a" * 400

        r = env.http.post("/workforce/v1/partner/routes/r1/confirm", content=chunks(),
                          headers=key_headers(k["api_key"]))
        assert_envelope(r, 413, "PAYLOAD_TOO_LARGE")


def test_body_limit_is_enforced_while_reading_not_after():
    pulled = []
    chunks = [b"x" * 400 for _ in range(10)]

    async def receive():
        if not chunks:
            return {"type": "http.disconnect"}
        pulled.append(1)
        return {"type": "http.request", "body": chunks.pop(), "more_body": bool(chunks)}

    app = SimpleNamespace(state=SimpleNamespace(wf=SimpleNamespace(settings=SimpleNamespace(wf_body_limit=1000))))
    req = Request({"type": "http", "method": "POST", "headers": [], "app": app}, receive)
    with pytest.raises(WorkforceError) as e:
        asyncio.run(load_body(req))
    assert e.value.http == 413
    assert len(pulled) == 3  # stopped at the first chunk that crossed the limit, 7 never read


def test_unexpected_failure_is_500_without_leaking(ready, monkeypatch):
    env, _, _, url, h = ready

    async def boom(*a, **k):
        raise RuntimeError("database password is hunter2")

    monkeypatch.setattr("awp.workforce.auth.authenticate", boom)
    r = env.http.post(url, json={}, headers=h)
    err = assert_envelope(r, 500, "INTERNAL_ERROR")
    assert err["retryable"] is True and "hunter2" not in r.text


def test_workforce_error_serialises_headers_and_details():
    e = WorkforceError("RATE_LIMITED", 429, "slow down", {"a": 1}, retryable=True, headers={"Retry-After": "3"})
    r = e.response("req_1")
    assert r.status_code == 429 and r.headers["retry-after"] == "3"
    assert errors.json.loads(r.body)["error"] == {"code": "RATE_LIMITED", "message": "slow down",
                                                  "details": {"a": 1}, "request_id": "req_1", "retryable": True}


# ---- the admin API keeps its own error shapes --------------------------------
def test_admin_errors_keep_the_admin_shape(env):
    r = env.http.get("/platform/v1/cases/nope", headers=ADM)
    assert r.status_code == 404 and r.json() == {"detail": "no such case"}
    r = env.http.post("/platform/v1/profiles", json={"nonsense": 1}, headers=ADM)
    assert r.status_code == 422
    detail = r.json()["detail"]  # FastAPI default: a list of {type, loc, msg, input}
    assert isinstance(detail, list) and {"type", "loc", "msg"} <= set(detail[0])
    assert env.http.get("/platform/v1/cases").status_code == 401
    assert env.http.get("/platform/v1/cases").json() == {"detail": "missing or unknown key"}
    r = env.http.get("/platform/v1/cases", headers=OLD_SVC)  # a connector key is simply unknown now
    assert r.status_code == 401 and r.json() == {"detail": "missing or unknown key"}


def test_admin_wf_errors_use_the_admin_api_shape(env):
    r = env.http.get("/platform/v1/wf/clients/missing", headers=ADM)
    assert r.status_code == 404 and r.json() == {"detail": "no such client"}
    r = env.http.post("/platform/v1/wf/clients", json={"name": ""}, headers=ADM)
    assert r.status_code == 422 and isinstance(r.json()["detail"], list)
