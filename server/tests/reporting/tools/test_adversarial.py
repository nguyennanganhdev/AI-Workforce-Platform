import asyncio
import json
from copy import deepcopy

import httpx
import pytest
from helpers import (
    ARGS,
    B1,
    B2,
    CATALOG,
    OPTIONS,
    STAFF,
    STAR_ARGS,
    TYPE,
    dataset,
    record_page,
    run,
)
from reporting.application.client import ReportBackend
from reporting.tools import ReportTools, RuntimeContext


@pytest.mark.parametrize("operation", [None, [], {}, True, 42, "unknown"])
def test_unknown_operation_has_no_http(operation):
    result, requests = run(operation)
    assert result["error"] == "REPORT_OPERATION_UNKNOWN" and not requests


@pytest.mark.parametrize(
    "mutation",
    [
        "identity",
        "building_ids",
        "bad_uuid",
        "bad_date",
        "reverse",
        "same",
        "long",
        "timezone",
        "legacy",
        "kind",
    ],
)
def test_invalid_input_never_sends_http(mutation):
    args = deepcopy(ARGS)
    if mutation == "identity":
        args["session_cookie"] = "admin"
    if mutation == "building_ids":
        args["building_ids"] = [B1, B2]
    if mutation == "bad_uuid":
        args["scope_id"] = "bad"
    if mutation == "bad_date":
        args["from_date"] = "20260901"
    if mutation == "reverse":
        args["from_date"] = "2026-11-01"
    if mutation == "same":
        args["from_date"] = args["to_date"]
    if mutation == "long":
        args["from_date"] = "2000-01-01"
    if mutation == "timezone":
        args["timezone"] = "UTC"
    if mutation == "legacy":
        args["building_id"] = args.pop("scope_id")
    if mutation == "kind":
        args["scope_type"] = "site"
    result, requests = run("get_repair_bill_summary", args)
    assert result["error"] == "REPORT_INPUT_INVALID" and not requests


@pytest.mark.parametrize("ids", [[], [STAFF, STAFF], ["bad"], None, "staff", [True]])
def test_staff_selection_is_required_typed_unique(ids):
    result, requests = run("get_employee_star_summary", {**ARGS, "staff_ids": ids})
    assert result["error"] == "REPORT_INPUT_INVALID" and not requests


def test_missing_staff_ids_cannot_be_auto_repaired_by_test_helper():
    result, requests = run("get_employee_star_summary", ARGS)
    assert result["error"] == "REPORT_INPUT_INVALID" and not requests


@pytest.mark.parametrize(
    "value",
    [
        True,
        None,
        -1,
        "-1",
        "1_000",
        " 100 ",
        "NaN",
        "Infinity",
        "1e10000",
        "1e-10000",
        "9" * 129,
    ],
)
def test_bad_money_fails_in_source_read(value):
    data = dataset()
    data["invoices"][B1][0]["grand_total"] = value
    result, _ = run("get_repair_bill_summary", ARGS, data=data)
    assert result["error"] == "BACKEND_CONTRACT_INVALID"


@pytest.mark.parametrize("value", [None, True, -1, 1.1, "1", 2**63, 0, 6])
def test_customer_star_score_must_be_integer_one_to_five(value):
    data = dataset()
    data["feedback"][(B1, STAFF)][0]["score"] = value
    result, _ = run("get_employee_star_summary", STAR_ARGS, data=data)
    assert result["error"] == "BACKEND_CONTRACT_INVALID"


@pytest.mark.parametrize(
    "mutation",
    [
        "id",
        "status",
        "currency",
        "ticket",
        "work",
        "issued",
        "line_invoice",
        "line_duplicate",
        "line_missing",
        "category",
    ],
)
def test_invoice_detail_identity_and_repair_classification_are_bound(mutation):
    data = dataset()
    row = data["invoices"][B1][0]
    detail = data["details"][row["id"]]
    invoice = detail["invoice"]
    line = detail["lines"][0]
    if mutation == "id":
        invoice["id"] = B2
    if mutation == "status":
        invoice["status"] = "draft"
    if mutation == "currency":
        invoice["currency"] = "USD"
    if mutation == "ticket":
        invoice["ticket_id"] = B2
    if mutation == "work":
        invoice["work_order_id"] = B2
    if mutation == "issued":
        invoice["issued_at"] = "2026-09-11T00:00:00Z"
    if mutation == "line_invoice":
        line["invoice_id"] = B2
    if mutation == "line_duplicate":
        detail["lines"].append(deepcopy(line))
    if mutation == "line_missing":
        detail["lines"] = []
    if mutation == "category":
        line["category_id"] = "bad"
    result, _ = run("get_repair_bill_summary", ARGS, data=data)
    assert result["error"] == "BACKEND_CONTRACT_INVALID"


