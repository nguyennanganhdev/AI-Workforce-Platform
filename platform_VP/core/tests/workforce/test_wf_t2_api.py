"""The Provider Event API at the door (slice T2): who may send, what the 202 and the receipt say, what is refused.
Contract 5.2, 10.1, 10.2, 11.2, 12 and the rows of 13.9 about signatures, duplicates and replays. No model."""
from __future__ import annotations

import json
import time

import pytest

from conftest import ALL_CUSTOMER
from t2kit import RECEIPTS, URL, Provider
from test_wf_errors import assert_envelope

RECEIPT_KEYS = {"receipt_id", "external_event_id", "ingestion_status", "normalized_status", "received_at", "applied_at",
                "error", "note"}


@pytest.fixture
def prov(env):
    c = env.client()
    return env, c, Provider(env, c["client_id"])


def inbox(env) -> list[tuple]:
    return env.sql("select receipt_id, external_event_id, ingestion_status from wf_provider_inbox order by received_at")


# ---- the 202 and the receipt -----------------------------------------------------------------------------------------
def test_contract_10_1_a_signed_event_is_stored_and_answered_202_with_the_fields_of_the_contract(prov):
    env, _, p = prov
    r, body = p.send("x.assigned", job="JOB-9", version=3, data={"worker_name": "An", "eta_minutes": 20})
    assert r.status_code == 202, r.text
    got = r.json()
    assert list(got) == ["receipt_id", "ingestion_status", "duplicate", "received_at", "status_url"]
    assert got["receipt_id"].startswith("rcpt_") and got["duplicate"] is False
    assert got["ingestion_status"] == "quarantined"  # it names a job nobody has yet: kept, matched later (10.1, last lines)
    assert got["status_url"] == f"{RECEIPTS}/{got['receipt_id']}" and got["received_at"].endswith("Z")
    assert inbox(env) == [(got["receipt_id"], body["external_event_id"], "quarantined")]
    (stored,) = env.sql("select payload_hash, event_type, provider_version, operation_id from wf_provider_inbox")
    assert stored[1:] == ("x.assigned", "3", None) and stored[0].startswith("sha256:")


def test_contract_10_2_the_receipt_has_the_contract_fields_and_nothing_about_people_or_chats(prov):
    env, _, p = prov
    rid = p.send("x.on_the_way", job="JOB-1", data={"eta_minutes": 5, "technician_phone": "0909"})[0].json()["receipt_id"]
    r = p.receipt(rid)
    assert r.status_code == 200
    got = r.json()
    assert set(got) == RECEIPT_KEYS
    assert (got["receipt_id"], got["normalized_status"], got["applied_at"], got["error"]) == (rid, "on_the_way", None, None)
    text = r.text
    for hidden in ("conversation", "workflow", "manager", "resident", "prompt", "0909", "technician"):
        assert hidden not in text


def test_contract_13_9_a_provider_duplicate_is_the_old_receipt_and_a_changed_payload_is_a_conflict(prov):
    env, _, p = prov
    first, body = p.send("x.assigned", job="JOB-1", version=1, data={"worker_name": "An", "eta_minutes": 5})
    again = p.post(body)  # a retry builds a new timestamp and signature (11.2)
    assert again.status_code == 202
    assert again.json() | {"duplicate": False} == first.json()
    assert again.json()["duplicate"] is True and again.json()["receipt_id"] == first.json()["receipt_id"]
    assert len(inbox(env)) == 1
    changed = {**body, "data": {"worker_name": "Binh", "eta_minutes": 5}}
    err = assert_envelope(p.post(changed), 409, "EVENT_ID_CONFLICT")
    assert err["retryable"] is False
    assert len(inbox(env)) == 1 and p.status_of(first.json()["receipt_id"]) == "quarantined"  # the original is untouched


def test_the_same_event_id_of_another_integration_is_another_event(env):
    c = env.client()
    a, b = Provider(env, c["client_id"]), Provider(env, c["client_id"])
    ra = a.post(a.event("x.on_the_way", job="J", event_id="same", data={"eta_minutes": 1}))
    rb = b.post(b.event("x.on_the_way", job="J", event_id="same", data={"eta_minutes": 2}))
    assert ra.status_code == rb.status_code == 202 and ra.json()["receipt_id"] != rb.json()["receipt_id"]
    assert not rb.json()["duplicate"]


