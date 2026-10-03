"""Contract tests use explicit mock transport; no production fallback."""

import asyncio

import httpx
import pytest
from reporting.application.client import ReportBackend
from reporting.tools import ReportTools, RuntimeContext
from reporting.tools.catalog import MODELS, tool_descriptors

B1 = "11111111-1111-4111-8111-111111111111"
B2 = "22222222-2222-4222-8222-222222222222"
STAFF = "33333333-3333-4333-8333-333333333333"
CATEGORY = "44444444-4444-4444-8444-444444444444"
EXPORT = "55555555-5555-4555-8555-555555555555"
PERIOD = {"building_id": B1, "from_date": "2026-09-01", "to_date": "2026-10-01"}


def response(operation, fields, resource=None):
    if resource is None and operation not in (
        "get_report_filter_options",
        "create_report_export",
        "get_report_export_status",
    ):
        arguments = {
            "get_employee_performance_summary": PERIOD,
            "get_employee_feedback_details": {"building_id": B1, "staff_id": STAFF},
            "get_repair_revenue_summary": {**PERIOD, "category_id": CATEGORY},
            "get_incident_frequency_summary": PERIOD,
            "get_report_supporting_records": PERIOD,
        }[operation]
        resource = (
            MODELS[operation].model_validate(arguments).model_dump(exclude_none=True)
        )
        resource.pop("timezone", None)
    return {
        **fields,
        "agentContext": {
            "operation": operation,
            "facts": {},
            "missingFields": [],
            "resourceContext": resource or {},
            "source": "business_api",
        },
    }


def export_response(operation="create_report_export", **overrides):
    return response(
        operation,
        {
            "id": EXPORT,
            "reportId": EXPORT,
            "jobId": EXPORT,
            "building_id": B1,
            "kind": "incident_frequency",
            "status": "ready",
            "execution": "synchronous",
            "downloadUrl": f"/reports/exports/{EXPORT}/content",
            **overrides,
        },
    )


def employee(**overrides):
    return {
        "staff_id": STAFF,
        "name": "Kỹ thuật A",
        "assigned_count": 8,
        "completed_count": 5,
        "timed_completion_count": 4,
        "on_time_count": 3,
        "average_processing_seconds": 600.0,
        "redo_count": 1,
        "average_rating": 4.5,
        "rating_count": 2,
        "on_time_rate": 999,
        **overrides,
    }


def harness(handler, *, retries=0, building=B1, cookie="vinhomes_session=private"):
    requests = []

    def transport(request):
        requests.append(request)
        return handler(request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(transport))
    backend = ReportBackend(
        "https://business.example", client=client, read_retries=retries
    )
    tools = ReportTools(backend, RuntimeContext("principal-A", (building,), cookie))
    return tools, requests, client


def call(handler, operation, arguments, *, retries=0):
    async def run():
        tools, requests, client = harness(handler, retries=retries)
        async with client:
            result = await tools.invoke(operation, arguments)
        return result, requests

    return asyncio.run(run())


