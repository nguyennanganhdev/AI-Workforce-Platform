"""The curator's verdict parsing; the decision itself is the backend's (see v3_learning.decide)."""

import asyncio
import json
from types import SimpleNamespace

from src.runtime.curator import judge


class Model:
    def __init__(self, answer):
        self.answer = answer

    async def ainvoke(self, messages):
        return SimpleNamespace(content=json.dumps(self.answer, ensure_ascii=False))


def verdict(answer, question="Chị Lan căn 1201 hỏi nhận bưu phẩm ở đâu?", reply="Nhận tại quầy lễ tân sảnh, từ 8 giờ."):
    return asyncio.run(judge(Model(answer), question, reply))


def test_a_general_answer_keeps_the_rewrite_without_the_askers_details():
    result = verdict({"personal_data": False, "generalizable": True, "risk": "none", "reason": "Chung cho mọi cư dân.",
                      "question": "Nhận bưu phẩm ở đâu?", "answer": "Nhận tại quầy lễ tân sảnh, từ 8 giờ."})
    assert result["generalizable"] and result["risk"] == "none"
    assert result["question"] == "Nhận bưu phẩm ở đâu?"


def test_a_rewrite_that_adds_a_figure_is_dropped():
    result = verdict({"personal_data": False, "generalizable": True, "risk": "none",
                      "question": "Nhận bưu phẩm ở đâu?", "answer": "Nhận tại quầy lễ tân sảnh, từ 8 giờ đến 17 giờ."})
    assert "question" not in result and "answer" not in result


def test_anything_but_an_explicit_none_is_treated_as_risky():
    assert verdict({"personal_data": False, "generalizable": True})["risk"] == "fee_rule_safety"
    assert verdict({"personal_data": "no", "generalizable": "yes", "risk": "none"})["generalizable"] is False
