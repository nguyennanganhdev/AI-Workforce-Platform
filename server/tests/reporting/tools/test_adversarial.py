"""Fault-oriented cases. Expectations are based on API/DB contracts, not code branches."""

import asyncio
import json
from copy import deepcopy
from datetime import date, timedelta

import httpx
import pytest
from reporting.application.client import ReportBackend
from reporting.tools import ReportTools, RuntimeContext
from reporting.tools.contracts import EmployeeInput
from test_tools import (
    B1,
    CASES,
    CATEGORY,
    EXPORT,
    PERIOD,
    STAFF,
    call,
    employee,
    export_response,
    response,
)


def run_payload(operation, arguments, fields, *, raw=False):
    body = fields if raw or "agentContext" in fields else response(operation, fields)
    return call(
        lambda _: httpx.Response(200, content=json.dumps(body)), operation, arguments
    )[0]


@pytest.mark.parametrize("operation", [None, [], {}, 7, True, "unknown_operation"])
def test_unknown_operation_is_sanitized_without_http(operation):
    result, requests = call(lambda _: pytest.fail("Must not send HTTP"), operation, {})
    assert result["error"] == "REPORT_OPERATION_UNKNOWN" and not requests


@pytest.mark.parametrize("arguments", [None, [], "instructions", 1, True])
def test_non_object_arguments_are_rejected(arguments):
    result, requests = call(
        lambda _: pytest.fail("Must not send HTTP"),
        "get_employee_performance_summary",
        arguments,
    )
    assert result["error"] == "REPORT_INPUT_INVALID" and not requests


@pytest.mark.parametrize("operation,args,_path,fields", CASES)
@pytest.mark.parametrize(
    "fault", ["missing_meta", "wrong_operation", "wrong_source", "bad_resource"]
)
def test_all_routes_reject_broken_metadata(operation, args, _path, fields, fault):
    body = deepcopy(fields if "agentContext" in fields else response(operation, fields))
    if fault == "missing_meta":
        del body["agentContext"]
    elif fault == "wrong_operation":
        body["agentContext"]["operation"] = "admin_reset"
    elif fault == "wrong_source":
        body["agentContext"]["source"] = "made_up"
    else:
        body["agentContext"]["resourceContext"] = []
    result = run_payload(operation, args, body, raw=True)
    assert result["error"] == "BACKEND_CONTRACT_INVALID"
    assert result["execution_unknown"] == (operation == "create_report_export")


@pytest.mark.parametrize("value", [None, {}, "rows", [None], [1], [[]]])
def test_items_wrong_shape(value):
    result = run_payload("get_employee_performance_summary", PERIOD, {"items": value})
    assert result["error"] == "BACKEND_CONTRACT_INVALID"


@pytest.mark.parametrize("score", [0, 6, -1, True, "NaN", "Infinity", "1e10000"])
def test_feedback_score_must_be_within_database_scale(score):
    result = run_payload(
        "get_employee_feedback_details",
        {"building_id": B1, "staff_id": STAFF},
        {"items": [{"id": "review-1", "score": score}], "nextOffset": None},
    )
    assert result["error"] == "BACKEND_CONTRACT_INVALID"


@pytest.mark.parametrize("score", [0, 5.1, 999, "6"])
def test_employee_average_rating_must_be_within_database_scale(score):
    result = run_payload(
        "get_employee_performance_summary",
        PERIOD,
        {"items": [employee(average_rating=score)]},
    )
    assert result["error"] == "BACKEND_CONTRACT_INVALID"


def test_employee_huge_numeric_does_not_crash_boundary():
    result = run_payload(
        "get_employee_performance_summary",
        PERIOD,
        {"items": [employee(average_processing_seconds=10**400)]},
    )
    assert result["error"] == "BACKEND_CONTRACT_INVALID"


@pytest.mark.parametrize("staff_id", ["", "not-a-uuid", " "])
def test_employee_identity_is_required(staff_id):
    result = run_payload(
        "get_employee_performance_summary",
        PERIOD,
        {"items": [employee(staff_id=staff_id)]},
    )
    assert result["error"] == "BACKEND_CONTRACT_INVALID"


