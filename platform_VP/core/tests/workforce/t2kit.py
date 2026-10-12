"""Helpers for the provider-event tests (slice T2): a provider integration with its schema, keys and signed POSTs,
and a world with one pending operation to send events about. Generic on purpose: 'x.' is no business, only a prefix.
"""
from __future__ import annotations

import copy
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone

import t1kit
from conftest import key_headers
from enginekit import world
from partnerkit import Partner
from t1kit import SETTINGS, act, configure, ops

URL = "/workforce/v1/provider/job-events"
RECEIPTS = "/workforce/v1/provider/event-receipts"
ITEMS = [{"label": "pipe", "amount": 300000}, {"label": "seal", "amount": 250000}]

SCHEMA = {
    "version": "1", "version_mode": "snapshot",
    "events": {
        "x.assigned": {"status": "assigned", "rank": 10, "public_status": "assigned",
                       "public_fields": ["worker_name", "eta_minutes"], "field_types": {"eta_minutes": "count"},
                       "message": "Worker {worker_name} is assigned, arriving in about {eta_minutes} minutes."},
        "x.on_the_way": {"status": "on_the_way", "rank": 20, "public_status": "on_the_way", "public_fields": ["eta_minutes"],
                         "field_types": {"eta_minutes": "count"}},
        "x.cost_reported": {"status": "cost_reported", "rank": 30, "public_fields": ["items", "total"],
                            "wake": True, "evidence": True},
        "x.progress": {"status": "in_progress", "rank": 40, "public_status": "in_progress", "public_fields": ["note"],
                       "wake": True},
        "x.completed": {"status": "completed", "rank": 90, "terminal": True, "outcome": "completed",
                        "public_status": "completed", "public_fields": ["summary"], "wake": True, "evidence": True},
        "x.finished_quietly": {"status": "completed", "rank": 91, "terminal": True, "outcome": "completed",
                               "public_status": "completed", "message": "The work is finished."},
        "x.cancelled": {"status": "cancelled", "rank": 95, "terminal": True, "outcome": "cancelled",
                        "public_status": "cancelled", "public_fields": ["reason"], "wake": True},
        "x.cancelled_quietly": {"status": "cancelled", "rank": 96, "terminal": True, "outcome": "cancelled",
                                "public_status": "cancelled"},
        "x.reopened": {"status": "reopened", "rank": 5, "public_status": "reopened", "reopen": True},
    },
}
DELTA = {**SCHEMA, "version_mode": "delta"}


