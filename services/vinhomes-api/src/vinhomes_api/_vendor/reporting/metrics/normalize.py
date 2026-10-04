"""Validate backend aggregates without inferring missing values or mixing currencies."""

from __future__ import annotations

import math
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from ..tools.contracts import ReportToolError, uuid_string

INTERPRETATION_VERSION = "v3-report-tools/1.0.1"


def invalid():
    raise ReportToolError("BACKEND_CONTRACT_INVALID")


def count(value):
    if type(value) is not int or not 0 <= value <= 2**63 - 1:
        invalid()
    return value


def money(value):
    if type(value) not in (int, float, str) or len(str(value)) > 128:
        invalid()
    if type(value) is str and not re.fullmatch(
        r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?", value
    ):
        invalid()
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        invalid()
    # Bound expansion before formatting scientific notation into a decimal string.
    # SQL aggregate/proportional amounts remain exact within this supported range.
    if (
        not result.is_finite()
        or result < 0
        or result.adjusted() > 38
        or result.as_tuple().exponent < -38
    ):
        invalid()
    return result


def number(value):
    if type(value) not in (int, float, str):
        invalid()
    value = float(money(value))
    if not math.isfinite(value):
        invalid()
    return value


def identity(value):
    if type(value) is not str:
        invalid()
    try:
        return uuid_string(value)
    except (ValueError, AttributeError):
        invalid()


def items(data):
    rows = data.get("items")
    if (
        type(rows) is not list
        or len(rows) > 10_000
        or any(type(row) is not dict for row in rows)
    ):
        invalid()
    return rows


def normalize(operation, data):
    data = dict(data)
    missing = []
    if operation in (
        "get_report_filter_options",
        "create_report_export",
        "get_report_export_status",
    ):
        return data, missing
    rows = [dict(row) for row in items(data)]
    if operation == "get_employee_performance_summary":
        seen = set()
        for i, row in enumerate(rows):
            staff_id = identity(row.get("staff_id"))
            if staff_id in seen:
                invalid()
            seen.add(staff_id)
            row["staff_id"] = staff_id
            assigned, completed, timed, on_time, redo, ratings = (
                count(row.get(key))
                for key in (
                    "assigned_count",
                    "completed_count",
                    "timed_completion_count",
                    "on_time_count",
                    "redo_count",
                    "rating_count",
                )
            )
            if not on_time <= timed <= completed <= assigned or redo > assigned:
                invalid()
            row["on_time_rate"] = on_time / timed if timed else None
            for key in ("average_processing_seconds", "average_rating"):
                if key not in row:
                    invalid()
                if row[key] is not None:
                    row[key] = number(row[key])
            if (
                (ratings == 0) != (row["average_rating"] is None)
                or (
                    row["average_rating"] is not None
                    and not 1 <= row["average_rating"] <= 5
                )
                or (completed == 0 and row["average_processing_seconds"] is not None)
            ):
                invalid()
            for key in ("on_time_rate", "average_processing_seconds", "average_rating"):
                if row[key] is None:
                    missing.append(f"items[{i}].{key}")
    elif operation == "get_repair_revenue_summary":
        currencies = set()
        for row in rows:
            currency = row.get("currency")
            if (
                type(currency) is not str
                or not re.fullmatch(r"[A-Z]{3}", currency)
                or currency in currencies
            ):
                invalid()
            currencies.add(currency)
            amounts = {
                key: money(row.get(key))
                for key in ("billed_amount", "collected_amount", "outstanding_amount")
            }
            invoices, work = (
                count(row.get("invoice_count")),
                count(row.get("billed_work_count")),
            )
            if (
                invoices == 0
                or work > invoices
                or amounts["outstanding_amount"] > amounts["billed_amount"]
            ):
                invalid()
            # Do not require outstanding == max(sum(billed)-sum(collected), 0).
            # Per-invoice overpayments can coexist with another unpaid invoice.
            for key, amount in amounts.items():
                row[key] = format(amount, "f")
        if data.get("laborMaterialsSplit") is None:
            missing.append("laborMaterialsSplit")
    elif operation == "get_incident_frequency_summary":
        total = count(data.get("totalTickets"))
        if sum(count(row.get("incident_count")) for row in rows) != total:
            invalid()
        seen = set()
        for row in rows:
            try:
                bucket = row["period"]
                if (
                    type(bucket) is not str
                    or date.fromisoformat(bucket).isoformat() != bucket
                ):
                    invalid()
                category = (
                    identity(row["category_id"])
                    if row["category_id"] is not None
                    else None
                )
                incident_type = (
                    identity(row["incident_type_id"])
                    if row["incident_type_id"] is not None
                    else None
                )
            except (KeyError, ValueError, TypeError):
                invalid()
            group = (bucket, category, incident_type)
            if (
                group in seen
                or row["incident_count"] == 0
                or type(row.get("incident_type")) is not str
                or not row["incident_type"].strip()
            ):
                invalid()
            seen.add(group)
            row["share"] = row["incident_count"] / total
    elif operation in (
        "get_employee_feedback_details",
        "get_report_supporting_records",
    ):
        if "nextOffset" not in data or (
            data["nextOffset"] is not None and type(data["nextOffset"]) is not int
        ):
            invalid()
        seen = set()
        for row in rows:
            if (
                type(row.get("id")) is not str
                or not row["id"].strip()
                or row["id"] in seen
            ):
                invalid()
            seen.add(row["id"])
        if operation == "get_employee_feedback_details":
            for row in rows:
                if not 1 <= count(row.get("score")) <= 5:
                    invalid()
    data["items"] = rows
    return data, missing
