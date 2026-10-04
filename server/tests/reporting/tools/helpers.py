import asyncio
from copy import deepcopy
from uuid import UUID

import httpx
from reporting.application.client import ReportBackend
from reporting.tools import ReportTools, RuntimeContext

B1 = "11111111-1111-4111-8111-111111111111"
B2 = "22222222-2222-4222-8222-222222222222"
Z1 = "33333333-3333-4333-8333-333333333333"
Z2 = "44444444-4444-4444-8444-444444444444"
STAFF = "55555555-5555-4555-8555-555555555555"
TYPE = "66666666-6666-4666-8666-666666666666"
STAFF2 = "77777777-7777-4777-8777-777777777777"
OTHER = "88888888-8888-4888-8888-888888888888"
ARGS = {
    "scope_type": "zone",
    "scope_id": Z1,
    "from_date": "2026-09-01",
    "to_date": "2026-10-01",
}
STAR_ARGS = {**ARGS, "staff_ids": [STAFF]}
CATALOG = {
    "zones": [{"id": Z1, "name": "Sapphire"}],
    "buildings": [
        {"id": B1, "name": "S1.01", "zone_id": Z1},
        {"id": B2, "name": "S1.02", "zone_id": Z1},
    ],
}


def uid(number):
    return str(UUID(int=number + 2**100))


def metadata(operation, data, resource=None):
    return {
        **data,
        "agentContext": {
            "operation": operation,
            "source": "business_api",
            "facts": {},
            "resourceContext": resource or {},
            "missingFields": [],
        },
    }


OPTIONS = metadata(
    "get_report_filter_options",
    {
        "buildings": [{"id": B1, "name": "S1.01"}, {"id": B2, "name": "S1.02"}],
        "employees": [{"id": STAFF, "name": "A"}, {"id": STAFF2, "name": "B"}],
    },
)


def record_page(request, items, feedback=False):
    q = request.url.params
    resource = {
        "building_id": q["buildingId"],
        "limit": int(q["limit"]),
        "offset": int(q["offset"]),
    }
    if feedback:
        resource["staff_id"] = q["staffId"]
    else:
        resource.update(from_date=q["fromDate"], to_date=q["toDate"], kind=q["kind"])
    return metadata(
        "get_employee_feedback_details"
        if feedback
        else "get_report_supporting_records",
        {
            "items": items,
            "nextOffset": resource["offset"] + len(items)
            if len(items) == resource["limit"]
            else None,
        },
        resource,
    )


def dataset():
    invoices, details, tickets, feedback = {}, {}, {}, {}
    for index, building in enumerate((B1, B2)):
        price = "9007199254740993.01" if index == 0 else "0.01"
        iid, tid, wid, lid = [uid(100 + index * 10 + n) for n in range(4)]
        invoice = {
            "id": iid,
            "invoice_no": f"INV{index}",
            "status": "issued",
            "grand_total": price,
            "currency": "VND",
            "ticket_id": tid,
            "work_order_id": wid,
            "issued_at": "2026-09-10T00:00:00+00:00",
        }
        invoices[building] = [invoice]
        details[iid] = {
            "invoice": deepcopy(invoice),
            "lines": [
                {
                    "id": lid,
                    "invoice_id": iid,
                    "category_id": TYPE,
                    "total_amount": price,
                }
            ],
            "collectedAmount": "0",
            "outstandingAmount": price,
        }
        tickets[building] = [
            {"id": uid(200 + index * 10 + n)} for n in range(3 if index == 0 else 2)
        ]
        feedback[(building, STAFF)] = [
            {
                "id": uid(300 + index * 10 + n),
                "score": s,
                "submitted_at": "2026-09-12T00:00:00Z"
                if index == 0
                else "2026-08-31T23:59:59Z",
            }
            for n, s in enumerate((4, 5) if index == 0 else (1,))
        ]
        feedback[(building, STAFF2)] = [
            {
                "id": uid(400 + index * 10 + n),
                "score": 1,
                "submitted_at": "2026-09-13T00:00:00Z",
            }
            for n in range(3 if index == 0 else 1)
        ]
    return {
        "invoices": invoices,
        "details": details,
        "tickets": tickets,
        "feedback": feedback,
    }


def run(
    operation,
    arguments=None,
    *,
    catalog=None,
    options=None,
    data=None,
    grants=(B1, B2),
    repair=(TYPE,),
    retries=0,
    handler=None,
    budget=60,
    max_pages=100,
    max_records=10000,
):
    requests = []
    data = dataset() if data is None else data

    def transport(request):
        requests.append(request)
        if handler:
            response = handler(request)
            if response is not None:
                return response
        path = request.url.path
        q = request.url.params
        if path == "/catalogs":
            value = CATALOG if catalog is None else catalog
        elif path == "/reports/filter-options":
            value = OPTIONS if options is None else options
        elif path.startswith("/invoices/"):
            value = data["details"][path.split("/")[-1]]
        elif path == "/reports/supporting-records":
            all_items = data[q["kind"]][q["buildingId"]]
            offset = int(q["offset"])
            limit = int(q["limit"])
            value = record_page(request, all_items[offset : offset + limit])
        elif path == "/reports/employee-feedback":
            all_items = data["feedback"].get((q["buildingId"], q["staffId"]), [])
            offset = int(q["offset"])
            limit = int(q["limit"])
            value = record_page(request, all_items[offset : offset + limit], True)
        elif path == "/reports/incident-frequency-summary":
            resource = {
                "building_id": q["buildingId"],
                "from_date": q["fromDate"],
                "to_date": q["toDate"],
                "interval": "month",
            }
            value = metadata(
                "get_incident_frequency_summary",
                {
                    "buildingId": q["buildingId"],
                    "interval": "month",
                    "totalTickets": 2,
                    "items": [
                        {
                            "period": "2026-09-01",
                            "category_id": TYPE,
                            "incident_type_id": TYPE,
                            "incident_type": "Điện",
                            "incident_count": 2,
                        }
                    ],
                },
                resource,
            )
        else:
            return httpx.Response(404)
        return httpx.Response(200, json=value)

    async def invoke():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(transport)
        ) as client:
            backend = ReportBackend(
                "https://business.example",
                client=client,
                read_retries=retries,
                operation_timeout_seconds=budget,
                max_pages=max_pages,
                max_records=max_records,
            )
            tools = ReportTools(
                backend, RuntimeContext("principal", grants, "session=private", repair)
            )
            return await tools.invoke(operation, {} if arguments is None else arguments)

    return asyncio.run(invoke()), requests