def test_duplicate_employee_rows_are_not_double_counted():
    result = run_payload(
        "get_employee_performance_summary", PERIOD, {"items": [employee(), employee()]}
    )
    assert result["error"] == "BACKEND_CONTRACT_INVALID"


@pytest.mark.parametrize(
    "money_value", ["NaN", "-0.01", True, None, "Infinity", "1e10000"]
)
def test_bad_money_is_not_reported_as_valid(money_value):
    fields = deepcopy(CASES[3][3])
    fields["items"][0]["billed_amount"] = money_value
    result = run_payload(CASES[3][0], CASES[3][1], fields)
    assert result["error"] == "BACKEND_CONTRACT_INVALID"


@pytest.mark.parametrize(
    "change",
    [
        {"outstanding_amount": "100000.11"},
        {"billed_work_count": 2},
        {"currency": "123"},
        {"currency": "vnd"},
    ],
)
def test_revenue_internal_invariants(change):
    fields = deepcopy(CASES[3][3])
    fields["items"][0].update(change)
    result = run_payload(CASES[3][0], CASES[3][1], fields)
    assert result["error"] == "BACKEND_CONTRACT_INVALID"


def test_overpayment_does_not_invent_negative_outstanding():
    fields = deepcopy(CASES[3][3])
    fields["items"][0].update(collected_amount="120000.10", outstanding_amount="0")
    result = run_payload(CASES[3][0], CASES[3][1], fields)
    assert result["outcome"] == "partial"
    assert result["data"]["items"][0]["collected_amount"] == "120000.10"


def test_multiple_currencies_remain_separate():
    fields = deepcopy(CASES[3][3])
    fields["items"].append(
        {
            **fields["items"][0],
            "currency": "USD",
            "billed_amount": "10.50",
            "collected_amount": "8.00",
            "outstanding_amount": "2.50",
        }
    )
    result = run_payload(CASES[3][0], CASES[3][1], fields)
    assert {row["currency"] for row in result["data"]["items"]} == {"VND", "USD"}
    assert "total" not in result["data"]


@pytest.mark.parametrize(
    "length,offset,next_offset",
    [(0, 0, 0), (0, 50, 50), (1, 0, 1), (1, 0, -1), (1, 0, True), (1, 0, "1")],
)
def test_pagination_cannot_loop_or_advance_short_page(length, offset, next_offset):
    fields = {
        "items": [{"id": f"ticket-{i}"} for i in range(length)],
        "nextOffset": next_offset,
    }
    result = run_payload(
        "get_report_supporting_records",
        {**PERIOD, "limit": 2, "offset": offset},
        response(
            "get_report_supporting_records",
            fields,
            {**PERIOD, "limit": 2, "offset": offset, "kind": "tickets"},
        ),
    )
    assert result["error"] == "BACKEND_CONTRACT_INVALID"


def test_full_page_cursor_moves_forward_and_terminal_page_is_empty():
    args = {**PERIOD, "limit": 2, "offset": 50}
    meta = {**args, "kind": "tickets"}
    result = run_payload(
        "get_report_supporting_records",
        args,
        response(
            "get_report_supporting_records",
            {"items": [{"id": "a"}, {"id": "b"}], "nextOffset": 52},
            meta,
        ),
    )
    assert result["data"]["nextOffset"] == 52
    result = run_payload(
        "get_report_supporting_records",
        {**args, "offset": 52},
        response(
            "get_report_supporting_records",
            {"items": [], "nextOffset": None},
            {**meta, "offset": 52},
        ),
    )
    assert result["outcome"] == "empty"


@pytest.mark.parametrize(
    "field,value",
    [
        ("categories", [None]),
        ("employees", ["admin"]),
        ("exportFormats", ["pdf"]),
        ("buildings", [{"id": B1}, {"id": B1}]),
    ],
)
def test_filter_options_do_not_advertise_invalid_records(field, value):
    fields = deepcopy(CASES[0][3])
    fields[field] = value
    assert run_payload(CASES[0][0], {}, fields)["error"] == "BACKEND_CONTRACT_INVALID"


