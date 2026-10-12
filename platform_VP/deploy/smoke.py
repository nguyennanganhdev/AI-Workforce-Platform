#!/usr/bin/env python3
"""Smoke test of a RUNNING stack (deploy/compose.yml), over HTTP only, standard library only.

It walks docs/WORKFORCE_V1_HUONG_DAN_KET_NOI.md from an empty platform to a closed workflow, as the three callers a
deployment has: the operator (admin key from deploy/.env), the partner (the `dp_` key it is given), the partner's
backend (the provider key and signing key). Every step asserts and prints PASS or FAIL; the first failure stops it.

    python smoke.py                       the whole walk
    python smoke.py --until approval      stop while the workflow waits for the resident's approval (state is saved)
    python smoke.py --until waiting       ... or while it waits for the partner's backend
    python smoke.py --resume              go on from the saved state (after restarting or killing the api container)
    python smoke.py --docker              also ask the sample MCP server how often it was really called
                                          (docker compose exec; without it that one check is skipped)

Two replicas (docker compose --profile two): the walk goes through one, the event stream is read from the other, and
the first can be killed in the middle of the approved call to the partner; the rest then goes through the second:
    python smoke.py --docker --sse-base http://127.0.0.1:8801
    python smoke.py --docker --sse-base http://127.0.0.1:8801 --failover-to http://127.0.0.1:8801 --kill awp-platform-api-1

With the `demo` profile the model is scripted (deploy/demo/fake_model.py): this proves the image, the migrations, the
wiring and the workflow machinery. It proves nothing about a real model. Without the demo model the same walk runs on
whatever model the catalog offers; a real model may word things differently and take longer.

Exit code: 0 all steps passed (or paused by --until), 1 a step failed, 2 the script could not start.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import http.client
import json
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = HERE / ".smoke_state.json"
PARTNER = "/workforce/v1/partner"
ADMIN = "/platform/v1"
OPS = ["submit_request", "reply", "read_result", "receive_events", "submit_consent", "close_workflow", "confirm_route",
       "sync_residence"]
USER = "resident-smoke-1"
MESSAGE = "Please book a repair visit for Monday."
SCHEMA = {"version": "1", "version_mode": "snapshot", "events": {
    "job.assigned": {"status": "assigned", "rank": 10, "public_status": "assigned",
                     "public_fields": ["worker_name", "eta_minutes"], "field_types": {"eta_minutes": "count"},
                     "message": "Worker {worker_name} is assigned, arriving in about {eta_minutes} minutes."},
    "job.completed": {"status": "completed", "rank": 90, "terminal": True, "outcome": "completed",
                      "public_status": "completed", "public_fields": ["summary"], "wake": True, "evidence": True}}}
INSTRUCTIONS = (
    "Answer in English. Say only what a tool has verified. When the resident asks to book or schedule a repair, call "
    "book_repair once with slot set to the day they named, then tell them with CaseSay what the tool answered (cite its "
    "evidence id); a pending answer means the partner will confirm later. When a provider event reports the work "
    "completed, ask the resident with CaseSay (expects: confirmation) whether everything is right. If you cannot "
    "verify something, record it with CaseGap and say that you do not know.")


class Failed(Exception):
    pass


class Paused(Exception):
    pass


def check(ok: bool, what: str) -> None:
    if not ok:
        raise Failed(what)


def read_env(path: Path) -> dict:
    out: dict = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                out[k.strip()] = v.strip()
    return out


def iso(at: float | None = None) -> str:
    return datetime.fromtimestamp(at or time.time(), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Smoke:
    def __init__(self, args, env: dict) -> None:
        self.args, self.env = args, env
        self.base = args.base.rstrip("/")
        self.admin = args.admin_key
        self.s: dict = {"done": [], "run": secrets.token_hex(3)}
        self.results: list[tuple[str, str, str, float]] = []

    # ---- HTTP ---------------------------------------------------------------------------------------------------------
    def call(self, method: str, path: str, body=None, *, bearer: str | None = None, apikey: str | None = None,
             raw: bytes | None = None, headers: dict | None = None, params: dict | None = None, timeout: float = 150):
        url = self.base + path + ("?" + urllib.parse.urlencode(params) if params else "")
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        h = {"Accept": "application/json", **(headers or {})}
        if data is not None:
            h.setdefault("Content-Type", "application/json")
        if bearer:
            h["Authorization"] = f"Bearer {bearer}"
        if apikey:
            h["Authorization"] = f"ApiKey {apikey}"
        req = urllib.request.Request(url, data=data, method=method, headers=h)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                status, text = r.status, r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            status, text = e.code, e.read().decode("utf-8", "replace")
        try:
            return status, json.loads(text) if text else None
        except ValueError:
            return status, text

    def adm(self, method: str, path: str, body=None, **kw):
        return self.call(method, ADMIN + path, body, bearer=self.admin, **kw)

    def partner(self, method: str, path: str, body=None, **kw):
        return self.call(method, PARTNER + path, body, apikey=self.s["partner_key"], **kw)

    def expect(self, got, want, what: str):
        status, body = got
        want = (want,) if isinstance(want, int) else want
        check(status in want, f"{what}: HTTP {status}, wanted {'/'.join(map(str, want))}: {json.dumps(body)[:600]}")
        return body

    def until(self, probe, timeout: float, what: str, every: float = 0.5):
        """Poll `probe` until it returns something true. The API being away for a moment (a restart) is not a failure."""
        end, last = time.monotonic() + timeout, None
        while time.monotonic() < end:
            try:
                got = probe()
                if got:
                    return got
                last = got
            except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
                last = f"{type(e).__name__}: {e}"
            time.sleep(every)
        raise Failed(f"timed out after {timeout:.0f}s waiting for {what} (last: {str(last)[:300]})")

    def workflow(self) -> dict:
        return self.expect(self.adm("GET", f"/wf/workflows/{self.s['workflow_id']}"), 200, "read the workflow")

    def wait_state(self, want: str, timeout: float | None = None) -> dict:
        def probe():
            w = self.workflow()
            if w["state"] == "needs_attention" and want != "needs_attention":
                raise Failed(f"the workflow needs attention ({w['attention_reason']}) while waiting for {want}")
            return w if w["state"] == want else None
        return self.until(probe, timeout or self.args.turn_timeout, f"workflow state {want}")

    def snapshot(self) -> dict:
        return self.expect(self.partner("GET", f"/conversations/{self.s['conversation_id']}",
                                        params={"external_user_id": USER}), 200, "conversation snapshot")

    def history(self) -> list[dict]:
        body = self.expect(self.partner("GET", f"/conversations/{self.s['conversation_id']}/event-history",
                                        params={"external_user_id": USER, "limit": 500}), 200, "event history")
        return body["items"]

    def ids(self) -> dict:
        return {"external_user_id": USER, "external_ticket_id": self.s["ticket"],
                "external_conversation_id": self.s["chat"]}

    def sample_partner(self, *argv: str) -> dict:
        """Run the sample MCP server's own command line inside its container (its port is not published)."""
        out = subprocess.run(["docker", "compose", "-p", self.args.project, "exec", "-T", "fake-mcp", "python", "/demo/fake_mcp.py",
                              *argv], capture_output=True, text=True, timeout=60, cwd=str(HERE))
        check(out.returncode == 0, f"could not reach the sample MCP server ({' '.join(argv)}): {out.stderr[:300]}")
        return json.loads(out.stdout)

    # ---- the steps ------------------------------------------------------------------------------------------------------
    def console(self):
        """The admin console is part of the image: the page and its three files come from the container, with the
        headers that keep it to its own origin, and without a key (it holds no data)."""
        req = urllib.request.Request(self.base + "/console", headers={"Accept": "text/html"})
        with urllib.request.urlopen(req, timeout=20) as r:
            page, kind, csp = r.read().decode("utf-8", "replace"), r.headers.get("content-type", ""), r.headers.get("content-security-policy", "")
            check(r.status == 200 and kind.startswith("text/html"), f"/console answered {r.status} {kind}")
        check("<html" in page.lower() and "app.js" in page and "app.css" in page, "the page is not the console's index.html")
        check("default-src 'self'" in csp, f"the console's Content-Security-Policy is {csp!r}")
        check("http://" not in page and "https://" not in page, "the console page refers to another origin")
        sizes = {}
        for name, want in (("app.js", "javascript"), ("app.css", "text/css")):
            with urllib.request.urlopen(self.base + "/console/" + name, timeout=20) as r:
                body = r.read()
                check(r.status == 200 and want in r.headers.get("content-type", "") and len(body) > 1000,
                      f"/console/{name} answered {r.status} {r.headers.get('content-type')} with {len(body)} bytes")
                sizes[name] = len(body)
        status, _ = self.call("GET", "/console/config.py")
        check(status == 404, f"a file that is not one of the console's answered {status}")
        return (f"GET /console: 200 text/html ({len(page)} bytes) with its CSP; app.js {sizes['app.js']} and app.css "
                f"{sizes['app.css']} bytes from the container; no key needed, nothing loaded from elsewhere")

    def health(self):
        body = self.until(lambda: (lambda r: r[1] if r[0] == 200 else None)(self.call("GET", "/platform/v1/health", timeout=5)),
                          self.args.health_timeout, "GET /platform/v1/health to answer 200")
        check(body == {"status": "ok"}, f"health said {body}")
        status, _ = self.call("GET", "/platform/v1/models")
        check(status == 401, f"an admin API without a key answered {status}, wanted 401")
        return "200 ok; without a key the admin API answers 401"

    def models(self):
        models = self.expect(self.adm("GET", "/models"), 200, "list models")["models"]
        usable = [m for m in models if m["available"]]
        check(bool(usable), f"no model is available (keys missing?): {models}")
        self.s["scripted"] = all(m["id"].startswith("demo-") for m in usable)
        kind = "scripted demo model" if self.s["scripted"] else "REAL model (answers are not scripted)"
        return f"{len(usable)} available: {', '.join(m['id'] for m in usable)} [{kind}]"

    def profile(self):
        key = self.s["profile"] = f"smoke_leader_{self.s['run']}"
        body = self.expect(self.adm("POST", "/profiles", {
            "key": key, "name": "Smoke leader", "role": "leader",
            "mission": "the assistant of a management office, talking to a resident.", "instructions": INSTRUCTIONS,
            "tools_allow": ["book_repair", "lookup_ticket"], "model_tier": "standard"}), 201, "create the leader profile")
        self.s["version"] = body.get("version", 1)
        return f"draft {key} v{self.s['version']}"

    def evaluation(self):
        path = f"/profiles/{self.s['profile']}/versions/{self.s['version']}/evals"
        run = self.expect(self.adm("POST", path, {"wait_seconds": 120}, timeout=200), (200, 202), "start the evaluation")

        def ended():
            runs = self.expect(self.adm("GET", path), 200, "read the evaluation")["runs"]
            mine = [r for r in runs if r.get("id") == run.get("id")] or runs[:1]
            return mine[0] if mine and mine[0]["status"] != "running" else None
        if run["status"] == "running":
            run = self.until(ended, self.args.eval_timeout, "the evaluation run to end", every=2)
        self.s["eval"] = run["status"]
        cases = run.get("cases") or run.get("results") or []
        bad = [f"{c.get('name')}: {'; '.join(map(str, c.get('problems') or c.get('failures') or []))[:160]}"
               for c in cases if not c.get("passed", c.get("ok", True))]
        check(run["status"] in ("passed", "failed"), f"the evaluation ended as {run['status']}: {json.dumps(run)[:500]}")
        return f"run {run['status']} ({len(cases)} cases" + (f"; not passed: {bad}" if bad else "") + ")"

    def publish(self):
        path = f"/profiles/{self.s['profile']}/versions/{self.s['version']}/publish"
        gate = self.expect(self.adm("GET", f"/profiles/{self.s['profile']}/versions/{self.s['version']}/gate"), 200, "read the gate")
        if self.s["eval"] == "passed":
            check(gate["publishable"], f"the evaluation passed but the gate refuses: {gate}")
            body = self.expect(self.adm("POST", path), 200, "publish")
            how = "evaluation passed, published through the gate"
        else:
            status, refused = self.adm("POST", path)
            code = ((refused or {}).get("detail") or {}).get("code") if isinstance(refused, dict) else None
            check(status == 409 and code == "EVAL_REQUIRED", f"the gate should refuse (409 EVAL_REQUIRED), got {status}: {refused}")
            body = self.expect(self.adm("POST", path, {"override_reason": "smoke test of a deployment: scripted model, "
                                                                           "the evaluation did not pass"}), 200, "publish with override")
            how = "evaluation not passed: plain publish refused with 409 EVAL_REQUIRED, then published with a recorded override"
        check(body["status"] == "published", f"publish answered {body}")
        events = self.expect(self.adm("GET", f"/profiles/{self.s['profile']}/history"), 200, "history")["events"]
        kinds = [e["kind"] for e in events]
        check("publish" in kinds and "eval" in kinds, f"the history does not record the evaluation and the release: {kinds}")
        who = next(e["actor"] for e in events if e["kind"] == "publish")
        return f"{how}; history: {kinds}, published by {who}"

    def client(self):
        c = self.expect(self.adm("POST", "/wf/clients", {"name": f"Smoke partner {self.s['run']}", "domain": "homes",
                                                         "environment": "sandbox"}), 201, "create the client")
        self.s["client_id"] = c["client_id"]
        k = self.expect(self.adm("POST", f"/wf/clients/{c['client_id']}/keys", {"operations": OPS}), 201, "create the partner key")
        check(k["api_key"].startswith("dp_"), "the partner key does not look like dp_<id>.<secret>")
        self.s["partner_key"] = k["api_key"]
        status, _ = self.call("GET", "/platform/v1/wf/clients", bearer=k["api_key"])
        check(status == 401, f"a partner key opened the admin API ({status})")
        return f"{c['client_id']} (sandbox), key {k['key_id']}; the partner key does not open /platform"

    def manager(self):
        m = self.expect(self.adm("POST", f"/wf/clients/{self.s['client_id']}/managers", {"name": "Smoke office A"}), 201, "create the manager")
        self.s["manager_id"] = m["manager_id"]
        k = self.expect(self.adm("POST", f"/wf/managers/{m['manager_id']}/keys"), 201, "create the manager key")
        check(k["api_key"].startswith("mk_"), "the manager key does not look like mk_<id>.<secret>")
        self.s["manager_key"] = k["api_key"]
        status, _ = self.call("POST", "/platform/v1/wf/clients", {"name": "x", "domain": "homes", "environment": "sandbox"},
                              bearer=k["api_key"])
        check(status == 403, f"a manager key could create a client ({status})")
        return f"{m['manager_id']}, key {k['key_id']}; a manager key cannot create clients (403)"

    def integration(self):
        i = self.expect(self.adm("POST", f"/wf/clients/{self.s['client_id']}/integrations", {"event_schema": SCHEMA}), 201, "create the integration")
        k = self.expect(self.adm("POST", f"/wf/integrations/{i['integration_id']}/keys", {}), 201, "create the provider keys")
        self.s.update(integration_id=i["integration_id"], provider_key=k["api_key"],
                      signing_key_id=k["signing_key"]["key_id"], signing_secret=k["signing_key"]["secret"])
        return f"{i['integration_id']} with an API key and a signing key (needs AWP_SECRET_KEY to seal it)"

    def route(self):
        ref = self.s["ref"] = f"SMOKE-{self.s['run'].upper()}"
        r = self.expect(self.adm("POST", f"/wf/clients/{self.s['client_id']}/routes", {
            "external_management_ref": ref, "leader_profile": self.s["profile"], "manager_id": self.s["manager_id"],
            "config": {"ticket_binding_mode": "required", "residence_required": False, "timezone": "Asia/Ho_Chi_Minh",
                       "rules": {"safe_reply": "The management office will get back to you.", "phrase_rules": []},
                       "policy": {"auto_close_read_only": True}}}), 201, "create the route")
        check(r["status"] == "pending", f"a new route should be pending, it is {r['status']}")
        self.s.update(route_id=r["route_id"], route_revision=r["revision"])
        return f"{r['route_id']} for {ref}: pending, revision {r['revision']}"

    def mcp(self):
        rid = self.s["route_id"]
        token = self.env.get("DEMO_MCP_TOKEN", "demo-mcp-token")
        self.expect(self.adm("POST", f"/wf/routes/{rid}/mcp", {"name": "partner", "url": self.args.mcp_url,
                                                               "headers": {"Authorization": f"Bearer {token}"}}), 201, "add the MCP server")
        got = self.expect(self.adm("POST", f"/wf/routes/{rid}/mcp/partner/enable", timeout=60), 200, "enable the MCP server")
        tools = {t["name"]: t for t in got["tools"]}
        check(got["server"]["enabled"] is True, "the server is not enabled")
        check({"lookup_ticket", "book_repair"} <= set(tools), f"discovery did not find the sample tools: {sorted(tools)}")
        look, book = tools["lookup_ticket"], tools["book_repair"]
        check((look["kind"], look["status"]) == ("lookup", "active"), f"a readOnlyHint tool should be an active look-up: {look}")
        check((book["kind"], book["status"], book["requires_consent"]) == ("action", "proposed", True),
              f"any other tool should be a proposed action that needs consent: {book}")
        listed = self.expect(self.adm("GET", f"/wf/routes/{rid}/mcp"), 200, "list the servers")
        check(token not in json.dumps(listed), "the MCP header value came back out of the API")
        return (f"{len(tools)} tools discovered at {self.args.mcp_url}: look-ups active, book_repair proposed and "
                "unusable; the header value is not readable back")

    def activate(self):
        # idempotency_arg: the sample partner makes a request with a reference it already has a no-op, so the platform
        # may send a request again that a crash left half sent (without it such a request needs a person)
        t = self.expect(self.adm("PATCH", f"/wf/routes/{self.s['route_id']}/tools/book_repair", {
            "status": "active", "tracking": "events", "client_reference_arg": "client_reference",
            "idempotency_arg": "client_reference",
            "integration_id": self.s["integration_id"], "consent_summary": "Book a repair visit for {slot}"}), 200, "activate book_repair")
        check((t["status"], t["tracking"], t["requires_consent"]) == ("active", "events", True), f"the tool is not as activated: {t}")
        return ("book_repair active: an action that needs the resident's consent, followed by provider events, safe to "
                "send again with the same reference")

    def confirm(self):
        self.s.update(ticket=f"TICKET-{self.s['run']}", chat=f"CHAT-{self.s['run']}")
        early = self.start_body("early")
        status, body = self.partner("POST", "/requests", early)
        code = ((body or {}).get("error") or {}).get("code") if isinstance(body, dict) else None
        check(status == 403 and code == "ROUTE_NOT_AUTHORIZED", f"a pending route took a request: {status} {body}")
        r = self.expect(self.partner("POST", f"/routes/{self.s['route_id']}/confirm", {
            "schema_version": "1", "expected_revision": self.s["route_revision"], "external_management_ref": self.s["ref"]}),
            200, "confirm the route as the partner")
        check(r["status"] == "active", f"the route is {r['status']} after the confirmation")
        return f"before: 403 ROUTE_NOT_AUTHORIZED; after the partner's confirmation: active, revision {r['revision']}"

    def start_body(self, tag: str = "start") -> dict:
        return {"schema_version": "1", "command_type": "start_workflow", "external_request_id": f"rq-{self.s['run']}-{tag}",
                "external_management_ref": self.s["ref"], **self.ids(), "message": {"type": "text", "text": MESSAGE}}

    def start(self):
        body = self.start_body()
        first = self.expect(self.partner("POST", "/requests", body), (200, 202), "start_workflow")
        self.s.update(workflow_id=first["workflow_id"], conversation_id=first["conversation_id"], request_id=first["request_id"])
        w = self.wait_state("awaiting_approval")
        check(w["next_action"] == "submit_approval", f"next_action is {w['next_action']}")
        again = self.expect(self.partner("POST", "/requests", body), (200, 202), "the same request again")
        check((again["request_id"], again["workflow_id"]) == (first["request_id"], first["workflow_id"]),
              "sending the same request again made a new request or workflow")
        ops = self.expect(self.adm("GET", "/wf/operations", params={"workflow_id": self.s["workflow_id"]}), 200, "operations")["operations"]
        check(ops == [], f"an operation exists before the resident agreed: {ops}")
        return (f"{first['workflow_id']} is awaiting_approval / submit_approval; the same request again returned the same "
                "ids; nothing was sent to the partner yet")

    def sse(self):
        """The event stream from its beginning: read frames until the approval request shows up. With --sse-base it
        is read from another replica than the one the requests went to."""
        source = (self.args.sse_base or self.base).rstrip("/")
        url = urllib.parse.urlsplit(source)
        conn = http.client.HTTPConnection(url.hostname, url.port or 80, timeout=20)
        seen: list[str] = []
        try:
            conn.request("GET", f"{PARTNER}/conversations/{self.s['conversation_id']}/events?" +
                         urllib.parse.urlencode({"external_user_id": USER}),
                         headers={"Authorization": f"ApiKey {self.s['partner_key']}", "Accept": "text/event-stream"})
            r = conn.getresponse()
            check(r.status == 200 and "text/event-stream" in (r.getheader("content-type") or ""),
                  f"the stream answered {r.status} {r.getheader('content-type')}")
            end, block = time.monotonic() + 20, {}
            while time.monotonic() < end and "approval.required" not in seen:
                line = r.readline().decode("utf-8", "replace").rstrip("\r\n")
                if line == "":
                    if block.get("event"):
                        check(bool(block.get("id")), "an event frame has no id (cursor)")
                        json.loads(block.get("data", "null"))
                        seen.append(block["event"])
                    block = {}
                elif not line.startswith(":"):
                    name, _, value = line.partition(": ")
                    block[name] = value
        finally:
            conn.close()
        check("approval.required" in seen, f"the stream did not deliver approval.required within 20 s: {seen}")
        where = f" (read from {source}, the requests went to {self.base})" if source != self.base else ""
        return f"SSE delivered {len(seen)} events with cursors{where}: {seen}"

    def read_approval(self):
        snap = self.snapshot()
        check(len(snap["approvals"]) == 1, f"wanted one pending approval, got {snap['approvals']}")
        a = snap["approvals"][0]
        check(a["tool_name"] == "book_repair" and a["status"] == "pending", f"unexpected approval: {a}")
        self.s["approval"] = {k: a.get(k) for k in ("approval_id", "arguments_hash", "expected_revision", "quote_ref")}
        mine = self.expect(self.call("GET", "/platform/v1/wf/workflows", bearer=self.s["manager_key"]), 200, "workflows as the manager")
        check([w["workflow_id"] for w in mine["workflows"]] == [self.s["workflow_id"]], "the manager does not see exactly its own workflow")
        return f"approval {a['approval_id']} pending: {json.dumps(a['summary'], ensure_ascii=False)}; the manager's key sees this workflow only"

    def approve(self):
        a = self.s["approval"]
        body = {"schema_version": "1", "external_request_id": f"rq-{self.s['run']}-decide", **self.ids(),
                "workflow_id": self.s["workflow_id"], "decision": "approve", "expected_revision": a["expected_revision"],
                "arguments_hash": a["arguments_hash"]}
        if a.get("quote_ref"):
            body["quote_ref"] = a["quote_ref"]
        to = (self.args.failover_to or "").rstrip("/")
        if to:  # the approved call will hang at the sample partner: the request is in, its answer is not out
            check(bool(self.args.kill and self.args.docker), "--failover-to needs --kill <container> and --docker")
            self.sample_partner("--hold", "on")
        d = self.expect(self.partner("POST", f"/approvals/{a['approval_id']}/decision", body), 202, "the decision")
        check(d["status"] == "approved", f"the decision answered {d}")
        note = "the tool ran"
        if to:
            self.until(lambda: self.sample_partner("--stats")["held"] == 1, 60, "the approved call to hang at the sample partner")
            killed = subprocess.run(["docker", "kill", "-s", "KILL", self.args.kill], capture_output=True, text=True, timeout=60)
            check(killed.returncode == 0, f"docker kill {self.args.kill}: {killed.stderr[:300]}")
            t0 = time.monotonic()
            self.sample_partner("--hold", "off")
            was, self.base = self.base, to
            self.s["failed_over"] = True
            self.wait_state("waiting_external_event", max(self.args.turn_timeout, 240))
            note = (f"{self.args.kill} was killed (SIGKILL) inside the approved call to the partner; {to} took the "
                    f"workflow over {time.monotonic() - t0:.0f}s later (it waits for the dead process's lease) instead of {was}")
        else:
            self.wait_state("waiting_external_event")
        again = self.expect(self.partner("POST", f"/approvals/{a['approval_id']}/decision", body), 202, "the same decision again")
        check(again == d, "sending the same decision again answered differently")
        return f"approved (202); {note} and the workflow is waiting_external_event; the same decision again is answered the same"

    def operation(self):
        def listed():
            return self.expect(self.adm("GET", "/wf/operations", params={"workflow_id": self.s["workflow_id"]}), 200, "operations")["operations"]
        if self.s.get("failed_over"):  # the dead process had the partner's answer, if any: the survivor asks again first
            self.until(lambda: [o for o in listed() if o["status"] == "pending"], 180, "the survivor to learn what became of the request")
        ops = listed()
        check(len(ops) == 1, f"wanted exactly one operation, got {len(ops)}: {ops}")
        op = ops[0]
        check(op["tool"] == "book_repair" and op["status"] == "pending" and op["client_reference"], f"unexpected operation: {op}")
        self.s.update(client_reference=op["client_reference"], job=op["external_job_id"])
        said = [e["payload"].get("text") or e["payload"] for e in self.history() if e["event_type"] == "assistant.message"]
        check(bool(said), "the leader said nothing to the resident")
        return f"one operation, pending, reference {op['client_reference']}, partner job {op['external_job_id']}; the leader said: {said[-1]!r}"

    def provider_post(self, event_id: str, event_type: str, version: int, data: dict, *, secret: str | None = None,
                      raw: bytes | None = None):
        """One signed event (contract 5.2: HMAC-SHA256 over "<timestamp>.<raw body>"). `raw`: send these bytes again."""
        raw = raw or json.dumps({"schema_version": "1", "external_event_id": event_id, "client_reference": self.s["client_reference"],
                                 "event_type": event_type, "provider_version": version, "occurred_at": iso(), "data": data}).encode()
        self.last_raw = raw
        stamp = str(int(time.time()))
        sig = "v1=" + hmac.new((secret or self.s["signing_secret"]).encode(), stamp.encode() + b"." + raw, hashlib.sha256).hexdigest()
        return self.call("POST", "/workforce/v1/provider/job-events", raw=raw, apikey=self.s["provider_key"], headers={
            "X-Partner-Timestamp": stamp, "X-Partner-Key-Id": self.s["signing_key_id"], "X-Partner-Signature": sig})

    def receipt(self, receipt_id: str, want: str = "applied") -> dict:
        def probe():
            r = self.expect(self.call("GET", f"/workforce/v1/provider/event-receipts/{receipt_id}", apikey=self.s["provider_key"]),
                            200, "the receipt")
            if r["ingestion_status"] in ("rejected", "needs_attention") and want == "applied":
                raise Failed(f"the event was not applied: {r}")
            return r if r["ingestion_status"] == want else None
        return self.until(probe, 60, f"receipt {receipt_id} to be {want}")

    def provider_event(self):
        ev = f"evt-{self.s['run']}"
        status, body = self.provider_post(ev + "-bad", "job.assigned", 1, {"worker_name": "An", "eta_minutes": 20}, secret="not-the-secret")
        check(status == 401, f"an event with a wrong signature was answered {status}: {body}")
        a = self.expect(self.provider_post(ev + "-1", "job.assigned", 1, {"worker_name": "An", "eta_minutes": 20}), 202, "job.assigned")
        self.receipt(a["receipt_id"])
        check(self.workflow()["state"] == "waiting_external_event", "progress that needs no model changed the workflow state")
        done = self.expect(self.provider_post(ev + "-2", "job.completed", 2, {"summary": "Pipe replaced"}), 202, "job.completed")
        self.receipt(done["receipt_id"])
        self.s["done_raw"] = self.last_raw.decode()
        return "wrong signature: 401; job.assigned applied without waking the leader; job.completed applied"

    def confirmation(self):
        w = self.wait_state("awaiting_confirmation")
        check(w["next_action"] == "confirm_close", f"next_action is {w['next_action']}")
        said = [e["payload"].get("text") for e in self.history() if e["event_type"] == "assistant.message"]
        return f"awaiting_confirmation / confirm_close; the leader asked: {said[-1]!r}"

    def close(self):
        wf = self.snapshot()["workflows"][0]
        check((wf["state"], wf["next_action"]) == ("awaiting_confirmation", "confirm_close"), f"the snapshot says {wf}")
        c = self.expect(self.partner("POST", f"/workflows/{self.s['workflow_id']}/close", {
            "schema_version": "1", "external_request_id": f"rq-{self.s['run']}-close", **self.ids(),
            "expected_revision": wf["revision"], "reason": "resident_confirmed_resolved", "stop_tracking_only": False}), 200, "close")
        check((c["state"], c["next_action"]) == ("closed", "none"), f"close answered {c}")
        return "closed by the partner after the resident confirmed"

    def exactly_once(self):
        wid = {"workflow_id": self.s["workflow_id"]}
        ops = self.expect(self.adm("GET", "/wf/operations", params=wid), 200, "operations")["operations"]
        apps = self.expect(self.adm("GET", "/wf/approvals", params=wid), 200, "approvals")["approvals"]
        recs = self.expect(self.adm("GET", "/wf/receipts", params=wid), 200, "receipts")["receipts"]
        kinds = [e["event_type"] for e in self.history()]
        says = [e["payload"].get("text") for e in self.history() if e["event_type"] == "assistant.message"]
        check(len(ops) == 1 and ops[0]["status"] == "completed", f"operations: {[(o['tool'], o['status']) for o in ops]}")
        check([a["status"] for a in apps] == ["approved"], f"approvals: {[a['status'] for a in apps]}")
        check(sorted(r["ingestion_status"] for r in recs) == ["applied", "applied"], f"receipts: {[(r['event_type'], r['ingestion_status']) for r in recs]}")
        for kind in ("approval.required", "approval.resolved", "workflow.closed"):
            check(kinds.count(kind) == 1, f"{kind} appears {kinds.count(kind)} times in the history: {kinds}")
        check(len(says) == len(set(says)), f"the resident was told the same thing twice: {says}")
        check(self.workflow()["state"] == "closed", "the workflow is not closed")
        dup = self.expect(self.provider_post("", "", 0, {}, raw=self.s["done_raw"].encode()), 202, "the same event again")
        check(dup.get("duplicate") is True, f"the same event sent again was not answered as a duplicate: {dup}")
        note = "202 duplicate"
        partner = "partner call count: skipped (run with --docker)"
        if self.args.docker:
            stats = self.sample_partner("--stats")
            ref = self.s["client_reference"]
            times, made = stats["book_repair_calls_by_reference"].get(ref, 0), stats["side_effects_by_reference"].get(ref, 0)
            # after a kill inside the call the survivor sends the request once more with the SAME reference; the partner
            # answers from the job it already has
            # after a kill inside the call: the agent is woken through a queue either replica may take. If the killed
            # one ran the call, the survivor sent the request once more with the SAME reference (2 calls, the partner
            # answers from the job it has); if the survivor ran it, the call simply went on (1 call).
            want = (1, 2) if self.s.get("failed_over") else (1,)
            check(ref in stats["jobs"] and times in want and made == 1,
                  f"the partner was called {times} times with this workflow's reference (wanted {' or '.join(map(str, want))}) "
                  f"and made {made} job(s) for it (wanted 1): {stats}")
            how = ("exactly once with this reference and holds one job for it" if times == 1 else
                   "twice with this reference (the second time by the replica that took over) and made ONE job for it")
            if self.s.get("failed_over") and times == 1:
                how += " (the call was running in the replica that survived; the killed one held the job)"
            partner = (f"the sample MCP server was called {how} ({stats['jobs'][ref]}); all its calls since it started, "
                       f"every workflow together: {stats['calls']}")
        return (f"1 operation (completed), 1 approval (approved), 2 receipts (applied), {len(says)} distinct messages to the "
                f"resident, one approval.required/approval.resolved/workflow.closed; the same event again: {note}; {partner}")

    STEPS = [
        ("health", "API is up and protected", health),
        ("console", "Admin console is served", console),
        ("models", "A model is available", models),
        ("profile", "Leader profile (draft)", profile),
        ("eval", "Evaluation of the draft", evaluation),
        ("publish", "Release gate and publish", publish),
        ("client", "Client and partner key", client),
        ("manager", "Manager and manager key", manager),
        ("integration", "Integration, provider key, signing key", integration),
        ("route", "Route (pending)", route),
        ("mcp", "MCP server: add, enable, discover", mcp),
        ("activate", "Activate the action tool", activate),
        ("confirm", "Partner confirms the route", confirm),
        ("start", "start_workflow parks on consent", start),
        ("sse", "Event stream (SSE)", sse),
        ("approval", "Snapshot shows the approval", read_approval),
        ("approve", "Resident approves; tool runs", approve),
        ("waiting", "One pending operation", operation),
        ("event", "Signed provider events", provider_event),
        ("confirmation", "Leader asks to confirm", confirmation),
        ("close", "Partner closes the workflow", close),
        ("once", "Nothing happened twice", exactly_once),
    ]

    def run(self) -> int:
        if self.args.resume:
            if not STATE.is_file():
                print(f"--resume: no saved state at {STATE}", file=sys.stderr)
                return 2
            self.s = json.loads(STATE.read_text(encoding="utf-8"))
        print(f"smoke run {self.s['run']} against {self.base}  ({iso()})")
        if self.args.resume:
            try:  # the API may have just been restarted or killed: wait for it, then say what it remembers
                t0 = time.monotonic()
                self.until(lambda: self.call("GET", "/platform/v1/health", timeout=5)[0] == 200, self.args.health_timeout,
                           "GET /platform/v1/health to answer 200")
                note = f"API healthy after {time.monotonic() - t0:.1f}s"
                if self.s.get("workflow_id"):
                    w = self.workflow()
                    note += f"; workflow {w['workflow_id']} is {w['state']} (revision {w['revision']})"
                print(f"RESUME after step '{self.s['done'][-1] if self.s['done'] else '(none)'}': {note}")
            except Failed as e:
                print(f"RESUME FAIL: {e}")
                return 1
        code = 0
        try:
            for i, (key, title, fn) in enumerate(self.STEPS, 1):
                if key in self.s["done"]:
                    continue
                t0 = time.monotonic()
                try:
                    detail = fn(self)
                except Failed as e:
                    self.line(i, "FAIL", title, str(e), time.monotonic() - t0)
                    code = 1
                    break
                except (urllib.error.URLError, ConnectionError, TimeoutError, OSError, KeyError, ValueError, TypeError) as e:
                    self.line(i, "FAIL", title, f"{type(e).__name__}: {e}", time.monotonic() - t0)
                    code = 1
                    break
                self.line(i, "PASS", title, detail, time.monotonic() - t0)
                self.s["done"].append(key)
                STATE.write_text(json.dumps(self.s), encoding="utf-8")
                if key == self.args.until:
                    raise Paused()
        except Paused:
            print(f"\nPAUSED after step '{self.args.until}' (state in {STATE.name}; it holds this run's keys). "
                  "Go on with: python smoke.py --resume")
            return 0
        passed = sum(1 for r in self.results if r[0] == "PASS")
        if code == 0:
            STATE.unlink(missing_ok=True)
            print(f"\nSMOKE PASS: {len(self.s['done'])} of {len(self.STEPS)} steps passed"
                  + ("" if self.s.get("scripted") else " (REAL model)") + (" (scripted demo model)" if self.s.get("scripted") else ""))
        else:
            print(f"\nSMOKE FAIL: {passed} step(s) passed in this run, then one failed; the steps after it did not run. "
                  f"State kept in {STATE.name}.")
        return code

    def line(self, i: int, verdict: str, title: str, detail: str, took: float) -> None:
        self.results.append((verdict, title, detail, took))
        print(f"[{i:02d}/{len(self.STEPS)}] {verdict}  {title}  ({took:.1f}s)\n         {detail}", flush=True)


