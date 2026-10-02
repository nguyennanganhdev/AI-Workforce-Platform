"""Deterministic chat-completions server for end-to-end tests; never used by the service itself."""

import json

from fastapi import FastAPI, Request

app = FastAPI()
INCIDENT_WORDS = ("hỏng", "rò", "không hoạt động", "không có điện", "sửa")


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
    facts = [{"key": "reported", "value": text[:100], "source": "customer_report", "source_message_id": source}]
    if "có vẻ" in text.lower():
        # Real models add their own guesses, labelled as such and citing the resident's message.
        facts.append({"key": "cause", "value": "chập điện", "source": "agent_inference", "source_message_id": source})
    return {"intent": "information", "title": text[:60], "description": text, "facts": facts, "answers": {}}


def proposal(data):
    codes = [c["code"] for c in data["categories"]]
    return {"category_code": "technical" if "technical" in codes else codes[0],
            "priority": "normal", "severity": "minor", "reason": "Sự cố thiết bị trong căn hộ."}


@app.post("/chat/completions")
async def completions(request: Request):
    body = await request.json()
    system, user = body["messages"][0]["content"], json.loads(body["messages"][1]["content"])
    assert body["response_format"] == {"type": "json_object"}
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