def test_detail_money_does_not_override_precise_source_list_price():
    data = dataset()
    row = data["invoices"][B1][0]
    detail = data["details"][row["id"]]
    detail["invoice"]["grand_total"] = 9007199254740994.0
    detail["lines"][0]["total_amount"] = 9007199254740994.0
    result, _ = run("get_repair_bill_summary", ARGS, data=data)
    assert result["data"]["items"][0]["billed_amount"] == "9007199254740993.02"


@pytest.mark.parametrize(
    "detail_time",
    ["2026-09-10T00:00:00Z", "2026-09-10T00:00:00+00:00", "2026-09-10T07:00:00+07:00"],
)
def test_same_invoice_instant_can_have_different_iso_representation(detail_time):
    data = dataset()
    row = data["invoices"][B1][0]
    data["details"][row["id"]]["invoice"]["issued_at"] = detail_time
    result, _ = run("get_repair_bill_summary", ARGS, data=data)
    assert result["outcome"] == "success"
    assert result["data"]["items"][0]["invoice_count"] == 2


@pytest.mark.parametrize(
    "mutation",
    [
        "meta_missing",
        "resource_wrong",
        "facts_wrong",
        "missing_fields_wrong",
        "cursor_loop",
        "short_cursor",
        "too_many",
        "bad_id",
    ],
)
def test_paginated_payload_guards(mutation):
    def handler(request):
        if request.url.path == "/reports/employee-feedback":
            items = dataset()["feedback"][(B1, STAFF)]
            body = record_page(request, items, True)
            if mutation == "meta_missing":
                del body["agentContext"]
            if mutation == "resource_wrong":
                body["agentContext"]["resourceContext"]["staff_id"] = B1
            if mutation == "facts_wrong":
                body["agentContext"]["facts"]["items"] = []
            if mutation == "missing_fields_wrong":
                body["agentContext"]["missingFields"] = [1]
            if mutation == "cursor_loop":
                body["nextOffset"] = 0
            if mutation == "short_cursor":
                body["nextOffset"] = 2
            if mutation == "too_many":
                body["items"] *= 51
            if mutation == "bad_id":
                body["items"][0]["id"] = "bad"
            return httpx.Response(200, json=body)

    result, _ = run("get_employee_star_summary", STAR_ARGS, handler=handler)
    assert result["error"] == "BACKEND_CONTRACT_INVALID"


@pytest.mark.parametrize(
    "status,error",
    [
        (401, "AUTHENTICATION_REQUIRED"),
        (403, "REPORT_SCOPE_FORBIDDEN"),
        (404, "REPORT_NOT_FOUND"),
        (409, "REPORT_CONFLICT"),
        (422, "BACKEND_INPUT_REJECTED"),
        (429, "RATE_LIMITED"),
        (500, "BACKEND_UNAVAILABLE"),
        (302, "BACKEND_HTTP_ERROR"),
    ],
)
def test_http_error_no_fake_zero_or_raw_body(status, error):
    def handler(request):
        if request.url.path == "/reports/supporting-records":
            return httpx.Response(status, json={"secret": "private"})

    result, requests = run("get_repair_bill_summary", ARGS, handler=handler, retries=2)
    assert (
        result["error"] == error and "private" not in str(result) and len(requests) == 3
    )


@pytest.mark.parametrize(
    "raw",
    ['{"a":1,"a":2}', '{"a":NaN}', "[]", "not JSON", "[" * 1200 + "0" + "]" * 1200],
)
def test_bad_json_is_not_retried(raw):
    def handler(request):
        if request.url.path == "/reports/supporting-records":
            return httpx.Response(200, content=raw)

    result, requests = run("get_repair_bill_summary", ARGS, handler=handler, retries=2)
    assert result["error"] == "BACKEND_CONTRACT_INVALID" and len(requests) == 3


