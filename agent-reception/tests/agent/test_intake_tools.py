"""The real toolbox with a scripted model: what reaches the backend when the model files a request.

The intake rules themselves live in the backend (services/vinhomes-api, tests/test_reception_intake.py);
here the backend's verdict is scripted and the payloads the runtime sends are checked.
"""

import asyncio
import json

from src.agent.loop import run_agent
from src.agent.tools import Toolbox
from src.runtime.service import agent_turn

CONTEXT = {"channelId": "chat-1", "requestId": "m1"}
HOME = {"domain_id": "d1", "building_id": "b1", "unit_id": "u1", "unit_code": "1201", "building_name": "S1.01"}
CATEGORIES = [{"id": "c1", "code": "technical", "name": "Kỹ thuật"}]
QUESTION = "Bạn thấy nước rò ở đâu trong nhà tắm: vòi, ống, bồn cầu, tường hay trần? Nếu chưa xác định được, bạn cứ nói chưa rõ nhé."
LEAK = "Nhà tắm của tôi bị rò nước"


def fact(key, value, message="m1"):
    return {"key": key, "value": value, "source": "customer_report", "source_message_id": message}


def verdict(ready, facts=(), rejected=(), description=LEAK, review=False):
    return {"ready": ready, "review": review, "missing": None if ready else "item", "question": None if ready else QUESTION,
            "title": description.splitlines()[0], "description": description, "facts": list(facts),
            "rejected": list(rejected), "file_ids": []}


class Backend:
    """Records every call. `intake` is the backend's verdict for the details the model sends."""

    def __init__(self, intake, history=None, open_request=None, handoff=None):
        self.intake, self.calls, self.operations = intake, [], []
        self.history = history or [{"id": "m1", "role": "resident", "text": LEAK, "photos": 1}]
        self.open_request = open_request
        self.handoff = handoff or {"accepted": True, "ticket": {"id": "t1", "code": "VH-1"}}

    def authorization(self, context):
        return {}

    async def call(self, method, path, context, body=None):
        self.calls.append((path.rsplit("/", 1)[-1].split("?")[0], body))
        if "/context" in path:
            return {"history": self.history, "open_request": self.open_request, "past_requests": []}
        if path.endswith("/catalog"):
            return {"categories": CATEGORIES}
        if path.endswith("/policy/evaluate"):
            return {"emergency": False}
        if path.endswith("/intake"):
            return self.intake(body["details"])
        if path.endswith("/follow-up"):
            return {"attached": 1, "delivered": self.open_request.get("pending") == "information", "pending": self.open_request.get("pending")}
        return {"accepted": True}

    async def execute(self, context, operation, value, key):
        self.operations.append((operation, value, key))
        return {"get_verified_resident_context": {"resident": {"name": "Cư dân"}, "residences": [HOME]},
                "create_ticket_draft": {"draftId": "draft-1"},
                "resolve_management_destination": {"managementUnitId": "unit-1"},
                "handoff_ticket": self.handoff}.get(operation, {})

    def ran(self, name):
        return [value for operation, value, _ in self.operations if operation == name]


class Model:
    def __init__(self, *answers):
        self.answers, self.seen = list(answers), []

    async def complete(self, messages, tools):
        self.seen.append(messages)
        return self.answers.pop(0)


