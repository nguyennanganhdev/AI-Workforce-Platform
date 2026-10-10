"""Owner-controlled golden cases, never supplied or edited by Builder."""

import json
from typing import Any, Dict, Mapping, Sequence, Tuple

from ._models import LifecycleError, canonical_hash


def grading_cases(
    suite: "EvaluationSuite", tools: Sequence[Mapping[str, Any]]
) -> Tuple[Dict[str, Any], ...]:
    """Restrict every case to bound tool snapshots, regardless of runner
    claims."""
    result = []
    indexed = {tool["tool_version_id"]: dict(tool) for tool in tools}
    for case in suite.cases:
        requested = case.get("allowed_tools", list(indexed))
        case["allowed_tools"] = [key for key in requested if key in indexed]
        case["tool_snapshots"] = indexed
        result.append(case)
    return tuple(result)


class EvaluationSuite:
    def __init__(
        self, version: str, cases: Sequence[Mapping[str, Any]]
    ) -> None:
        if not version or not cases:
            raise ValueError("suite version and golden cases are required")
        ids = [case.get("case_id") for case in cases]
        if any(not isinstance(case_id, str) for case_id in ids) or len(
            set(ids)
        ) != len(ids):
            raise ValueError("case IDs must be unique strings")
        self.version = version
        self._json = json.dumps(list(cases), sort_keys=True, allow_nan=False)
        self.content_hash = canonical_hash(
            {"version": version, "cases": list(cases)}
        )

    @property
    def cases(self) -> Tuple[Dict[str, Any], ...]:
        return tuple(json.loads(self._json))


class SuiteCatalog:
    def __init__(self, suites: Sequence[EvaluationSuite]) -> None:
        self._suites = {suite.version: suite for suite in suites}
        if len(self._suites) != len(suites):
            raise ValueError("suite versions must be unique")

    def get(self, version: str) -> EvaluationSuite:
        if version not in self._suites:
            raise LifecycleError("SUITE_NOT_FOUND", 422)
        return self._suites[version]


def travel_suite() -> EvaluationSuite:
    """Lifecycle-owned golden travel inputs pending Execution's shared
    fixtures."""
    return EvaluationSuite(
        "travel-v1",
        [
            {
                "case_id": "travel-missing-inputs",
                "pattern": "interactive",
                "input": {
                    "text": "Plan a weekend trip to Bai Chay",
                    "budget_minor": 10000000,
                    "sent_at": "2026-10-09T03:00:00Z",
                    "timezone": "Asia/Ho_Chi_Minh",
                },
                "expected_facts": {
                    "missing_party_size": True,
                    "missing_departure": True,
                    "missing_nights": True,
                    "booking_created": False,
                },
                "allowed_tools": [],
                "mock_tools_only": True,
                "turns": [
                    {
                        "trigger": "request",
                        "workflow_state": "awaiting_user",
                        "next_action": "submit_reply",
                        "operation_pending": False,
                    }
                ],
            },
            {
                "case_id": "travel-budget-with-peers",
                "pattern": "interactive",
                "input": {
                    "party_size": 2,
                    "departure": "Ha Noi",
                    "destination": "Bai Chay",
                    "start_date": "2026-10-10",
                    "end_date": "2026-10-11",
                    "nights": 1,
                    "budget_minor": 10000000,
                    "meals_reserve_minor": 2000000,
                },
                "mock_peer_capabilities": [
                    "hotel.quote",
                    "car.quote",
                    "calculate",
                ],
                "mock_peer_results": {
                    "hotel_minor": 4000000,
                    "car_minor": 3000000,
                    "quote_ref": "fixture-quote-v1",
                },
                "expected_facts": {
                    "total_minor": 9000000,
                    "remaining_minor": 1000000,
                    "meals_reserve_minor": 2000000,
                    "booking_created": False,
                },
                "mock_tools_only": True,
                "quality_required": True,
                "quality_threshold": 0.8,
                ("expected_answer"): (
                    "Explain options, verified quotes, "
                    "total and missing fees; ask for "
                    "selection."
                ),
                "turns": [
                    {
                        "trigger": "request",
                        "workflow_state": "awaiting_user",
                        "next_action": "submit_reply",
                        "operation_pending": False,
                    }
                ],
            },
        ],
    )
