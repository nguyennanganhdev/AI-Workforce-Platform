"""The model-led agent's loop and reply guard, with a scripted model and a recording toolbox."""

import asyncio
import json

from src.agent.loop import EMERGENCY_FAILED_REPLY, EMERGENCY_REPLY, FILED_REPLY, SAFE_REPLY, run_agent, violations

HISTORY = [{"role": "resident", "text": "Phí gửi xe máy tháng bao nhiêu?"}]


class Toolbox:
    def __init__(self, results=None):
        self.results = results or {}
        self.calls, self.evidence, self.passages = [], [], {}
        self.status, self.emergency, self.acted = None, False, False
        self.emergency_failed, self.question, self.filed_code = False, None, None

    async def call(self, name, arguments):
        self.calls.append((name, arguments))
        result = self.results.get(name, {"error": "unknown_tool"})
        if name == "search_knowledge":
            self.passages = {p["rank"]: p for p in result["passages"]}
        if name == "report_emergency":
            # As the real toolbox: told to the resident only when management was reached.
            self.emergency, self.emergency_failed = "error" not in result, "error" in result
        if result.get("filed"):
            self.acted = True
        if result.get("filed"):
            self.filed_code = "VH-1"
        self.evidence.append(str(result))
        return result


class Model:
    """Returns the scripted assistant messages in order and records what it was sent."""

    def __init__(self, *answers):
        self.answers, self.seen = list(answers), []

    async def complete(self, messages, tools):
        self.seen.append(messages)
        return self.answers.pop(0)


def tool_call(name, **arguments):
    return {"content": None, "tool_calls": [{"id": "call-1", "type": "function",
                                             "function": {"name": name, "arguments": json.dumps(arguments)}}]}


def final(reply, sources=()):
    return {"content": json.dumps({"reply": reply, "sources": list(sources)}, ensure_ascii=False)}


def run(model, toolbox):
    return asyncio.run(run_agent(model, toolbox, "system", HISTORY))


def test_answer_from_a_passage_carries_its_source():
    passage = {"rank": 1, "title": "Nội quy trông giữ xe", "text": "Phí gửi xe máy là 100.000 đồng mỗi tháng.", "unverified": False}
    toolbox = Toolbox({"search_knowledge": {"passages": [passage]}})
    reply = run(Model(tool_call("search_knowledge", query="phí gửi xe máy"),
                      final("Phí gửi xe máy là 100.000 đồng mỗi tháng.", [1])), toolbox)
    assert reply == "Phí gửi xe máy là 100.000 đồng mỗi tháng.\n(Nguồn: Nội quy trông giữ xe)"
    assert toolbox.calls == [("search_knowledge", {"query": "phí gửi xe máy"})]


def test_a_figure_taken_from_a_passage_is_attributed_even_when_the_model_names_no_source():
    passages = [{"rank": 1, "title": "Nội quy trông giữ xe", "text": "Phí gửi xe máy là 100.000 đồng mỗi tháng.", "unverified": False},
                {"rank": 2, "title": "Dịch vụ cư dân", "text": "Phòng gym ở tầng 2.", "unverified": False}]
    toolbox = Toolbox({"search_knowledge": {"passages": passages}})
    reply = run(Model(tool_call("search_knowledge", query="phí gửi xe máy"),
                      final("Phí gửi xe máy là 100.000 đồng mỗi tháng.")), toolbox)
    assert reply.endswith("(Nguồn: Nội quy trông giữ xe)")


def test_a_figure_without_a_source_is_sent_back_once_then_replaced():
    toolbox = Toolbox({"search_knowledge": {"passages": [], "note": "Không có nguồn phù hợp."}})
    model = Model(tool_call("search_knowledge", query="phí gửi xe máy"),
                  final("Phí gửi xe máy là 120.000 đồng mỗi tháng."),
                  final("Mình chưa có thông tin về phí gửi xe máy."))
    assert run(model, toolbox) == "Mình chưa có thông tin về phí gửi xe máy."
    assert "120.000" in model.seen[-1][-1]["content"]  # the model was told which figure had no source

    stubborn = Model(final("Phí là 120.000 đồng."), final("Phí là 150.000 đồng."))
    assert run(stubborn, Toolbox()) == SAFE_REPLY


def test_a_malformed_final_answer_never_reaches_the_resident():
    assert run(Model({"content": "Xin chào"}, {"content": "{not json"}), Toolbox()) == SAFE_REPLY


def test_emergency_is_acknowledged_with_the_fixed_sentence():
    toolbox = Toolbox({"report_emergency": {"emergency_reported": True}})
    assert run(Model(tool_call("report_emergency")), toolbox) == EMERGENCY_REPLY


def test_an_emergency_that_did_not_reach_management_is_never_acknowledged():
    toolbox = Toolbox({"report_emergency": {"error": "unavailable"}})
    assert run(Model(tool_call("report_emergency"), final("Mình đã chuyển khẩn cấp.")), toolbox) == EMERGENCY_FAILED_REPLY


def test_the_loop_stops_after_its_step_budget():
    model = Model(*[tool_call("request_status") for _ in range(10)])
    toolbox = Toolbox({"request_status": {"error": "no_open_request"}})
    assert run(model, toolbox) == SAFE_REPLY
    assert len(toolbox.calls) == 6


def test_a_filed_request_is_confirmed_even_when_no_wording_of_the_model_can_be_sent():
    toolbox = Toolbox({"file_request": {"filed": True}})
    model = Model(tool_call("file_request", symptom="bị rò", kind="incident", category_code="technical", priority="normal"),
                  final("Kỹ thuật sẽ đến trong 30 phút."), final("Thợ sẽ có mặt trong 15 phút."))
    assert run(model, toolbox) == FILED_REPLY


def test_claiming_to_have_passed_something_on_requires_a_tool_that_did():
    # The model says it forwarded the complaint but called nothing: it is sent back and then files it.
    toolbox = Toolbox({"file_request": {"filed": True}})
    model = Model(final("Mình đã ghi nhận và sẽ chuyển Ban quản lý nhắc nhở giúp bạn."),
                  tool_call("file_request", symptom="khoan tường sau 22 giờ", item="Hàng xóm", kind="incident",
                            category_code="security", priority="normal"),
                  final("Mình đã ghi nhận và chuyển Ban quản lý nhắc nhở giúp bạn."))
    assert run(model, toolbox) == "Mình đã ghi nhận và chuyển Ban quản lý nhắc nhở giúp bạn."
    assert [name for name, _ in toolbox.calls] == ["file_request"]


def test_guard_rules():
    toolbox = Toolbox()
    toolbox.evidence = ["{'title': 'Vòi nước rò', 'status': 'đang được xử lý'}", "An ninh: 0858 001 080"]
    conversation = "Vòi nước bếp rò từ 7 giờ sáng, căn 1201"
    toolbox.acted = True
    assert violations("Yêu cầu của bạn đang được xử lý.", toolbox, conversation) == []
    assert violations("Số an ninh là 0858 001 080.", toolbox, conversation) == []
    assert violations("Mình đã ghi nhận vòi nước rò ở căn 1201.", toolbox, conversation) == []
    assert violations("Kỹ thuật sẽ đến trong 30 phút.", toolbox, conversation)
    assert violations("Phí sửa là 200.000 đồng.", toolbox, conversation)
    assert violations("Yêu cầu của bạn đã hoàn tất.", toolbox, conversation)
    assert violations("Mình đã tạo ticket cho bạn.", toolbox, conversation)
    toolbox.status = "closed"
    assert violations("Yêu cầu của bạn đã hoàn tất.", toolbox, conversation) == []
