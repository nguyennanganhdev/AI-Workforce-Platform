"""Ticket-scoped travel simulation with durable inventory, exact resident consent and Platform-owned messaging."""

import hashlib
import inspect
import json
import os
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import text

from . import platform_work as work
from .mock_travel import data, service
from .platform import TENANT, command
from .travel_models import SEARCH, SELECTION, CancelSelection

KINDS = ("hotel", "bus", "restaurant")
CATALOG = {"hotel": data.HOTELS, "bus": data.BUS_TRIPS, "restaurant": data.RESTAURANTS}
BOOKINGS = {
    "hotel": data.HOTEL_BOOKINGS,
    "bus": data.BUS_BOOKINGS,
    "restaurant": data.RESTAURANT_BOOKINGS,
}
SEARCH_CALLS = {
    "hotel": service.search_hotels,
    "bus": service.search_bus_trips,
    "restaurant": service.search_restaurants,
}
DETAILS = {
    "hotel": service.get_hotel_details,
    "bus": service.get_bus_trip_details,
    "restaurant": service.get_restaurant_details,
}
AVAILABILITY = {
    "hotel": service.check_hotel_availability,
    "bus": service.check_bus_availability,
    "restaurant": service.check_restaurant_availability,
}
BOOK = {
    "hotel": service.book_hotel,
    "bus": service.book_bus_trip,
    "restaurant": service.book_restaurant,
}
CANCEL = {
    "hotel": service.cancel_hotel_booking,
    "bus": service.cancel_bus_booking,
    "restaurant": service.cancel_restaurant_booking,
}
PRIVATE = {"customer_name", "customer_phone", "customer_email", "passenger_names"}


def safe(value):
    if isinstance(value, dict):
        return {key: safe(item) for key, item in value.items() if key not in PRIVATE}
    if isinstance(value, list):
        return [safe(item) for item in value]
    return value


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()


def checked(value):
    if not value.get("success"):
        error = value.get("error") or {}
        raise work.Refused(
            error.get("message", "Không thực hiện được mô phỏng."),
            "TRAVEL_" + error.get("code", "REFUSED"),
        )
    return deepcopy(value)


def reply(**values):
    return {
        "provider_mode": "mock",
        "is_simulation": True,
        "real_booking": False,
        **safe(values),
    }


def inputs(kind, values, search=False):
    if kind not in KINDS:
        raise work.Refused("Loại dịch vụ không được hỗ trợ.", "TRAVEL_KIND_INVALID")
    try:
        return (
            (SEARCH if search else SELECTION)[kind].model_validate(values).model_dump()
        )
    except ValidationError:
        raise work.Refused(
            "Thông số không hợp lệ; không truyền danh tính/điện thoại cư dân vào công cụ.",
            "TRAVEL_INPUT_INVALID",
        ) from None


async def scope(db, ticket_id, lock=False):
    if os.getenv("VINHOMES_TRAVEL_MOCK_ENABLED", "") != "1":
        raise work.Refused("Mô phỏng travel chưa được bật.", "TRAVEL_DISABLED")
    ticket = await work._ticket(db, ticket_id, lock)
    if ticket["category_code"] != "travel":
        raise work.Refused(
            "Công cụ travel chỉ dùng cho yêu cầu travel đã bàn giao.",
            "TRAVEL_TICKET_REQUIRED",
        )
    if ticket["status"] in ("closed", "cancelled"):
        raise work.Refused("Yêu cầu đã kết thúc.", "TRAVEL_TICKET_CLOSED")
    return ticket


async def hydrate(db):
    # Serializes inventory read/check/write across API workers and restarts. RLS isolates the mock provider per tenant.
    await db.execute(
        text(
            f"select pg_advisory_xact_lock(hashtextextended(cast({TENANT} as text)||:lock_suffix,0))"
        ),
        {"lock_suffix": ":travel-mock"},
    )
    catalog = (
        (
            await db.execute(
                text(
                    f"select kind,data from travel_mock_catalog where tenant_id={TENANT} order by kind,service_id"
                )
            )
        )
        .mappings()
        .all()
    )
    if {row["kind"] for row in catalog} != set(KINDS):
        raise work.Refused("Danh mục mô phỏng chưa được nạp.", "TRAVEL_CATALOG_MISSING")
    for kind in KINDS:
        CATALOG[kind][:] = [row["data"] for row in catalog if row["kind"] == kind]
    bookings = (
        (
            await db.execute(
                text(
                    f"select kind,data from travel_mock_bookings where tenant_id={TENANT} order by created_at,id"
                )
            )
        )
        .mappings()
        .all()
    )
    for kind in KINDS:
        BOOKINGS[kind][:] = [row["data"] for row in bookings if row["kind"] == kind]


