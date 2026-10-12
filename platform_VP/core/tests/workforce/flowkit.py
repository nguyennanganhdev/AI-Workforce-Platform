"""Test helpers for the request flow: a partner with a key and an active route, and the commands."""
from __future__ import annotations

import contextlib
import itertools
import json
import queue
import threading
from dataclasses import dataclass, field

import httpx

from conftest import key_headers
from fake_engine import TestEngine

P = "/workforce/v1/partner"


@dataclass
class Flow:
    env: object
    client: dict
    key: dict
    route: dict
    engine: TestEngine
    _n: itertools.count = field(default_factory=lambda: itertools.count(1))

    @property
    def http(self):
        return self.env.http

    @property
    def h(self) -> dict:
        return key_headers(self.key["api_key"])

    def n(self) -> int:
        return next(self._n)

    @contextlib.contextmanager
    def waiting(self, seconds: float):
        """The route answers 202 after `seconds` of waiting (the fixtures wait up to 20), then goes back."""
        rid = self.route["route_id"]
        [(old,)] = self.env.sql("select config from wf_routes where id=?", (rid,))
        cfg = json.loads(old) if isinstance(old, str) else old
        self.env.sql("update wf_routes set config=? where id=?", (json.dumps({**cfg, "wait_seconds": seconds}), rid))
        try:
            yield
        finally:
            self.env.sql("update wf_routes set config=? where id=?", (json.dumps(cfg), rid))

    # ---- bodies ----------------------------------------------------------------
    def start_body(self, **over) -> dict:
        i = self.n()
        body = {"schema_version": "1", "command_type": "start_workflow",
                "external_request_id": f"rq-{i}", "external_management_ref": "BQL-OP1-A",
                "external_user_id": "resident-123", "external_ticket_id": f"TICKET-{i}",
                "external_conversation_id": f"CHAT-{i}",
                "message": {"type": "text", "text": "Hãy gọi thợ đến sửa ống nước."}}
        body.update(over)
        return {k: v for k, v in body.items() if v is not None}

    def reply_body(self, started: dict, start: dict, **over) -> dict:
        """A reply built from the start body and the start response."""
        body = {"schema_version": "1", "command_type": "workflow_reply",
                "external_request_id": f"rq-{self.n()}",
                "external_management_ref": start["external_management_ref"],
                "external_user_id": start["external_user_id"],
                "external_ticket_id": start.get("external_ticket_id"),
                "external_conversation_id": start["external_conversation_id"],
                "workflow_id": started["workflow_id"],
                "message": {"type": "text", "text": "Tôi rảnh từ 14 giờ."}}
        body.update(over)
        return {k: v for k, v in body.items() if v is not None}

    def post(self, body: dict, headers: dict | None = None):
        return self.http.post(f"{P}/requests", json=body, headers=self.h if headers is None else headers)

    def start(self, **over):
        """(response, body sent)."""
        body = self.start_body(**over)
        return self.post(body), body

    def begin(self, **over) -> tuple[dict, dict]:
        """Start a workflow and return (start body, response json); asserts a 2xx."""
        r, body = self.start(**over)
        assert r.status_code in (200, 202), r.text
        return body, r.json()

    def reply(self, start: dict, started: dict, **over):
        body = self.reply_body(started, start, **over)
        return self.post(body), body

    # ---- reads -------------------------------------------------------------------
    def get(self, path: str, user: str | None = "resident-123", headers: dict | None = None, **params):
        if user is not None:
            params["external_user_id"] = user
        return self.http.get(f"{P}{path}", params=params, headers=self.h if headers is None else headers)

    def request(self, request_id: str, **kw):
        return self.get(f"/requests/{request_id}", **kw)

    def snapshot(self, conv_id: str, **kw):
        return self.get(f"/conversations/{conv_id}", **kw)

    def history(self, conv_id: str, **kw):
        return self.get(f"/conversations/{conv_id}/event-history", **kw)

    def close_body(self, wf: dict, start: dict, revision: int | None = None, **over) -> dict:
        body = {"schema_version": "1", "external_request_id": f"rq-{self.n()}",
                "external_user_id": start["external_user_id"],
                "external_ticket_id": start.get("external_ticket_id"),
                "external_conversation_id": start["external_conversation_id"],
                "expected_revision": wf["workflow_revision"] if revision is None else revision,
                "reason": "resident_confirmed_resolved", "stop_tracking_only": False}
        body.update(over)
        return {k: v for k, v in body.items() if v is not None}

    def close(self, wf: dict, start: dict, revision: int | None = None, **over):
        """(response, body sent)."""
        body = self.close_body(wf, start, revision, **over)
        return self.http.post(f"{P}/workflows/{wf['workflow_id']}/close", json=body, headers=self.h), body


    # ---- approvals -----------------------------------------------------------------
    def approvals(self, conv_id: str, **kw) -> list[dict]:
        """The pending approvals of the snapshot (contract 9.4)."""
        return self.snapshot(conv_id, **kw).json()["approvals"]

    def decide_body(self, start: dict, started: dict, approval: dict, decision: str = "approve", **over) -> dict:
        """A decision (contract 9.8) built from the start body, the start response and a snapshot approval."""
        body = {"schema_version": "1", "external_request_id": f"rq-{self.n()}",
                "external_user_id": start["external_user_id"], "external_ticket_id": start.get("external_ticket_id"),
                "external_conversation_id": start["external_conversation_id"], "workflow_id": started["workflow_id"],
                "decision": decision, "expected_revision": approval["expected_revision"],
                "arguments_hash": approval["arguments_hash"], "quote_ref": approval.get("quote_ref")}
        body.update(over)
        return {k: v for k, v in body.items() if v is not None}

    def decide(self, approval_id: str, body: dict, headers: dict | None = None):
        return self.http.post(f"{P}/approvals/{approval_id}/decision", json=body,
                              headers=self.h if headers is None else headers)


