"""Helpers for the P0 crash probe: a scripted model, a side-effect tool, a node launcher.

Everything is a copy-and-adapt of tests/fake_llm.py and tests/support.py (those files are
not touched). The "node" is a real OS process running the real `awp` app, so killing it is a
real hard crash (TerminateProcess), not a cancelled asyncio task.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / "src"
SVC = {"Authorization": "Bearer svc-key"}
ADM = {"Authorization": "Bearer adm-key"}
USER = "awp:t1"  # owner of every platform agent and session of tenant t1


# ---------------------------------------------------------------- scripted model
CALLS: list[dict] = []


def _text(m: dict) -> str:
    c = m.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(p.get("text", "") for p in c if isinstance(p, dict))
    return ""


def _system(msgs: list[dict]) -> str:
    return next((_text(m) for m in msgs if m.get("role") in ("system", "developer")), "")


def _called(msgs: list[dict], name: str) -> int:
    return sum(1 for m in msgs for tc in (m.get("tool_calls") or []) if tc["function"]["name"] == name)


def _results(msgs: list[dict], name: str) -> list[str]:
    ids = [tc["id"] for m in msgs for tc in (m.get("tool_calls") or []) if tc["function"]["name"] == name]
    return [_text(m) for m in msgs if m.get("role") == "tool" and m.get("tool_call_id") in ids]


def policy(msgs: list[dict], tools: list[dict]):
    """Leader: book the plumber (side effect), then finalize citing the tool result."""
    if 'key="dispatcher"' not in _system(msgs):
        return "ok"
    if not _called(msgs, "book_plumber"):
        return [("book_plumber", {"unit": "A-12-05", "issue": "leaking pipe"})]
    ev = re.findall(r"\[evidence (E\d+)\]", " ".join(_results(msgs, "book_plumber")))
    if ev and not _called(msgs, "CaseFinalize"):
        return [("CaseFinalize", {"answer": "The plumber is booked.", "outcome": "resolved", "cites": ev[:1]})]
    return "Done."


def _chunk(cid: str, delta, finish=None, usage=None) -> str:
    body = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()), "model": "fake-1",
            "choices": [] if usage else [{"index": 0, "delta": delta, "finish_reason": finish}]}
    if usage:
        body["usage"] = usage
    return "data: " + json.dumps(body, ensure_ascii=False) + "\n\n"


def make_llm_app() -> FastAPI:
    app = FastAPI()

    @app.post("/v1/chat/completions")
    async def completions(req: Request):
        body = await req.json()
        msgs, tools = body.get("messages", []), body.get("tools")
        out = policy(msgs, tools)
        # what the model was shown: this is the evidence of "what the new instance's context holds"
        CALLS.append({
            "roles": [m.get("role") for m in msgs if m.get("role") != "system"],
            "user_texts": [_text(m)[:60] for m in msgs if m.get("role") == "user"],
            "tool_call_ids": [tc["id"] for m in msgs for tc in (m.get("tool_calls") or [])],
            "n_book_calls": _called(msgs, "book_plumber"),
            "out": out if isinstance(out, str) else [(n, a) for n, a in out]})
        cid = "chatcmpl-" + uuid.uuid4().hex[:8]
        issued = [] if isinstance(out, str) else [f"call_{uuid.uuid4().hex[:8]}" for _ in out]
        CALLS[-1]["issued_ids"] = issued
        ptok = sum(len(json.dumps(m, ensure_ascii=False)) for m in msgs) // 4
        usage = lambda c: {"prompt_tokens": ptok, "completion_tokens": c, "total_tokens": ptok + c}

        async def gen():
            if isinstance(out, str):
                yield _chunk(cid, {"role": "assistant", "content": ""})
                for i in range(0, len(out), 16):
                    yield _chunk(cid, {"content": out[i:i + 16]})
                yield _chunk(cid, {}, "stop")
                yield _chunk(cid, None, usage=usage(max(1, len(out) // 4)))
            else:
                yield _chunk(cid, {"role": "assistant", "content": None})
                for i, (name, args) in enumerate(out):
                    yield _chunk(cid, {"tool_calls": [{"index": i, "id": issued[i],
                                                       "type": "function", "function": {"name": name, "arguments": ""}}]})
                    yield _chunk(cid, {"tool_calls": [{"index": i, "function": {"arguments": json.dumps(args)}}]})
                yield _chunk(cid, {}, "tool_calls")
                yield _chunk(cid, None, usage=usage(30 * len(out)))
            yield "data: [DONE]\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

    return app


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class FakeLLM:
    def __enter__(self) -> "FakeLLM":
        self.port = free_port()
        self.server = uvicorn.Server(uvicorn.Config(make_llm_app(), host="127.0.0.1", port=self.port,
                                                    log_level="error"))
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        for _ in range(100):
            if self.server.started:
                break
            time.sleep(0.05)
        CALLS.clear()
        return self

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def __exit__(self, *exc) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=5)


# ---------------------------------------------------------------- the side-effect tool
def canon(args: dict) -> str:
    return json.dumps(args, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def args_hash(args: dict) -> str:
    return "sha256:" + hashlib.sha256(canon(args).encode()).hexdigest()


def client_reference(case_id: str, tool: str, ahash: str) -> str:
    return "cr-" + hashlib.sha256(f"{case_id}|{tool}|{ahash}".encode()).hexdigest()[:16]


DDL = """CREATE TABLE IF NOT EXISTS p0_operations (
  client_reference TEXT PRIMARY KEY, case_id TEXT NOT NULL, tool TEXT NOT NULL, args_hash TEXT NOT NULL,
  status TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL)"""


def provider_book(effects_log: Path, ref: str, dedupe: bool) -> bool:
    """The outside world: a plumber is booked. Returns True if a real booking was made.
    With `dedupe` the provider is idempotent on client_reference (what the contract asks of it)."""
    if dedupe and effects_log.exists() and f" {ref} " in effects_log.read_text():
        return False
    with effects_log.open("a") as f:
        f.write(f"BOOKED {ref} pid={os.getpid()} t={time.time():.3f}\n")
        f.flush()
        os.fsync(f.fileno())
    return True


def build_tool_class():
    """Defined lazily so the test process need not import agentscope."""
    from agentscope.message import TextBlock, ToolResultState
    from agentscope.permission import PermissionBehavior, PermissionDecision
    from agentscope.tool import ParamsBase, ToolBase, ToolChunk
    from pydantic import Field

    class _P(ParamsBase):
        unit: str = Field(description="Unit")
        issue: str = Field(description="Issue")

    class BookPlumber(ToolBase):
        name = "book_plumber"
        description = "Book a plumber (has a real side effect)."
        input_schema = _P.model_json_schema()
        is_read_only = False
        is_concurrency_safe = False

        def __init__(self, cfg: dict, case_id: str) -> None:
            self.cfg, self.case_id = cfg, case_id

        async def check_permissions(self, *a, **k):
            return PermissionDecision(behavior=PermissionBehavior.ALLOW, message="probe")

        async def _hang(self, point: str) -> None:
            if self.cfg.get("hang_at") == point:
                Path(self.cfg["side_dir"], f"reached_{point}").write_text(str(os.getpid()))
                await asyncio.sleep(3600)  # "in flight": the test kills the process here

        async def call(self, unit: str, issue: str):
            cfg = self.cfg
            side = Path(cfg["side_dir"])
            args = {"unit": unit, "issue": issue}
            ahash = args_hash(args)
            ref = client_reference(self.case_id, self.name, ahash)
            effects = side / "effects.log"
            log = side / "tool_calls.log"
            with log.open("a") as f:
                f.write(f"CALL {ref} pid={os.getpid()} guard={cfg['guard']}\n")
            con = sqlite3.connect(cfg["awp_db"], timeout=30)
            con.execute(DDL)
            con.commit()

            def status() -> str | None:
                r = con.execute("SELECT status FROM p0_operations WHERE client_reference=?", (ref,)).fetchone()
                return r[0] if r else None

            def mark(s: str) -> None:
                con.execute("UPDATE p0_operations SET status=?, updated_at=? WHERE client_reference=?",
                            (s, time.time(), ref))
                con.commit()

            if cfg["guard"]:
                prev = status()
                if prev in ("sent", "completed"):
                    with log.open("a") as f:
                        f.write(f"SKIP {ref} previous={prev}\n")
                    return ToolChunk(content=[TextBlock(
                        text=f"Already booked earlier, reference {ref}. Nothing was repeated.")],
                        state=ToolResultState.SUCCESS)
                if prev is None:
                    con.execute("INSERT INTO p0_operations VALUES (?,?,?,?,?,?,?)",
                                (ref, self.case_id, self.name, ahash, "intent", time.time(), time.time()))
                    con.commit()
                if prev == "intent" and cfg.get("on_intent") == "unknown":
                    # Cannot tell "never sent" from "sent, result lost": do not touch the provider.
                    mark("unknown")
                    with log.open("a") as f:
                        f.write(f"UNKNOWN {ref}\n")
                    return ToolChunk(content=[TextBlock(
                        text=f"UNKNOWN: an earlier attempt {ref} did not finish. Not repeated; status must be checked.")],
                        state=ToolResultState.SUCCESS)
                # prev == "intent" and on_intent == "retry_same_ref": go on with the SAME reference,
                # the provider is idempotent on it (only if cfg provider_dedupe).
            await self._hang("after_intent")
            made = provider_book(effects, ref, cfg["provider_dedupe"])
            await self._hang("after_effect")
            if cfg["guard"]:
                mark("sent")
            await self._hang("after_mark")
            if cfg["guard"]:
                mark("completed")
            con.close()
            return ToolChunk(content=[TextBlock(text=f"Plumber booked, reference {ref}." + ("" if made else " (provider already had it)"))],
                             state=ToolResultState.SUCCESS)

    return BookPlumber


# ---------------------------------------------------------------- node process
class Node:
    """One instance of the platform in its own OS process."""

    def __init__(self, root: Path, name: str, llm_url: str, **over) -> None:
        self.root, self.name = root, name
        self.port = free_port()
        side = root / "side"
        side.mkdir(exist_ok=True)
        self.cfg = {
            "port": self.port, "llm_url": llm_url,
            "awp_db": (root / "awp.db").as_posix(), "as_db": (root / "as.db").as_posix(),
            "workspace": (root / "ws").as_posix(), "side_dir": side.as_posix(),
            "guard": False, "provider_dedupe": False, "hang_at": "", "redis": None, "on_intent": "retry_same_ref",
            "approval": False,
            "name": name, "case_stall_seconds": 900,
        }
        self.cfg.update(over)
        self.cfg_path = root / f"node_{name}.json"
        self.cfg_path.write_text(json.dumps(self.cfg))
        self.log_path = root / f"node_{name}.log"
        self.proc: subprocess.Popen | None = None
        self.http = httpx.Client(base_url=f"http://127.0.0.1:{self.port}", timeout=30)

    def start(self, timeout: float = 90) -> "Node":
        env = {**os.environ, "PYTHONPATH": str(SRC), "PYTHONUNBUFFERED": "1", "AWP_NODE_NAME": self.name}
        self.logf = self.log_path.open("wb")
        self.proc = subprocess.Popen([sys.executable, str(HERE / "p0_crash_node.py"), str(self.cfg_path)],
                                     env=env, stdout=self.logf, stderr=subprocess.STDOUT)
        end = time.time() + timeout
        while time.time() < end:
            if self.proc.poll() is not None:
                raise RuntimeError(f"node {self.name} exited: {self.log_path.read_text(errors='replace')[-2000:]}")
            try:
                if self.http.get("/platform/v1/health").status_code == 200:
                    return self
            except httpx.HTTPError:
                pass
            time.sleep(0.3)
        raise RuntimeError(f"node {self.name} did not start: {self.log_path.read_text(errors='replace')[-2000:]}")

    def kill(self) -> None:
        """Hard crash: TerminateProcess on Windows (SIGKILL elsewhere). No handler runs."""
        if self.proc and self.proc.poll() is None:
            self.proc.kill()
            self.proc.wait(timeout=20)
        self.http.close()
        self.logf.close()

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def log(self) -> str:
        return self.log_path.read_text(errors="replace")


def wait_for(pred, timeout: float = 60, every: float = 0.25, what: str = "condition"):
    end = time.time() + timeout
    last = None
    while time.time() < end:
        last = pred()
        if last:
            return last
        time.sleep(every)
    raise AssertionError(f"timed out waiting for {what}")


# ---------------------------------------------------------------- inspection of the files
def sql(db: str, query: str, args=()) -> list[tuple]:
    con = sqlite3.connect(db, timeout=30)
    try:
        return con.execute(query, args).fetchall()
    finally:
        con.close()


def summarize_blocks(msg: dict) -> list[str]:
    out = []
    content = msg.get("content")
    if isinstance(content, str):
        return [f"text:{content[:40]}"]
    for b in content or []:
        t = b.get("type")
        if t == "tool_call":
            out.append(f"tool_call:{b.get('name')}:{b.get('state')}")
        elif t == "tool_result":
            txt = " ".join(o.get("text", "") for o in b.get("output") or [] if isinstance(o, dict))
            out.append(f"tool_result:{b.get('name')}:{b.get('state')}:{txt[:90]}")
        elif t == "text":
            out.append(f"text:{(b.get('text') or '')[:30]}")
        else:
            out.append(str(t))
    return out


def session_state(as_db: str, session_id: str) -> dict:
    """The AgentScope session state as stored: context summary, reply_context."""
    rows = sql(as_db, "SELECT payload FROM sessions WHERE id=?", (session_id,))
    if not rows:
        return {}
    payload = json.loads(rows[0][0]) if isinstance(rows[0][0], str) else rows[0][0]
    st = payload.get("state") or {}
    ctx = st.get("context") or []
    return {"context": [(m.get("role"), m.get("name"), summarize_blocks(m)) for m in ctx],
            "reply_context": st.get("reply_context"), "raw_state_keys": sorted(st)}


def stored_messages(as_db: str, session_id: str) -> list[tuple]:
    rows = sql(as_db, "SELECT payload FROM messages WHERE session_id=? ORDER BY created_at", (session_id,))
    out = []
    for (p,) in rows:
        p = json.loads(p) if isinstance(p, str) else p
        out.append((p.get("role"), p.get("name"), summarize_blocks(p)))
    return out


def effects(root: Path) -> list[str]:
    f = root / "side" / "effects.log"
    return f.read_text().splitlines() if f.exists() else []


def tool_calls(root: Path) -> list[str]:
    f = root / "side" / "tool_calls.log"
    return f.read_text().splitlines() if f.exists() else []


def intents(awp_db: str) -> list[tuple]:
    try:
        return sql(awp_db, "SELECT client_reference, status FROM p0_operations")
    except sqlite3.OperationalError:
        return []


def first_user_text(as_db: str, session_id: str) -> str:
    rows = sql(as_db, "SELECT payload FROM messages WHERE session_id=? ORDER BY created_at", (session_id,))
    for (p,) in rows:
        p = json.loads(p) if isinstance(p, str) else p
        if p.get("role") == "user":
            return "".join(b.get("text", "") for b in p.get("content") or [] if b.get("type") == "text")
    return ""


def case_items(awp_db: str, case_id: str) -> list[tuple]:
    return sql(awp_db, "SELECT ref, kind, author FROM awp_case_items WHERE case_id=? ORDER BY id", (case_id,))


def say(node: "Node", agent_id: str, session_id: str, text: str, name: str = "resident"):
    return node.http.post("/chat/", headers=ADM, json={"agent_id": agent_id, "session_id": session_id, "input": {
        "name": name, "role": "user", "content": [{"type": "text", "text": text}]}})


def raw_state(as_db: str, session_id: str) -> dict:
    rows = sql(as_db, "SELECT payload FROM sessions WHERE id=?", (session_id,))
    payload = json.loads(rows[0][0]) if isinstance(rows[0][0], str) else rows[0][0]
    return payload["state"]


def pending_tool_call(as_db: str, session_id: str):
    """(reply_id, tool_call block dict) of the last tool call without a result in the saved context."""
    ctx = raw_state(as_db, session_id)["context"]
    for m in reversed(ctx):
        blocks = m.get("content") or []
        done = {b["id"] for b in blocks if b.get("type") == "tool_result"}
        for b in blocks:
            if b.get("type") == "tool_call" and b["id"] not in done:
                return m["id"], b
    return None, None


def confirm_body(agent_id: str, session_id: str, reply_id: str, call: dict, confirmed: bool = True) -> dict:
    return {"agent_id": agent_id, "session_id": session_id, "input": {
        "type": "USER_CONFIRM_RESULT", "reply_id": reply_id,
        "confirm_results": [{"confirmed": confirmed, "tool_call": call}]}}


def session_status(node: "Node", agent_id: str, session_id: str) -> str:
    return node.http.get(f"/sessions/{session_id}/status", headers=ADM, params={"agent_id": agent_id}).json()["status"]
