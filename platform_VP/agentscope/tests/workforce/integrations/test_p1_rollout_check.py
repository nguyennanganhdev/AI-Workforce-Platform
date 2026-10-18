"""Upgrading must expose incompatible legacy data without rewriting it."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from scripts.workforce.p1_rollout_check import inventory


@pytest.mark.asyncio
async def test_old_schema_reports_unpinned_workflow_and_unreplayable_receipt(tmp_path):
    url = f"sqlite+aiosqlite:///{(tmp_path / 'legacy.sqlite').as_posix()}"
    engine = create_async_engine(url)
    async with engine.begin() as db:
        for statement in (
            "create table wf_workflows(id text, state text, payload JSON)",
            "create table wf_unified_routes(route_id text)",
            "create table wf_unified_receipts(receipt_id text, ingestion_status text)",
            "create table wf_unified_operations(terminal boolean)",
            "create table wf_unified_approvals(status text)",
            "insert into wf_unified_routes values('route')",
            "insert into wf_unified_receipts values('old-event','quarantined')",
        ):
            await db.execute(text(statement))
        await db.execute(text("insert into wf_workflows values('wf','awaiting_user',:payload)"),
                         {"payload": json.dumps({"workflow": {"route_id": "route"}})})
    result = await inventory(url)
    assert not result["data_preflight_pass"]
    assert {b["code"] for b in result["blockers"]} == {"WORKFLOW_CONTRACT_NOT_PINNED", "QUARANTINE_ENVELOPE_MISSING"}
    assert result["production_acceptance"] == "not_assessed"
    async with engine.connect() as db:
        assert "contract_snapshot" not in await db.scalar(text("select payload from wf_workflows"))
    await engine.dispose()


@pytest.mark.asyncio
async def test_empty_valid_inventory_does_not_certify_production(tmp_path):
    url = f"sqlite+aiosqlite:///{(tmp_path / 'empty.sqlite').as_posix()}"
    engine = create_async_engine(url)
    async with engine.begin() as db:
        for statement in (
            "create table wf_workflows(id text, state text, payload JSON)",
            "create table wf_unified_routes(route_id text)",
            "create table wf_unified_receipts(receipt_id text, ingestion_status text)",
            "create table wf_unified_operations(terminal boolean)",
            "create table wf_unified_approvals(status text)",
        ):
            await db.execute(text(statement))
    result = await inventory(url, SimpleNamespace(get_agent=AsyncMock()))
    assert result["data_preflight_pass"]
    assert result["still_required"]
    assert result["production_acceptance"] == "not_assessed"
    await engine.dispose()


@pytest.mark.asyncio
async def test_empty_incomplete_schema_cannot_pass(tmp_path):
    url = f"sqlite+aiosqlite:///{(tmp_path / 'incomplete.sqlite').as_posix()}"
    engine = create_async_engine(url)
    async with engine.begin() as db:
        await db.execute(text("create table wf_workflows(unused text)"))
    result = await inventory(url)
    assert not result["data_preflight_pass"]
    assert {b["code"] for b in result["blockers"]} == {"SCHEMA_INVENTORY_INCOMPLETE"}
    await engine.dispose()
