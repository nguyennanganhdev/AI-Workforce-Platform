"""Valid unusual data and exported interfaces, as well as malformed contracts."""

import asyncio
from copy import deepcopy

import httpx
import pytest
from reporting.application.client import ReportBackend
from reporting.tools import RuntimeContext
from test_adversarial import run_payload
from test_tools import B1, CASES, PERIOD, employee, harness, response


@pytest.mark.parametrize("operation,args,_path,fields", CASES)
def test_named_public_methods_are_callable(operation, args, _path, fields):
    async def run():
        body = fields if "agentContext" in fields else response(operation, fields)
        tools, requests, client = harness(lambda _: httpx.Response(200, json=body))
        async with client:
            method = getattr(tools, operation)
            result = (
                await method()
                if operation == "get_report_filter_options"
                else await method(args)
            )
        assert result["outcome"] in ("success", "partial") and len(requests) == 1

    asyncio.run(run())


@pytest.mark.parametrize(
    "change",
    [
        {"principal_id": " "},
        {"session_cookie": " "},
        {"session_cookie": "session=A\r\nX-Demo-Actor:admin"},
        {"allowed_building_ids": [B1]},
        {"allowed_building_ids": ("bad-uuid",)},
    ],
)
def test_runtime_context_invalid_configuration_is_rejected(change):
    with pytest.raises((ValueError, TypeError)):
        RuntimeContext(
            **{
                "principal_id": "A",
                "allowed_building_ids": (B1,),
                "session_cookie": "session=A",
                **change,
            }
        )


def test_cookie_not_present_in_context_repr():
    assert "private-token" not in repr(
        RuntimeContext("A", (B1,), "session=private-token")
    )


@pytest.mark.parametrize(
    "missing",
    ["average_processing_seconds", "average_rating", "rating_count", "completed_count"],
)
def test_required_metric_missing_is_not_filled_with_zero(missing):
    row = employee()
    del row[missing]
    assert (
        run_payload(CASES[1][0], PERIOD, {"items": [row]})["error"]
        == "BACKEND_CONTRACT_INVALID"
    )


def test_employee_has_no_completed_jobs_but_has_separate_feedback_cohort():
    row = employee(
        completed_count=0,
        timed_completion_count=0,
        on_time_count=0,
        average_processing_seconds=None,
    )
    result = run_payload(CASES[1][0], PERIOD, {"items": [row]})
    assert result["outcome"] == "partial"
    assert result["data"]["items"][0]["average_rating"] == 4.5
    assert "items[0].average_processing_seconds" in result["missing_data"]


def test_unclassified_group_and_pre_period_bucket_are_valid():
    fields = {
        "buildingId": B1,
        "interval": "week",
        "totalTickets": 1,
        "items": [
            {
                "period": "2026-08-31",
                "category_id": None,
                "category_name": None,
                "incident_type_id": None,
                "incident_type": "Không phân loại",
                "incident_count": 1,
            }
        ],
    }
    args = {**PERIOD, "interval": "week"}
    body = response(CASES[4][0], fields, args)
    result = run_payload(CASES[4][0], args, body)
    assert result["outcome"] == "success" and result["data"]["items"][0]["share"] == 1


def test_empty_frequency_has_no_invented_zero_group():
    fields = {"buildingId": B1, "interval": "month", "totalTickets": 0, "items": []}
    assert run_payload(CASES[4][0], PERIOD, fields)["outcome"] == "empty"


def test_invoice_overpayment_can_coexist_with_unpaid_invoice():
    fields = deepcopy(CASES[3][3])
    fields["items"][0].update(
        billed_amount="200",
        collected_amount="200",
        outstanding_amount="100",
        invoice_count=2,
    )
    result = run_payload(CASES[3][0], CASES[3][1], fields)
    assert result["data"]["items"][0]["outstanding_amount"] == "100"


@pytest.mark.parametrize("rows", [[{"id": " "}], [{"id": "same"}, {"id": "same"}]])
def test_bad_supporting_record_identity(rows):
    assert (
        run_payload(CASES[5][0], PERIOD, {"items": rows, "nextOffset": None})["error"]
        == "BACKEND_CONTRACT_INVALID"
    )


@pytest.mark.parametrize("depth", [600, 1200])
def test_deep_json_cannot_escape_as_recursion_error(depth):
    body = '{"agentContext":{},"unexpected":' + "[" * depth + "0" + "]" * depth + "}"
    from test_tools import call

    result, requests = call(
        lambda _: httpx.Response(200, content=body), CASES[0][0], {}, retries=2
    )
    assert result["error"] == "BACKEND_CONTRACT_INVALID" and len(requests) == 1


def test_numeric_budget_much_larger_than_float_does_not_escape():
    with pytest.raises(ValueError):
        ReportBackend("https://business.example", timeout_seconds=10**400)
