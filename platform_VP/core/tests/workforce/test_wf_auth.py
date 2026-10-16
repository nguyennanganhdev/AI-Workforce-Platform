"""ApiKey auth: lifecycle, kinds, operations, route scope, hash-only storage, rate limit."""
import re
import time

import pytest
from fastapi import Depends

import awp.workforce as wf
from awp.workforce import crypto
from awp.workforce.auth import RateLimiter, require
from conftest import ADM, ALL_CUSTOMER, EVENT_SCHEMA, OLD_SVC, build, key_headers
from test_wf_errors import assert_envelope


@pytest.fixture
def probe(tmp_path, monkeypatch):
    """An app with one customer and one provider probe endpoint, to test auth on its own."""
    real = wf.build_onboarding

    def wired(r, ctx):
        real(r, ctx)

        @r.get("/_probe/customer")
        async def customer(p=Depends(require("close_workflow"))):
            return {"client_id": p.client.id, "operations": sorted(p.operations), "routes": list(p.routes),
                    "tenant": p.client.tenant, "domain": p.client.domain}

        @r.post("/_probe/provider")
        async def provider(p=Depends(require("publish_job_event", "provider"))):
            return {"integration_id": p.integration_id, "client_id": p.client.id}

    monkeypatch.setattr(wf, "build_onboarding", wired)
    with build(tmp_path) as env:
        yield env


CUSTOMER = "/workforce/v1/_probe/customer"
PROVIDER = "/workforce/v1/_probe/provider"


def test_valid_key_authenticates_and_carries_scope(probe):
    c = probe.client(domain="travel", env="production")
    k = probe.key(c["client_id"], operations=["close_workflow", "reply"])
    r = probe.http.get(CUSTOMER, headers=key_headers(k["api_key"]))
    assert r.status_code == 200
    assert r.json() == {"client_id": c["client_id"], "operations": ["close_workflow", "reply"],
                        "routes": ["*"], "tenant": "ta", "domain": "travel"}


@pytest.mark.parametrize("header", [
    None, "", "ApiKey", "ApiKey nonsense", "ApiKey dp_.", "Bearer dp_abcdef.0123456789abcdef0123",
    "ApiKey abcdef.0123456789abcdef0123", "Basic dXNlcjpwYXNz", "ApiKey dp_abcdef0123.short"])
def test_missing_or_malformed_credentials_are_401(probe, header):
    h = {"Authorization": header} if header is not None else {}
    assert_envelope(probe.http.get(CUSTOMER, headers=h), 401, "UNAUTHENTICATED")


def test_unknown_key_id_and_wrong_secret_are_401_alike(probe):
    c = probe.client()
    k = probe.key(c["client_id"])
    key_id = k["key_id"]
    wrong_secret = key_headers(f"dp_{key_id}.{'A' * 43}")
    unknown_id = key_headers(f"dp_{'0' * 16}.{'A' * 43}")
    a = assert_envelope(probe.http.get(CUSTOMER, headers=wrong_secret), 401, "UNAUTHENTICATED")
    b = assert_envelope(probe.http.get(CUSTOMER, headers=unknown_id), 401, "UNAUTHENTICATED")
    assert a["message"] == b["message"] and a["details"] == b["details"] == {}  # nothing to tell them apart


def test_revoked_key_is_401(probe):
    c = probe.client()
    k = probe.key(c["client_id"])
    h = key_headers(k["api_key"])
    assert probe.http.get(CUSTOMER, headers=h).status_code == 200
    assert probe.post(f"/platform/v1/wf/keys/{k['key_id']}/revoke").status_code == 200
    err = assert_envelope(probe.http.get(CUSTOMER, headers=h), 401, "UNAUTHENTICATED")
    assert err["details"] == {"reason": "revoked"}


def test_expired_key_is_401(probe):
    c = probe.client()
    k = probe.key(c["client_id"], expires_at="2999-01-01T00:00:00Z")
    h = key_headers(k["api_key"])
    assert probe.http.get(CUSTOMER, headers=h).status_code == 200
    probe.sql("update wf_keys set expires_at = ? where key_id = ?", (time.time() - 5, k["key_id"]))
    err = assert_envelope(probe.http.get(CUSTOMER, headers=h), 401, "UNAUTHENTICATED")
    assert err["details"] == {"reason": "expired"}


