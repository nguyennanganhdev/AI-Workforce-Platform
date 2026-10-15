"""Offline handoff validation. Synthetic rows stay inside pytest's temporary folder."""

import csv
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

DEPLOY = Path(__file__).resolve().parents[3] / "deploy"


def script(name):
    spec = importlib.util.spec_from_file_location(name, DEPLOY / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def bundle(tmp_path):
    validator = script("validate-owner-data")
    common = {
        "document_reference": "fixture-only",
        "approved_by": "fixture-reviewer",
        "approved_at": "2026-01-01T00:00:00Z",
        "effective_from": "2026-01-01T00:00:00Z",
        "effective_until": "",
    }
    rows = {table: [] for table in validator.FIELDS}
    for site in sorted(validator.SITES):
        # Identical local codes across three sites must not collide.
        base = {
            "site_code": site,
            "zone_code": "same-zone",
            "building_code": "same-building",
            "operator_code": "same-operator",
        }
        values = {
            "operators": {
                "legal_name": "Fixture only",
                "contact_reference": "fixture-contact",
            },
            "zones": {"name": "Fixture only", "current_address": "Fixture address"},
            "buildings": {"name": "Fixture only", "current_address": "Fixture address"},
            "units": {"unit_code": "same-unit", "asset_type": "apartment"},
            "coverage": {
                "category_code": "technical",
                "platform_route_id": "fixture-route",
                "route_revision": "1",
            },
            "residents": {
                "unit_code": "same-unit",
                "account_code": "same-account",
                "name": "Fixture resident",
                "email": "fixture@example.test",
                "relation": "tenant",
                "valid_from": "2026-01-01T00:00:00Z",
                "valid_until": "",
                "verification_reference": "fixture-proof",
            },
            "services": {
                "service_code": "same-service",
                "title": "Fixture service",
                "category_code": "technical",
                "eligibility": "fixture-only",
                "fee_policy": "quote",
                "fee_amount": "",
                "currency": "VND",
                "fee_unit": "job",
                "vat_policy": "quote",
                "operating_hours": "fixture-only",
                "warranty_policy": "fixture-only",
                "booking_policy": "fixture-only",
                "cancellation_policy": "fixture-only",
                "contact_reference": "fixture-contact",
            },
        }
        for table, extra in values.items():
            rows[table].append(
                {
                    field: {**base, **common, **extra}[field]
                    for field in validator.FIELDS[table].split() + validator.REVIEW
                }
            )
        for index in (1, 2):
            employee = site + "-employee-" + str(index)
            extra = {
                "employee_code": employee,
                "name": "Fixture staff",
                "email": employee + "@example.test",
                "category_code": "technical",
                "max_concurrent_jobs": "1",
                "backup_employee_code": site + "-employee-" + str(3 - index),
            }
            rows["staff"].append(
                {
                    field: {**base, **common, **extra}[field]
                    for field in validator.FIELDS["staff"].split() + validator.REVIEW
                }
            )
            extra = {
                "employee_code": employee,
                "starts_at": "2026-10-14T08:00:00+07:00",
                "ends_at": "2026-10-14T16:00:00+07:00",
            }
            rows["shifts"].append(
                {
                    field: {**base, **common, **extra}[field]
                    for field in validator.FIELDS["shifts"].split() + validator.REVIEW
                }
            )
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "site_codes": sorted(validator.SITES),
                "data_owner": "fixture-only",
                "exported_at": "2026-10-13T00:00:00Z",
                "version": "fixture",
                "document_reference": "fixture-only",
            }
        )
    )
    return validator, rows


def check(tmp_path, validator, rows):
    for table, records in rows.items():
        with (tmp_path / (table + ".csv")).open(
            "w", newline="", encoding="utf-8"
        ) as out:
            writer = csv.DictWriter(
                out, fieldnames=validator.FIELDS[table].split() + validator.REVIEW
            )
            writer.writeheader()
            writer.writerows(records)
    return validator.validate(tmp_path, datetime(2026, 10, 14, tzinfo=timezone.utc))


def test_site_local_codes_are_valid_in_three_distinct_sites(tmp_path):
    validator, rows = bundle(tmp_path)
    report = check(tmp_path, validator, rows)
    assert report["valid"], report["errors"]
    assert report["counts"]["staff"] == 6 and report["database_written"] is False


