"""Complete synthetic OP1 technical handoff; private records remain in an isolated test database."""

import asyncio
import csv
import hashlib
import json
import os
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid4

import asyncpg
import pytest
from test_owner_data_handoff import bundle, script
from vinhomes_api import database as tool
from vinhomes_api.bootstrap import bootstrap
from vinhomes_api.owner_bundle import (
    FIELDS,
    REVIEW,
    SOP_FIELDS,
    inspect_bundle,
    validate,
)
from vinhomes_api.owner_operational import stage

NOW = datetime(2026, 10, 15, 7, tzinfo=UTC)


def pilot(tmp_path):
    _, rows = bundle(tmp_path)
    for table, values in rows.items():
        rows[table] = [row for row in values if row["site_code"] == "ocean-park-1"]
    for shift in rows["shifts"]:
        shift.update(starts_at="2026-10-15T08:00:00Z", ends_at="2026-10-15T16:00:00Z")
    service = rows["services"][0]
    common = {
        key: service[key]
        for key in REVIEW + ["site_code", "zone_code", "building_code", "service_code"]
    }
    rows["sops"] = [
        {
            **common,
            "sop_code": "fixture-sop-" + audience,
            "title": "Synthetic technical procedure",
            "audience": audience,
            "request_kind": "service_request",
            "priority": "normal",
            "response_minutes": "30",
            "resolution_minutes": "120",
            "clock_policy": "elapsed",
            "intake_requirements": "Synthetic input only",
            "safety_policy": "Synthetic safety only",
            "escalation_policy": "Synthetic escalation only",
            "evidence_requirements": "Synthetic before/after",
            "acceptance_criteria": "Synthetic acceptance only",
            "approval_policy": "resident_quote_and_completion",
            "steps": "Synthetic receive, dispatch, assess, consent, execute, evidence, completion, rework",
        }
        for audience in ("resident", "staff")
    ]
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    manifest.update(
        schema_version=2,
        bundle_code="op1-technical-test",
        data_mode="synthetic_test",
        site_codes=["ocean-park-1"],
        pilot={
            "site_code": "ocean-park-1",
            "zone_code": "same-zone",
            "building_code": "same-building",
            "category_codes": ["technical"],
        },
    )
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    document = evidence / "fixture.txt"
    document.write_text(
        "Synthetic test evidence, never operator certification", encoding="utf-8"
    )
    manifest["source_documents"] = [
        {
            "document_reference": "fixture-only",
            "file": "evidence/fixture.txt",
            "sha256": hashlib.sha256(document.read_bytes()).hexdigest(),
        }
    ]
    return rows, manifest


def write_bundle(folder, rows, manifest):
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    for table, fields in {**FIELDS, "sops": SOP_FIELDS}.items():
        with (folder / (table + ".csv")).open(
            "w", encoding="utf-8-sig", newline=""
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=fields.split() + REVIEW)
            writer.writeheader()
            writer.writerows(rows[table])


def test_complete_pilot_snapshot_is_scoped_and_report_is_redacted(tmp_path):
    rows, manifest = pilot(tmp_path)
    write_bundle(tmp_path, rows, manifest)
    report, private, _ = inspect_bundle(tmp_path, NOW)
    assert report["valid"], report["errors"]
    assert report["counts"] == {
        "operators": 1,
        "zones": 1,
        "buildings": 1,
        "units": 1,
        "coverage": 1,
        "residents": 1,
        "staff": 2,
        "shifts": 2,
        "services": 1,
        "sops": 2,
    }
    assert "example.test" not in json.dumps(report)
    assert private["residents"][0]["email"] == rows["residents"][0]["email"]
    assert not report["operational_activation"] and not report["database_written"]
    assert len(report["snapshot_sha256"]) == 64


@pytest.mark.parametrize(
    ("table", "field", "value", "error"),
    [
        ("units", "building_code", "other", "outside explicit pilot scope"),
        ("services", "category_code", "sanitation", "outside pilot category"),
        ("services", "operator_code", "unknown", "service has no matching"),
        ("coverage", "route_revision", "0", "positive route revision"),
        ("sops", "service_code", "unknown", "SOP service outside scope"),
        ("sops", "audience", "platform", "unsupported SOP policy"),
        (
            "sops",
            "approval_policy",
            "auto_approve",
            "resident consent cannot be bypassed",
        ),
        ("sops", "clock_policy", "business_hours", "unsupported SOP policy"),
        ("sops", "response_minutes", "0", "invalid SLA minutes"),
        ("sops", "resolution_minutes", "10", "invalid SLA minutes"),
        ("residents", "document_reference", "unbound", "evidence reference missing"),
        (
            "staff",
            "email",
            "fixture@example.test",
            "resident and staff logins must be distinct",
        ),
        ("shifts", "ends_at", "2026-10-15T20:00:00Z", "backup shift must cover"),
        ("shifts", "ends_at", "2026-10-14T20:00:00Z", "pilot shift already ended"),
    ],
)
def test_incomplete_pilot_is_refused(tmp_path, table, field, value, error):
    rows, manifest = pilot(tmp_path)
    rows[table][0][field] = value
    write_bundle(tmp_path, rows, manifest)
    report = validate(tmp_path, NOW)
    assert not report["valid"] and any(error in message for message in report["errors"])
    assert "example.test" not in json.dumps(report)


def test_evidence_tampering_and_path_escape_are_refused(tmp_path):
    rows, manifest = pilot(tmp_path)
    write_bundle(tmp_path, rows, manifest)
    (tmp_path / "evidence/fixture.txt").write_text("changed")
    assert not validate(tmp_path, NOW)["valid"]
    manifest["source_documents"][0]["file"] = "../outside.txt"
    write_bundle(tmp_path, rows, manifest)
    assert any("evidence/hash" in error for error in validate(tmp_path, NOW)["errors"])