def test_native_json_money_precision_remains_exact():
    data = dataset()

    def handler(request):
        if request.url.path == "/reports/supporting-records":
            body = record_page(
                request, data["invoices"][request.url.params["buildingId"]]
            )
        elif request.url.path.startswith("/invoices/"):
            body = data["details"][request.url.path.split("/")[-1]]
        else:
            return None
        raw = json.dumps(body).replace('"9007199254740993.01"', "9007199254740993.01")
        return httpx.Response(200, content=raw)

    result, _ = run("get_repair_bill_summary", ARGS, handler=handler)
    assert result["data"]["items"][0]["billed_amount"] == "9007199254740993.02"
    json.dumps(result, allow_nan=False)


def test_stale_ticket_summary_is_not_used_when_incidents_exceed_records():
    data = dataset()
    data["tickets"] = {B1: [], B2: []}
    result, _ = run("get_ticket_frequency_summary", ARGS, data=data)
    assert result["error"] == "REPORT_SOURCE_INCONSISTENT"


def test_limits_do_not_silently_return_first_rows_only():
    result, _ = run("get_employee_star_summary", STAR_ARGS, max_records=1)
    assert result["error"] == "REPORT_DATA_LIMIT_REACHED" and "data" not in result


def test_total_deadline_includes_scope_reads():
    async def invoke():
        sent = []

        async def handler(request):
            sent.append(request)
            await asyncio.sleep(0.06 if request.url.path == "/catalogs" else 0.12)
            return httpx.Response(
                200, json=CATALOG if request.url.path == "/catalogs" else OPTIONS
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            tools = ReportTools(
                ReportBackend(
                    "https://business.example",
                    client=client,
                    operation_timeout_seconds=0.15,
                ),
                RuntimeContext("p", (B1, B2), "x=y", (TYPE,)),
            )
            result = await tools.get_repair_bill_summary(ARGS)
            assert result["error"] == "BACKEND_UNAVAILABLE" and len(sent) == 2

    asyncio.run(invoke())


def test_cancel_is_propagated():
    async def invoke():
        async def handler(request):
            raise asyncio.CancelledError

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            tools = ReportTools(
                ReportBackend("https://business.example", client=client),
                RuntimeContext("p", (B1,), "x=y"),
            )
            with pytest.raises(asyncio.CancelledError):
                await tools.filter_report_scope()

    asyncio.run(invoke())


@pytest.mark.parametrize("fault", [502, 503, 504, "transport"])
@pytest.mark.parametrize("recovers", [False, True])
def test_read_retry_recovers_or_fails_without_stale_response(fault, recovers):
    attempts = []

    def handler(request):
        if request.url.path == "/reports/supporting-records":
            attempts.append(request)
            if not recovers or len(attempts) == 1:
                if fault == "transport":
                    raise httpx.ReadTimeout(
                        "private transport diagnostic", request=request
                    )
                return httpx.Response(fault, json={"private": "untrusted"})

    result, _ = run("get_repair_bill_summary", ARGS, handler=handler, retries=1)
    if recovers:
        assert result["outcome"] == "success" and len(attempts) == 3
        assert result["data"]["items"][0]["invoice_count"] == 2
    else:
        assert result == {
            "outcome": "failure",
            "error": "BACKEND_UNAVAILABLE",
            "retryable": True,
        }
        assert len(attempts) == 2


@pytest.mark.parametrize(
    "value", [True, "1", None, 0, -1, float("nan"), float("inf"), 10**400]
)
@pytest.mark.parametrize("key", ["timeout_seconds", "operation_timeout_seconds"])
def test_invalid_budget_is_rejected(value, key):
    with pytest.raises(ValueError):
        ReportBackend("https://business.example", **{key: value})


@pytest.mark.parametrize("value", [True, 0, -1, 1.1, "2", None])
@pytest.mark.parametrize("key", ["max_pages", "max_records"])
def test_invalid_scan_limit_is_rejected(value, key):
    with pytest.raises(ValueError):
        ReportBackend("https://business.example", **{key: value})
