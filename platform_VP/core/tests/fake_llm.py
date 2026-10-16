"""A scripted OpenAI-compatible server. It plays a fixed case so the plumbing
(case file, digest, protocol, guard, cost, engine) can be tested without
spending money. It says nothing about how a real model would behave.
"""
from __future__ import annotations

import asyncio
import json
import re
import socket
import threading
import time
import uuid

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

CALLS: list[dict] = []  # every request, for assertions
# Tests flip this to script a failing leader, or set `answer_gate` (a threading.Event) to hold back a teammate's
# answer to a peer question until the test sets it.
# Workflow tests set `script` (a function of a `Call`, used for the leader), `leader_delay` (seconds the
# leader's model call takes) and `leader_http` (answer the leader's model calls with this HTTP status).
# `leader_gate` (a threading.Event) holds every model call of the leader until the test sets it: a gate where a
# delay would make a test depend on the speed of the machine.
# `worker` is the same kind of script for the technician ('tech'), `worker_http` makes its model calls fail.
# `agents` maps a profile key to a script for the agent of that profile (any key, asked before the fixed ones).
# `builder` is the scenario of the agent builder: a function of a `Call` that returns the structured answer (a dict
# shaped like awp.builder.Reply); without one the builder asks a question back (`builder_default`).
# `delay` is a function of the system prompt that says how many seconds this model call takes (the server stays free
# for the other agents meanwhile, which a sleep inside a script would not allow).
# `eval_leader` replaces the script of the platform's own leader of a specialist's evaluation (`eval_leader`).
MODE: dict = {"leader": "normal", "scenario": "default", "answer_gate": None, "script": None,
              "leader_delay": 0, "leader_gate": None, "leader_http": 0, "worker": None, "worker_http": 0,
              "agents": {}, "builder": None, "eval_leader": None, "delay": None}
STRUCTURED = "generate_structured_output"  # the tool AgentScope forces for a structured answer


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


class Call:
    """One request to the scripted model, with the questions a leader script asks about it."""

    HINTS = ("<system-reminder", "<workflow-state", "<room-digest")  # reminders the room adds as user messages

    def __init__(self, msgs: list[dict], tools: list[dict] | None) -> None:
        self.msgs, self.tools, self.names = msgs, tools or [], [t["function"]["name"] for t in tools or []]
        self.blob = " ".join(_text(m) for m in msgs if m.get("role") != "system")
        # what started this turn: the last user message that is not one of the room's own reminders
        self.at = max((i for i, m in enumerate(msgs) if m.get("role") == "user"
                       and not _text(m).startswith(self.HINTS)), default=-1)
        self.last_user = _text(msgs[self.at]) if self.at >= 0 else ""

    def called(self, name: str) -> int:
        return _called(self.msgs, name)

    def results(self, name: str) -> list[str]:
        return _results(self.msgs, name)

    def after_user(self) -> "Call":
        """The calls and results since the last user message: what this turn did so far."""
        out = Call(self.msgs[:1] + self.msgs[self.at + 1:], None)
        out.names, out.tools, out.last_user = self.names, self.tools, self.last_user
        return out


def builder_default(c: Call) -> dict:
    """The builder scenario when a test sets none: it cannot propose yet and asks."""
    return {"reply": "I need to know more.", "proposals": [
        {"action": "clarify", "question": "What should the agent handle?", "reason": "the request names no work"}]}