async def catalog(db, ticket_id):
    await scope(db, ticket_id)
    await hydrate(db)
    return reply(status="mock_catalog", catalog=checked(service.get_service_catalog()))


async def search(db, ticket_id, kind, criteria):
    await scope(db, ticket_id)
    values = inputs(kind, criteria, search=True)
    await hydrate(db)
    return reply(status="mock_results", results=checked(SEARCH_CALLS[kind](**values)))


async def details(db, ticket_id, kind, service_id):
    await scope(db, ticket_id)
    if kind not in KINDS:
        raise work.Refused("Loại dịch vụ không hợp lệ.", "TRAVEL_KIND_INVALID")
    await hydrate(db)
    return reply(status="mock_details", details=checked(DETAILS[kind](service_id)))


def availability_result(kind, selection):
    names = inspect.signature(AVAILABILITY[kind]).parameters
    return checked(
        AVAILABILITY[kind](
            **{key: value for key, value in selection.items() if key in names}
        )
    )


def terms(kind, selection):
    resource_key = {
        "hotel": "hotel_id",
        "bus": "trip_id",
        "restaurant": "restaurant_id",
    }[kind]
    found = checked(DETAILS[kind](selection[resource_key]))
    resource = found[
        {"hotel": "hotel", "bus": "trip", "restaurant": "restaurant"}[kind]
    ]
    return {
        key: resource.get(key)
        for key in (
            "name",
            "operator",
            "address",
            "cancellation_policy",
            "check_in_time",
            "check_out_time",
            "opening_hours",
        )
    }


async def availability(db, ticket_id, kind, selection):
    await scope(db, ticket_id)
    values = inputs(kind, selection)
    await hydrate(db)
    return reply(
        status="mock_availability", availability=availability_result(kind, values)
    )


def version(ticket, expected):
    if expected is None:
        raise work.Refused("Cần phiên bản ticket hiện tại.", "TICKET_VERSION_REQUIRED")
    if expected != ticket["version"]:
        raise work.Refused(
            "Ticket đã thay đổi; đọc lại trước khi thao tác.", "STALE_TICKET_VERSION"
        )