CASES = [
    (
        "get_report_filter_options",
        {},
        "/reports/filter-options",
        {
            "buildings": [{"id": B1}],
            "categories": [],
            "employees": [],
            "exportFormats": ["docx"],
        },
    ),
    (
        "get_employee_performance_summary",
        PERIOD,
        "/reports/employee-performance",
        {"items": [employee()]},
    ),
    (
        "get_employee_feedback_details",
        {"building_id": B1, "staff_id": STAFF},
        "/reports/employee-feedback",
        {"items": [{"id": "review-1", "score": 5}], "nextOffset": None},
    ),
    (
        "get_repair_revenue_summary",
        {**PERIOD, "category_id": CATEGORY},
        "/reports/repair-revenue",
        {
            "items": [
                {
                    "currency": "VND",
                    "billed_amount": "100000.10",
                    "collected_amount": "70000.05",
                    "outstanding_amount": "30000.05",
                    "billed_work_count": 1,
                    "invoice_count": 1,
                }
            ],
            "laborMaterialsSplit": None,
        },
    ),
    (
        "get_incident_frequency_summary",
        PERIOD,
        "/reports/incident-frequency-summary",
        {
            "buildingId": B1,
            "interval": "month",
            "totalTickets": 2,
            "items": [
                {
                    "period": "2026-09-01",
                    "category_id": CATEGORY,
                    "category_name": "Điện",
                    "incident_type_id": CATEGORY,
                    "incident_type": "Mất điện",
                    "incident_count": 2,
                    "share": 999,
                }
            ],
        },
    ),
    (
        "get_report_supporting_records",
        PERIOD,
        "/reports/supporting-records",
        {"items": [{"id": "ticket-1"}], "nextOffset": None},
    ),
    (
        "create_report_export",
        {**PERIOD, "kind": "incident_frequency", "idempotency_key": "run-A-export-1"},
        "/reports/exports",
        export_response(),
    ),
    (
        "get_report_export_status",
        {"export_id": EXPORT},
        f"/reports/exports/{EXPORT}",
        export_response("get_report_export_status"),
    ),
]


@pytest.mark.parametrize("operation,args,path,fields", CASES)
def test_eight_routes(operation, args, path, fields):
    body = fields if "agentContext" in fields else response(operation, fields)
    result, requests = call(lambda _: httpx.Response(200, json=body), operation, args)
    assert result["outcome"] in ("success", "partial")
    assert len(requests) == 1
    req = requests[0]
    assert req.url.path == path
    assert req.headers["cookie"] == "vinhomes_session=private"
    assert "X-Demo-Actor" not in req.headers
    assert "timezone" not in req.url.params
    assert result["as_of"] is None and result["snapshot_id"] is None
    assert "metric_version" in result["missing_data"]
    assert "private" not in str(result)
    assert "idempotency_key" not in str(result["source_references"])
    if operation == "create_report_export":
        import json

        assert req.method == "POST"
        assert json.loads(req.content)["idempotency_key"] == "run-A-export-1"
        assert "timezone" not in json.loads(req.content)
    elif "building_id" in args:
        assert req.url.params["buildingId"] == B1
        assert "building_id" not in req.url.params


@pytest.mark.parametrize(
    "change",
    [
        {"building_id": B2},
        {"scope_ids": [B2]},
        {"principal_id": "admin"},
        {"session_cookie": "forged"},
        {"sql": "select *"},
        {"url": "https://evil.example"},
        {"from_date": "2026-10-01"},
        {"from_date": "2026-02-30"},
        {"from_date": "20260901"},
        {"timezone": "bad/timezone"},
        {"building_id": "../admin"},
        {"to_date": "2040-01-01"},
    ],
)
def test_untrusted_input_never_reaches_http(change):
    result, requests = call(
        lambda _: pytest.fail("Unexpected HTTP call"),
        "get_employee_performance_summary",
        {**PERIOD, **change},
    )
    assert result["outcome"] == "failure" and not requests


@pytest.mark.parametrize(
    "args",
    [
        {"kind": "employee_performance"},
        {"kind": "repair_revenue"},
        {"kind": "issued_revenue"},
        {"kind": "incident_frequency", "category_id": CATEGORY},
        {"kind": "incident_frequency", "format": "pdf"},
        {"kind": "incident_frequency", "idempotency_key": " "},
    ],
)
def test_exports_reject_unsupported_semantics(args):
    result, requests = call(
        lambda _: pytest.fail("Unexpected HTTP call"),
        "create_report_export",
        {**PERIOD, "idempotency_key": "key", **args},
    )
    assert result["error"] == "REPORT_INPUT_INVALID" and not requests