@pytest.mark.parametrize(
    "field,value",
    [("facts", []), ("missingFields", "private"), ("facts", {"status": "failed"})],
)
def test_metadata_shape_or_fact_contradiction_is_rejected(field, value):
    body = export_response("get_report_export_status")
    body["agentContext"][field] = value
    assert (
        run_payload("get_report_export_status", {"export_id": EXPORT}, body)["error"]
        == "BACKEND_CONTRACT_INVALID"
    )


@pytest.mark.parametrize("field", ["downloadUrl", "kind", "execution"])
def test_export_requires_complete_status_fields(field):
    body = export_response(
        "get_report_export_status", status="failed", downloadUrl=None
    )
    del body[field]
    assert (
        run_payload("get_report_export_status", {"export_id": EXPORT}, body)["error"]
        == "BACKEND_CONTRACT_INVALID"
    )


def test_transport_retry_then_success_and_auth_revocation():
    async def run():
        calls = 0

        def handler(req):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise httpx.ConnectError("credential-secret", request=req)
            if calls == 2:
                return httpx.Response(200, json=response(CASES[0][0], CASES[0][3]))
            return httpx.Response(401)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            tools = ReportTools(
                ReportBackend("https://business.example", client=client),
                RuntimeContext("A", (B1,), "session=A"),
            )
            assert (await tools.get_report_filter_options())["outcome"] == "success"
            assert (await tools.get_report_filter_options())[
                "error"
            ] == "AUTHENTICATION_REQUIRED"
        assert calls == 3

    asyncio.run(run())


@pytest.mark.parametrize("status", [200, 201, 204])
def test_json_contract_failure_not_retried(status):
    result, requests = call(
        lambda _: httpx.Response(status, content=b"not json"),
        "get_report_filter_options",
        {},
        retries=2,
    )
    assert result["error"] == "BACKEND_CONTRACT_INVALID" and len(requests) == 1


def test_total_deadline_covers_slow_transport_and_keeps_write_unknown():
    async def run(write):
        calls = 0

        async def handler(req):
            nonlocal calls
            calls += 1
            await asyncio.sleep(1)
            return httpx.Response(200, json={})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            backend = ReportBackend(
                "https://business.example",
                client=client,
                operation_timeout_seconds=0.01,
            )
            tools = ReportTools(backend, RuntimeContext("A", (B1,), "session=A"))
            result = await tools.invoke(
                "create_report_export" if write else "get_report_filter_options",
                CASES[6][1] if write else {},
            )
            assert result["error"] == "BACKEND_UNAVAILABLE"
            assert result["execution_unknown"] is write and calls == 1

    asyncio.run(run(False))
    asyncio.run(run(True))


@pytest.mark.parametrize(
    "budget", [True, False, "10", None, float("nan"), float("inf"), 0, -1]
)
def test_invalid_timeout_configuration_fails_cleanly(budget):
    with pytest.raises(ValueError):
        ReportBackend("https://business.example", timeout_seconds=budget)


def test_operation_deadline_cannot_exceed_descriptor_budget():
    with pytest.raises(ValueError):
        ReportBackend("https://business.example", operation_timeout_seconds=60.1)


def test_owned_and_injected_http_clients_have_correct_lifecycle():
    async def run():
        owned = ReportBackend("https://business.example")
        await owned.aclose()
        assert owned.client.is_closed
        async with httpx.AsyncClient() as client:
            injected = ReportBackend("https://business.example", client=client)
            await injected.aclose()
            assert not client.is_closed

    asyncio.run(run())


@pytest.mark.parametrize("days", [1, 3660])
def test_period_accepts_exact_limits_and_leap_day(days):
    start = date(2024, 2, 29)
    value = EmployeeInput.model_validate(
        {
            **PERIOD,
            "from_date": start.isoformat(),
            "to_date": (start + timedelta(days=days)).isoformat(),
        }
    )
    assert value.timezone == "Asia/Ho_Chi_Minh"


def test_null_vs_omitted_category_do_not_change_http_filter():
    calls = []
    fields = deepcopy(CASES[4][3])

    def handler(req):
        calls.append(str(req.url))
        return httpx.Response(200, json=response(CASES[4][0], fields))

    a, _ = call(handler, CASES[4][0], PERIOD)
    b, _ = call(handler, CASES[4][0], {**PERIOD, "category_id": None})
    assert a["outcome"] == b["outcome"] and calls[0] == calls[1]


