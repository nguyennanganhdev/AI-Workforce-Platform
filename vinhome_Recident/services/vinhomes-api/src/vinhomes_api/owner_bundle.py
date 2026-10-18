"""Validate an owner-confirmed, site-scoped CSV handoff offline. Never writes to a database."""

import argparse
import csv
import hashlib
import io
import json
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

SITES = {"ocean-park-1", "ocean-park-2", "ocean-park-3"}
REVIEW = [
    "document_reference",
    "approved_by",
    "approved_at",
    "effective_from",
    "effective_until",
]
FIELDS = {
    "operators": "site_code operator_code legal_name contact_reference",
    "zones": "site_code zone_code name operator_code current_address",
    "buildings": "site_code zone_code building_code name operator_code current_address",
    "units": "site_code zone_code building_code unit_code asset_type operator_code",
    "coverage": "site_code zone_code building_code operator_code category_code platform_route_id route_revision",
    "residents": "site_code zone_code building_code unit_code account_code name email relation valid_from valid_until verification_reference",
    "staff": "site_code zone_code building_code employee_code name email operator_code category_code max_concurrent_jobs backup_employee_code",
    "shifts": "site_code zone_code building_code employee_code starts_at ends_at",
    "services": "site_code zone_code building_code service_code title category_code operator_code eligibility fee_policy fee_amount currency fee_unit vat_policy operating_hours warranty_policy booking_policy cancellation_policy contact_reference",
}
OPTIONAL = {"effective_until", "valid_until", "building_code", "fee_amount"}
SOP_FIELDS = "site_code zone_code building_code sop_code service_code title audience request_kind priority response_minutes resolution_minutes clock_policy intake_requirements safety_policy escalation_policy evidence_requirements acceptance_criteria approval_policy steps"


def timestamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("timezone required")
    return result


