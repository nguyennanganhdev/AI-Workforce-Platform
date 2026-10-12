"""A scripted OpenAI-compatible model for the MCP probe (copied and cut down from tests/fake_llm.py).

The leader makes a team with one worker ("tech"). The worker calls the partner tools listed in
MODE["worker_calls"] one after the other, records one fact per result that carries an evidence id,
and reports. The leader then finalizes citing those facts.
It proves plumbing only; it says nothing about how a real model would behave.
"""
from __future__ import annotations

import json
import re
import socket
import threading
import time
import uuid

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

CALLS: list[dict] = []
MODE: dict = {"worker_calls": [], "answer": "", "fact_texts": []}


def _text(m: dict) -> str:
    c = m.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(p.get("text", "") for p in c if isinstance(p, dict))
    return ""


def _system(msgs: list[dict]) -> str:
    for m in msgs:
        if m.get("role") in ("system", "developer"):
            return _text(m)
    return ""


def _called(msgs: list[dict], name: str) -> int:
    return sum(1 for m in msgs for tc in (m.get("tool_calls") or []) if tc["function"]["name"] == name)


def _results(msgs: list[dict], name: str) -> list[str]:
    ids = [tc["id"] for m in msgs for tc in (m.get("tool_calls") or []) if tc["function"]["name"] == name]
    return [_text(m) for m in msgs if m.get("role") == "tool" and m.get("tool_call_id") in ids]


def policy(msgs: list[dict], tools: list[dict]):
    sp = _system(msgs)
    blob = " ".join(_text(m) for m in msgs if m.get("role") != "system")
    names = [t["function"]["name"] for t in tools or []]

    if 'key="supervisor"' in sp:
        if _called(msgs, "TeamCreate") == 0:
            return [("TeamCreate", {"name": "case-team", "description": "Resolve the leak"})]
        if _called(msgs, "AgentCreate") == 0:
            return [("AgentCreate", {"name": "tech", "description": "Checks and books", "subagent_type": "tech",
                                     "prompt": "Use your partner tools, record what you find."})]
        facts = sorted(set(re.findall(r"\b(F\d+) tech:", blob)), key=lambda x: int(x[1:]))
        if facts:
            if _called(msgs, "CaseFinalize") == 0 or "Not " in (_results(msgs, "CaseFinalize") or [""])[-1][:4]:
                return [("CaseFinalize", {"answer": MODE["answer"], "outcome": "resolved", "cites": facts})]
            return "Done."
        return "Waiting for the specialist."

    if 'key="tech"' in sp:
        plan = MODE["worker_calls"]
        for name, args in plan:             # distinct tool names, each called once, in order
            if _called(msgs, name) == 0:
                return [(name, args)]
        if _called(msgs, "CaseFact") == 0:
            outs = []
            for (name, _args), text in zip(plan, MODE["fact_texts"]):
                ev = re.findall(r"\[evidence (E\d+)\]", " ".join(_results(msgs, name)))
                if ev and text:
                    outs.append(("CaseFact", {"text": text, "evidence": ev[:1]}))
            if outs:
                return outs
        if _called(msgs, "TeamSay") == 0:
            return [("TeamSay", {"content": "Checked with the partner, see my facts.", "to": "case-leader"})]
        return "Reported."
    return "ok"


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
        out = policy(msgs, tools)
        CALLS.append({"sys": _system(msgs)[:80], "tools": [t["function"]["name"] for t in tools or []],
                      "out": out if isinstance(out, str) else [(n, a) for n, a in out], "schemas": tools,
                      "tool_msgs": [_text(m) for m in msgs if m.get("role") == "tool"]})
        cid = "chatcmpl-" + uuid.uuid4().hex[:8]
        ptok = sum(len(json.dumps(m, ensure_ascii=False)) for m in msgs) // 4
        usage = lambda c: {"prompt_tokens": ptok, "completion_tokens": c, "total_tokens": ptok + c}  # noqa: E731

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
        return self

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v1"

    def __exit__(self, *exc) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=5)
