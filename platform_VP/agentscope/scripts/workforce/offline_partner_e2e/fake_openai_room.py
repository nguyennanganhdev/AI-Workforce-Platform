"""Scripted model for the room scenario (see drive_room.py). No real model.

Leader (system prompt has PARTNER CASE POLICY):
  handover            -> TeamCreate -> AgentInvite(first member, with the ticket id) -> end of reply
  "Thành viên đã báo về" (the runtime's nudge after the member reported)
                      -> vh_work_order_dispatch -> CaseSay citing the member's evidence label -> end
Member (system prompt has PARTNER CASE MEMBER POLICY):
  assignment          -> vh_ticket_get -> TeamSay(kind="result", with the E label) -> end
"""

import json
import re
import sys
import time
import uuid

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

sys.stdout.reconfigure(encoding="utf-8")
app = FastAPI()


def _text(message) -> str:
    content = message.get("content")
    if isinstance(content, list):
        return " ".join(part.get("text", "") for part in content if isinstance(part, dict))
    return content or ""


def _last_tool(messages):
    for message in reversed(messages):
        if message.get("role") == "assistant" and message.get("tool_calls"):
            return message["tool_calls"][-1]["function"]["name"]
    return None


def _ticket(messages) -> str:
    found = re.search(r"ticket_id: ?(T-[\w-]+)", json.dumps(messages, ensure_ascii=False))
    return found.group(1) if found else "unknown"


def _member_label(messages) -> str | None:
    """The E label the member's report cites (it is in the leader's inbox)."""
    for message in reversed(messages):
        found = re.search(r"Bằng chứng (E\d+)", _text(message))
        if found:
            return found.group(1)
    return None


def _effective(messages):
    """Drop what the runtime appends after each step (the Shared Context packet,
    system reminders) so the script reacts to the last real step; the runtime's
    nudge after a member's report is kept."""
    out = list(messages)
    while out and (out[-1].get("name") == "shared_context" or (
            _text(out[-1]).startswith("<system-reminder>") and "Thành viên đã báo về" not in _text(out[-1]))):
        out.pop()
    return out


def _leader(messages, tools):
    everything = messages
    messages = _effective(messages)
    last = messages[-1]
    tail = " ".join(_text(m) for m in messages[-3:])
    if last.get("role") == "tool":
        name = _last_tool(messages)
        label = (re.match(r"\s*(E\d+):", _text(last)) or [None, None])[1]
        if name == "TeamCreate":
            invite = next(t for t in tools if t["function"]["name"] == "AgentInvite")
            target = invite["function"]["parameters"]["properties"]["target"]["enum"][0]
            return ("tool", "AgentInvite", {
                "target": target,
                "prompt": f"ticket_id: {_ticket(messages)}\nĐánh giá sự cố ổ cắm có mùi khét, cần chuyên môn gì.",
                "done_when": "Có kết luận kèm mã E của kết quả công cụ.",
            })
        if name == "AgentInvite":
            return ("text", "Đã giao cho chuyên viên, chờ báo cáo.", None)
        if name == "vh_work_order_dispatch":
            cites = [x for x in (_member_label(everything), label) if x]
            return ("tool", "CaseSay", {
                "text": "Chào anh/chị, chuyên viên kỹ thuật đã đánh giá sự cố và yêu cầu đã được gửi cho thợ điện, đang chờ người nhận.",
                "expects": "none",
                "cites": cites,
            })
        return ("text", "Xong lượt.", None)
    if "Thành viên đã báo về" in tail:
        return ("tool", "vh_work_order_dispatch", {"ticket_id": _ticket(messages), "description": "Kiểm tra ổ cắm bếp có mùi khét"})
    if "Sự kiện" in _text(last):
        return ("tool", "CaseSay", {"text": "Đã có cập nhật, anh/chị xác nhận giúp tôi.", "expects": "confirmation", "cites": []})
    return ("tool", "TeamCreate", {"name": "Phòng phiếu", "description": "Đánh giá kỹ thuật trước khi giao việc"})


def _member(messages):
    ticket = _ticket(messages)  # the assignment arrives as a system reminder
    messages = _effective(messages)
    last = messages[-1]
    if last.get("role") == "tool":
        name = _last_tool(messages)
        label = (re.match(r"\s*(E\d+):", _text(last)) or [None, None])[1]
        if name == "vh_ticket_get":
            return ("tool", "TeamSay", {
                "kind": "result",
                "content": f"Kết luận: cần thợ điện kiểm tra ổ cắm và aptomat. Bằng chứng {label}.",
            })
        return ("text", "Đã báo leader.", None)
    return ("tool", "vh_ticket_get", {"ticket_id": ticket})


@app.get("/v1/models")
async def models():
    return {"object": "list", "data": [{"id": "gpt-5.4-mini", "object": "model"}, {"id": "gpt-5.5", "object": "model"}]}


@app.post("/v1/chat/completions")
async def chat(request: Request):
    body = await request.json()
    messages, tools = body["messages"], body.get("tools") or []
    system = " ".join(_text(m) for m in messages if m.get("role") == "system")
    role = "member" if "PARTNER CASE MEMBER POLICY" in system else "leader" if "PARTNER CASE POLICY" in system else "other"
    kind, name, args = _member(messages) if role == "member" else _leader(messages, tools) if role == "leader" else ("text", "ok", None)
    tail = [[m.get("role"), m.get("name"), _text(m)[:60]] for m in messages[-3:]]
    print(json.dumps({"role": role, "tools": [t["function"]["name"] for t in tools], "decision": [kind, name, args],
                      "tail": tail}, ensure_ascii=False), flush=True)
    created, cid = int(time.time()), "chatcmpl-" + uuid.uuid4().hex[:12]
    if kind == "tool":
        call = {"index": 0, "id": "call_" + uuid.uuid4().hex[:10], "type": "function",
                "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)}}
        delta, finish, message = {"role": "assistant", "content": None, "tool_calls": [call]}, "tool_calls", {
            "role": "assistant", "content": None, "tool_calls": [{k: v for k, v in call.items() if k != "index"}]}
    else:
        delta, finish, message = {"role": "assistant", "content": name}, "stop", {"role": "assistant", "content": name}
    usage = {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}
    if not body.get("stream"):
        return JSONResponse({"id": cid, "object": "chat.completion", "created": created, "model": body.get("model"),
                             "choices": [{"index": 0, "message": message, "finish_reason": finish}], "usage": usage})

    def events():
        base = {"id": cid, "object": "chat.completion.chunk", "created": created, "model": body.get("model")}
        yield "data: " + json.dumps({**base, "choices": [{"index": 0, "delta": delta, "finish_reason": None}]}, ensure_ascii=False) + "\n\n"
        yield "data: " + json.dumps({**base, "choices": [{"index": 0, "delta": {}, "finish_reason": finish}]}) + "\n\n"
        yield "data: " + json.dumps({**base, "choices": [], "usage": usage}) + "\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(sys.argv[1]) if len(sys.argv) > 1 else 18080, log_level="warning")
