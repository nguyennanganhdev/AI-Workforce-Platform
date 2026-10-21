# -*- coding: utf-8 -*-
"""The Leader's "is this asking the customer for details?" check does not
throw away a finished answer that ends with a polite offer."""
from unittest import TestCase

from agentscope.app.middleware._leader_evidence_middleware import (
    LeaderEvidenceMiddleware,
)

intake = LeaderEvidenceMiddleware._is_customer_intake  # pylint: disable=protected-access


class LeaderIntakeHeuristicTest(TestCase):

    def test_a_short_request_for_details_is_intake(self) -> None:
        self.assertTrue(intake("Bạn xuất phát từ đâu và đi mấy người?"))
        self.assertTrue(intake("Please tell me your travel dates."))

    def test_a_conditional_offer_is_not_intake(self) -> None:
        self.assertFalse(intake("Đây là lịch trình. Hãy cho biết nếu bạn muốn đổi khách sạn."))
        self.assertFalse(intake("Here is the plan. Please tell me if you want changes."))

    def test_a_long_synthesis_is_not_intake(self) -> None:
        answer = "Ngày 1: tham quan Bà Nà. " * 40 + "Hãy cho biết thêm ngân sách."
        self.assertFalse(intake(answer))