class Stream:
    """An SSE connection read on a thread, so a test can wait for frames with a timeout."""

    def __init__(self, http: httpx.Client, url: str, headers: dict, params: dict | None = None) -> None:
        self.frames: "queue.Queue[tuple]" = queue.Queue()
        self.status: int | None = None
        self.headers: dict = {}
        self.body: bytes = b""
        self._ready = threading.Event()
        self._client: httpx.Client | None = None
        self._thread = threading.Thread(target=self._read, args=(http.base_url, url, headers, params or {}),
                                        daemon=True)
        self._thread.start()
        assert self._ready.wait(15), "no response headers"

    def _read(self, base, url, headers, params):
        try:
            with httpx.Client(base_url=base, timeout=None) as c:
                self._client = c
                with c.stream("GET", url, headers=headers, params=params) as r:
                    self.status, self.headers = r.status_code, dict(r.headers)
                    if r.status_code != 200:
                        self.body = r.read()
                        self._ready.set()
                        self.frames.put(("end", None))
                        return
                    self._ready.set()
                    block: list[str] = []
                    for line in r.iter_lines():
                        if line == "":
                            if block:
                                self.frames.put(("frame", block))
                                block = []
                        else:
                            block.append(line)
        except Exception as e:  # the connection was closed under us
            self.frames.put(("error", e))
        finally:
            self._ready.set()
            self.frames.put(("end", None))

    def next(self, timeout: float = 10.0):
        """The next frame as a dict {id, event, data(parsed)} or {comment}, or None on timeout/end."""
        try:
            kind, block = self.frames.get(timeout=timeout)
        except queue.Empty:
            return None
        if kind != "frame":
            return None
        if all(line.startswith(":") for line in block):
            return {"comment": block[0]}
        out: dict = {}
        for line in block:
            name, _, value = line.partition(": ")
            out[name] = value
        out["data"] = json.loads(out["data"])
        out["raw"] = block
        return out

    def events(self, count: int, timeout: float = 10.0) -> list[dict]:
        """The next `count` business events (comments skipped)."""
        got: list[dict] = []
        while len(got) < count:
            f = self.next(timeout)
            assert f is not None, f"only {len(got)} of {count} events arrived"
            if "comment" not in f:
                got.append(f)
        return got

    def ended(self, timeout: float = 10.0) -> bool:
        """True when the server closed the stream within `timeout`."""
        while True:
            try:
                kind, _ = self.frames.get(timeout=timeout)
            except queue.Empty:
                return False
            if kind in ("end", "error"):
                return True

    def close(self) -> None:
        """Drop the connection (as a client that went away would)."""
        c = self._client
        if c is not None:
            try:
                c.close()
            except Exception:
                pass
