from copy import deepcopy

import httpx
import pytest
from helpers import (
    ARGS,
    B1,
    B2,
    OTHER,
    STAFF,
    STAFF2,
    STAR_ARGS,
    TYPE,
    dataset,
    metadata,
    run,
    uid,
)
from pydantic import TypeAdapter
from reporting.tools.catalog import MODELS, OUTPUTS, tool_descriptors
from reporting.tools.contracts import Failure


@pytest.mark.parametrize(
    "operation,args",
    [
        ("get_repair_bill_summary", ARGS),
        ("get_ticket_frequency_summary", ARGS),
        ("get_employee_star_summary", STAR_ARGS),
    ],
)
def test_reads_existing_routes_for_whole_zone_and_typed_result(operation, args):
    result, requests = run(operation, args)
    assert result["outcome"] == "success"
    assert result["scope"]["building_ids"] == [B1, B2]
    assert all(
        r.method == "GET" and r.headers["Cookie"] == "session=private" for r in requests
    )
    TypeAdapter(OUTPUTS[operation] | Failure).validate_python(result)
    assert not any(
        "-bills-summary" in r.url.path
        or "-ratings-summary" in r.url.path
        or "employee-performance" in r.url.path
        for r in requests
    )


def test_invoice_grand_total_added_exactly_once_across_buildings():
    result, requests = run("get_repair_bill_summary", ARGS)
    assert result["data"]["items"] == [
        {"currency": "VND", "invoice_count": 2, "billed_amount": "9007199254740993.02"}
    ]
    assert result["data"]["basis"] == "issued_repair_invoice_grand_total"
    assert sum(r.url.path.startswith("/invoices/") for r in requests) == 2


def test_currencies_stay_separate_and_nonrepair_bill_excluded():
    data = dataset()
    row = data["invoices"][B2][0]
    row["currency"] = "USD"
    data["details"][row["id"]]["invoice"]["currency"] = "USD"
    result, _ = run("get_repair_bill_summary", ARGS, data=data)
    assert len(result["data"]["items"]) == 2 and "total_amount" not in result["data"]
    data["details"][row["id"]]["lines"][0]["category_id"] = OTHER
    result, _ = run("get_repair_bill_summary", ARGS, data=data)
    assert result["data"]["items"][0]["invoice_count"] == 1


def test_mixed_invoice_is_not_counted_as_whole_repair_bill():
    data = dataset()
    iid = data["invoices"][B2][0]["id"]
    data["details"][iid]["lines"].append(
        {"id": uid(900), "invoice_id": iid, "category_id": OTHER, "total_amount": "0"}
    )
    result, _ = run("get_repair_bill_summary", ARGS, data=data)
    assert result["error"] == "REPORT_MIXED_INVOICE" and "data" not in result


def test_repair_categories_are_trusted_runtime_config_not_model_guess():
    result, requests = run("get_repair_bill_summary", ARGS, repair=())
    assert result["error"] == "REPORT_REPAIR_CATEGORIES_REQUIRED" and not requests
    result, requests = run(
        "get_repair_bill_summary", {**ARGS, "repair_category_ids": [TYPE]}
    )
    assert result["error"] == "REPORT_INPUT_INVALID" and not requests


def test_tickets_count_all_rows_and_incident_types_separately():
    result, _ = run("get_ticket_frequency_summary", ARGS)
    assert result["data"]["total_ticket_count"] == 5
    assert result["data"]["incident_ticket_count"] == 4
    assert result["data"]["non_incident_ticket_count"] == 1
    assert result["data"]["items"] == [
        {
            "incident_type_id": TYPE,
            "incident_type_name": "Điện",
            "ticket_count": 4,
            "share": 1.0,
        }
    ]


def test_customer_stars_filter_submission_period_and_weight_by_review_count():
    result, requests = run(
        "get_employee_star_summary", {**STAR_ARGS, "staff_ids": [STAFF, STAFF2]}
    )
    assert result["data"]["total_rating_count"] == 6
    assert result["data"]["average_stars"] == "2.17"
    assert result["data"]["items"][0]["average_stars"] == "4.50"
    assert result["period"]["timezone"] == "UTC"
    assert not any(r.url.path == "/reports/employee-performance" for r in requests)


@pytest.mark.parametrize(
    "date,expected",
    [
        ("2026-09-01T00:00:00Z", 1),
        ("2026-10-01T00:00:00Z", 0),
        ("2026-09-01T06:59:59+07:00", 0),
        ("2026-10-01T06:59:59+07:00", 1),
    ],
)
def test_feedback_half_open_utc_date_boundaries(date, expected):
    data = dataset()
    data["feedback"] = {
        (B1, STAFF): [{"id": uid(999), "score": 5, "submitted_at": date}],
        (B2, STAFF): [],
    }
    result, _ = run("get_employee_star_summary", STAR_ARGS, data=data)
    assert result["data"]["total_rating_count"] == expected
    assert result["data"]["average_stars"] == ("5.00" if expected else None)


def test_staff_with_feedback_does_not_need_any_job_and_missing_name_is_null():
    data = dataset()
    data["feedback"][(B1, OTHER)] = [
        {"id": uid(908), "score": 4, "submitted_at": "2026-09-02T00:00:00Z"}
    ]
    result, _ = run(
        "get_employee_star_summary", {**STAR_ARGS, "staff_ids": [OTHER]}, data=data
    )
    assert result["data"]["items"][0]["rating_count"] == 1
    assert result["data"]["items"][0]["staff_name"] is None


