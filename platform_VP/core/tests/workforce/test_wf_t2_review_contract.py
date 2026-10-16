"""Regression tests for the T2 review, the part about the contract: error codes and limits, opaque ids, what the public
event says, what a schema may declare, and what the door refuses. (Findings C1, C3, C4, C5, C6, K5, A8's schema side.)"""
from __future__ import annotations

import copy
import json
import time

import pytest
from conftest import ADM
from partnerkit import Partner
from t2kit import SCHEMA, Provider, pending_world, sent_ok, wait_status
from test_wf_errors import assert_envelope


@pytest.fixture
def partner():
    with Partner() as p:
        yield p


@pytest.fixture
def prov(env):
    c = env.client()
    return env, c, Provider(env, c["client_id"])


def schema_with(**events) -> dict:
    out = copy.deepcopy(SCHEMA)
    out["events"].update(events)
    return out


def create(env, client_id: str, schema: dict):
    return env.http.post(f"/platform/v1/wf/clients/{client_id}/integrations", headers=ADM, json={"event_schema": schema})


# ---- C1: the ids of the partner are opaque -----------------------------------------------------------------------------
@pytest.mark.parametrize("odd", ["ORD/2026 A#7", "đơn hàng #12 (ống nước)", "a" * 200])
def test_a_job_id_the_partner_chose_correlates_whatever_characters_it_has(tmp_path, partner, odd):
    def job(ref, what):
        partner.effects.append(what)
        return odd

    partner._job = job
    with pending_world(tmp_path, partner) as (w, prov, p):
        w.quiet()
        assert p.op_row()[4] == odd  # kept as the partner wrote it
        rid, _ = sent_ok(prov, "x.on_the_way", job=odd, version=2, data={"eta_minutes": 2})  # knows only the job id
        assert wait_status(w, prov, rid)["ingestion_status"] == "applied"
        assert p.events("operation.status_changed")[-1]["payload"]["external_job_id"] == odd


def test_a_job_id_with_spaces_is_not_repeated_to_the_model_but_the_platform_keeps_it(tmp_path, partner):
    from awp.workforce.partner_tools import reference

    assert reference({"external_job_id": "ORD/2026 A#7"}) == "The partner has given a reference; the platform keeps it."
    assert reference({"external_job_id": "JOB-1"}) == "Reference: JOB-1."
    assert reference({"external_job_id": None}) == "The partner has given no reference yet."


def test_an_id_with_a_control_character_is_still_refused(prov):
    _, _, p = prov
    r, _ = p.send("x.on_the_way", job="JOB\n1", data={"eta_minutes": 1})
    assert r.status_code == 422


# ---- C3, C4: the codes of contract 6.3 -----------------------------------------------------------------------------------
def test_ids_that_point_at_two_operations_are_a_conflict_not_a_schema_error(tmp_path, partner):
    with pending_world(tmp_path, partner) as (w, prov, p):
        r, _ = prov.send("x.on_the_way", ref=p.ref, job="NOT-" + p.job, data={"eta_minutes": 1})
        assert_envelope(r, 409, "JOB_CORRELATION_MISMATCH")


def test_data_over_64_kib_is_413_and_stores_nothing(prov):
    env, _, p = prov
    big = {"eta_minutes": 1, "pad": "x" * (66 * 1024)}
    err = assert_envelope(p.send("x.on_the_way", job="J2", data=big)[0], 413, "PAYLOAD_TOO_LARGE")
    assert err["details"] == {"limit_bytes": 64 * 1024} and env.sql("select count(*) from wf_provider_inbox") == [(0,)]


# ---- C5: the public event carries the integration's own status ---------------------------------------------------------
def test_the_public_operation_event_says_the_status_of_the_integration_and_the_platforms_state(tmp_path, partner):
    with pending_world(tmp_path, partner) as (w, prov, p):
        w.quiet()
        p.applied("x.on_the_way", version=1, data={"eta_minutes": 5})
        p.applied("x.completed", version=2, data={"summary": "Pipe replaced"})
        first, last = [e["payload"] for e in p.events("operation.status_changed")[-2:]]
        assert (first["status"], first["operation_state"]) == ("on_the_way", "pending")
        assert (last["status"], last["operation_state"]) == ("completed", "completed")
        assert "partner_status" not in first and first["tool"] == "partner_repair"


