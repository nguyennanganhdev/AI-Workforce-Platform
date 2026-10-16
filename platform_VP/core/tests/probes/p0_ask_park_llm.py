"""Scripted OpenAI-compatible model for the ask/park probe.

Same idea as tests/fake_llm.py (not edited, not imported): the test installs a
`policy(sys_prompt, msgs, tools) -> str | [(tool, args)]` and every request is
kept in CALLS with its full message list, so a test can assert what the model
was (or was not) shown.
"""
from __future__ import annotations

import json
import socket
import threading
import time
import uuid

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

CALLS: list[dict] = []
POLICY: dict = {"fn": lambda sys, msgs, tools: "ok"}


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


def n_calls(msgs: list[dict], name: str) -> int:
    return sum(1 for m in msgs for tc in (m.get("tool_calls") or []) if tc["function"]["name"] == name)


def results_of(msgs: list[dict], name: str) -> list[str]:
    ids = [tc["id"] for m in msgs for tc in (m.get("tool_calls") or []) if tc["function"]["name"] == name]
    return [text_of(m) for m in msgs if m.get("role") == "tool" and m.get("tool_call_id") in ids]


def _chunk(cid: str, delta, finish=None, usage=None) -> str:
    body = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()), "model": "fake-1",
            "choices": [] if usage else [{"index": 0, "delta": delta, "finish_reason": finish}]}
    if usage:
        body["usage"] = usage
    return "data: " + json.dumps(body, ensure_ascii=False) + "\n\n"


def make_app() -> FastAPI:
    app = FastAPI()

    @app.post("/v1/chat/completions")
    async def completions(req: Request):
        body = await req.json()
        msgs, tools = body.get("messages", []), body.get("tools")
        sys_prompt = system_of(msgs)
        out = POLICY["fn"](sys_prompt, msgs, tools)
        CALLS.append({"sys": sys_prompt, "msgs": msgs, "tools": [t["function"]["name"] for t in tools or []],
                      "out": out if isinstance(out, str) else [(n, a) for n, a in out]})
        cid = "chatcmpl-" + uuid.uuid4().hex[:8]
        usage = {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60}

        async def gen():
            if isinstance(out, str):
                yield _chunk(cid, {"role": "assistant", "content": ""})
                for i in range(0, len(out), 16):
                    yield _chunk(cid, {"content": out[i:i + 16]})
                yield _chunk(cid, {}, "stop")
            else:
                yield _chunk(cid, {"role": "assistant", "content": None})
                for i, (name, args) in enumerate(out):
                    yield _chunk(cid, {"tool_calls": [{"index": i, "id": f"call_{uuid.uuid4().hex[:8]}",
                                                       "type": "function", "function": {"name": name, "arguments": ""}}]})
                    yield _chunk(cid, {"tool_calls": [{"index": i, "function": {"arguments": json.dumps(args)}}]})
                yield _chunk(cid, {}, "tool_calls")
            yield _chunk(cid, None, usage=usage)
            yield "data: [DONE]\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

    return app


class FakeServer:
    def __enter__(self) -> "FakeServer":
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        self.port = s.getsockname()[1]
        s.close()
        self.server = uvicorn.Server(uvicorn.Config(make_app(), host="127.0.0.1", port=self.port, log_level="error"))
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        for _ in range(100):
            if self.server.started:
                break
            time.sleep(0.05)
        CALLS.clear()
        POLICY["fn"] = lambda sys, msgs, tools: "ok"
        return self

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def __exit__(self, *exc) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=5)
        CALLS.clear()