def iso(at: float | None = None) -> str:
    return datetime.fromtimestamp(at or time.time(), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sign(secret: str, stamp: str | int, raw: bytes) -> str:
    """The signature of contract 5.2, written independently of the platform's own code."""
    return "v1=" + hmac.new(secret.encode(), f"{stamp}.".encode() + raw, hashlib.sha256).hexdigest()


class Provider:
    """A provider's backend: one integration, its API key and signing key (both from the admin API)."""

    def __init__(self, env, client_id: str, schema: dict = SCHEMA) -> None:
        self.env, self.n = env, 0
        made = env.post(f"/platform/v1/wf/clients/{client_id}/integrations", {"event_schema": schema})
        assert made.status_code == 201, made.text
        self.id = made.json()["integration_id"]
        keys = env.post(f"/platform/v1/wf/integrations/{self.id}/keys")
        assert keys.status_code == 201, keys.text
        self.api_key, self.key_id, self.secret = keys.json()["api_key"], keys.json()["signing_key"]["key_id"], \
            keys.json()["signing_key"]["secret"]

    def other_signing_key(self) -> tuple[str, str]:
        r = self.env.post(f"/platform/v1/wf/integrations/{self.id}/signing-keys")
        assert r.status_code == 201, r.text
        return r.json()["signing_key"]["key_id"], r.json()["signing_key"]["secret"]

    def with_key(self, routes: list[str]) -> "Provider":
        """The same integration with another API key (and signing key) that reaches only `routes`."""
        r = self.env.post(f"/platform/v1/wf/integrations/{self.id}/keys", {"routes": routes})
        assert r.status_code == 201, r.text
        other = copy.copy(self)
        other.api_key, other.key_id, other.secret = r.json()["api_key"], r.json()["signing_key"]["key_id"], r.json()["signing_key"]["secret"]
        return other

    def event(self, event_type: str, *, ref: str | None = None, job: str | None = None, version: int | None = None,
              data: dict | None = None, event_id: str | None = None, **over) -> dict:
        self.n += 1
        body = {"schema_version": "1", "external_event_id": event_id or f"ev-{self.id[-6:]}-{self.n}",
                "event_type": event_type, "occurred_at": iso(), "data": data or {}}
        if ref:
            body["client_reference"] = ref
        if job:
            body["external_job_id"] = job
        if version is not None:
            body["provider_version"] = version
        body.update(over)
        return body

    def headers(self, raw: bytes, *, stamp=None, key_id=None, secret=None, api_key=None, signature=None) -> dict:
        stamp = str(int(time.time())) if stamp is None else str(stamp)
        return {**key_headers(api_key or self.api_key), "Content-Type": "application/json",
                "X-Partner-Timestamp": stamp, "X-Partner-Key-Id": key_id or self.key_id,
                "X-Partner-Signature": signature or sign(secret or self.secret, stamp, raw)}

    @staticmethod
    def raw(body: dict) -> bytes:
        return json.dumps(body, ensure_ascii=False).encode()

    def post(self, body: dict, *, raw: bytes | None = None, **how):
        raw = raw if raw is not None else self.raw(body)
        return self.env.http.post(URL, content=raw, headers=self.headers(raw, **how))

    def send(self, event_type: str, **kw):
        """Build and POST one event; returns (response, body)."""
        body = self.event(event_type, **kw)
        return self.post(body), body

    def receipt(self, receipt_id: str, api_key: str | None = None):
        return self.env.http.get(f"{RECEIPTS}/{receipt_id}", headers=key_headers(api_key or self.api_key))

    def status_of(self, receipt_id: str) -> str:
        return self.receipt(receipt_id).json()["ingestion_status"]


def sent_ok(provider: Provider, event_type: str, **kw) -> tuple[str, dict]:
    r, body = provider.send(event_type, **kw)
    assert r.status_code == 202, r.text
    return r.json()["receipt_id"], body


def wait_status(w, provider: Provider, receipt_id: str, want: str | tuple = "applied", timeout: float = 20.0) -> dict:
    want = (want,) if isinstance(want, str) else want
    return w.wait(lambda: (lambda r: r if r["ingestion_status"] in want else None)(provider.receipt(receipt_id).json()),
                  timeout, f"receipt {receipt_id} to be {want}")


# ---- a world with a pending operation -------------------------------------------------------------------------------
def tools_for(integration_id: str | None) -> list[dict]:
    return [t1kit.lookup(), t1kit.action("partner_repair", "book_repair", integration_id=integration_id)]


class Pending:
    """One started workflow whose operation is waiting for the provider."""

    def __init__(self, w, partner: Partner, provider: Provider, start: dict, first: dict) -> None:
        self.w, self.partner, self.provider, self.start, self.first = w, partner, provider, start, first
        [self.op] = ops(w, first["workflow_id"])
        self.ref, self.job = self.op["reference"], self.op["job"]
        self.conv, self.wid = first["conversation_id"], first["workflow_id"]

    def send(self, event_type: str, **kw):
        kw.setdefault("ref", self.ref)
        return sent_ok(self.provider, event_type, **kw)

    def applied(self, event_type: str, **kw) -> dict:
        rid, _ = self.send(event_type, **kw)
        return wait_status(self.w, self.provider, rid)

    def kinds(self) -> list[str]:
        return t1kit.event_types(self.w, self.conv)

    def events(self, kind: str) -> list[dict]:
        return [e for e in self.w.flow.history(self.conv, limit=500).json()["items"] if e["event_type"] == kind]

    def state(self) -> str:
        return self.w.state(self.wid)[0]

    def op_row(self) -> tuple:
        return self.w.sql("select status, normalized_status, last_rank, provider_version, external_job_id from wf_operations "
                          "where workflow_id=?", (self.wid,))[0]

    def jobs(self, kind: str = "provider_wake") -> int:
        return self.w.sql("select count(*) from wf_jobs where kind=? and workflow_id=?", (kind, self.wid))[0][0]


def pending_world(tmp_path, partner: Partner, script=None, schema: dict = SCHEMA, begin: bool = True, **over):
    """A context manager yielding (world, provider, pending). The leader calls the partner's action once and says it is
    pending (or runs `script`); the tool follows `Provider` events. `begin=False`: nothing is started, `pending` is None
    (the test configures more and starts the workflow itself)."""
    import contextlib

    @contextlib.contextmanager
    def run():
        over.setdefault("sweep_every", 3600.0)  # these tests step the sweep by hand (`w.run(w.engine.sweep)`)
        leader = script or act("partner_repair", {"slot": "mon"}, "I asked for a plumber for Monday; it is pending.")
        names = ["partner_repair", "partner_lookup", "partner_repair_b"]
        with world(tmp_path, leader, leader_tools=names, worker_tools=["partner_lookup"], **{**SETTINGS, **over}) as w:
            provider = Provider(w.env, w.flow.client["client_id"], schema)
            configure(w, partner, tools_for(provider.id))
            if not begin:
                yield w, provider, None
                return
            start, first = w.flow.begin()
            yield w, provider, Pending(w, partner, provider, start, first)
    return run()
