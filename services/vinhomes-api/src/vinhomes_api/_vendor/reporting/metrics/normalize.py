"""Deterministic bill, incident-count and customer-star validation."""

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext

from ..tools.contracts import ReportToolError, uuid_string


def invalid():
    raise ReportToolError("BACKEND_CONTRACT_INVALID")


def count(value):
    if type(value) is not int or not 0 <= value <= 2**63 - 1:
        invalid()
    return value


def identity(value):
    if type(value) is not str:
        invalid()
    try:
        return uuid_string(value)
    except (ValueError, AttributeError):
        invalid()


def text(value):
    if type(value) is not str or not value.strip() or len(value) > 200:
        invalid()
    return value


def money(value):
    if type(value) not in (int, str) or len(str(value)) > 128:
        invalid()
    if not re.fullmatch(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?", str(value)):
        invalid()
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        invalid()
    if (
        not result.is_finite()
        or result < 0
        or result.adjusted() > 38
        or result.as_tuple().exponent < -38
    ):
        invalid()
    return format(result, "f")


def rows(value):
    if (
        type(value) is not list
        or len(value) > 10000
        or any(type(row) is not dict for row in value)
    ):
        invalid()
    return value


def keys(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        invalid()


def bill_data(data):
    keys(data, ("basis", "items"))
    if data["basis"] != "issued_repair_invoice_grand_total":
        invalid()
    items, seen = [], set()
    for row in rows(data["items"]):
        keys(row, ("currency", "invoice_count", "billed_amount"))
        currency = row["currency"]
        if (
            type(currency) is not str
            or not re.fullmatch(r"[A-Z]{3}", currency)
            or currency in seen
        ):
            invalid()
        seen.add(currency)
        if not count(row["invoice_count"]):
            invalid()
        items.append({**row, "billed_amount": money(row["billed_amount"])})
    return {"basis": data["basis"], "items": items}, not items


def ticket_data(data):
    keys(
        data,
        (
            "total_ticket_count",
            "incident_ticket_count",
            "non_incident_ticket_count",
            "items",
        ),
    )
    total, incident, other = [
        count(data[key])
        for key in (
            "total_ticket_count",
            "incident_ticket_count",
            "non_incident_ticket_count",
        )
    ]
    if total != incident + other:
        invalid()
    items, seen = [], set()
    for row in rows(data["items"]):
        keys(row, ("incident_type_id", "incident_type_name", "ticket_count"))
        kind = (
            identity(row["incident_type_id"])
            if row["incident_type_id"] is not None
            else None
        )
        amount = count(row["ticket_count"])
        if kind in seen or not amount:
            invalid()
        seen.add(kind)
        items.append(
            {
                "incident_type_id": kind,
                "incident_type_name": text(row["incident_type_name"]),
                "ticket_count": amount,
                "share": amount / incident if incident else 0.0,
            }
        )
    if sum(row["ticket_count"] for row in items) != incident:
        invalid()
    return {
        "total_ticket_count": total,
        "incident_ticket_count": incident,
        "non_incident_ticket_count": other,
        "share_basis": "incident_ticket_count",
        "items": items,
    }, total == 0


def mean_stars(weighted, amount):
    if not amount:
        return None
    with localcontext() as context:
        context.prec = 40
        return format(
            (Decimal(weighted) / Decimal(amount)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            ),
            "f",
        )


def rating_data(data):
    keys(data, ("basis", "items"))
    if data["basis"] != "customer_review_submission":
        invalid()
    items, seen, total, weighted = [], set(), 0, 0
    for row in rows(data["items"]):
        keys(row, ("staff_id", "staff_name", "rating_count", "star_counts"))
        identifier = identity(row["staff_id"])
        if identifier in seen:
            invalid()
        seen.add(identifier)
        keys(row["star_counts"], ("1", "2", "3", "4", "5"))
        histogram = {star: count(amount) for star, amount in row["star_counts"].items()}
        amount = count(row["rating_count"])
        if sum(histogram.values()) != amount:
            invalid()
        score = sum(int(star) * n for star, n in histogram.items())
        total += amount
        weighted += score
        name = text(row["staff_name"]) if row["staff_name"] is not None else None
        items.append(
            {
                "staff_id": identifier,
                "staff_name": name,
                "rating_count": amount,
                "star_counts": histogram,
                "average_stars": mean_stars(score, amount),
            }
        )
    count(total)
    return {
        "basis": data["basis"],
        "total_rating_count": total,
        "average_stars": mean_stars(weighted, total),
        "items": items,
    }, total == 0