def test_ratios_computed_by_code_and_zero_denominator_is_missing():
    body = response(
        "get_employee_performance_summary",
        {
            "items": [
                employee(
                    timed_completion_count=0,
                    on_time_count=0,
                    rating_count=0,
                    average_rating=None,
                )
            ]
        },
    )
    result, _ = call(
        lambda _: httpx.Response(200, json=body),
        "get_employee_performance_summary",
        PERIOD,
    )
    assert result["outcome"] == "partial"
    assert result["data"]["items"][0]["on_time_rate"] is None
    assert "items[0].average_rating" in result["missing_data"]


def test_ratio_and_money_precision():
    emp = response("get_employee_performance_summary", {"items": [employee()]})
    result, _ = call(
        lambda _: httpx.Response(200, json=emp),
        "get_employee_performance_summary",
        PERIOD,
    )
    assert result["data"]["items"][0]["on_time_rate"] == 0.75
    op, args, _, fields = CASES[3]
    result, _ = call(lambda _: httpx.Response(200, json=response(op, fields)), op, args)
    assert result["data"]["items"][0]["billed_amount"] == "100000.10"


def test_frequency_uses_ticket_total_and_validates_sum():
    op, args, _, fields = CASES[4]
    result, _ = call(lambda _: httpx.Response(200, json=response(op, fields)), op, args)
    assert result["data"]["items"][0]["share"] == 1.0
    bad = {**fields, "totalTickets": 3}
    result, _ = call(lambda _: httpx.Response(200, json=response(op, bad)), op, args)
    assert result["error"] == "BACKEND_CONTRACT_INVALID"


def test_empty_distinct_from_http_error():
    op = "get_employee_performance_summary"
    result, _ = call(
        lambda _: httpx.Response(200, json=response(op, {"items": []})), op, PERIOD
    )
    assert result["outcome"] == "empty"
    failed, _ = call(
        lambda _: httpx.Response(503, text="secret backend error"), op, PERIOD
    )
    assert failed["outcome"] == "failure" and "secret" not in str(failed)


@pytest.mark.parametrize(
    "status,error",
    [
        (401, "AUTHENTICATION_REQUIRED"),
        (403, "REPORT_SCOPE_FORBIDDEN"),
        (404, "REPORT_NOT_FOUND"),
        (409, "REPORT_CONFLICT"),
        (422, "BACKEND_INPUT_REJECTED"),
        (429, "RATE_LIMITED"),
    ],
)
def test_error_mapping_without_retry(status, error):
    result, reqs = call(
        lambda _: httpx.Response(status, text="private"),
        "get_report_filter_options",
        {},
        retries=2,
    )
    assert result["error"] == error and len(reqs) == 1 and "private" not in str(result)


def test_read_retries_bounded():
    result, reqs = call(
        lambda _: httpx.Response(503), "get_report_filter_options", {}, retries=2
    )
    assert result["retryable"] and len(reqs) == 3