@pytest.mark.parametrize(
    ("table", "field", "value", "error"),
    [
        ("units", "site_code", "outside-project", "site outside manifest"),
        ("units", "building_code", "missing-building", "building outside site/zone"),
        ("coverage", "operator_code", "unknown-operator", "operator not in this site"),
        ("residents", "relation", "admin", "unit/relation invalid"),
        (
            "residents",
            "valid_until",
            "2020-01-01T00:00:00Z",
            "residency not currently effective",
        ),
        (
            "staff",
            "backup_employee_code",
            "missing-backup",
            "backup must be another employee",
        ),
        (
            "staff",
            "approved_at",
            "2099-01-01T00:00:00Z",
            "approval/effective dates invalid",
        ),
        ("staff", "category_code", "management", "unsupported dispatch category"),
        ("services", "fee_policy", "unknown", "fee policy/currency invalid"),
        ("services", "fee_amount", "100000", "fee amount inconsistent"),
        ("shifts", "starts_at", "2026-10-14T08:00:00", "invalid shift timestamps"),
    ],
)
def test_incomplete_or_cross_scoped_operational_data_is_refused(
    tmp_path, table, field, value, error
):
    validator, rows = bundle(tmp_path)
    rows[table][0][field] = value
    report = check(tmp_path, validator, rows)
    assert not report["valid"] and any(error in message for message in report["errors"])


def test_overlapping_shifts_are_refused_without_exposing_personal_data(tmp_path):
    validator, rows = bundle(tmp_path)
    rows["shifts"].append(
        {**rows["shifts"][0], "starts_at": "2026-10-14T09:00:00+07:00"}
    )
    report = check(tmp_path, validator, rows)
    assert any("overlapping" in error for error in report["errors"])
    assert "example.test" not in json.dumps(report)


def test_an_external_resident_id_cannot_identify_different_people_across_sites(
    tmp_path,
):
    validator, rows = bundle(tmp_path)
    rows["residents"][1]["email"] = "another-person@example.test"
    report = check(tmp_path, validator, rows)
    assert not report["valid"] and any(
        "inconsistent identity" in error for error in report["errors"]
    )


def test_public_catalog_cannot_turn_into_approved_owner_data():
    compiler = script("prepare-reference-pack")
    rows = [
        {
            "site_code": "ocean-park-1",
            "record_code": "geography/test",
            "title": "Reference",
            "body": "Reference only",
            "authority": "reference",
            "sources": ["https://vinhomes.vn/"],
            "source_published_at": None,
            "retrieved_at": "2026-10-14",
        }
    ]
    doc = compiler.compile_records(rows)[0]
    assert (
        doc["unverified"] is True
        and doc["metadata"]["operational_approval"] == "pending"
    )
    assert doc["metadata"]["fee_policy"] is None
    with pytest.raises(ValueError, match="Duplicate"):
        compiler.compile_records(rows + rows)
    rows[0]["authority"] = "approved"
    with pytest.raises(SystemExit):
        compiler.compile_records(rows)


def test_shipped_reference_catalog_is_scoped_sourced_and_does_not_include_private_data():
    compiler = script("prepare-reference-pack")
    records = json.loads(
        (DEPLOY / "reference-data/owner-public-catalog-20261014.json").read_text(
            encoding="utf-8"
        )
    )
    documents = compiler.compile_records(records)
    assert len(documents) == 80 and len({doc["id"] for doc in documents}) == 80
    assert {doc["site"] for doc in documents} == {
        "ocean-park-1",
        "ocean-park-2",
        "ocean-park-3",
    }
    assert all(
        doc["zone"] is None and doc["buildings"] == [] and doc["unverified"]
        for doc in documents
    )
    assert all(
        record["kind"] in {"subdivision", "building", "amenity"} for record in records
    )
    assert all(
        record["official_code"] is None
        for record in records
        if record["kind"] != "building"
    )
    assert all(
        "?" not in record["title"] and "?" not in record["body"] for record in records
    )
    assert all(
        doc["metadata"]["operator"] is None
        and doc["metadata"]["operating_hours"] is None
        for doc in documents
    )
