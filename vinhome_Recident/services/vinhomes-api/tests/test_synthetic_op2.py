"""Simulation expansion must stay bounded, private and scoped to OP2."""
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path

import pytest

from vinhomes_api.synthetic_op2 import TABLES, apply, build

TEMPLATE = Path(__file__).resolve().parents[3] / "deploy/owner-data-pilot/op2-simulation/template.json"
NOW = datetime(2026, 10, 15, 14, tzinfo=UTC)


@pytest.fixture(scope="module")
def generated():
    return build(json.loads(TEMPLATE.read_text(encoding="utf-8")), "existing-admin", NOW)


def test_template_has_no_credentials_and_expansion_has_no_elevated_roles(generated):
    template = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    assert all(not set(row) & {"password", "access_token", "refresh_token", "id_token"} for row in template["tables"]["accounts"])
    bundle, credentials = generated
    assert set(bundle["tables"]) == set(TABLES)
    assert len(credentials) == 30 and len({c["password"] for c in credentials}) == 30
    assert all(c["email"].endswith("@op2-sandbox.test") for c in credentials)
    assert {row["role_code"] for row in bundle["tables"]["scoped_user_roles"]} == {"staff", "customer"}
    assert not set(TABLES) & {"platform_admins", "platform_connection_settings", "sessions", "tickets", "platform_commands", "platform_mcp_grants"}


def test_scope_roster_and_business_relations_are_complete(generated):
    tables = generated[0]["tables"]
    assert len(tables["buildings"]) == 3 and len(tables["units"]) == 6
    assert len(tables["unit_residents"]) == 6 and len(tables["staff_profiles"]) == 24
    assert len(tables["domain_service_catalog"]) == 10 and len(tables["vh_knowledge_documents"]) == 20
    assert all(row["unverified"] for row in tables["vh_knowledge_documents"])
    assert all(row["policy"]["data_mode"] == "synthetic_test" for row in tables["domain_service_catalog"])
    users = {row["id"] for row in tables["users"]}
    units = {row["id"] for row in tables["units"]}
    assert all(row["user_id"] in users and row["unit_id"] in units for row in tables["unit_residents"])
    for hour in range(14 * 24):
        instant = NOW.replace(hour=0) + timedelta(hours=hour, minutes=1)
        active = {r["staff_id"] for r in tables["staff_shifts"] if datetime.fromisoformat(r["starts_at"]) <= instant < datetime.fromisoformat(r["ends_at"])}
        assert len(active) == 8
    for staff in tables["staff_profiles"]:
        shifts = sorted((r for r in tables["staff_shifts"] if r["staff_id"] == staff["id"]), key=lambda r: r["starts_at"])
        assert len(shifts) == 14
        assert all(a["ends_at"] <= b["starts_at"] for a, b in zip(shifts, shifts[1:]))


def test_import_rejects_unrelated_database_before_connecting(generated):
    import asyncio
    with pytest.raises(ValueError, match="unrelated database"):
        asyncio.run(apply("postgresql://irrelevant@invalid/real_production", generated[0]))


def test_builder_rejects_unlabelled_input():
    with pytest.raises(ValueError, match="sanitized OP2"):
        build({"data_mode": "real", "tables": {}}, "existing-admin", NOW)