@pytest.mark.parametrize(
    "failure", ["timeout", "500", "bad_json", "bad_shape", "redirect"]
)
def test_export_unknown_not_automatically_retried(failure):
    def handler(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("private", request=request)
        if failure == "500":
            return httpx.Response(500)
        if failure == "redirect":
            return httpx.Response(302, headers={"location": "https://evil.example"})
        return httpx.Response(200, text="invalid" if failure == "bad_json" else "{}")

    result, reqs = call(handler, "create_report_export", CASES[6][1], retries=2)
    assert len(reqs) == 1 and result["execution_unknown"]


def test_retry_same_export_key_is_preserved():
    async def run():
        seen = []

        def handler(req):
            seen.append(req.content)
            return httpx.Response(201, json=export_response())

        tools, _reqs, client = harness(handler)
        async with client:
            a = await tools.create_report_export(CASES[6][1])
            b = await tools.create_report_export(CASES[6][1])
        assert seen[0] == seen[1]
        assert a["data"]["reportId"] == b["data"]["reportId"]

    asyncio.run(run())


@pytest.mark.parametrize(
    "change",
    [
        {"downloadUrl": "https://evil.example/docx"},
        {"reportId": B2},
        {"building_id": B2},
        {"status": "invented"},
        {"jobId": B2},
    ],
)
def test_export_response_binding(change):
    result, _ = call(
        lambda _: httpx.Response(
            200, json=export_response("get_report_export_status", **change)
        ),
        "get_report_export_status",
        {"export_id": EXPORT},
    )
    assert result["error"] == "BACKEND_CONTRACT_INVALID"


def test_revocation_checked_again_by_backend_for_status():
    result, reqs = call(
        lambda _: httpx.Response(403), "get_report_export_status", {"export_id": EXPORT}
    )
    assert result["error"] == "REPORT_SCOPE_FORBIDDEN" and len(reqs) == 1


def test_concurrent_principals_keep_cookies_and_scope_separate():
    async def run():
        async def handler(req):
            await asyncio.sleep(0)
            building = req.url.params["buildingId"]
            assert req.headers["cookie"] == (
                "session=A" if building == B1 else "session=B"
            )
            return httpx.Response(
                200,
                json=response(
                    "get_employee_performance_summary",
                    {"items": []},
                    {**PERIOD, "building_id": building},
                ),
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            backend = ReportBackend("https://business.example", client=client)
            a = ReportTools(backend, RuntimeContext("A", (B1,), "session=A"))
            b = ReportTools(backend, RuntimeContext("B", (B2,), "session=B"))
            results = await asyncio.gather(
                a.get_employee_performance_summary(PERIOD),
                b.get_employee_performance_summary({**PERIOD, "building_id": B2}),
            )
            assert all(r["outcome"] == "empty" for r in results)
            forbidden = await b.get_employee_performance_summary(PERIOD)
            assert forbidden["error"] == "REPORT_SCOPE_FORBIDDEN"

    asyncio.run(run())


def test_mismatched_response_resource_is_rejected():
    body = response(
        "get_employee_performance_summary", {"items": []}, {"building_id": B2}
    )
    result, _ = call(
        lambda _: httpx.Response(200, json=body),
        "get_employee_performance_summary",
        PERIOD,
    )
    assert result["error"] == "BACKEND_CONTRACT_INVALID"


@pytest.mark.parametrize(
    "row",
    [
        employee(assigned_count=True),
        employee(on_time_count=9),
        employee(average_rating=float("inf")),
        employee(redo_count=-1),
    ],
)
def test_invalid_metric_values_rejected(row):
    # httpx's JSON encoder correctly refuses infinity; simulate a raw invalid JSON producer.
    import json

    body = response("get_employee_performance_summary", {"items": [row]})
    result, _ = call(
        lambda _: httpx.Response(200, content=json.dumps(body)),
        "get_employee_performance_summary",
        PERIOD,
    )
    assert result["error"] == "BACKEND_CONTRACT_INVALID"


def test_catalog_has_strict_inputs_and_no_identity_fields():
    catalog = tool_descriptors()
    assert len(catalog) == 8 and {t["name"] for t in catalog} == set(MODELS)
    for tool in catalog:
        schema = tool["inputSchema"]
        assert schema["additionalProperties"] is False
        assert (
            not {"session_cookie", "principal_id", "allowed_building_ids", "sql", "url"}
            & schema["properties"].keys()
        )
        assert tool["requiresIdempotencyKey"] == (tool["effect"] == "write")
        assert tool["retry"]["maxRetries"] == 0


def test_cancel_propagates_without_retry():
    async def handler(req):
        raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        call(handler, "get_report_filter_options", {}, retries=2)


@pytest.mark.parametrize(
    "url",
    [
        "http://business.example",
        "https://user:pass@example.com",
        "https://example.com?token=private",
        "file:///data",
    ],
)
def test_unsafe_backend_url_rejected(url):
    with pytest.raises(ValueError):
        ReportBackend(url)