def inspect_bundle(folder, now=None):
    """Return a redacted report and private parsed records from the same byte snapshot."""
    now = now or datetime.now(UTC)
    errors, rows = [], {}
    manifest_bytes = (folder / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8-sig"))
    hashes = {"manifest.json": hashlib.sha256(manifest_bytes).hexdigest()}
    fields_by_table = dict(FIELDS)
    version = manifest.get("schema_version", 1)
    if version not in (1, 2):
        errors.append("manifest: unsupported schema_version")
    if version == 2:
        fields_by_table["sops"] = SOP_FIELDS
    scope = manifest.get("site_codes", [])
    if not scope or len(set(scope)) != len(scope) or not set(scope) <= SITES:
        errors.append("manifest: invalid site_codes")
    if any(
        not manifest.get(key)
        for key in ("data_owner", "exported_at", "version", "document_reference")
    ):
        errors.append("manifest: owner, export time, version and source required")
    try:
        if timestamp(manifest["exported_at"]) > now:
            raise ValueError()
    except (KeyError, ValueError, TypeError):
        errors.append(
            "manifest: exported_at must be a non-future timestamp with timezone"
        )
    for table, fields in fields_by_table.items():
        rows[table] = []
        path = folder / (table + ".csv")
        if not path.exists():
            errors.append(table + ": file required")
            continue
        raw_bytes = path.read_bytes()
        hashes[path.name] = hashlib.sha256(raw_bytes).hexdigest()
        with io.StringIO(raw_bytes.decode("utf-8-sig"), newline="") as source:
            reader = csv.DictReader(source)
            expected = fields.split() + REVIEW
            if reader.fieldnames != expected:
                errors.append(
                    table
                    + ": headers must match the template exactly; no passwords or extra identity fields"
                )
                continue
            for number, raw in enumerate(reader, 2):
                label = f"{table}:{number}"
                if None in raw or any(value is None for value in raw.values()):
                    errors.append(label + ": invalid CSV column count")
                    continue
                row = {key: value.strip() for key, value in raw.items()}
                if any(not row[key] for key in expected if key not in OPTIONAL):
                    errors.append(label + ": required field missing")
                if row["site_code"] not in scope:
                    errors.append(label + ": site outside manifest")
                try:
                    start = timestamp(row["effective_from"])
                    end = (
                        timestamp(row["effective_until"])
                        if row["effective_until"]
                        else None
                    )
                    if (
                        timestamp(row["approved_at"]) > now
                        or start > now
                        or (end and (end <= start or end <= now))
                    ):
                        raise ValueError()
                except ValueError:
                    errors.append(
                        label
                        + ": approval/effective dates invalid or not currently effective"
                    )
                row["_label"] = label
                rows[table].append(row)
        if not rows[table]:
            errors.append(table + ": no owner-confirmed records")
    indexes = {}
    keys = {
        "operators": ("site_code", "operator_code"),
        "zones": ("site_code", "zone_code"),
        "buildings": ("site_code", "building_code"),
        "units": ("site_code", "zone_code", "building_code", "unit_code"),
        "coverage": ("site_code", "zone_code", "building_code", "category_code"),
        "residents": (
            "site_code",
            "zone_code",
            "building_code",
            "unit_code",
            "account_code",
        ),
        "staff": ("site_code", "employee_code"),
        "shifts": ("site_code", "employee_code", "starts_at"),
        "services": ("site_code", "service_code"),
    }
    if version == 2:
        keys["sops"] = ("site_code", "sop_code")
    for table, fields in keys.items():
        indexes[table] = {}
        for row in rows[table]:
            key = tuple(row[field] for field in fields)
            if key in indexes[table]:
                errors.append(row["_label"] + ": duplicate scoped key")
            indexes[table][key] = row
    for table, records in rows.items():
        for row in records:
            label, site = row["_label"], row["site_code"]
            if (
                "operator_code" in row
                and table != "operators"
                and (site, row["operator_code"]) not in indexes["operators"]
            ):
                errors.append(label + ": operator not in this site")
            if (
                "zone_code" in row
                and table != "zones"
                and (site, row["zone_code"]) not in indexes["zones"]
            ):
                errors.append(label + ": zone not in this site")
            if row.get("building_code") and table != "buildings":
                building = indexes["buildings"].get((site, row["building_code"]))
                if not building or building["zone_code"] != row["zone_code"]:
                    errors.append(label + ": building outside site/zone")
            if table in {"staff", "coverage"} and row["category_code"] not in {
                "technical",
                "security",
                "sanitation",
            }:
                errors.append(label + ": unsupported dispatch category")
            if table in {"residents", "staff"} and (
                row["email"].count("@") != 1
                or "." not in row["email"].split("@")[-1]
                or row["email"].lower().endswith(".invalid")
            ):
                errors.append(label + ": real login email required")
            if table == "residents":
                key = tuple(row[field] for field in keys["units"])
                if key not in indexes["units"] or row["relation"] not in {
                    "owner",
                    "tenant",
                    "household",
                }:
                    errors.append(label + ": unit/relation invalid")
                try:
                    start = timestamp(row["valid_from"])
                    end = timestamp(row["valid_until"]) if row["valid_until"] else None
                    if start > now or (end and (end <= start or end <= now)):
                        raise ValueError()
                except ValueError:
                    errors.append(label + ": residency not currently effective")
            if table == "units" and row["asset_type"] not in {
                "apartment",
                "villa",
                "shophouse",
                "land",
            }:
                errors.append(label + ": invalid asset_type")
            if table == "staff":
                backup = indexes["staff"].get((site, row["backup_employee_code"]))
                if (
                    not row["max_concurrent_jobs"].isdigit()
                    or int(row["max_concurrent_jobs"]) < 1
                ):
                    errors.append(label + ": positive capacity required")
                if (
                    not backup
                    or backup is row
                    or any(
                        backup[field] != row[field]
                        for field in (
                            "zone_code",
                            "building_code",
                            "operator_code",
                            "category_code",
                        )
                    )
                ):
                    errors.append(
                        label
                        + ": backup must be another employee with matching scope and specialty"
                    )
                route = indexes["coverage"].get(
                    tuple(row[field] for field in keys["coverage"])
                )
                if not route or route["operator_code"] != row["operator_code"]:
                    errors.append(label + ": no matching operator/dispatch coverage")
            if table == "shifts":
                staff = indexes["staff"].get((site, row["employee_code"]))
                if not staff or any(
                    staff[field] != row[field]
                    for field in ("zone_code", "building_code")
                ):
                    errors.append(label + ": shift outside employee scope")
            if table == "services":
                if (
                    row["fee_policy"] not in {"free", "fixed", "quote"}
                    or row["currency"] != "VND"
                ):
                    errors.append(label + ": fee policy/currency invalid")
                try:
                    amount = Decimal(row["fee_amount"]) if row["fee_amount"] else None
                    if (
                        (amount is not None and (not amount.is_finite() or amount < 0))
                        or (row["fee_policy"] == "fixed" and amount is None)
                        or (row["fee_policy"] == "free" and amount != 0)
                        or (row["fee_policy"] == "quote" and amount is not None)
                    ):
                        raise ValueError()
                except (InvalidOperation, ValueError):
                    errors.append(label + ": fee amount inconsistent with policy")
                route = indexes["coverage"].get(
                    tuple(row[field] for field in keys["coverage"])
                )
                if version == 2 and (
                    not route or route["operator_code"] != row["operator_code"]
                ):
                    errors.append(
                        label + ": service has no matching operator/dispatch coverage"
                    )
    for table, identifier in (
        ("residents", "account_code"),
        ("staff", "employee_code"),
    ):
        identities, logins = {}, {}
        for row in rows[table]:
            person, login = row[identifier], row["email"].casefold()
            profile = (row["name"], login)
            if person in identities and identities[person] != profile:
                errors.append(row["_label"] + ": inconsistent identity across sites")
            if login in logins and logins[login] != person:
                errors.append(
                    row["_label"] + ": login belongs to another external identity"
                )
            identities[person], logins[login] = profile, person
    shifts = {}
    for row in rows["shifts"]:
        try:
            start, end = timestamp(row["starts_at"]), timestamp(row["ends_at"])
            if end <= start:
                raise ValueError()
            # Employee codes must identify the same person across sites; one person cannot work overlapping shifts.
            for previous_start, previous_end in shifts.setdefault(
                row["employee_code"], []
            ):
                if start < previous_end and previous_start < end:
                    errors.append(row["_label"] + ": overlapping employee shifts")
            shifts[row["employee_code"]].append((start, end))
        except ValueError:
            errors.append(row["_label"] + ": invalid shift timestamps")
    for table in (
        "zones",
        "units",
        "coverage",
        "residents",
        "staff",
        "shifts",
        "services",
    ):
        if set(scope) - {row["site_code"] for row in rows[table]}:
            errors.append(table + ": missing records for one or more manifest sites")
    for row in rows["staff"]:
        if not any(
            s["site_code"] == row["site_code"]
            and s["employee_code"] == row["employee_code"]
            for s in rows["shifts"]
        ):
            errors.append(row["_label"] + ": employee has no shift")
    if version == 2:
        validate_pilot(manifest, rows, indexes, folder, hashes, now, errors)
    report = {
        "valid": not errors,
        "counts": {key: len(value) for key, value in rows.items()},
        "errors": errors,
        "database_written": False,
        "approval_authenticity": "requires owner verification; not proven by CSV values",
        "schema_version": version,
        "snapshot_sha256": hashlib.sha256(
            json.dumps(hashes, sort_keys=True).encode()
        ).hexdigest(),
        "file_hashes": hashes,
        "operational_activation": False,
    }
    return report, rows, manifest


def validate_pilot(manifest, rows, indexes, folder, hashes, now, errors):
    if not isinstance(manifest.get("bundle_code"), str) or not re.fullmatch(
        r"[a-z0-9][a-z0-9_-]{0,79}", manifest["bundle_code"]
    ):
        errors.append("manifest: bundle_code must be a stable safe identifier")
    if manifest.get("data_mode") not in {"owner_candidate", "synthetic_test"}:
        errors.append(
            "manifest: explicit owner_candidate or synthetic_test data_mode required"
        )
    pilot = manifest.get("pilot") or {}
    scope = (pilot.get("site_code"), pilot.get("zone_code"), pilot.get("building_code"))
    if (
        manifest.get("site_codes") != ["ocean-park-1"]
        or scope[0] != "ocean-park-1"
        or not all(isinstance(value, str) and value.strip() for value in scope)
        or pilot.get("category_codes") != ["technical"]
    ):
        errors.append(
            "manifest: pilot requires OP1, one explicit zone/building and technical only"
        )
    for records in rows.values():
        for row in records:
            if any(
                row.get(field) != value
                for field, value in zip(
                    ("site_code", "zone_code", "building_code"), scope
                )
                if field in row
            ):
                errors.append(row["_label"] + ": outside explicit pilot scope")
            if "category_code" in row and row["category_code"] != "technical":
                errors.append(row["_label"] + ": outside pilot category")
    if len(rows["buildings"]) != 1 or len(rows["zones"]) != 1:
        errors.append("pilot: exactly one zone and one building required")
    for row in rows["coverage"]:
        try:
            if int(row["route_revision"]) < 1:
                raise ValueError()
        except ValueError:
            errors.append(row["_label"] + ": positive route revision required")
        matching = [
            staff
            for staff in rows["staff"]
            if all(
                staff[field] == row[field]
                for field in (
                    "site_code",
                    "zone_code",
                    "building_code",
                    "category_code",
                    "operator_code",
                )
            )
        ]
        if len(matching) < 2:
            errors.append(row["_label"] + ": primary and backup staff required")
    for row in rows["sops"]:
        service = indexes["services"].get((row["site_code"], row["service_code"]))
        if not service or any(
            service[field] != row[field] for field in ("zone_code", "building_code")
        ):
            errors.append(row["_label"] + ": SOP service outside scope")
        if (
            row["audience"] not in {"resident", "staff"}
            or row["request_kind"] not in {"incident", "service_request"}
            or row["priority"] not in {"low", "normal", "high", "critical"}
            or row["clock_policy"] != "elapsed"
            or row["approval_policy"] != "resident_quote_and_completion"
        ):
            errors.append(
                row["_label"]
                + ": unsupported SOP policy; resident consent cannot be bypassed"
            )
        try:
            response, resolution = (
                int(row["response_minutes"]),
                int(row["resolution_minutes"]),
            )
            if not 0 < response <= resolution:
                raise ValueError()
        except ValueError:
            errors.append(row["_label"] + ": invalid SLA minutes")
    for service in rows["services"]:
        audiences = {
            sop["audience"]
            for sop in rows["sops"]
            if sop["site_code"] == service["site_code"]
            and sop["service_code"] == service["service_code"]
        }
        if not {"resident", "staff"} <= audiences:
            errors.append(service["_label"] + ": resident and staff SOP required")
    documents = manifest.get("source_documents")
    if not isinstance(documents, list) or not documents:
        errors.append("manifest: source_documents with local evidence hashes required")
        documents = []
    references = set()
    for index, document in enumerate(documents):
        try:
            reference, name = document["document_reference"], document["file"]
            if (
                not reference
                or reference in references
                or not re.fullmatch(r"evidence/[A-Za-z0-9_.-]+", name)
            ):
                raise ValueError()
            path = folder / name
            if path.is_symlink() or not path.resolve().is_relative_to(folder.resolve()):
                raise ValueError()
            content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            if content_hash != document["sha256"]:
                raise ValueError()
            hashes[f"source_document_{index + 1}"] = content_hash
            references.add(reference)
        except (KeyError, TypeError, ValueError, OSError):
            errors.append(
                f"source_documents:{index + 1}: missing, duplicate or invalid evidence/hash"
            )
    for records in rows.values():
        for row in records:
            if row["document_reference"] not in references:
                errors.append(row["_label"] + ": evidence reference missing")
    for row in rows["shifts"]:
        try:
            if timestamp(row["ends_at"]) <= now:
                errors.append(row["_label"] + ": pilot shift already ended")
            staff = indexes["staff"].get((row["site_code"], row["employee_code"]))
            if staff:
                start, end = timestamp(row["starts_at"]), timestamp(row["ends_at"])
                if start < timestamp(staff["effective_from"]) or (
                    staff["effective_until"]
                    and end > timestamp(staff["effective_until"])
                ):
                    errors.append(
                        row["_label"] + ": shift outside staff effective dates"
                    )
                backup_shifts = [
                    shift
                    for shift in rows["shifts"]
                    if shift["site_code"] == row["site_code"]
                    and shift["employee_code"] == staff["backup_employee_code"]
                ]
                if not any(
                    timestamp(shift["starts_at"]) <= start
                    and timestamp(shift["ends_at"]) >= end
                    for shift in backup_shifts
                ):
                    errors.append(
                        row["_label"] + ": backup shift must cover the primary shift"
                    )
        except ValueError:
            pass  # The base validator already reports invalid timestamps.
    resident_logins = {row["email"].casefold() for row in rows["residents"]}
    if any(row["email"].casefold() in resident_logins for row in rows["staff"]):
        errors.append("pilot: resident and staff logins must be distinct")
    if manifest.get("data_mode") == "owner_candidate":
        for row in rows["residents"] + rows["staff"]:
            domain = row["email"].casefold().split("@")[-1]
            if domain.endswith((".test", ".example", ".localhost")) or domain in {
                "example.com",
                "example.org",
                "example.net",
                "localhost",
            }:
                errors.append(
                    row["_label"]
                    + ": synthetic email prohibited in owner_candidate data"
                )


def validate(folder, now=None):
    return inspect_bundle(folder, now)[0]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = validate(args.folder)
    except (OSError, ValueError, TypeError) as exc:
        report = {
            "valid": False,
            "errors": ["Invalid or unreadable bundle: " + type(exc).__name__],
            "database_written": False,
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["valid"] else 1)
