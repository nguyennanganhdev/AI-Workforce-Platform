"""Scripted model for the room scenario (see drive_room.py). No real model.

Leader (the console Leader; system prompt has PARTNER CASE POLICY):
  handover            -> TeamCreate -> AgentInvite(KyThuat: assess; DieuPhoi: dispatch, depends_on KyThuat)
                      -> end of reply
  "Thành viên đã báo về" (the runtime's nudge once the room reported)
                      -> CaseSay citing every E label of the reports -> end
  provider event      -> CaseSay(expects="confirmation") -> end
Members (system prompt has PARTNER CASE MEMBER POLICY), told apart by their tools:
  KyThuat  (vh_ticket_get only)          -> vh_ticket_get -> TeamSay(result with its E label);
                                            a teammate's question -> TeamSay(answer)
  DieuPhoi (has vh_work_order_dispatch)  -> TeamSay(question, to=KyThuat) about the assessment -> waits;
                                            the answer -> vh_work_order_dispatch -> TeamSay(result, E label, proposed sentence)
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
    found = re.search(r"ticket_id: ?([A-Za-z0-9][\w-]*)", json.dumps(messages, ensure_ascii=False))
    return found.group(1) if found else "unknown"


def _report_labels(messages) -> list[str]:
    """The E labels the members' reports cite (they are in the Leader's inbox)."""
    found = re.findall(r"Bằng chứng (E\d+)", json.dumps(messages, ensure_ascii=False))
    return list(dict.fromkeys(found))


def _effective(messages):
    """Drop what the runtime appends after each step (the Shared Context packet,
    system reminders) so the script reacts to the last real step; the runtime's
    nudge after the members' reports is kept."""
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
        if name == "TeamCreate":
            invite = next(t for t in tools if t["function"]["name"] == "AgentInvite")
            targets = invite["function"]["parameters"]["properties"]["target"]["enum"]
            expert = next(t for t in targets if "KyThuat" in t)
            coordinator = next(t for t in targets if "DieuPhoi" in t)
            return ("tool", "AgentInvite", {
                "target": expert,
                "prompt": f"ticket_id: {_ticket(messages)}\nĐánh giá sự cố, cần thợ chuyên môn gì.",
                "done_when": "Có kết luận kèm mã E của kết quả công cụ.",
                "additional_assignments": [{
                    "target": coordinator,
                    "prompt": f"ticket_id: {_ticket(messages)}\nGiao việc cho nhân viên theo đánh giá kỹ thuật, "
                              "báo lại kèm mã E và câu đề xuất gửi người dùng.",
                    "done_when": "Đã giao việc, có mã E của kết quả giao việc.",
                    "depends_on": [expert],
                }],
            })
        if name == "AgentInvite":
            return ("text", "Đã giao việc cho phòng, chờ báo cáo.", None)
        return ("text", "Xong lượt.", None)
    if "Thành viên đã báo về" in tail:
        return ("tool", "CaseSay", {
            "text": "Chào bạn, chuyên viên kỹ thuật đã đánh giá sự cố và yêu cầu đã được gửi cho thợ, đang chờ người nhận.",
            "expects": "none",
            "cites": _report_labels(everything),
        })
    if "Sự kiện" in _text(last):
        return ("tool", "CaseSay", {"text": "Đã có kết quả, bạn xác nhận hoàn thành giúp tôi.", "expects": "confirmation", "cites": []})
    return ("tool", "TeamCreate", {"name": "Phòng phiếu", "description": "Đánh giá kỹ thuật rồi giao việc"})


def _calls(messages, tool, kind=None):
    """How many times this agent already called ``tool`` (with ``kind``)."""
    count = 0
    for message in messages:
        for call in message.get("tool_calls") or []:
            if call["function"]["name"] != tool:
                continue
            if kind is None or json.loads(call["function"]["arguments"] or "{}").get("kind") == kind:
                count += 1
    return count


def _member(messages, tools):
    ticket = _ticket(messages)  # the assignment arrives as a system reminder
    names = {t["function"]["name"] for t in tools}
    # Team messages arrive as <team-message ... kind="..."> tags (not the policy text).
    history = " ".join(_text(m) for m in messages if m.get("role") != "system")
    effective = _effective(messages)
    last = effective[-1]
    if last.get("role") == "tool":
        name = _last_tool(effective)
        label = (re.match(r"\s*(E\d+):", _text(last)) or [None, None])[1]
        if name == "vh_ticket_get":
            return ("tool", "TeamSay", {
                "kind": "result",
                "content": f"Kết luận: cần thợ điện kiểm tra ổ cắm và aptomat. Bằng chứng {label}.",
            })
        if name == "vh_work_order_dispatch":
            return ("tool", "TeamSay", {
                "kind": "result",
                "content": f"Đã giao việc cho thợ điện, đang chờ người nhận. Đã làm rõ với chuyên viên kỹ thuật: "
                           f"cần thợ điện vì có mùi khét. Bằng chứng {label}. "
                           "Đề xuất: Yêu cầu của bạn đã được gửi cho thợ điện, đang chờ người nhận.",
            })
        return ("text", "Đã gửi.", None)
    if "vh_work_order_dispatch" in names:
        # DieuPhoi: checks the assessment it depends on, asks once, then dispatches.
        expert = re.search(r"Inputs from teammates: (\S+?)[ ,(]", history)
        if _calls(messages, "TeamSay", "question") == 0 and expert:
            return ("tool", "TeamSay", {
                "kind": "question",
                "to": expert.group(1),
                "content": "Đánh giá E1 ghi cần thợ điện, nhưng phiếu chỉ tả rò nước bồn rửa. "
                           "Bạn chắc là thợ điện, không phải thợ nước?",
            })
        if 'kind="answer">' in history and _calls(messages, "vh_work_order_dispatch") == 0:
            return ("tool", "vh_work_order_dispatch", {"ticket_id": ticket, "description": "Kiểm tra ổ cắm bếp có mùi khét"})
        return ("text", "Chờ chuyên viên trả lời.", None)
    # KyThuat: assesses, and answers a teammate's question.
    if history.count('kind="question">') > _calls(messages, "TeamSay", "answer"):
        return ("tool", "TeamSay", {
            "kind": "answer",
            "content": "Đúng là thợ điện: cư dân báo ổ cắm bếp có mùi khét, nước rò gần ổ cắm. Bằng chứng E1.",
        })
    if _calls(messages, "vh_ticket_get") == 0:
        return ("tool", "vh_ticket_get", {"ticket_id": ticket})
    return ("text", "Đã báo.", None)


@app.get("/v1/models")
async def models():
    return {"object": "list", "data": [{"id": "gpt-5.4-mini", "object": "model"}, {"id": "gpt-5.5", "object": "model"}]}


@app.post("/v1/chat/completions")
async def chat(request: Request):
    body = await request.json()
    messages, tools = body["messages"], body.get("tools") or []
    system = " ".join(_text(m) for m in messages if m.get("role") == "system")
    role = "member" if "PARTNER CASE MEMBER POLICY" in system else "leader" if "PARTNER CASE POLICY" in system else "other"
    if role == "member":
        kind, name, args = _member(messages, tools)
    elif role == "leader":
        kind, name, args = _leader(messages, tools)
    else:
        kind, name, args = "text", "ok", None
    tail = [[m.get("role"), m.get("name"), _text(m)[:60]] for m in messages[-3:]]
    print(json.dumps({"role": role, "model": body.get("model"), "tools": [t["function"]["name"] for t in tools],
                      "decision": [kind, name, args], "tail": tail}, ensure_ascii=False), flush=True)
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
