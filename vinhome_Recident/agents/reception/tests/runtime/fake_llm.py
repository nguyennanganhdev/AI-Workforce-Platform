"""Deterministic chat-completions server for end-to-end tests; never used by the service itself."""

import json

from fastapi import FastAPI, Request

app = FastAPI()
INCIDENT_WORDS = ("hỏng", "rò", "không hoạt động", "không có điện", "sửa")


def details(text):
    """What a careful model quotes from "X bị Y": the thing before "bị", the symptom from it on.

    Like a real model it also adds a cause the resident never gave; the backend must drop it.
    """
    thing, found, symptom = text.partition(" bị ")
    quoted = {"symptom": ("bị " + symptom) if found else text, "cause": "ống âm tường bị vỡ từ sáng"}
    if found:
        quoted["item"] = thing
    if "không biết" in text.lower():
        quoted["item_unknown"] = text
    return quoted


def assessment(data):
    text, active = data["message"]["text"].lower(), data.get("active_ticket_id")
    incident = any(word in text for word in INCIDENT_WORDS)
    return {
        "intent": "ticket_follow_up" if active else "incident" if incident else "information",
        "proposed_action": "continue_existing_ticket" if active else "start_ticket" if incident else "retrieve_knowledge",
        "explicit_staff_request": False,
        "self_help_declined": False,
        "self_help_failed": False,
        "emergency_signals": [],
        "missing_information": [],
        "reason": "Phân loại theo nội dung tin nhắn.",
    }


def turn(data):
    message = data["message"]
    text = message["text"]
    if "tiến độ" in text.lower():
        return {"intent": "status", "facts": [], "answers": {}}
    if "hủy" in text.lower():
        return {"intent": "cancel", "facts": [], "answers": {}}
    source = (data.get("pending_incident_messages") or [message])[-1]["id"]
    facts = [{"key": key, "value": value, "source": "customer_report", "source_message_id": source}
             for key, value in details(text).items()]
    if "có vẻ" in text.lower():
        # Real models add their own guesses, labelled as such and citing the resident's message.
        facts.append({"key": "cause", "value": "chập điện", "source": "agent_inference", "source_message_id": source})
    # Title and description as a real model words them: not what the backend records.
    return {"intent": "information", "title": "Sự cố kỹ thuật nghiêm trọng", "description": "Ống âm tường bị vỡ, nước ngập sàn.",
            "facts": facts, "answers": {}}


def proposal(data):
    codes = [c["code"] for c in data["categories"]]
    return {"category_code": "technical" if "technical" in codes else codes[0],
            "priority": "normal", "severity": "minor", "reason": "Sự cố thiết bị trong căn hộ."}


def agent_step(messages):
    """The model-led agent (src/agent): one tool for the resident's message, then a reply from its result."""
    def tool(name, **arguments):
        return {"role": "assistant", "content": None, "tool_calls": [{
            "id": "call-1", "type": "function", "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)}}]}

    def reply(text, sources=()):
        return {"role": "assistant", "content": json.dumps({"reply": text, "sources": list(sources)}, ensure_ascii=False)}

    last = messages[-1]
    if last["role"] == "tool":
        result = json.loads(last["content"])
        if result.get("filed"):
            return reply("Mình đã ghi nhận yêu cầu của bạn và chuyển tới Ban quản lý.")
        if "status" in result:
            return reply(f"Yêu cầu của bạn {result['status']}.")
        if result.get("passages"):
            return reply(result["passages"][0]["text"], [result["passages"][0]["rank"]])
        if "passages" in result:
            return reply("Mình chưa có thông tin chính thức về việc này. Bạn vui lòng liên hệ trực tiếp Ban quản lý nhé.")
        if result.get("error") == "conversation_has_open_request":
            return reply("Mình đã ghi nhận thêm thông tin cho yêu cầu đang mở của bạn.")
        return reply("Mình chưa hỗ trợ được việc này.")
    text = last["content"]
    if "tiến độ" in text.lower():
        return tool("request_status")
    # Everything the resident said so far in this conversation, as a model reads it.
    said = " ".join(m["content"] for m in messages if m["role"] == "user")
    if any(word in said.lower() for word in INCIDENT_WORDS):
        quoted = details(next(m["content"] for m in messages if m["role"] == "user" and " bị " in m["content"]) if " bị " in said else text)
        if "không biết" in text.lower():
            quoted["item_unknown"] = text
        elif text != said and " bị " not in text:
            # The answer to a question about the exact spot.
            quoted["item"] = text
        # The tool has no place for a cause; the invented detail goes where a model would put it.
        quoted["area"] = quoted.pop("cause")
        return tool("file_request", kind="incident", category_code="technical", priority="normal", **quoted)
    return tool("search_knowledge", query=text)


@app.post("/chat/completions")
async def completions(request: Request):
    body = await request.json()
    assert body["response_format"] == {"type": "json_object"}
    if "tools" in body:
        return {"choices": [{"message": agent_step(body["messages"])}]}
    system, user = body["messages"][0]["content"], json.loads(body["messages"][1]["content"])
    if '"route"' in system:
        return {"choices": [{"message": {"role": "assistant", "content": json.dumps({"route": "management"})}}]}
    if '"used"' in system:
        answer = {"answer": user["passages"][0]["text"], "used": [user["passages"][0]["rank"]]}
    else:
        answer = assessment(user) if "NODE assess_request" in system else proposal(user) if "category_code" in system else turn(user)
    return {"choices": [{"message": {"role": "assistant", "content": json.dumps(answer, ensure_ascii=False)}}]}


RUN, DOCUMENT, VERSION, CHUNK = (f"{n}{n}{n}{n}{n}{n}{n}{n}-{n}{n}{n}{n}-4{n}{n}{n}-8{n}{n}{n}-{n}{n}{n}{n}{n}{n}{n}{n}{n}{n}{n}{n}" for n in "abcd")


@app.post("/internal/knowledge/search")
async def search(request: Request):
    """Shaped like search_knowledge v1; one passage about the management fee, nothing else."""
    body = await request.json()
    assert set(body) <= {"query", "topK", "scopeId"} and request.headers["authorization"].startswith("Bearer ")
    hits = [{"rank": 1, "chunkId": CHUNK, "documentId": DOCUMENT, "versionId": VERSION, "title": "Biểu phí",
             "section": None, "text": "Phí quản lý là 12.000 đồng mỗi mét vuông mỗi tháng.", "similarity": 0.8, "score": 0.8,
             "reliability": "van_ban_bql", "scope": {}, "kind": "fee", "collectionStatus": None, "updatedAt": None,
             "unverified": False, "sources": []}] if "phí quản lý" in body["query"].lower() else []
    return {"retrievalRunId": RUN, "policyVersion": "acl-first-hybrid-3", "insufficientSources": not hits, "hits": hits}