def test_owner_candidate_cannot_use_test_logins_or_missing_sops(tmp_path):
    rows, manifest = pilot(tmp_path)
    manifest["data_mode"] = "owner_candidate"
    rows["sops"] = rows["sops"][:1]
    write_bundle(tmp_path, rows, manifest)
    report = validate(tmp_path, NOW)
    assert not report["valid"]
    assert any("synthetic email prohibited" in error for error in report["errors"])
    assert any("resident and staff SOP required" in error for error in report["errors"])


def test_empty_pilot_preparation_never_overwrites_owner_edits(tmp_path):
    prepare = script("prepare-owner-pilot").prepare
    assert prepare(tmp_path)["personal_records"] == 0
    assert not validate(tmp_path, NOW)["valid"]
    (tmp_path / "residents.csv").write_text("owner edits", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        prepare(tmp_path)
    assert (tmp_path / "residents.csv").read_text() == "owner edits"


def test_synthetic_pilot_is_refused_before_connecting_to_a_production_database(
    tmp_path,
):
    rows, manifest = pilot(tmp_path)
    write_bundle(tmp_path, rows, manifest)
    with pytest.raises(ValueError, match="isolated owner_pilot_test"):
        asyncio.run(
            stage("postgresql://nobody@127.0.0.1/production", tmp_path, "admin", NOW)
        )


def test_private_staging_is_atomic_idempotent_and_inaccessible_to_runtime(tmp_path):
    admin_url, runtime_url = (
        os.getenv("RESIDENT_TEST_ADMIN_URL"),
        os.getenv("RESIDENT_TEST_RUNTIME_URL"),
    )
    if not admin_url or not runtime_url:
        pytest.skip("Isolated PostgreSQL configuration required")
    rows, manifest = pilot(tmp_path)
    write_bundle(tmp_path, rows, manifest)
    name = "owner_pilot_test_" + uuid4().hex
    target = urlunsplit(urlsplit(admin_url)._replace(path="/" + name))
    runtime = urlunsplit(urlsplit(runtime_url)._replace(path="/" + name))

    async def check():
        await tool.create(admin_url, name)
        try:
            await tool.migrate(target)
            await bootstrap(target)
            await tool.role(target, urlsplit(runtime_url).username, None)
            conn = await asyncpg.connect(target)
            try:
                await conn.execute(
                    "insert into users(id,email,name,status) values('pilot-test-admin','admin@example.test','Synthetic admin','active')"
                )
                await conn.execute(
                    "insert into platform_admins(user_id) values('pilot-test-admin')"
                )
                await conn.execute(
                    "insert into tenant_memberships(id,tenant_id,user_id,status) values(gen_random_uuid(),$1,'pilot-test-admin','active')",
                    UUID(tool.TENANT),
                )
            finally:
                await conn.close()
            first = await stage(target, tmp_path, "pilot-test-admin", NOW)
            again = await stage(target, tmp_path, "pilot-test-admin", NOW)
            assert first["status"] == "staged" and first["database_written"]
            assert again["idempotent_replay"] and not again["database_written"]
            conn = await asyncpg.connect(target)
            try:
                assert (
                    await conn.fetchval(
                        "select count(*) from owner_operational_batches"
                    )
                    == 1
                )
                assert (
                    await conn.fetchval(
                        "select count(*) from owner_operational_records"
                    )
                    == 13
                )
                for table in (
                    "units",
                    "unit_residents",
                    "staff_profiles",
                    "staff_shifts",
                    "management_coverage",
                    "accounts",
                    "platform_commands",
                ):
                    assert await conn.fetchval("select count(*) from " + table) == 0
                assert await conn.fetchval("select count(*) from users") == 1
            finally:
                await conn.close()
            conn = await asyncpg.connect(runtime)
            try:
                for table in ("owner_operational_batches", "owner_operational_records"):
                    assert not await conn.fetchval(
                        "select has_table_privilege(current_user,$1,'INSERT')", table
                    )
                    with pytest.raises(asyncpg.InsufficientPrivilegeError):
                        await conn.fetch("select * from " + table)
            finally:
                await conn.close()
            rows["services"][0]["title"] = "Changed content under same version"
            write_bundle(tmp_path, rows, manifest)
            with pytest.raises(ValueError, match="different content"):
                await stage(target, tmp_path, "pilot-test-admin", NOW)
            with pytest.raises(ValueError, match="administrator"):
                await stage(target, tmp_path, "not-an-admin", NOW)
            # Fail after the new batch and preceding datasets have been inserted: the entire import must roll back.
            conn = await asyncpg.connect(target)
            try:
                await conn.execute(
                    "ALTER TABLE owner_operational_records ADD CONSTRAINT fixture_reject_new_sops CHECK (dataset <> 'sops' OR batch_id='"
                    + first["batch_id"]
                    + "'::uuid)"
                )
            finally:
                await conn.close()
            manifest["version"] = "fixture-2"
            write_bundle(tmp_path, rows, manifest)
            with pytest.raises(asyncpg.CheckViolationError):
                await stage(target, tmp_path, "pilot-test-admin", NOW)
            conn = await asyncpg.connect(target)
            try:
                assert (
                    await conn.fetchval(
                        "select count(*) from owner_operational_batches"
                    )
                    == 1
                )
                assert (
                    await conn.fetchval(
                        "select count(*) from owner_operational_records"
                    )
                    == 13
                )
            finally:
                await conn.close()
        finally:
            conn = await asyncpg.connect(admin_url)
            try:
                await conn.execute('DROP DATABASE "' + name + '" WITH (FORCE)')
            finally:
                await conn.close()

    asyncio.run(check())