def test_contract_13_9_a_captured_signed_request_replayed_is_the_duplicate_path_and_later_it_is_refused(make_env):
    with make_env(wf_provider_skew_seconds=2) as env:
        c = env.client()
        p = Provider(env, c["client_id"])
        raw = p.raw(p.event("x.on_the_way", job="JOB-1", data={"eta_minutes": 5}))
        headers = p.headers(raw)  # what an eavesdropper captured: bytes, timestamp, signature
        first = env.http.post(URL, content=raw, headers=headers)
        replay = env.http.post(URL, content=raw, headers=headers)
        assert first.status_code == replay.status_code == 202
        assert replay.json()["duplicate"] is True and replay.json()["receipt_id"] == first.json()["receipt_id"]
        assert len(inbox(env)) == 1  # timestamp + event id: the replay changed nothing
        time.sleep(3)
        late = env.http.post(URL, content=raw, headers=headers)
        assert assert_envelope(late, 401, "UNAUTHENTICATED")["details"] == {"reason": "timestamp_out_of_range"}
        assert len(inbox(env)) == 1


# ---- who may send ----------------------------------------------------------------------------------------------------------
def _refused(p, why: str, **how):
    body = p.event("x.on_the_way", job="JOB-1", data={"eta_minutes": 5})
    err = assert_envelope(p.post(body, **how), 401, "UNAUTHENTICATED")
    assert err["details"] == {"reason": why}


def test_contract_13_9_a_wrong_signature_is_refused_and_nothing_is_stored(prov):
    env, _, p = prov
    _refused(p, "signature_invalid", secret="not-the-secret")
    body = p.event("x.on_the_way", job="JOB-1", data={"eta_minutes": 5})
    # signed for other bytes: one character of the body changed after signing
    raw = p.raw(body)
    r = env.http.post(URL, content=raw.replace(b"JOB-1", b"JOB-2"), headers=p.headers(raw))
    assert_envelope(r, 401, "UNAUTHENTICATED")
    reserialized = json.dumps(body, indent=2).encode()  # same JSON, other bytes: the signature is over the raw bytes
    assert_envelope(env.http.post(URL, content=reserialized, headers=p.headers(p.raw(body))), 401, "UNAUTHENTICATED")
    assert inbox(env) == []


@pytest.mark.parametrize("stamp", [lambda: int(time.time()) - 3600, lambda: int(time.time()) + 3600, lambda: 0])
def test_contract_13_9_a_stale_or_future_timestamp_is_refused(prov, stamp):
    env, _, p = prov
    _refused(p, "timestamp_out_of_range", stamp=stamp())
    assert inbox(env) == []


def test_a_timestamp_inside_the_window_is_fine_and_the_window_is_configurable(make_env):
    with make_env(wf_provider_skew_seconds=60) as env:
        p = Provider(env, env.client()["client_id"])
        assert p.post(p.event("x.on_the_way", job="J", data={"eta_minutes": 1}), stamp=int(time.time()) - 50).status_code == 202
        _refused(p, "timestamp_out_of_range", stamp=int(time.time()) - 70)


@pytest.mark.parametrize("drop", ["X-Partner-Timestamp", "X-Partner-Key-Id", "X-Partner-Signature"])
def test_a_missing_signature_header_is_refused(prov, drop):
    env, _, p = prov
    raw = p.raw(p.event("x.on_the_way", job="J", data={"eta_minutes": 1}))
    headers = {k: v for k, v in p.headers(raw).items() if k != drop}
    assert assert_envelope(env.http.post(URL, content=raw, headers=headers), 401, "UNAUTHENTICATED")["details"] == {"reason": "signature_missing"}


@pytest.mark.parametrize("bad", ["v1=", "v2=" + "0" * 64, "0" * 64, "v1=" + "A" * 64, "v1=" + "0" * 63, "v1=zz" + "0" * 62])
def test_a_malformed_signature_is_refused(prov, bad):
    env, _, p = prov
    _refused(p, "signature_invalid", signature=bad)


def test_the_signature_is_compared_in_constant_time_also_when_the_signing_key_is_unknown(prov, monkeypatch):
    import hmac
    env, _, p = prov
    calls = []
    real = hmac.compare_digest
    monkeypatch.setattr(hmac, "compare_digest", lambda a, b: calls.append((a, b)) or real(a, b))
    body = p.event("x.on_the_way", job="J", data={"eta_minutes": 1})
    assert p.post(body).status_code == 202
    assert len(calls) == 2  # the API secret's hash, then the signature
    assert calls[1][0] == calls[1][1] and len(calls[1][0]) == 64  # a good signature: equal hex digests
    calls.clear()
    _refused(p, "signature_invalid", key_id="sk_unknown")
    assert len(calls) == 2  # an unknown key costs the same comparison, against a dummy