def main() -> int:
    env = read_env(HERE / ".env")
    ap = argparse.ArgumentParser(description="Smoke test of a running stack: onboarding and one whole workflow, over HTTP.")
    ap.add_argument("--base", default=f"http://127.0.0.1:{env.get('AWP_HOST_PORT', '8800')}", help="the platform's address")
    ap.add_argument("--admin-key", default=(env.get("AWP_ADMIN_KEYS", "").split(";")[0].partition(":")[0] or None),
                    help="an admin key (default: the first of AWP_ADMIN_KEYS in deploy/.env)")
    ap.add_argument("--mcp-url", default="http://fake-mcp:8901/mcp", help="the partner MCP server, as the platform reaches it")
    ap.add_argument("--until", choices=[k for k, _, _ in Smoke.STEPS], help="stop after this step and save the state")
    ap.add_argument("--resume", action="store_true", help="go on from the saved state")
    ap.add_argument("--docker", action="store_true", help="also read the sample MCP server's call counters (docker compose exec)")
    ap.add_argument("--project", default="awp-platform", help="compose project name, for --docker")
    ap.add_argument("--sse-base", help="read the event stream from this address (another replica) instead of --base")
    ap.add_argument("--failover-to", help="address of another replica: the replica at --base is killed inside the approved "
                    "call to the partner and the walk goes on through this one (needs --kill and --docker)")
    ap.add_argument("--kill", help="container to kill for --failover-to (docker kill -s KILL), e.g. awp-platform-api-1")
    ap.add_argument("--health-timeout", type=float, default=120)
    ap.add_argument("--turn-timeout", type=float, default=120, help="seconds one agent turn may take")
    ap.add_argument("--eval-timeout", type=float, default=900)
    args = ap.parse_args()
    if not args.admin_key:
        print("no admin key: run init_env.py (deploy/.env) or pass --admin-key", file=sys.stderr)
        return 2
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    return Smoke(args, env).run()


if __name__ == "__main__":
    sys.exit(main())