def eval_leader(c: Call):
    """The platform's leader of a specialist's evaluation, as its instructions say: make the team, create the one
    specialist it may create with the resident's message as its task, wait for the report, finish."""
    if c.called("CaseFinalize"):
        return "Done."
    if c.called("TeamCreate") == 0:
        return [("TeamCreate", {"name": "eval-team", "description": "Evaluate one specialist"})]
    done = [("CaseFinalize", {"answer": "Evaluation finished.", "outcome": "needs_human", "unknowns": ["evaluation only"]})]
    if c.called("AgentCreate") == 0:
        schema = next(t["function"]["parameters"] for t in c.tools if t["function"]["name"] == "AgentCreate")
        kinds = (schema["properties"].get("subagent_type") or {}).get("enum") or []
        if not kinds:
            return done
        task = re.search(r"<resident-message[^>]*>\n(.*?)\n</resident-message>", c.last_user, re.S)
        return [("AgentCreate", {"name": "subject", "description": "The specialist under evaluation",
                                 "subagent_type": kinds[0], "prompt": task.group(1) if task else c.last_user})]
    if re.search(r"\bR\d+ \S+ reported:", c.blob) or not all("subject" in r for r in c.results("AgentCreate")):
        return done
    return "Waiting for the specialist."


def policy(msgs: list[dict], tools: list[dict]) -> list[tuple[str, dict]] | str:
    sp = _system(msgs)
    blob = " ".join(_text(m) for m in msgs if m.get("role") != "system")
    names = [t["function"]["name"] for t in tools or []]

    if names == [STRUCTURED]:  # the agent builder asking for its structured answer
        return [(STRUCTURED, (MODE["builder"] or builder_default)(Call(msgs, tools)))]
    for key, script in MODE["agents"].items():
        if f'key="{key}"' in sp:
            return script(Call(msgs, tools))
    if 'key="awp_eval_leader"' in sp:
        return (MODE["eval_leader"] or eval_leader)(Call(msgs, tools))

    if MODE["script"] is not None and 'key="supervisor"' in sp:
        return MODE["script"](Call(msgs, tools))
    if MODE["worker"] is not None and 'key="tech"' in sp:
        return MODE["worker"](Call(msgs, tools))
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
            if not any("Not accepted" in t for t in tries):  # first real attempt invents a figure on purpose
                return [("CaseFinalize", {"answer": "Repair costs 2000000 VND.", "outcome": "resolved", "cites": cites})]
            if tries[-1].startswith("Not "):  # refused (not accepted, or told to wait): try again with the right figure
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
        leader = 'key="supervisor"' in _system(msgs)
        if leader and MODE["leader_delay"]:
            await asyncio.sleep(MODE["leader_delay"])
        if MODE["delay"] is not None:
            await asyncio.sleep(MODE["delay"](_system(msgs)) or 0)
        gate = MODE["leader_gate"]
        if leader and gate is not None:
            for _ in range(4000):  # 40 s at most: a test that forgets to open the gate fails instead of hanging
                if gate.is_set():
                    break
                await asyncio.sleep(0.01)
        if leader and MODE["leader_http"]:
            CALLS.append({"sys": _system(msgs)[:80], "tools": [], "out": f"http {MODE['leader_http']}",
                          "last_user": Call(msgs, tools).last_user})
            return JSONResponse({"error": {"message": "scripted failure", "type": "invalid_request_error"}},
                                status_code=MODE["leader_http"])
        if MODE["worker_http"] and 'key="tech"' in _system(msgs):
            return JSONResponse({"error": {"message": "scripted failure", "type": "invalid_request_error"}},
                                status_code=MODE["worker_http"])
        out = policy(msgs, tools)
        gate = MODE["answer_gate"]
        if gate is not None and 'key="tech"' in _system(msgs) and isinstance(out, list) and any(n == "CaseAnswer" for n, _ in out):
            while not gate.is_set():  # the answer to a peer question comes late: when the test lets it
                await asyncio.sleep(0.05)
        CALLS.append({"sys": _system(msgs)[:80], "tools": [t["function"]["name"] for t in tools or []],
                      "out": out if isinstance(out, str) else [(n, a) for n, a in out],
                      "last_user": Call(msgs, tools).last_user,
                      "shape": [(m.get("role"), _text(m)[:1600], [tc["function"]["name"] for tc in m.get("tool_calls") or []])
                                for m in msgs if m.get("role") != "system"]})
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
