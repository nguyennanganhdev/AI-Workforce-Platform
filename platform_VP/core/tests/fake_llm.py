"""A scripted OpenAI-compatible server. It plays a fixed case so the plumbing
(case file, digest, protocol, guard, cost, delivery) can be tested without
spending money. It says nothing about how a real model would behave.
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

CALLS: list[dict] = []  # every request, for assertions
MODE: dict = {"leader": "normal"}  # tests flip this to script a failing leader


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
    """Tool result texts of calls to `name`, in order."""
    ids = [tc["id"] for m in msgs for tc in (m.get("tool_calls") or []) if tc["function"]["name"] == name]
    return [_text(m) for m in msgs if m.get("role") == "tool" and m.get("tool_call_id") in ids]


def policy(msgs: list[dict], tools: list[dict]) -> list[tuple[str, dict]] | str:
    sp = _system(msgs)
    blob = " ".join(_text(m) for m in msgs if m.get("role") != "system")
    names = [t["function"]["name"] for t in tools or []]

    out_of_budget = "budget for this case is spent" in blob
    if 'key="supervisor"' in sp:
        if MODE["leader"] == "mute":
            return "Everything looks fine to me."
        if out_of_budget:
            return [("CaseFinalize", {"answer": "Out of budget.", "outcome": "needs_human",
                                      "unknowns": ["budget spent before the case was verified"]})]
        if _called(msgs, "TeamCreate") == 0:
            return [("TeamCreate", {"name": "case-team", "description": "Resolve the leak"})]
        if _called(msgs, "AgentCreate") == 0:
            return [
                ("AgentCreate", {"name": "tech", "description": "Checks the ticket", "subagent_type": "tech",
                                 "prompt": "Look up ticket T-1001 and record what you find."}),
                ("AgentCreate", {"name": "fin", "description": "Finds the cost", "subagent_type": "fin",
                                 "prompt": "Find the repair cost and record it."}),
            ]
        f_tech = re.findall(r"\b(F\d+) tech:", blob)
        f_fin = re.findall(r"\b(F\d+) fin:", blob)
        if f_tech and f_fin:
            cites = [f_tech[0], f_fin[0]]
            tries = _results(msgs, "CaseFinalize")
            if not tries:  # first attempt invents a figure on purpose
                return [("CaseFinalize", {"answer": "Repair costs 2000000 VND.", "outcome": "resolved", "cites": cites})]
            if "Not accepted" in tries[-1]:
                return [("CaseFinalize", {
                    "answer": "Pipe repair costs 1500000 VND; ticket T-1001 is waiting for the plumber.",
                    "outcome": "resolved", "cites": cites})]
            return "Done."
        return "Waiting for the specialists."

    if out_of_budget and ('key="tech"' in sp or 'key="fin"' in sp):
        if _called(msgs, "TeamSay") == 0:
            return [("TeamSay", {"content": "Out of budget; reporting what I have.", "to": "case-leader"})]
        return "Reported."

    if 'key="tech"' in sp:
        if "lookup_ticket" in names and _called(msgs, "lookup_ticket") == 0:
            return [("lookup_ticket", {"ticket_id": "T-1001"})]
        ev = re.findall(r"\[evidence (E\d+)\]", " ".join(_results(msgs, "lookup_ticket")))
        if _called(msgs, "CaseFact") == 0 and ev:
            return [("CaseFact", {"text": "Ticket T-1001 is waiting for the plumber", "evidence": ev[:1]})]
        q = re.findall(r'ref="(Q\d+)"', blob)
        if q and _called(msgs, "CaseAnswer") == 0:
            return [("CaseAnswer", {"ref": q[0], "text": "The unit is occupied", "evidence": ev[:1]})]
        reports_needed = 1 + (1 if _called(msgs, "CaseAnswer") else 0)
        if _called(msgs, "TeamSay") < reports_needed:
            return [("TeamSay", {"content": "Checked the ticket, see my facts.", "to": None})]  # broadcast on purpose
        return "Reported."

    if 'key="fin"' in sp:
        if "price_list" in names and _called(msgs, "price_list") == 0:
            return [("price_list", {"item": "pipe repair"})]
        ev = re.findall(r"\[evidence (E\d+)\]", " ".join(_results(msgs, "price_list")))
        if _called(msgs, "CaseFact") == 0 and ev:
            return [("CaseFact", {"text": "Pipe repair costs 1500000 VND", "evidence": ev[:1]})]
        if _called(msgs, "CaseAsk") == 0:
            return [("CaseAsk", {"to": "tech", "question": "Is the unit occupied?"})]
        if _called(msgs, "TeamSay") == 0:
            return [("TeamSay", {"content": "Cost found; waiting for tech about occupancy.", "to": "case-leader"})]
        if "answers Q" in blob and _called(msgs, "TeamSay") < 2:
            return [("TeamSay", {"content": "Cost recorded and occupancy confirmed.", "to": None})]
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
                      "out": out if isinstance(out, str) else [(n, a) for n, a in out]})
        cid = "chatcmpl-" + uuid.uuid4().hex[:8]
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
        self.server = uvicorn.Server(uvicorn.Config(make_app(), host="127.0.0.1", port=self.port,
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
