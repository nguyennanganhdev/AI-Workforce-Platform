"""Maintenance must preserve identity/history and never manufacture operator approval."""

import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path

import pytest
from vinhomes_api import synthetic_op2
from vinhomes_api.bootstrap import site_id
from vinhomes_api.operating_data import PROFILE, build, service_text, validate

ROOT = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 10, 15, 16, 30, tzinfo=UTC)


@pytest.fixture(scope="module")
def maintained():
    template = json.loads((ROOT / "deploy/owner-data-pilot/op2-simulation/template.json").read_text(encoding="utf-8"))
    snapshot = deepcopy(template["tables"])
    snapshot["sites"] = [{"id": str(site_id(f"ocean-park-{n}")), "code": f"ocean-park-{n}"} for n in (1, 2, 3)]
    snapshot["users"].extend([{"id": template["source_admin"], "email": "admin@op1-sandbox.test", "name": "Old admin"}, {"id": "existing-admin", "email": "admin@example.invalid", "name": "Existing admin"}])
    snapshot["platform_admins"] = [{"user_id": template["source_admin"]}, {"user_id": "existing-admin"}]
    # Password computation is independently checked by API acceptance; no slow hashing in this structural fixture.
    original = synthetic_op2.password_hash
    synthetic_op2.password_hash = lambda value: "test-hash"
    try:
        for site in ("ocean-park-2", "ocean-park-3"):
            bundle, _ = synthetic_op2.build(template, template["source_admin"], NOW, site_code=site)
            for table, rows in bundle["tables"].items():
                snapshot[table].extend(rows)
    finally:
        synthetic_op2.password_hash = original
    refs = json.loads((ROOT / "deploy/owner-data-pilot/customer-care-reference-20261015.json").read_text(encoding="utf-8"))
    plan, credentials = build(snapshot, now=NOW, hasher=lambda value: "test-hash", reference_documents=refs)
    return snapshot, plan, credentials


def test_identity_rename_keeps_all_ids_and_only_adds_bounded_staff(maintained):
    snapshot, plan, credentials = maintained
    assert len(plan["identities"]) == 88 and len(credentials) == 16
    assert len(plan["patches"]["users"]) == len(snapshot["users"]) == 72
    assert {c["role"] for c in credentials} == {"staff"}
    assert len({i["email"] for i in plan["identities"]}) == 88
    assert all(i["email"].endswith("@accounts.vinhome.test") and not any(s in i["email"] for s in ("demo", "sandbox", "mock")) for i in plan["identities"])
    assert all(set(p["after"]) == {"email", "name"} for p in plan["patches"]["users"])
    assert not {"platform_connection_settings", "tickets", "sessions", "platform_admins", "unit_residents"} & (set(plan["patches"]) | set(plan["inserts"]))


def test_op1_has_coverage_capacity_backup_and_one_explicit_leave(maintained):
    _, plan, _ = maintained
    identities = {i["user_id"]: i for i in plan["identities"]}
    profiles = {p["id"]: p for p in plan["inserts"]["staff_profiles"]}
    for p in maintained[0]["staff_profiles"]:
        profiles[p["id"]] = p
    shifts = plan["inserts"]["staff_shifts"]
    assert len(shifts) == 336 and sum(s["status"] == "leave" for s in shifts) == 1
    anchor = NOW.replace(minute=0)
    for hour in range(14 * 24):
        at = anchor + timedelta(hours=hour)
        active = [s for s in shifts if s["status"] == "available" and datetime.fromisoformat(s["starts_at"]) <= at < datetime.fromisoformat(s["ends_at"])]
        teams = [identities[profiles[s["staff_id"]]["user_id"]]["team"] for s in active]
        assert set(teams) == {"kythuat", "anninh", "vesinh", "dichvu"}
        assert len(teams) in (7, 8)
    assert all(p["max_concurrent_jobs"] == 1 for p in profiles.values())
    for profile in profiles:
        own = sorted((s for s in shifts if s["staff_id"] == profile), key=lambda s: s["starts_at"])
        assert all(a["ends_at"] <= b["starts_at"] for a, b in pairwise(own))


def test_sources_and_false_verification_are_preserved(maintained):
    snapshot, plan, _ = maintained
    assert len(plan["patches"]["vh_knowledge_documents"]) == 60
    assert len(plan["inserts"]["vh_knowledge_documents"]) == 10
    assert len(plan["inserts"]["owner_data_records"]) == 12
    assert all(not r["operational_verified"] for r in plan["inserts"]["owner_data_records"])
    assert all(r["unverified"] and r["metadata"]["sources"] for r in plan["inserts"]["vh_knowledge_documents"])
    originals = {r["id"]: r for r in snapshot["vh_knowledge_documents"]}
    assert all(p["after"]["metadata"].get("manifest") == originals[p["id"]]["metadata"].get("manifest") for p in plan["patches"]["vh_knowledge_documents"])
    old_chunks = {r["id"]: r for r in snapshot["vh_knowledge_chunks"]}
    assert all(r["after"].get("embedding", old_chunks[r["id"]]["embedding"]) is None for r in plan["patches"]["vh_knowledge_chunks"])
    assert all("Platform" in r["after"]["text_content"] for r in plan["patches"]["vh_knowledge_chunks"])
    assert {r["category"] for r in plan["inserts"]["vh_knowledge_documents"]} == {"resident-care-public-reference"}


def test_validate_rejects_privilege_and_out_of_scope_database(maintained):
    plan = maintained[1]
    validate(plan, "postgresql://user@host/clean_data_test_" + "a" * 32)
    with pytest.raises(ValueError, match="unrelated"):
        validate(plan, "postgresql://user@host/production")
    bad = deepcopy(plan)
    bad["inserts"]["scoped_user_roles"][0]["role_code"] = "management"
    with pytest.raises(ValueError, match="privileged"):
        validate(bad, "postgresql://user@host/clean_data_test_" + "a" * 32)
    bad = deepcopy(plan)
    bad["patches"]["users"][0]["after"]["status"] = "active"
    with pytest.raises(ValueError, match="columns"):
        validate(bad, "postgresql://user@host/clean_data_test_" + "a" * 32)


def test_reserved_email_and_plan_profile_are_required(maintained):
    with pytest.raises(ValueError, match="reserved"):
        build(maintained[0], email_domain="vinhomes.vn", now=NOW)
    assert maintained[1]["profile"] == PROFILE


def test_desk_work_does_not_claim_field_execution_or_extra_tool_authority():
    field = service_text("technical", "staff", "OP1")
    assert "ETA" in field and "di chuyển" in field
    desk = service_text("billing", "staff", "OP2")
    assert "di chuyển" not in desk and "ETA" not in desk
    assert "endpoint, quyền và bước duyệt" in desk and "Platform" in desk