def test_success_does_not_mutate_backend_payload():
    fields = {"items": [employee()]}
    original = deepcopy(fields)
    run_payload("get_employee_performance_summary", PERIOD, fields)
    assert fields == original


@pytest.mark.parametrize(
    "fault", ["missing_period", "invalid_period", "missing_category", "duplicate_group"]
)
def test_frequency_group_identity_is_not_optional(fault):
    row = {
        "period": "2026-09-01",
        "category_id": CATEGORY,
        "category_name": "Điện",
        "incident_type_id": CATEGORY,
        "incident_type": "Mất điện",
        "incident_count": 2,
    }
    rows = [row]
    if fault == "missing_period":
        del row["period"]
    elif fault == "invalid_period":
        row["period"] = "2026-02-30"
    elif fault == "missing_category":
        del row["category_id"]
    else:
        rows.append(dict(row))
    fields = {
        "buildingId": B1,
        "interval": "month",
        "totalTickets": sum(r["incident_count"] for r in rows),
        "items": rows,
    }
    assert (
        run_payload(CASES[4][0], PERIOD, fields)["error"] == "BACKEND_CONTRACT_INVALID"
    )


def test_zero_total_with_fake_groups_is_rejected():
    fields = {
        "buildingId": B1,
        "interval": "month",
        "totalTickets": 0,
        "items": [{"incident_count": 0}],
    }
    assert (
        run_payload(CASES[4][0], PERIOD, fields)["error"] == "BACKEND_CONTRACT_INVALID"
    )


def test_json_numeric_money_keeps_digits_before_float_conversion():
    fields = deepcopy(CASES[3][3])
    fields["items"][0].update(
        billed_amount="EXACT_NUMBER", collected_amount="0", outstanding_amount="0"
    )
    body = json.dumps(response(CASES[3][0], fields)).replace(
        '"EXACT_NUMBER"', "9007199254740993.01"
    )
    result, _ = call(
        lambda _: httpx.Response(200, content=body), CASES[3][0], CASES[3][1]
    )
    assert result["data"]["items"][0]["billed_amount"] == "9007199254740993.01"
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("value", ["1_000", " 100 "])
def test_money_strings_follow_json_numeric_syntax(value):
    fields = deepcopy(CASES[3][3])
    fields["items"][0]["collected_amount"] = value
    assert (
        run_payload(CASES[3][0], CASES[3][1], fields)["error"]
        == "BACKEND_CONTRACT_INVALID"
    )


@pytest.mark.parametrize(
    "body", ['{"agentContext":{},"agentContext":{}}', '{"n":NaN}', "[]", "null"]
)
def test_ambiguous_or_non_object_json_is_rejected(body):
    result, requests = call(
        lambda _: httpx.Response(200, content=body),
        "get_report_filter_options",
        {},
        retries=2,
    )
    assert result["error"] == "BACKEND_CONTRACT_INVALID" and len(requests) == 1


def test_deadline_includes_retry_backoff():
    async def run():
        requests = []

        def handler(req):
            requests.append(req)
            return httpx.Response(503)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            backend = ReportBackend(
                "https://business.example",
                client=client,
                operation_timeout_seconds=0.02,
            )
            tools = ReportTools(backend, RuntimeContext("A", (B1,), "session=A"))
            result = await tools.get_report_filter_options()
            assert result["error"] == "BACKEND_UNAVAILABLE" and len(requests) == 1

    asyncio.run(run())


def test_external_cancel_after_export_send_propagates_and_does_not_retry():
    async def run():
        sent = asyncio.Event()
        requests = []

        async def handler(req):
            requests.append(req)
            sent.set()
            await asyncio.Future()

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            tools = ReportTools(
                ReportBackend("https://business.example", client=client),
                RuntimeContext("A", (B1,), "session=A"),
            )
            task = asyncio.create_task(tools.create_report_export(CASES[6][1]))
            await sent.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert (
                len(requests) == 1
                and json.loads(requests[0].content)["idempotency_key"]
                == CASES[6][1]["idempotency_key"]
            )

    asyncio.run(run())