def calls(*named):
    return {"content": None, "tool_calls": [
        {"id": f"call-{index}", "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}
        for index, (name, arguments) in enumerate(named)]}


def file_request(**details):
    return ("file_request", {"kind": "incident", "category_code": "technical", "priority": "normal", **details})


def final(reply):
    return {"content": json.dumps({"reply": reply, "sources": []}, ensure_ascii=False)}


def turn(backend, model, message=None):
    return asyncio.run(agent_turn(backend, None, model, None, CONTEXT, message or {"id": "m1", "text": LEAK, "fileIds": ["f1"]}))


def test_a_vague_leak_gets_the_backends_question_and_nothing_is_filed():
    backend = Backend(lambda details: verdict(False, [fact("symptom", "bị rò nước")]))
    # The model wants to file at once, and to say so.
    model = Model(calls(file_request(symptom="bị rò nước", area="Nhà tắm")), final("Mình đã ghi nhận và gửi Ban quản lý."))
    reply, asked = turn(backend, model)
    assert reply == QUESTION and asked == "item"
    assert backend.operations == [backend.operations[0]] and backend.operations[0][0] == "get_verified_resident_context"
    assert len(model.seen) == 1  # the model is not asked to reword the question


def test_invented_details_are_sent_for_checking_and_never_as_a_description():
    seen = {}

    def intake(details):
        seen.update(details)
        return verdict(False, [fact("symptom", "bị rò nước")], rejected=["item"])

    backend = Backend(intake)
    model = Model(calls(file_request(symptom="bị rò nước", item="ống âm tường bị vỡ từ sáng")))
    assert turn(backend, model)[0] == QUESTION
    assert seen == {"symptom": "bị rò nước", "item": "ống âm tường bị vỡ từ sáng"}
    assert backend.ran("update_ticket_incident") == [] and backend.ran("handoff_ticket") == []


def test_no_other_tool_hands_the_request_over_after_the_question():
    backend = Backend(lambda details: verdict(False))
    model = Model(calls(file_request(symptom="bị rò nước"), ("ask_management", {}), ("report_emergency", {}),
                        file_request(symptom="bị rò nước", item="ống vỡ")))
    assert turn(backend, model)[0] == QUESTION
    asked = [name for name, _ in backend.calls]
    assert asked.count("intake") == 1 and "inquiries" not in asked
    assert backend.ran("handoff_ticket") == [] and backend.ran("escalate_emergency") == []


def test_a_complete_report_is_filed_with_the_backends_facts_and_no_wording_of_the_model():
    history = [{"id": "m1", "role": "resident", "text": LEAK, "photos": 1},
               {"id": "a1", "role": "reception", "text": QUESTION, "photos": 0},
               {"id": "m2", "role": "resident", "text": "Rò ở chân vòi lavabo", "photos": 0}]
    facts = [fact("symptom", "bị rò nước"), fact("area", "Nhà tắm"), fact("item", "chân vòi lavabo", "m2")]
    backend = Backend(lambda details: verdict(True, facts, description=LEAK + "\nRò ở chân vòi lavabo"), history=history)
    model = Model(calls(file_request(symptom="bị rò nước", area="Nhà tắm", item="chân vòi lavabo")),
                  final("Mình đã ghi nhận sự cố và gửi Ban quản lý."))
    reply, asked = turn(backend, model, {"id": "m2", "text": "Rò ở chân vòi lavabo", "fileIds": []})
    assert reply == "Mình đã ghi nhận sự cố và gửi Ban quản lý." and asked is None
    fields = backend.ran("update_ticket_incident")[0]["fields"]
    assert fields["facts"] == facts and fields["source_message_id"] == "m2" and fields["request_kind"] == "incident"
    # Title, description and photos are the backend's to derive from the cited messages.
    assert not {"title", "description", "file_ids"} & set(fields)
    assert backend.ran("handoff_ticket")[0]["handoff_reason"] == "needs_staff"


def test_a_report_handed_over_after_two_questions_says_so_to_management():
    backend = Backend(lambda details: verdict(True, [fact("symptom", "bị rò nước")], review=True))
    turn(backend, Model(calls(file_request(symptom="bị rò nước")), final("Mình đã gửi Ban quản lý kiểm tra.")))
    assert "sau hai lần hỏi" in backend.ran("submit_ticket_assessment")[0]["assessment"]["reason"]


def test_a_refusal_at_handoff_is_reported_as_what_is_missing():
    backend = Backend(lambda details: verdict(True), handoff={"accepted": False, "missingFields": ["verified_resident_phone"]})
    toolbox = Toolbox(backend, None, None, CONTEXT, {"id": "m1", "text": LEAK}, None, {"homes": [HOME]}, CATEGORIES)
    result = asyncio.run(toolbox.call(*file_request(symptom="bị rò nước", item="vòi")))
    assert result["error"] == "resident_profile_incomplete" and toolbox.filed_code is None


def test_a_second_filing_in_one_turn_does_not_reuse_the_keys_of_the_first():
    backend = Backend(lambda details: verdict(True), handoff={"accepted": False, "missingFields": ["management_coverage"]})
    toolbox = Toolbox(backend, None, None, CONTEXT, {"id": "m1", "text": LEAK}, None, {"homes": [HOME]}, CATEGORIES)
    for _ in range(2):
        asyncio.run(toolbox.call(*file_request(symptom="bị rò nước", item="vòi")))
    keys = [key for operation, _, key in backend.operations if operation == "update_ticket_incident"]
    drafts = [key for operation, _, key in backend.operations if operation == "create_ticket_draft"]
    assert len(set(keys)) == 2 and len(set(drafts)) == 1


def test_an_awaited_answer_goes_to_the_open_request_and_the_reply_says_exactly_that():
    request = {"id": "t1", "code": "VH-1", "title": LEAK, "status": "open", "version": 3, "priority": "normal",
               "submitted": None, "pending": "information"}
    backend = Backend(lambda details: verdict(True), open_request=request)
    # A model would call these words "another incident" and tell the resident nothing was recorded.
    model = Model(final("Mình chưa ghi nhận được việc này ở đây, bạn bấm Chat mới nhé."))
    reply, _ = turn(backend, model, {"id": "m2", "text": "Mất nước cả căn từ sáng", "fileIds": ["f2"]})
    assert reply == "Mình đã chuyển câu trả lời của bạn tới Ban quản lý."
    assert ("follow-up", {"message_id": "m2"}) in backend.calls and model.seen == []


def test_a_photo_added_to_an_open_request_is_told_to_the_model_as_what_was_stored():
    request = {"id": "t1", "code": "VH-1", "title": LEAK, "status": "open", "version": 3, "priority": "normal",
               "submitted": None, "pending": None}
    backend = Backend(lambda details: verdict(True), open_request=request)
    model = Model(final("Mình đã ghi nhận thêm ảnh bạn gửi cho yêu cầu này."))
    reply, _ = turn(backend, model, {"id": "m2", "text": "Gửi thêm ảnh", "fileIds": ["f2"]})
    assert reply == "Mình đã ghi nhận thêm ảnh bạn gửi cho yêu cầu này."
    system = model.seen[0][0]["content"]
    assert '"anh_them": 1' in system and '"da_chuyen_cau_tra_loi": false' in system


def test_a_message_of_photos_alone_is_shown_to_the_model_as_photos_not_as_words():
    history = [{"id": "m1", "role": "resident", "text": "", "photos": 2}]
    backend = Backend(lambda details: verdict(False), history=history)
    model = Model(final("Bạn đang gặp việc gì với căn hộ ạ? Bạn mô tả giúp mình nhé."))
    toolbox = Toolbox(backend, None, None, CONTEXT, {"id": "m1", "text": "", "fileIds": ["f1", "f2"]}, None, {"homes": [HOME]}, CATEGORIES)
    reply = asyncio.run(run_agent(model, toolbox, "system", history))
    assert reply.startswith("Bạn đang gặp việc gì")
    assert model.seen[0][1] == {"role": "user", "content": "[Cư dân gửi 2 ảnh, không viết gì]"}