def test_a_timestamp_that_is_not_a_number_is_refused(prov):
    env, _, p = prov
    _refused(p, "signature_invalid", stamp="1.5e9")
    _refused(p, "signature_invalid", stamp="12345678901234")


def test_contract_13_9_an_unknown_or_revoked_signing_key_is_refused_the_same_way(prov):
    env, _, p = prov
    _refused(p, "signature_invalid", key_id="sk_unknown")
    second_id, second_secret = p.other_signing_key()
    ok = p.post(p.event("x.on_the_way", job="J", data={"eta_minutes": 1}), key_id=second_id, secret=second_secret)
    assert ok.status_code == 202  # a second signing key of the integration works (rotation)
    assert env.post(f"/platform/v1/wf/integrations/{p.id}/signing-keys/{second_id}/revoke").status_code == 200
    _refused(p, "signature_invalid", key_id=second_id, secret=second_secret)
    assert p.post(p.event("x.on_the_way", job="J", data={"eta_minutes": 2})).status_code == 202  # the first one still does


def test_contract_13_9_the_signature_of_another_integration_is_refused(env):
    c = env.client()
    a, b = Provider(env, c["client_id"]), Provider(env, c["client_id"])
    body = a.event("x.on_the_way", job="J", data={"eta_minutes": 1})
    # A's API key with B's signing key (valid HMAC, wrong owner), and the other way round
    _refused(a, "signature_invalid", key_id=b.key_id, secret=b.secret)
    r = b.post(body, api_key=a.api_key)
    assert_envelope(r, 401, "UNAUTHENTICATED")
    assert env.sql("select count(*) from wf_provider_inbox") == [(0,)]


def test_contract_13_9_a_revoked_or_expired_api_key_is_refused(prov):
    env, _, p = prov
    body = p.event("x.on_the_way", job="J", data={"eta_minutes": 1})
    key_id = p.api_key.split(".")[0][3:]
    assert env.post(f"/platform/v1/wf/keys/{key_id}/revoke").status_code == 200
    assert assert_envelope(p.post(body), 401, "UNAUTHENTICATED")["details"] == {"reason": "revoked"}
    assert env.sql("select count(*) from wf_provider_inbox") == [(0,)]
    q = Provider(env, env.client()["client_id"])
    env.sql("update wf_keys set expires_at=? where key_id=?", (time.time() - 10, q.api_key.split(".")[0][3:]))
    assert assert_envelope(q.post(q.event("x.on_the_way", job="J", data={"eta_minutes": 1})), 401, "UNAUTHENTICATED")["details"] == {"reason": "expired"}


def test_contract_13_9_a_customer_key_or_a_key_without_the_operation_cannot_publish(prov):
    env, c, p = prov
    customer = env.key(c["client_id"], operations=ALL_CUSTOMER)
    body = p.event("x.on_the_way", job="J", data={"eta_minutes": 1})
    err = assert_envelope(p.post(body, api_key=customer["api_key"]), 403, "PERMISSION_DENIED")
    assert err["details"] == {"reason": "wrong_credential_kind"}
    reader = env.post(f"/platform/v1/wf/integrations/{p.id}/keys", {"operations": ["read_event_receipt"]}).json()
    err = assert_envelope(p.post(body, api_key=reader["api_key"]), 403, "PERMISSION_DENIED")
    assert err["details"] == {"operation": "publish_job_event"}
    assert env.sql("select count(*) from wf_provider_inbox") == [(0,)]


def test_no_credential_at_all_is_401_before_the_body_is_read(prov):
    env, _, p = prov
    assert_envelope(env.http.post(URL, content=b"{}", headers={"Content-Type": "application/json"}), 401, "UNAUTHENTICATED")


# ---- the body --------------------------------------------------------------------------------------------------------------
def test_an_unknown_event_type_is_422_unknown_event_type(prov):
    env, _, p = prov
    err = assert_envelope(p.send("x.teleported", job="J")[0], 422, "UNKNOWN_EVENT_TYPE")
    assert err["retryable"] is False and env.sql("select count(*) from wf_provider_inbox") == [(0,)]


@pytest.mark.parametrize("over", [
    {"manager_account_id": "m1"}, {"workflow_id": "wf_1"}, {"conversation_id": "c"}, {"agent_id": "a"}, {"domain_id": "d"},
    {"external_event_id": ""}, {"external_event_id": "a\x01b"}, {"schema_version": "2"}, {"provider_version": -1},
    {"provider_version": True}, {"provider_version": "3"}, {"provider_version": 1.5}, {"occurred_at": "yesterday"},
    {"occurred_at": "2026-10-09T02:30:00"}, {"data": [1]}, {"data": "x"}, {"event_type": "X.Bad Type"}])
