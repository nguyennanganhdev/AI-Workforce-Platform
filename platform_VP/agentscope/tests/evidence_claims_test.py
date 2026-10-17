"""Pure deterministic evidence validation: no model/provider dependencies."""

import importlib.util
import json
import sys
import unittest
from pathlib import Path

# Loading this pure module directly also makes this suite runnable on a machine
# without the optional runtime/provider packages installed.
_SPEC = importlib.util.spec_from_file_location(
    "workforce_evidence_claims",
    Path(__file__).parents[1] / "src/agentscope/app/_evidence_claims.py",
)
_CLAIMS = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _CLAIMS
_SPEC.loader.exec_module(_CLAIMS)
EvidenceSource = _CLAIMS.EvidenceSource
validate_claims = _CLAIMS.validate_claims
unsupported_claim_anchors = _CLAIMS.unsupported_claim_anchors


class EvidenceClaimsTest(unittest.TestCase):
    def test_ticket_quote_envelope_keeps_money_and_material_quantity_separate(self):
        quote = {"currency": "VND", "items": [
            {"label": "Dây điện (1 mét)", "amount": 50000}],
            "total": 50000, "warranty_months": 0}
        source = json.dumps({"tool_call": {"name": "vh_ticket_get", "input": "{}"},
            "tool_result": {"type": "tool_result", "name": "vh_ticket_get",
                "output": [{"type": "text", "text": "E20: " + json.dumps({"quote": quote})}]}})
        report = "Báo giá: Dây điện (1 mét), tổng 50.000đ, bảo hành 0 tháng."
        self.assertEqual(validate_claims(report, [source]).unsupported, ())
        self.assertTrue(validate_claims(report.replace("50.000đ", "60.000đ"), [source]).unsupported)
        self.assertTrue(validate_claims(report.replace("1 mét", "2 mét"), [source]).unsupported)
        self.assertTrue(validate_claims(report.replace("50.000đ", "50.000 USD"), [source]).unsupported)
        # A missing currency must still be repaired at the producer.
        del quote["currency"]
        self.assertTrue(validate_claims("Tổng 50.000đ.", [json.dumps(quote)]).unsupported)

    def setUp(self):
        self.hotels = [
            EvidenceSource(
                json.dumps(
                    {"name": "Hotel Alpha", "price_per_night_usd": 100, "rating": 4}
                ),
                "E1",
            ),
            EvidenceSource(
                json.dumps(
                    {"name": "Hotel Beta", "price_per_night_usd": 200, "rating": 5}
                ),
                "E2",
            ),
        ]

    def test_formatting_and_short_quoted_reasoning_are_not_facts(self):
        text = '## Proposed Action Plan\nI recommend "compare before deciding".\n12. Ask the customer for approval.'
        result = validate_claims(text, [])
        self.assertEqual(result.unsupported, ())
        self.assertEqual(result.supported_text, text)
        self.assertEqual(result.rejected_texts, ())
        self.assertFalse(result.has_concrete_claims)

    def test_headings_quotes_and_numbered_rows_still_check_concrete_facts(self):
        for text in (
            "## Hotel Alpha costs 200 USD per night",
            "> Hotel Alpha costs 200 USD per night.",
            "12. Hotel Alpha costs 200 USD per night.",
            'I was told "Hotel Alpha costs 200 USD per night".',
        ):
            with self.subTest(text=text):
                self.assertTrue(validate_claims(text, self.hotels).unsupported)

    def test_valid_typed_json_fields_keep_source_and_unit(self):
        result = validate_claims(
            "Hotel Alpha costs 100 USD per night and has a rating 4.", self.hotels
        )
        self.assertEqual(result.unsupported, ())
        self.assertTrue(result.has_concrete_claims)
        self.assertEqual(
            validate_claims(
                "Hotel Alpha costs 100 USD per night.",
                [
                    EvidenceSource(
                        '{"hotel":"Hotel Alpha","price":100,"currency":"USD","unit":"night"}',
                        "E1",
                    )
                ],
            ).unsupported,
            (),
        )

    def test_prices_cannot_be_borrowed_from_another_entity_or_field(self):
        for text in (
            "Hotel Alpha costs 200 USD per night.",
            "Hotel Alpha rating 100.",
            "Hotel Alpha costs 4 USD per night.",
        ):
            with self.subTest(text=text):
                self.assertTrue(validate_claims(text, self.hotels).unsupported)

    def test_current_conflicting_prices_require_review_instead_of_picking_a_source(
        self,
    ):
        sources = self.hotels + [
            EvidenceSource('{"name":"Hotel Alpha","price_per_night_usd":110}', "E3")
        ]
        for amount in (100, 110):
            self.assertTrue(
                validate_claims(
                    f"Hotel Alpha costs {amount} USD per night.", sources
                ).unsupported
            )
        self.assertTrue(validate_claims("Total 310 USD.", sources).unsupported)
        self.assertEqual(
            validate_claims("Hotel Beta costs 200 USD per night.", sources).unsupported,
            (),
        )

    def test_different_price_units_and_valid_date_options_do_not_conflict(self):
        sources = self.hotels + [
            EvidenceSource('{"name":"Hotel Alpha","price_per_person_usd":110}', "E3")
        ]
        self.assertEqual(
            validate_claims(
                "Hotel Alpha costs 100 USD per night.", sources
            ).unsupported,
            (),
        )
        sources = [
            '{"name":"Hotel Alpha","check_in_date":"2026-10-17"}',
            '{"name":"Hotel Alpha","check_in_date":"17/10"}',
        ]
        self.assertEqual(
            validate_claims("Hotel Alpha check-in 17/10.", sources).unsupported, ()
        )
        sources.append('{"name":"Hotel Alpha","check_in_date":"2026-10-18"}')
        self.assertEqual(
            validate_claims("Hotel Alpha check-in 17/10.", sources).unsupported, ()
        )

    def test_multiple_departure_options_do_not_become_scalar_conflicts(self):
        sources = ["Nhà xe Mây Việt Express có chuyến 07:00 và 05:30."]
        self.assertEqual(
            validate_claims(
                "Mây Việt Express Limousine khởi hành lúc 7:00; Mây Việt Express Giường khởi hành lúc 5:30.",
                sources,
            ).unsupported,
            (),
        )

    def test_prose_binds_common_english_and_vietnamese_price_fields(self):
        for sources, good, bad in (
            (
                [
                    "Hotel Alpha costs 100 USD per night; Hotel Beta costs 200 USD per night."
                ],
                "Hotel Alpha costs 100 USD per night.",
                "Hotel Alpha costs 200 USD per night.",
            ),
            (
                [
                    "Khách sạn Hoa Sen giá 1.200.000 VND/đêm.",
                    "Khách sạn Hoa Mai giá 2.000.000 VND/đêm.",
                ],
                "Khách sạn Hoa Sen giá 1,2 triệu VND/đêm.",
                "Khách sạn Hoa Sen giá 2.000.000 VND/đêm.",
            ),
        ):
            with self.subTest(good=good):
                self.assertEqual(validate_claims(good, sources).unsupported, ())
                self.assertTrue(validate_claims(bad, sources).unsupported)

    def test_currency_and_denominator_swaps_are_rejected(self):
        for text in (
            "Hotel Alpha costs 100 EUR per night.",
            "Hotel Alpha costs 100 USD per person.",
            "Hotel Alpha costs 100 USD/2 nights.",
        ):
            with self.subTest(text=text):
                self.assertTrue(validate_claims(text, self.hotels).unsupported)
        # Omitting the unit in a source is ambiguous, not evidence for /night.
        self.assertTrue(
            validate_claims(
                "Hotel Alpha costs 100 USD per night.",
                ['{"name":"Hotel Alpha","price_usd":100}'],
            ).unsupported
        )

    def test_currency_or_unit_from_another_record_cannot_complete_price(self):
        sources = [
            EvidenceSource('{"name":"Hotel Alpha","price":100}', "E1"),
            EvidenceSource(
                '{"name":"Hotel Alpha","currency":"USD","unit":"night"}', "E2"
            ),
        ]
        self.assertTrue(
            validate_claims("Hotel Alpha costs 100 USD per night.", sources).unsupported
        )

    def test_count_cannot_be_used_as_currency(self):
        self.assertTrue(validate_claims("Price 100 USD.", ["100 guests."]).unsupported)

    def test_general_customer_count_may_be_repeated_with_a_selected_option(self):
        sources = [
            EvidenceSource(
                "Find a hotel for 2 people with a 3 million VND budget", "customer-1"
            ),
            EvidenceSource(
                "Verified Hotel costs 1500000 VND and is available", "tool-1"
            ),
        ]
        self.assertEqual(
            validate_claims(
                "Choose Verified Hotel at 1,500,000 VND for 2 people", sources
            ).unsupported,
            (),
        )
        self.assertTrue(
            validate_claims("Verified Hotel costs 2 VND.", sources).unsupported
        )
        self.assertTrue(
            validate_claims(
                "Verified Hotel is for 2 people.", ["Another Hotel is for 2 people."]
            ).unsupported
        )

    def test_unknown_or_compound_denominators_are_not_silently_dropped(self):
        for text in (
            "Hotel Alpha costs 100 GBP per night.",
            "Hotel Alpha costs 100 USD per week.",
            "Hotel Alpha costs 100 USD per night per person.",
            "Hotel Alpha costs 100 USD/booking.",
        ):
            self.assertTrue(validate_claims(text, self.hotels).unsupported)

    def test_record_price_string_and_per_metadata_are_supported(self):
        source = '{"name":"Hotel Alpha","price":"100 USD","unit":"per night"}'
        self.assertEqual(
            validate_claims(
                "Hotel Alpha costs 100 USD per night.", [source]
            ).unsupported,
            (),
        )

    def test_plain_tool_prose_inside_json_envelope_keeps_its_associations(self):
        source = json.dumps(
            {
                "content": [
                    {
                        "type": "text",
                        "text": "Hotel Alpha costs 100 USD per night; Hotel Beta costs 200 USD per night.",
                    }
                ]
            }
        )
        self.assertEqual(
            validate_claims(
                "Hotel Alpha costs 100 USD per night.", [source]
            ).unsupported,
            (),
        )
        self.assertTrue(
            validate_claims(
                "Hotel Alpha costs 200 USD per night.", [source]
            ).unsupported
        )

    def test_arithmetic_uses_quantity_dimension_and_explicit_calculation(self):
        source = '{"price_per_night_usd":100}'
        self.assertTrue(
            validate_claims("Total 300 USD.", [source, "3 guests"]).unsupported
        )
        self.assertEqual(
            validate_claims("Total 300 USD.", [source, "3 nights"]).unsupported, ()
        )
        self.assertTrue(
            validate_claims(
                "Price 300 USD.", ['{"price_usd":100}', '{"price_usd":200}']
            ).unsupported
        )

    def test_ambiguous_bare_entity_numbers_are_not_borrowed(self):
        self.assertTrue(validate_claims("Hotel Alpha 200.", self.hotels).unsupported)

    def test_dates_times_and_fields_are_bound_to_entity(self):
        sources = [
            '{"name":"Hotel Alpha","check_in_date":"2026-10-17","check_out_date":"2026-10-19","check_in_time":"14:00","check_out_time":"11:00"}'
        ]
        self.assertEqual(
            validate_claims(
                "Hotel Alpha check-in 17/10 at 14:00.", sources
            ).unsupported,
            (),
        )
        for text in (
            "Hotel Alpha check-in 19/10 at 14:00.",
            "Hotel Alpha check-in 17/10 at 11:00.",
        ):
            self.assertTrue(validate_claims(text, sources).unsupported)

    def test_cross_entity_dates_and_times_are_not_supported(self):
        sources = [
            "Hotel Alpha check-in 17/10 at 14:00.",
            "Hotel Beta check-in 19/10 at 11:00.",
        ]
        self.assertTrue(
            validate_claims("Hotel Alpha check-in 19/10 at 11:00.", sources).unsupported
        )

    def test_partial_result_preserves_whole_supported_units(self):
        good = "Hotel Alpha costs 100 USD per night."
        bad = "Hotel Beta costs 100 USD per night."
        result = validate_claims(good + "\n" + bad, self.hotels)
        self.assertEqual(result.supported_text, good)
        self.assertEqual(result.rejected_texts, (bad,))
        # Never salvage the first clause of one contradictory sentence.
        contradictory = good[:-1] + ", but Hotel Alpha costs 200 USD per night."
        result = validate_claims(contradictory, self.hotels)
        self.assertEqual(result.supported_text, "")
        self.assertEqual(result.rejected_texts, (contradictory,))

    def test_calculated_vietnamese_totals_remain_supported(self):
        sources = [
            "Ngân sách 4 triệu, cần để dư 500 nghìn.",
            "Tổng chi phí đã xác minh là 2.720.000đ.",
        ]
        self.assertEqual(
            unsupported_claim_anchors(
                "Trần chi 3,5 triệu; còn 1.280.000đ từ ngân sách và cao hơn mức dự phòng 780.000đ.",
                sources,
            ),
            (),
        )
        sources = [
            "Mình đi Đà Nẵng 2 người, ở 2 đêm",
            '{"name":"DEMO Song Han","price_per_night_vnd":1200000}',
            '{"car":"4 chỗ","price_vnd":250000}',
        ]
        self.assertEqual(
            unsupported_claim_anchors("Khách sạn 2 đêm: 2.400.000 VND", sources), ()
        )
        self.assertEqual(
            unsupported_claim_anchors("Tổng cả xe: 2.650.000 VND", sources), ()
        )
        self.assertEqual(
            unsupported_claim_anchors("Tổng: 3.100.000 VND", sources),
            ("number:3100000",),
        )

    def test_calculation_does_not_mix_currencies_or_borrow_entity_price(self):
        sources = ['{"price_usd":100}', '{"price_eur":200}']
        self.assertTrue(validate_claims("Total 300 USD.", sources).unsupported)
        self.assertEqual(
            validate_claims(
                "Total 300 USD.", ['{"price_usd":100}', '{"price_usd":200}']
            ).unsupported,
            (),
        )
        self.assertTrue(
            validate_claims(
                "Hotel Alpha costs 300 USD per night.", self.hotels
            ).unsupported
        )

    def test_plain_strings_and_immutable_report_are_backward_compatible(self):
        from dataclasses import FrozenInstanceError

        self.assertEqual(
            unsupported_claim_anchors(
                "Phiếu WO-1001 ngày 17/10.",
                ['{"ticket_id":"WO-1001","date":"2026-10-17"}'],
            ),
            (),
        )
        with self.assertRaises(FrozenInstanceError):
            validate_claims("Please confirm.", []).supported_text = "changed"


if __name__ == "__main__":
    unittest.main()
