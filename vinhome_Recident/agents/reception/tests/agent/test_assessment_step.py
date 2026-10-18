"""The reasoning step between a proposed request and the backend's check (src/agent/assessment.py)."""

import asyncio
import json

from src.agent.assessment import assess_report, parse
from src.agent.tools import Toolbox

from .test_intake_tools import CATEGORIES, CONTEXT, HOME, LEAK, QUESTION, Backend, fact, file_request, verdict

CATS = CATEGORIES + [{"id": "c2", "code": "sanitation", "name": "Vệ sinh"}]
HOOD = "Máy hút mùi nhà bếp bị chảy nước xuống bếp, nước lan ra sàn"


def assessment(**fields):
    base = {"symptom": "", "area": "", "item": "", "item_unknown": "", "kind": "incident", "category_code": "technical",
            "priority": "normal", "severity": "unknown", "summary": "", "reason": "", "question": ""}
    return json.dumps({**base, **fields}, ensure_ascii=False)


def toolbox(backend, assessed):
    box = Toolbox(backend, None, None, CONTEXT, {"id": "m1", "text": HOOD}, None, {"homes": [HOME]}, CATS)

    async def assess(proposal):
        assessed.setdefault("proposals", []).append(proposal)
        return assessed.get("result")

    box.assess = assess
    return box


def test_parse_keeps_valid_fields_and_drops_what_cannot_be_sent():
    value = parse(assessment(symptom="bị chảy nước", item="Máy hút mùi", priority="urgent", category_code="travel",
                             summary="Máy hút mùi rò nước, gọi 0901234567", reason="Nước lan ra sàn bếp.",
                             question="Bạn kiểm tra giúp mình ticket nhé?"), CATS, HOOD)
    assert value["details"] == {"symptom": "bị chảy nước", "item": "Máy hút mùi"}
    assert value["priority"] is None and value["category_code"] is None and value["severity"] == "unknown"
    assert "0901234567" not in value["summary"] and value["reason"] == "Nước lan ra sàn bếp."
    assert value["question"] == ""  # an internal word never reaches the resident
    assert parse("không phải JSON", CATS, HOOD) is None
    two = parse(assessment(question="Ở đâu? Khi nào?"), CATS, HOOD)
    assert two["question"] == ""


def test_the_assessment_details_priority_and_reasons_reach_the_request():
    seen = []

    def intake(details):
        seen.append(dict(details))
        return verdict(True, [fact("symptom", "bị chảy nước"), fact("item", "Máy hút mùi")], description=HOOD)

    backend = Backend(intake)
    assessed = {"result": parse(assessment(symptom="bị chảy nước", item="Máy hút mùi", area="nhà bếp", priority="high",
                                           severity="moderate", summary="Máy hút mùi chảy nước, lan ra sàn bếp",
                                           reason="Nước lan ra sàn nên cần xử lý sớm."), CATS, HOOD)}
    box = toolbox(backend, assessed)
    result = asyncio.run(box.call(*file_request(symptom="chảy nước")))
    assert result == {"filed": True}
    assert seen == [{"symptom": "bị chảy nước", "item": "Máy hút mùi", "area": "nhà bếp"}]
    filed = backend.ran("submit_ticket_assessment")[0]["assessment"]
    assert (filed["priority"], filed["severity"]) == ("high", "moderate")
    assert filed["reason"] == "Tóm tắt của Lễ tân: Máy hút mùi chảy nước, lan ra sàn bếp. Nước lan ra sàn nên cần xử lý sớm."
    assert assessed["proposals"][0]["symptom"] == "chảy nước"


def test_a_detail_the_resident_did_not_write_falls_back_to_the_proposal():
    seen = []

    def intake(details):
        seen.append(dict(details))
        if details.get("item") == "máy hút khói":
            return verdict(False, [fact("symptom", "bị chảy nước")], rejected=["item"])
        return verdict(True, [fact("symptom", "bị chảy nước"), fact("item", details["item"])], description=HOOD)

    backend = Backend(intake)
    assessed = {"result": parse(assessment(symptom="bị chảy nước", item="máy hút khói"), CATS, HOOD)}
    result = asyncio.run(toolbox(backend, assessed).call(*file_request(symptom="bị chảy nước", item="Máy hút mùi")))
    assert result == {"filed": True}
    assert [entry["item"] for entry in seen] == ["máy hút khói", "Máy hút mùi"]


def test_the_assessment_words_the_question_only_for_the_detail_the_backend_misses():
    own = "Nước chảy ra từ chỗ nào của máy hút mùi vậy bạn, hay bạn chưa rõ?"
    backend = Backend(lambda details: verdict(False, [fact("symptom", "bị chảy nước")]))
    assessed = {"result": parse(assessment(symptom="bị chảy nước", question=own), CATS, HOOD)}
    box = toolbox(backend, assessed)
    assert asyncio.run(box.call(*file_request(symptom="bị chảy nước")))["error"] == "needs_clarification"
    assert box.question == own and box.clarification == "item"
    # The assessment found the item, the backend did not: the backend's own question is asked.
    assessed = {"result": parse(assessment(symptom="bị chảy nước", item="vòi", question=own), CATS, HOOD)}
    box = toolbox(backend, assessed)
    asyncio.run(box.call(*file_request(symptom="bị chảy nước")))
    assert box.question == QUESTION


def test_without_an_assessment_the_proposal_is_filed_as_before():
    backend = Backend(lambda details: verdict(True, [fact("symptom", "bị rò nước")], description=LEAK))
    box = toolbox(backend, {"result": None})
    assert asyncio.run(box.call(*file_request(symptom="bị rò nước", item="vòi"))) == {"filed": True}
    filed = backend.ran("submit_ticket_assessment")[0]["assessment"]
    assert (filed["priority"], filed["severity"], filed["reason"]) == ("normal", "unknown", "Đề xuất của lễ tân từ mô tả của cư dân.")


def test_assess_report_reads_only_the_residents_words_at_its_effort():
    class Model:
        seen = None

        async def complete(self, messages, tools, effort=None):
            Model.seen = (messages, tools, effort)
            return {"content": assessment(symptom="bị chảy nước")}

    history = [{"role": "resident", "text": HOOD}, {"role": "reception", "text": "Bạn cho mình biết thêm nhé?"}]
    result = asyncio.run(assess_report(Model(), history, {"symptom": "chảy nước"}, CATS, "medium"))
    messages, tools, effort = Model.seen
    sent = json.loads(messages[1]["content"])
    assert sent["tin_cua_cu_dan"] == [HOOD] and tools == [] and effort == "medium"
    assert result["details"] == {"symptom": "bị chảy nước"}

    class Broken:
        async def complete(self, *args, **kwargs):
            raise RuntimeError("down")

    assert asyncio.run(assess_report(Broken(), history, {}, CATS, "medium")) is None
