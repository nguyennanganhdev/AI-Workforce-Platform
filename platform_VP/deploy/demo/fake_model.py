"""A scripted OpenAI-compatible model for the `demo` profile of deploy/compose.yml (made from tests/fake_llm.py).

It lets deploy/smoke.py prove the image and the wiring with NO model key and no cost. It proves nothing about how a
real model behaves: every answer below is a fixed script.

What the script plays, for whichever agent asks:
- a resident who asks to book a repair -> call the partner tool `book_repair` once, then tell the resident what the
  tool answered;
- a provider event that wakes the leader -> tell the resident, and ask for confirmation when the work is finished;
- anything else (the platform's evaluation cases included) -> record that it does not know, and say so;
- the agent builder -> asks a question back.

Run: python fake_model.py   (listens on 0.0.0.0:8900; GET /health, POST /v1/chat/completions)
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

STRUCTURED = "generate_structured_output"  # the tool AgentScope forces for a structured answer
HINTS = ("<system-reminder", "<workflow-state", "<room-digest")  # reminders the room adds as user messages
ACTION = "book_repair"
CALLS = {"requests": 0}


def text_of(m: dict) -> str:
    c = m.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(p.get("text", "") for p in c if isinstance(p, dict))
    return ""


class Call:
    """One request to the model, with the questions the script asks about it."""

    def __init__(self, msgs: list[dict], tools: list[dict] | None) -> None:
        self.msgs = msgs
        self.names = [t["function"]["name"] for t in tools or []]
        # what started this turn: the last user message that is not one of the room's own reminders
        self.at = max((i for i, m in enumerate(msgs) if m.get("role") == "user"
                       and not text_of(m).startswith(HINTS)), default=-1)
        self.last_user = text_of(msgs[self.at]) if self.at >= 0 else ""
        self.turn = msgs[self.at + 1:]  # the calls and results since then: what this turn did so far

    def called(self, name: str) -> int:
        return sum(1 for m in self.turn for tc in (m.get("tool_calls") or []) if tc["function"]["name"] == name)

    def results(self, name: str) -> list[str]:
        ids = [tc["id"] for m in self.turn for tc in (m.get("tool_calls") or []) if tc["function"]["name"] == name]
        return [text_of(m) for m in self.turn if m.get("role") == "tool" and m.get("tool_call_id") in ids]


def say(text: str, expects: str = "none", cites: list[str] | None = None) -> list:
    return [("CaseSay", {"text": text, "expects": expects, "cites": cites or []})]


def evidence_of(text: str) -> list[str]:
    return re.findall(r"\[evidence (E\d+)\]", text)


def script(c: Call):
    if c.names == [STRUCTURED]:  # the agent builder
        return [(STRUCTURED, {"reply": "I need to know more.", "proposals": [
            {"action": "clarify", "question": "What should the agent handle?", "reason": "the request names no work"}]})]
    if "CaseSay" not in c.names:  # not a leader inside a workflow: nothing scripted for it
        return "ok"
    said = c.called("CaseSay")

    if "<provider-event" in c.last_user:  # the partner's backend reported something that wakes the leader
        if said:
            return "Said."
        ev = re.search(r'evidence="(E\d+)"', c.last_user)
        cites = [ev.group(1)] if ev else []
        if re.search(r'type="[^"]*(completed|finished|done)"', c.last_user):
            return say("The partner reports the work finished. Is everything right?", "confirmation", cites)
        return say("The partner sent an update.", "none", cites)

    if ACTION in c.names and re.search(r"\b(book|schedule)\b.*\brepair\b", c.last_user, re.I | re.S):
        if c.called(ACTION) == 0:
            return [(ACTION, {"slot": "monday"})]
        if said:
            return "Said."
        got = " ".join(c.results(ACTION))
        if evidence_of(got):
            return say("I asked for the visit on Monday; it is pending.", "none", evidence_of(got)[:1])
        return say("Understood, nothing was requested. Anything else?", "reply")

    # everything else: it does not know, records that, and says so (no figure, no date, no promise)
    if c.called("CaseGap") == 0 and "CaseGap" in c.names:
        return [("CaseGap", {"topic": "what the resident asked", "tried": "none of my tools answers this"})]
    if said:
        return "Said."
    return say("I do not know that yet. A person will follow up with you.", "reply")


def chunk(cid: str, delta, finish=None, usage=None) -> str:
    body = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()), "model": "demo-scripted",
            "choices": [] if usage else [{"index": 0, "delta": delta, "finish_reason": finish}]}
    if usage:
        body["usage"] = usage
    return "data: " + json.dumps(body, ensure_ascii=False) + "\n\n"


app = FastAPI(title="scripted demo model")


@app.get("/health")
async def health():
    return {"status": "ok", "requests": CALLS["requests"]}


@app.post("/v1/chat/completions")
async def completions(req: Request):
    body = await req.json()
    msgs, tools = body.get("messages", []), body.get("tools")
    CALLS["requests"] += 1
    out = script(Call(msgs, tools))
    cid = "chatcmpl-" + uuid.uuid4().hex[:8]
    ptok = sum(len(json.dumps(m, ensure_ascii=False)) for m in msgs) // 4

    def usage(completion: int) -> dict:
        return {"prompt_tokens": ptok, "completion_tokens": completion, "total_tokens": ptok + completion}

    async def gen():
        if isinstance(out, str):
            yield chunk(cid, {"role": "assistant", "content": ""})
            for i in range(0, len(out), 16):
                yield chunk(cid, {"content": out[i:i + 16]})
            yield chunk(cid, {}, "stop")
            yield chunk(cid, None, usage=usage(max(1, len(out) // 4)))
        else:
            yield chunk(cid, {"role": "assistant", "content": None})
            for i, (name, args) in enumerate(out):
                yield chunk(cid, {"tool_calls": [{"index": i, "id": f"call_{uuid.uuid4().hex[:8]}", "type": "function",
                                                  "function": {"name": name, "arguments": ""}}]})
                yield chunk(cid, {"tool_calls": [{"index": i, "function": {"arguments": json.dumps(args)}}]})
            yield chunk(cid, {}, "tool_calls")
            yield chunk(cid, None, usage=usage(30 * len(out)))
        yield "data: [DONE]\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("DEMO_MODEL_PORT", "8900")), log_level="warning")