async def booking_row(db, ticket_id, booking_ref):
    try:
        key = UUID(str(booking_ref))
    except ValueError:
        raise work.Refused(
            "Mã booking không hợp lệ.", "TRAVEL_BOOKING_NOT_FOUND"
        ) from None
    row = (
        (
            await db.execute(
                text(f"""select * from travel_mock_bookings
        where tenant_id={TENANT} and ticket_id=:ticket and id=:id"""),
                {"ticket": ticket_id, "id": key},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise work.Refused(
            "Không có booking này trong yêu cầu.", "TRAVEL_BOOKING_NOT_FOUND"
        )
    return row


async def prepare(
    db, ticket_id, kind, operation, selection, client_reference, expected_ticket_version
):
    ticket = await scope(db, ticket_id, True)
    if operation not in ("book", "cancel") or kind not in KINDS:
        raise work.Refused("Thao tác travel không hợp lệ.", "TRAVEL_INPUT_INVALID")
    try:
        values = (
            inputs(kind, selection)
            if operation == "book"
            else CancelSelection.model_validate(selection).model_dump()
        )
    except ValidationError:
        raise work.Refused(
            "Thông số hủy không hợp lệ.", "TRAVEL_INPUT_INVALID"
        ) from None
    if (
        operation == "book"
        and kind == "bus"
        and (not values["pickup_point"] or not values["dropoff_point"])
    ):
        raise work.Refused(
            "Cần cư dân chọn rõ điểm đón và trả trước khi xác nhận.",
            "TRAVEL_PICKUP_REQUIRED",
        )
    fingerprint = digest({"kind": kind, "operation": operation, "selection": values})
    existing = (
        (
            await db.execute(
                text(f"""select * from travel_mock_intents
        where tenant_id={TENANT} and ticket_id=:ticket and client_reference=:ref"""),
                {"ticket": ticket["id"], "ref": client_reference},
            )
        )
        .mappings()
        .first()
    )
    if existing:
        if existing["request_hash"] != fingerprint:
            raise work.Refused(
                "Reference đã được dùng với nội dung khác.", "REFERENCE_CONFLICT"
            )
        return prepared(existing)
    version(ticket, expected_ticket_version)
    await hydrate(db)
    if operation == "book":
        available = availability_result(kind, values)
        if not available["is_available"]:
            raise work.Refused("Không còn đủ chỗ mô phỏng.", "TRAVEL_SOLD_OUT")
        if (
            kind == "hotel"
            and values["guests"]
            > available["room_type"]["max_guests"] * values["rooms"]
        ):
            raise work.Refused(
                "Số khách vượt sức chứa phòng.", "TRAVEL_CAPACITY_EXCEEDED"
            )
        # Keep the full selection, price and cancellation policy bound to the approval hash.
        quote = {
            "operation": operation,
            "kind": kind,
            "selection": values,
            "availability": available,
            "amount": available.get("total_price", available.get("estimated_total")),
            "terms": terms(kind, values),
        }
        if quote["amount"] is None:
            raise work.Refused(
                "Không có giá mô phỏng để xác nhận.", "TRAVEL_QUOTE_MISSING"
            )
    else:
        booking = await booking_row(db, ticket["id"], values["booking_ref"])
        if booking["kind"] != kind or booking["status"] != "confirmed":
            raise work.Refused(
                "Booking không thể hủy theo lựa chọn này.",
                "TRAVEL_BOOKING_NOT_CANCELLABLE",
            )
        quote = {
            "operation": operation,
            "kind": kind,
            "selection": values,
            "booking": safe(booking["data"]),
            "amount": None,
            "financial_settlement": "not_simulated",
        }
    identifier = uuid4()
    arguments_hash = digest(
        {"intent_id": str(identifier), "ticket_id": str(ticket["id"]), "quote": quote}
    )
    expires = datetime.now(timezone.utc) + timedelta(minutes=15)
    row = (
        (
            await db.execute(
                text(f"""insert into travel_mock_intents
        (id,tenant_id,ticket_id,client_reference,request_hash,kind,operation,selection,quote,arguments_hash,expires_at)
        values(:id,{TENANT},:ticket,:ref,:hash,:kind,:operation,cast(:selection as jsonb),cast(:quote as jsonb),:arguments,:expires)
        returning *"""),
                {
                    "id": identifier,
                    "ticket": ticket["id"],
                    "ref": client_reference,
                    "hash": fingerprint,
                    "kind": kind,
                    "operation": operation,
                    "selection": json.dumps(values),
                    "quote": json.dumps(quote, ensure_ascii=False),
                    "arguments": arguments_hash,
                    "expires": expires,
                },
            )
        )
        .mappings()
        .one()
    )
    return prepared(row)


def prepared(row):
    summary = {
        "text": "MÔ PHỎNG: "
        + ("đặt chỗ" if row["operation"] == "book" else "hủy đặt chỗ")
        + ". Không đặt với nhà cung cấp thật hoặc thu/hoàn tiền. Chi tiết: "
        + json.dumps(safe(row["quote"]), ensure_ascii=False)
    }
    amount = row["quote"].get("amount")
    if amount is not None:
        summary.update(
            items=[{"label": "Giá mô phỏng (VND)", "amount": amount}], total=amount
        )
    return reply(
        status="awaiting_resident_approval",
        intent_id=str(row["id"]),
        quote=row["quote"],
        approval_request={
            "quote_ref": str(row["id"]),
            "arguments_hash": row["arguments_hash"],
            "expires_at": row["expires_at"].isoformat(),
            "summary": summary,
        },
    )


async def commit(
    db, ticket_id, intent_id, approval_id, client_reference, expected_ticket_version
):
    ticket = await scope(db, ticket_id, True)
    try:
        key = UUID(intent_id)
    except ValueError:
        raise work.Refused(
            "Mã phương án không hợp lệ.", "TRAVEL_INTENT_NOT_FOUND"
        ) from None
    row = (
        (
            await db.execute(
                text(f"""select * from travel_mock_intents
        where tenant_id={TENANT} and ticket_id=:ticket and id=:id for update"""),
                {"ticket": ticket["id"], "id": key},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise work.Refused(
            "Không có phương án này trong ticket.", "TRAVEL_INTENT_NOT_FOUND"
        )
    if row["result"] is not None:
        if (
            row["approval_id"] != approval_id
            or row["commit_reference"] != client_reference
        ):
            raise work.Refused(
                "Phương án đã thực hiện với reference khác.", "REFERENCE_CONFLICT"
            )
        return row["result"]
    version(ticket, expected_ticket_version)
    if row["expires_at"] <= datetime.now(timezone.utc):
        raise work.Refused(
            "Giá/đề nghị đã hết hiệu lực; cần xác nhận lại.", "TRAVEL_QUOTE_EXPIRED"
        )
    approved = (
        await db.execute(
            text(f"""select 1 from platform_approvals a
        where a.tenant_id={TENANT} and a.ticket_id=:ticket and a.approval_id=:approval and a.status='approved'
          and a.quote_ref=:intent and a.arguments_hash=:hash and (a.expires_at is null or a.expires_at>now())
          and exists(select 1 from platform_commands c where c.tenant_id=a.tenant_id and c.ticket_id=a.ticket_id
            and c.kind='approval_decision' and c.body->>'approval_id'=a.approval_id
            and c.body->>'decision'='approve' and c.body->>'arguments_hash'=a.arguments_hash
            and c.body->>'quote_ref'=a.quote_ref)"""),
            {
                "ticket": ticket["id"],
                "approval": approval_id,
                "intent": str(key),
                "hash": row["arguments_hash"],
            },
        )
    ).first()
    if approved is None:
        raise work.Refused(
            "Cần cư dân tự đồng ý đúng phương án Platform đã gửi.",
            "TRAVEL_RESIDENT_APPROVAL_REQUIRED",
        )
    await hydrate(db)
    kind, selection = row["kind"], row["selection"]
    if row["operation"] == "book":
        available = availability_result(kind, selection)
        if not available["is_available"]:
            raise work.Refused("Không còn đủ chỗ; chưa tạo booking.", "TRAVEL_SOLD_OUT")
        if (
            available.get("total_price", available.get("estimated_total"))
            != row["quote"]["amount"]
        ):
            raise work.Refused(
                "Giá đã đổi; cần phương án và sự đồng ý mới.", "TRAVEL_QUOTE_CHANGED"
            )
        if terms(kind, selection) != row["quote"]["terms"]:
            raise work.Refused(
                "Điều kiện dịch vụ đã đổi; cần phương án mới.", "TRAVEL_QUOTE_CHANGED"
            )
        person = (
            (
                await db.execute(
                    text("""select t.contact_name as name,t.contact_phone as phone,u.email
            from tickets t join users u on u.id=t.requester_user_id where t.id=:id"""),
                    {"id": ticket["id"]},
                )
            )
            .mappings()
            .one()
        )
        if not person["name"] or not person["phone"]:
            raise work.Refused(
                "Ticket thiếu thông tin liên hệ được cư dân cung cấp.",
                "TRAVEL_CONTACT_REQUIRED",
            )
        args = {
            **selection,
            "customer_name": person["name"],
            "customer_phone": person["phone"],
            "client_reference": str(key),
        }
        if kind == "hotel":
            args["customer_email"] = person["email"] or ""
        booking = checked(BOOK[kind](**args))["booking"]
        identifier = uuid4()
        await db.execute(
            text(f"""insert into travel_mock_bookings(id,tenant_id,ticket_id,intent_id,kind,provider_booking_id,status,data)
            values(:id,{TENANT},:ticket,:intent,:kind,:provider,'confirmed',cast(:data as jsonb))"""),
            {
                "id": identifier,
                "ticket": ticket["id"],
                "intent": key,
                "kind": kind,
                "provider": booking["booking_id"],
                "data": json.dumps(booking, ensure_ascii=False),
            },
        )
    else:
        stored = await booking_row(db, ticket["id"], selection["booking_ref"])
        booking = checked(
            CANCEL[kind](stored["provider_booking_id"], selection["reason"])
        )["booking"]
        identifier = stored["id"]
        await db.execute(
            text(f"""update travel_mock_bookings set status='cancelled',data=cast(:data as jsonb),updated_at=now()
            where tenant_id={TENANT} and id=:id"""),
            {"id": identifier, "data": json.dumps(booking, ensure_ascii=False)},
        )
    result = reply(
        status="mock_" + booking["status"],
        ticket_id=str(ticket["id"]),
        booking_ref=str(identifier),
        booking=booking,
    )
    await db.execute(
        text(f"""update travel_mock_intents set commit_reference=:ref,approval_id=:approval,result=cast(:result as jsonb)
        where tenant_id={TENANT} and id=:id"""),
        {
            "ref": client_reference,
            "approval": approval_id,
            "result": json.dumps(result, ensure_ascii=False),
            "id": key,
        },
    )
    await command(
        db,
        ticket["id"],
        "workflow_reply",
        {
            "own": True,
            "domain_notice_key": "travel-mock:" + str(key),
            "text": "Kết quả MÔ PHỎNG từ Domain; Platform tổng hợp và phản hồi cư dân. "
            + json.dumps(result, ensure_ascii=False),
        },
    )
    return result


async def bookings(db, ticket_id):
    ticket = await scope(db, ticket_id)
    rows = (
        (
            await db.execute(
                text(f"""select id,kind,status,data from travel_mock_bookings
        where tenant_id={TENANT} and ticket_id=:ticket order by created_at desc limit 50"""),
                {"ticket": ticket["id"]},
            )
        )
        .mappings()
        .all()
    )
    return reply(
        status="mock_bookings",
        bookings=[
            {
                "booking_ref": str(row["id"]),
                "kind": row["kind"],
                "status": row["status"],
                "booking": row["data"],
            }
            for row in rows
        ],
    )
