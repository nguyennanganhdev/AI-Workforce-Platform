"""Scripted OpenAI-compatible chat model for an offline end-to-end check.

Turn script (by the last message of the request):
  user message                -> call vh_ticket_get(ticket_id)
  tool result of vh_ticket_get -> call vh_work_order_dispatch(ticket_id, description)
  tool result of dispatch      -> call CaseSay(text, expects="none", cites=[E of dispatch])
  tool result of CaseSay       -> plain text (end of turn)
  user message with "Sự kiện"  -> CaseSay(..., expects="confirmation")
No real model is called. Requests are logged to stdout for inspection.
"""

import json
import re
import sys
import time
import uuid

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI()
LOG = []


def _last_tool_name(messages):
    for message in reversed(messages):
        if message.get("role") == "assistant" and message.get("tool_calls"):
            return message["tool_calls"][-1]["function"]["name"]
    return None


def _decide(messages):
    last = messages[-1]
    if last.get("role") == "tool":
        name = _last_tool_name(messages)
        content = last.get("content")
        if isinstance(content, list):
            content = " ".join(part.get("text", "") for part in content if isinstance(part, dict))
        label = (re.match(r"\s*(E\d+):", content or "") or [None, None])[1]
        if name == "vh_ticket_get":
            ticket = re.search(r"ticket_id: (\S+)", json.dumps(messages, ensure_ascii=False))
            return ("tool", "vh_work_order_dispatch", {
                "ticket_id": ticket.group(1) if ticket else "unknown",
                "description": "Sửa rò nước bồn rửa bếp",
            })
        if name == "vh_work_order_dispatch":
            return ("tool", "CaseSay", {
                "text": "Chào anh/chị, tôi là trợ lý điều phối của Ban quản lý. Yêu cầu đã được gửi cho nhân viên và đang chờ người nhận.",
                "expects": "none",
                "cites": [label] if label else [],
            })
        return ("text", "Xong lượt.", None)
    text = last.get("content")
    if isinstance(text, list):
        text = " ".join(part.get("text", "") for part in text if isinstance(part, dict))
    if "Sự kiện" in (text or ""):
        return ("tool", "CaseSay", {
            "text": "Nhân viên đã gửi kết quả nghiệm thu phía trên. Anh/chị xem rồi xác nhận hoàn thành giúp tôi.",
            "expects": "confirmation",
            "cites": [],
        })
    ticket = re.search(r"ticket_id: (\S+)", text or "")
    return ("tool", "vh_ticket_get", {"ticket_id": ticket.group(1) if ticket else "unknown"})


@app.get("/v1/models")
async def models():
    return {"object": "list", "data": [{"id": "gpt-5.4-mini", "object": "model"}, {"id": "gpt-5.5", "object": "model"}]}


@app.post("/v1/chat/completions")
async def chat(request: Request):
    body = await request.json()
    kind, name, args = _decide(body["messages"])
    tools = [t["function"]["name"] for t in body.get("tools") or []]
    system = " ".join(str(m.get("content")) for m in body["messages"] if m.get("role") == "system")
    LOG.append({"model": body.get("model"), "tools": tools, "decision": [kind, name, args],
                "partner_policy": "PARTNER CASE POLICY" in system, "teamsay_policy": 'TeamSay(kind="result")' in system,
                "leader_instructions": "Tra phiếu, giao việc" in system})
    print(json.dumps(LOG[-1], ensure_ascii=False), flush=True)
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