def test_key_of_a_disabled_client_is_401(probe):
    c = probe.client()
    k = probe.key(c["client_id"])
    probe.sql("update wf_clients set status = 'suspended' where id = ?", (c["client_id"],))
    assert_envelope(probe.http.get(CUSTOMER, headers=key_headers(k["api_key"])), 401, "UNAUTHENTICATED")


def test_missing_operation_is_403(probe):
    c = probe.client()
    k = probe.key(c["client_id"], operations=["reply"])
    err = assert_envelope(probe.http.get(CUSTOMER, headers=key_headers(k["api_key"])), 403, "PERMISSION_DENIED")
    assert err["details"] == {"operation": "close_workflow"}


def test_customer_and_provider_keys_do_not_cross(probe):
    c = probe.client()
    customer = probe.key(c["client_id"], operations=ALL_CUSTOMER)
    integ = probe.post(f"/platform/v1/wf/clients/{c['client_id']}/integrations", {"event_schema": EVENT_SCHEMA}).json()
    provider = probe.post(f"/platform/v1/wf/integrations/{integ['integration_id']}/keys").json()

    ok = probe.http.post(PROVIDER, headers=key_headers(provider["api_key"]))
    assert ok.status_code == 200
    assert ok.json() == {"integration_id": integ["integration_id"], "client_id": c["client_id"]}

    err = assert_envelope(probe.http.post(PROVIDER, headers=key_headers(customer["api_key"])), 403, "PERMISSION_DENIED")
    assert err["details"] == {"reason": "wrong_credential_kind"}
    err = assert_envelope(probe.http.get(CUSTOMER, headers=key_headers(provider["api_key"])), 403, "PERMISSION_DENIED")
    assert err["details"] == {"reason": "wrong_credential_kind"}


def test_provider_key_of_a_disabled_integration_is_401(probe):
    c = probe.client()
    integ = probe.post(f"/platform/v1/wf/clients/{c['client_id']}/integrations", {"event_schema": EVENT_SCHEMA}).json()
    provider = probe.post(f"/platform/v1/wf/integrations/{integ['integration_id']}/keys").json()
    probe.sql("update wf_integrations set status = 'disabled' where id = ?", (integ["integration_id"],))
    assert_envelope(probe.http.post(PROVIDER, headers=key_headers(provider["api_key"])), 401, "UNAUTHENTICATED")


def test_route_scope_of_a_key(probe):
    c = probe.client()
    r1, r2 = probe.route(c["client_id"], "A"), probe.route(c["client_id"], "B")
    k = probe.key(c["client_id"], routes=[r1["route_id"]])
    assert probe.confirm(k["api_key"], r2).status_code == 403
    err = assert_envelope(probe.confirm(k["api_key"], r2), 403, "ROUTE_NOT_AUTHORIZED")
    assert err["details"] == {}
    assert probe.confirm(k["api_key"], r1).status_code == 200
    scoped = probe.http.get(CUSTOMER, headers=key_headers(k["api_key"])).json()
    assert scoped["routes"] == [r1["route_id"]]


def test_secret_is_stored_only_as_a_sha256_hash(probe):
    c = probe.client()
    k = probe.key(c["client_id"])
    secret = k["api_key"].split(".", 1)[1]
    assert re.fullmatch(r"dp_[0-9a-f]{16}\.[A-Za-z0-9_-]{43}", k["api_key"])
    integ = probe.post(f"/platform/v1/wf/clients/{c['client_id']}/integrations", {"event_schema": EVENT_SCHEMA}).json()
    prov = probe.post(f"/platform/v1/wf/integrations/{integ['integration_id']}/keys").json()
    dump = probe.dump()
    for plain in (secret, k["api_key"], prov["api_key"].split(".", 1)[1], prov["api_key"], prov["signing_key"]["secret"]):
        assert plain not in dump
    (row,) = probe.sql("select secret_hash from wf_keys where key_id = ?", (k["key_id"],))
    assert row[0] == crypto.hash_secret(secret) and re.fullmatch(r"[0-9a-f]{64}", row[0])