# ---- C6: a terminal event says how it ended ------------------------------------------------------------------------------
def test_a_terminal_event_whose_ending_is_not_a_known_word_is_refused_when_the_schema_is_written(prov):
    env, c, _ = prov
    r = create(env, c["client_id"], schema_with(**{"x.delivered": {"status": "delivered", "rank": 92, "terminal": True}}))
    assert r.status_code == 422 and "must say how it ended" in r.text
    ok = create(env, c["client_id"], schema_with(**{"x.delivered": {"status": "delivered", "outcome": "completed", "rank": 92,
                                                                   "terminal": True}}))
    assert ok.status_code == 201  # the partner's word in status, the ending in outcome
    assert create(env, c["client_id"], schema_with(**{"x.gone": {"status": "cancelled", "rank": 99, "terminal": True}})).status_code == 201
    assert create(env, c["client_id"], schema_with(**{"x.late": {"status": "delivered", "rank": 1}})).status_code == 201  # not terminal


def test_a_delivered_event_with_a_declared_ending_completes_the_operation(tmp_path, partner):
    schema = schema_with(**{"x.delivered": {"status": "delivered", "outcome": "completed", "rank": 92, "terminal": True,
                                            "public_status": "delivered"}})
    with pending_world(tmp_path, partner, schema=schema) as (w, prov, p):
        w.quiet()
        p.applied("x.delivered", version=1)
        assert p.op_row()[:2] == ("completed", "delivered") and p.state() == "awaiting_confirmation"


# ---- A8, the schema side: typed fields ---------------------------------------------------------------------------------
def test_a_field_may_only_be_typed_when_the_schema_shows_it_and_the_type_is_known(prov):
    env, c, _ = prov
    typed = {"x.a": {"status": "a", "rank": 1, "public_fields": ["n"], "field_types": {"n": "count"}}}
    assert create(env, c["client_id"], schema_with(**typed)).status_code == 201
    stray = {"x.a": {"status": "a", "rank": 1, "public_fields": ["n"], "field_types": {"other": "count"}}}
    assert create(env, c["client_id"], schema_with(**stray)).status_code == 422
    odd = {"x.a": {"status": "a", "rank": 1, "public_fields": ["n"], "field_types": {"n": "date"}}}
    assert create(env, c["client_id"], schema_with(**odd)).status_code == 422


# ---- K5: what is not JSON is not stored ----------------------------------------------------------------------------------
@pytest.mark.parametrize("junk", [b'"junk": NaN', b'"junk": -Infinity', b'"junk": Infinity', b'"junk": 1e999'])
def test_numbers_that_are_not_json_are_refused_at_the_door(tmp_path, partner, junk):
    with pending_world(tmp_path, partner) as (w, prov, p):
        w.quiet()
        body = prov.event("x.on_the_way", ref=p.ref, version=1, data={"eta_minutes": 5})
        raw = prov.raw(body).replace(b'"data": {', b'"data": {' + junk + b", ")
        assert_envelope(prov.post(body, raw=raw), 400, "INVALID_REQUEST")
        assert w.sql("select count(*) from wf_provider_inbox") == [(0,)]


def test_text_that_cannot_be_written_as_utf8_is_refused_and_not_an_internal_error(prov):
    env, _, p = prov
    body = p.event("x.on_the_way", job="JOB-1")
    raw = p.raw({k: v for k, v in body.items() if k != "data"})[:-1] + b', "data": {"worker_name": "\\ud800"}}'
    assert_envelope(p.post(body, raw=raw), 400, "INVALID_REQUEST")
    assert env.sql("select count(*) from wf_provider_inbox") == [(0,)]


def test_ordinary_json_with_big_exponents_and_unicode_still_goes_through(tmp_path, partner):
    with pending_world(tmp_path, partner) as (w, prov, p):
        w.quiet()
        body = prov.event("x.on_the_way", ref=p.ref, version=1, data={"eta_minutes": 5, "note": "ống nước 1e5 é"})
        raw = prov.raw(body).replace(b'"eta_minutes": 5', b'"eta_minutes": 5, "ratio": 1.5e10')
        r = prov.post(body, raw=raw)
        assert r.status_code == 202, r.text
        assert json.loads(raw)["data"]["ratio"] == 1.5e10
        wait_status(w, prov, r.json()["receipt_id"])
