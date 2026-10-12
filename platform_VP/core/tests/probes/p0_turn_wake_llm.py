"""Scripted OpenAI-compatible model for the turn/wake probe.

Adapted from tests/fake_llm.py (not imported, not edited). Differences: every call is recorded with
the session it belongs to (read from the system prompt attachment "You're within a session (id=...)"),
a call can be delayed or made to fail, and the answer comes from a per-test `policy`.
"""
from __future__ import annotations

import asyncio
import json
import re
import socket
import threading
import time
import uuid
from typing import Callable

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

SID_RE = re.compile(r"session \(id=([^)]+)\)")


def text_of(m: dict) -> str:
    c = m.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(p.get("text", "") for p in c if isinstance(p, dict))
    return ""


def system_of(msgs: list[dict]) -> str:
    for m in msgs:
        if m.get("role") in ("system", "developer"):
            return text_of(m)
    return ""


def called(msgs: list[dict], name: str) -> int:
    return sum(1 for m in msgs for tc in (m.get("tool_calls") or []) if tc["function"]["name"] == name)


class Call:
    def __init__(self, sid: str, msgs: list[dict], tools: list[str]) -> None:
        self.sid, self.msgs, self.tools = sid, msgs, tools
        self.blob = json.dumps(msgs, ensure_ascii=False)
        self.t0 = time.perf_counter()
        self.t1 = 0.0
        self.out: object = None


class LLM:
    """policy(call) -> str | list[(tool, args)]. `delay(call)` seconds before answering.
    `fail(call)` True -> HTTP 500 for that model call."""

    def __init__(self) -> None:
        self.calls: list[Call] = []
        self.policy: Callable[[Call], object] = lambda c: "ok"
        self.delay: Callable[[Call], float] = lambda c: 0.0
        self.fail: Callable[[Call], bool] = lambda c: False

    def reset(self) -> None:
        self.calls.clear()
        self.policy = lambda c: "ok"
        self.delay = lambda c: 0.0
        self.fail = lambda c: False

    def of(self, sid: str) -> list[Call]:
        return [c for c in self.calls if c.sid == sid]


def _chunk(cid: str, delta, finish=None, usage=None) -> str:
    body = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()), "model": "fake-1",
            "choices": [] if usage else [{"index": 0, "delta": delta, "finish_reason": finish}]}
    if usage:
        body["usage"] = usage
    return "data: " + json.dumps(body, ensure_ascii=False) + "\n\n"


def make_app(llm: LLM) -> FastAPI:
    app = FastAPI()

    @app.post("/v1/chat/completions")
    async def completions(req: Request):
        body = await req.json()
        msgs, tools = body.get("messages", []), body.get("tools")
        m = SID_RE.search(system_of(msgs))
        call = Call(m.group(1) if m else "?", msgs, [t["function"]["name"] for t in tools or []])
        llm.calls.append(call)
        if llm.fail(call):
            call.t1 = time.perf_counter()
            call.out = "HTTP500"
            return JSONResponse({"error": {"message": "scripted failure", "type": "server_error"}}, status_code=500)
        d = llm.delay(call)
        if d:
            await asyncio.sleep(d)
        out = llm.policy(call)
        call.out = out if isinstance(out, str) else [(n, a) for n, a in out]
        call.t1 = time.perf_counter()
        cid = "chatcmpl-" + uuid.uuid4().hex[:8]
        ptok = len(call.blob) // 4
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
                    yield _chunk(cid, {"tool_calls": [{"index": i, "id": f"call_{uuid.uuid4().hex[:8]}",
                                                       "type": "function", "function": {"name": name, "arguments": ""}}]})
                    yield _chunk(cid, {"tool_calls": [{"index": i, "function": {"arguments": json.dumps(args)}}]})
                yield _chunk(cid, {}, "tool_calls")
                yield _chunk(cid, None, usage=usage(30 * len(out)))
            yield "data: [DONE]\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

    return app


class FakeServer:
    def __init__(self, llm: LLM) -> None:
        self.llm = llm

    def __enter__(self) -> "FakeServer":
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        self.port = s.getsockname()[1]
        s.close()
        self.server = uvicorn.Server(uvicorn.Config(make_app(self.llm), host="127.0.0.1", port=self.port,
                                                    log_level="error"))
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        for _ in range(100):
            if self.server.started:
                break
            time.sleep(0.05)
        return self

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def __exit__(self, *exc) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=5)