def test_hash_compare_is_constant_time(probe, monkeypatch):
    calls = []
    real = crypto.hmac.compare_digest

    class Spy:
        compare_digest = staticmethod(lambda a, b: calls.append((a, b)) or real(a, b))

    monkeypatch.setattr(crypto, "hmac", Spy)
    c = probe.client()
    k = probe.key(c["client_id"])
    assert probe.http.get(CUSTOMER, headers=key_headers(k["api_key"])).status_code == 200
    assert len(calls) == 1 and calls[0][0] == calls[0][1] == crypto.hash_secret(k["api_key"].split(".", 1)[1])
    # an unknown key id still costs one comparison, against a dummy hash
    calls.clear()
    probe.http.get(CUSTOMER, headers=key_headers(f"dp_{'1' * 16}.{'B' * 43}"))
    assert len(calls) == 1


def test_secret_checks_use_the_stdlib_comparison():
    assert crypto.verify_secret("s" * 20, crypto.hash_secret("s" * 20))
    assert not crypto.verify_secret("t" * 20, crypto.hash_secret("s" * 20))
    assert not crypto.verify_secret("s" * 20, None)


def test_rate_limit_per_key_with_retry_after(make_env):
    with make_env(wf_rate_per_minute=3) as env:
        c = env.client()
        k1, k2 = env.key(c["client_id"]), env.key(c["client_id"])
        h1, h2 = key_headers(k1["api_key"]), key_headers(k2["api_key"])
        url = "/workforce/v1/partner/routes/none/confirm"
        assert [env.http.post(url, json={}, headers=h1).status_code for _ in range(3)] == [422, 422, 422]
        r = env.http.post(url, json={}, headers=h1)
        err = assert_envelope(r, 429, "RATE_LIMITED")
        assert err["retryable"] is True
        assert 1 <= int(r.headers["retry-after"]) <= 60 and err["details"]["retry_after_seconds"] == int(r.headers["retry-after"])
        assert env.http.post(url, json={}, headers=h2).status_code == 422  # another key has its own budget


def test_rate_limiter_window_slides_and_zero_disables():
    now = [100.0]
    lim = RateLimiter(2, clock=lambda: now[0])
    assert lim.hit("k") is None and lim.hit("k") is None
    assert lim.hit("k") == 60
    now[0] += 59
    assert lim.hit("k") == 1
    now[0] += 1.5
    assert lim.hit("k") is None
    assert lim.hit("other") is None
    off = RateLimiter(0)
    assert all(off.hit("k") is None for _ in range(100))


def test_require_rejects_an_operation_of_the_wrong_kind():
    with pytest.raises(ValueError):
        require("publish_job_event")  # provider operation on the customer kind
    with pytest.raises(ValueError):
        require("reply", "provider")


# ---- keys never cross between the partner API and the rest of the platform --------
def test_partner_key_is_refused_by_the_platform_and_agentscope_apis(probe):
    c = probe.client()
    k = probe.key(c["client_id"])
    h = key_headers(k["api_key"])
    for path in ("/platform/v1/cases", "/platform/v1/wf/clients", "/platform/v1/health", "/agent", "/sessions",
                 "/credential", "/health"):
        r = probe.http.get(path, headers=h)
        assert r.status_code == 401, path
        assert "detail" in r.json() and "error" not in r.json()
    assert probe.http.get("/platform/v1/cases", headers={"Authorization": f"Bearer {k['api_key']}"}).status_code == 401


def test_admin_and_old_connector_keys_are_not_partner_keys(probe):
    for h in (ADM, OLD_SVC):
        assert_envelope(probe.http.get(CUSTOMER, headers=h), 401, "UNAUTHENTICATED")
        assert_envelope(probe.http.post("/workforce/v1/partner/routes/x/confirm", json={}, headers=h),
                        401, "UNAUTHENTICATED")


def test_workforce_does_not_use_dev_open(make_env):
    with make_env(dev_open=True) as env:
        assert_envelope(env.http.post("/workforce/v1/partner/routes/x/confirm", json={}), 401, "UNAUTHENTICATED")
        # dev mode is unchanged for the admin API
        assert env.http.get("/platform/v1/cases").status_code == 200
        c = env.client(headers={})  # keyless admin acts as tenant dev
        k = env.key(c["client_id"], headers={})
        assert env.http.get("/platform/v1/cases", headers=key_headers(k["api_key"])).status_code == 401
        assert env.http.get("/platform/v1/cases",
                            headers={"Authorization": f"Bearer {k['api_key']}"}).status_code == 401