def test_the_body_is_strict(prov, over):
    env, _, p = prov
    body = p.event("x.on_the_way", job="J", data={"eta_minutes": 1})
    body.update(over)
    r = p.post(body)
    assert r.status_code in (422, 400), r.text
    assert r.json()["error"]["code"] in ("VALIDATION_FAILED", "UNKNOWN_EVENT_TYPE")
    assert env.sql("select count(*) from wf_provider_inbox") == [(0,)]


def test_an_event_names_a_job_or_a_reference_and_the_message_values_must_be_there(prov):
    env, _, p = prov
    body = p.event("x.on_the_way", data={"eta_minutes": 1})
    err = assert_envelope(p.post(body), 422, "VALIDATION_FAILED")
    assert err["details"]["errors"]
    err = assert_envelope(p.send("x.assigned", job="J", data={"worker_name": "An"})[0], 422, "VALIDATION_FAILED")
    assert err["details"]["errors"] == [{"field": "data.eta_minutes", "reason": "required by the event schema's message, as a plain value"}]
    assert p.send("x.assigned", job="J", data={"worker_name": "An", "eta_minutes": 3})[0].status_code == 202


def test_the_data_may_be_64_kib_and_not_more_and_the_whole_body_256_kib(prov):
    env, _, p = prov
    small = {"eta_minutes": 1, "pad": "x" * (60 * 1024)}
    assert p.send("x.on_the_way", job="J", data=small)[0].status_code == 202
    big = {"eta_minutes": 1, "pad": "x" * (66 * 1024)}
    err = assert_envelope(p.send("x.on_the_way", job="J2", data=big)[0], 413, "PAYLOAD_TOO_LARGE")  # contract 6.2: 413 or 429
    assert err["details"] == {"limit_bytes": 64 * 1024}
    raw = b'{"data": "' + b"x" * (300 * 1024) + b'"}'
    assert_envelope(env.http.post(URL, content=raw, headers=p.headers(raw)), 413, "PAYLOAD_TOO_LARGE")
    assert env.sql("select count(*) from wf_provider_inbox") == [(1,)]


def test_a_body_that_is_not_json_or_not_an_object_is_400(prov):
    env, _, p = prov
    for raw in (b"not json", b"[1]", b"\xff\xfe"):
        assert_envelope(env.http.post(URL, content=raw, headers=p.headers(raw)), 400, "INVALID_REQUEST")
    raw = p.raw(p.event("x.on_the_way", job="J", data={"eta_minutes": 1}))
    wrong = {**p.headers(raw), "Content-Type": "text/plain"}
    assert_envelope(env.http.post(URL, content=raw, headers=wrong), 400, "INVALID_REQUEST")


def test_nothing_the_provider_sends_in_data_leaks_into_the_error_answers(prov):
    env, _, p = prov
    r = p.send("x.assigned", job="J", data={"worker_name": "TOPSECRET-NAME"})[0]
    assert "TOPSECRET-NAME" not in r.text


# ---- receipts: whose they are ---------------------------------------------------------------------------------------------
def test_contract_13_9_a_receipt_is_visible_only_to_its_own_integration(env):
    c1, c2 = env.client(domain="a"), env.client(domain="b")
    a, same_client, other_client = Provider(env, c1["client_id"]), Provider(env, c1["client_id"]), Provider(env, c2["client_id"])
    rid = a.send("x.on_the_way", job="J", data={"eta_minutes": 1})[0].json()["receipt_id"]
    assert a.receipt(rid).status_code == 200
    for stranger in (same_client, other_client):
        err = assert_envelope(stranger.receipt(rid), 404, "NOT_FOUND")
        assert "J" not in json.dumps(err) and rid not in json.dumps(err)
    assert_envelope(a.receipt("rcpt_nothing"), 404, "NOT_FOUND")
    customer = env.key(c1["client_id"], operations=ALL_CUSTOMER)
    assert_envelope(a.receipt(rid, api_key=customer["api_key"]), 403, "PERMISSION_DENIED")
    reader = env.post(f"/platform/v1/wf/integrations/{a.id}/keys", {"operations": ["publish_job_event"]}).json()
    assert assert_envelope(a.receipt(rid, api_key=reader["api_key"]), 403, "PERMISSION_DENIED")["details"] == {"operation": "read_event_receipt"}