def test_full_page_requires_terminal_page_and_never_returns_truncated_total():
    data = dataset()
    data["feedback"][(B1, STAFF)] = [
        {"id": uid(1000 + i), "score": 5, "submitted_at": "2026-09-02T00:00:00Z"}
        for i in range(101)
    ]
    data["feedback"][(B2, STAFF)] = []
    result, requests = run("get_employee_star_summary", STAR_ARGS, data=data)
    assert result["data"]["total_rating_count"] == 101
    assert [
        r.url.params["offset"]
        for r in requests
        if r.url.path == "/reports/employee-feedback"
    ] == ["0", "100", "0"]
    result, _ = run("get_employee_star_summary", STAR_ARGS, data=data, max_pages=1)
    assert result["error"] == "REPORT_DATA_LIMIT_REACHED" and "data" not in result


def test_invoice_scan_reads_more_than_first_page():
    data = dataset()
    source = deepcopy(data["invoices"][B2][0])
    data["invoices"] = {B1: [], B2: []}
    data["details"] = {}
    for i in range(101):
        row = {**source, "id": uid(2000 + i)}
        data["invoices"][B1].append(row)
        data["details"][row["id"]] = {
            "invoice": row,
            "lines": [
                {
                    "id": uid(3000 + i),
                    "invoice_id": row["id"],
                    "category_id": TYPE,
                    "total_amount": "0.01",
                }
            ],
        }
    result, requests = run("get_repair_bill_summary", ARGS, data=data)
    assert result["data"]["items"][0]["billed_amount"] == "1.01"
    assert result["data"]["items"][0]["invoice_count"] == 101
    assert (
        len([r for r in requests if r.url.path == "/reports/supporting-records"]) == 3
    )


@pytest.mark.parametrize(
    "operation,args",
    [
        ("get_repair_bill_summary", ARGS),
        ("get_ticket_frequency_summary", ARGS),
        ("get_employee_star_summary", STAR_ARGS),
    ],
)
def test_component_error_is_failure_not_zero_or_partial_success(operation, args):
    def handler(request):
        if request.url.path not in ("/catalogs", "/reports/filter-options"):
            return httpx.Response(503, json={"secret": "private"})

    result, _ = run(operation, args, handler=handler)
    assert (
        result["error"] == "BACKEND_UNAVAILABLE"
        and "data" not in result
        and "private" not in str(result)
    )


def test_source_ids_duplicated_across_buildings_are_not_silently_counted_twice():
    data = dataset()
    data["invoices"][B2] = data["invoices"][B1]
    result, _ = run("get_repair_bill_summary", ARGS, data=data)
    assert result["error"] == "REPORT_SOURCE_DUPLICATED"


def test_single_building_summary_does_not_read_other_building():
    result, requests = run(
        "get_repair_bill_summary", {**ARGS, "scope_type": "building", "scope_id": B1}
    )
    assert result["data"]["items"][0]["invoice_count"] == 1
    assert all(r.url.params.get("buildingId") in (None, B1) for r in requests)


@pytest.mark.parametrize("nonrepair", [False, True])
def test_no_repair_invoices_returns_empty_after_all_buildings_read(nonrepair):
    data = dataset()
    if nonrepair:
        for detail in data["details"].values():
            detail["lines"][0]["category_id"] = OTHER
    else:
        data["invoices"] = {B1: [], B2: []}
    result, requests = run("get_repair_bill_summary", ARGS, data=data)
    assert result["outcome"] == "empty" and result["data"]["items"] == []
    assert {
        r.url.params["buildingId"]
        for r in requests
        if r.url.path == "/reports/supporting-records"
    } == {B1, B2}


def test_zero_tickets_is_valid_empty_not_backend_failure():
    data = dataset()
    data["tickets"] = {B1: [], B2: []}

    def handler(request):
        if request.url.path == "/reports/incident-frequency-summary":
            q = request.url.params
            return httpx.Response(
                200,
                json=metadata(
                    "get_incident_frequency_summary",
                    {
                        "buildingId": q["buildingId"],
                        "interval": "month",
                        "totalTickets": 0,
                        "items": [],
                    },
                    {
                        "building_id": q["buildingId"],
                        "from_date": q["fromDate"],
                        "to_date": q["toDate"],
                        "interval": "month",
                    },
                ),
            )

    result, _ = run("get_ticket_frequency_summary", ARGS, data=data, handler=handler)
    assert result["outcome"] == "empty"
    assert result["data"] == {
        "total_ticket_count": 0,
        "incident_ticket_count": 0,
        "non_incident_ticket_count": 0,
        "share_basis": "incident_ticket_count",
        "items": [],
    }


def test_four_read_descriptors_have_strict_inputs_and_full_outputs():
    descriptors = tool_descriptors()
    assert len(descriptors) == 4 and {d["name"] for d in descriptors} == set(MODELS)
    for d in descriptors:
        assert d["effect"] == "read" and d["requiredPermissions"] == ["reports:read"]
        assert d["inputSchema"]["additionalProperties"] is False
        assert "$defs" in d["outputSchema"] and "anyOf" in d["outputSchema"]
        assert not {
            "session_cookie",
            "repair_category_ids",
            "principal_id",
            "building_ids",
        } & set(d["inputSchema"]["properties"])


@pytest.mark.parametrize(
    "operation",
    [
        "get_employee_performance_summary",
        "create_report_export",
        "get_report_export_status",
        "get_report_supporting_records",
        "get_employee_feedback_details",
        "get_repair_revenue_summary",
    ],
)
def test_removed_operations_cannot_execute(operation):
    result, requests = run(operation)
    assert result["error"] == "REPORT_OPERATION_UNKNOWN" and not requests
