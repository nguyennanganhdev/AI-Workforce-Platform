"""Review regressions: disabled connectors/skills never reach external IO."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from agentscope.app._router._schema._workspace import AddSkillsFromLibraryRequest
from agentscope.app._router._workspace import add_skills_from_library
from agentscope.app._service._eval_sandbox import eval_sandbox, resolve_eval_mcp
from agentscope.app._service._agent_eval import EvalToolError, run_spec_tests
from agentscope.app.storage import SkillRecord
from test_eval_sandbox import DISCOVERED, spec


@pytest.mark.asyncio
@pytest.mark.parametrize("record,status", [(None, None), (SimpleNamespace(enabled=False), None), (None, 403), (None, 404), (None, 409)])
async def test_disabled_or_revoked_eval_mcp_reports_environment_before_model(monkeypatch, record, status):
    monkeypatch.setenv("WORKFORCE_EVAL_SANDBOXES", '[{"mcp_url":"https://offline.invalid/mcp"}]')
    resolver = AsyncMock(return_value=record)
    if status:
        resolver.side_effect = HTTPException(status, "offline-sentinel-never-expose")
    model = AsyncMock(side_effect=AssertionError("No model IO allowed"))
    with patch("agentscope.app._service._catalog_resources.resolve_catalog_resource", new=resolver):
        with pytest.raises(EvalToolError) as denied:
            await resolve_eval_mcp(SimpleNamespace(), "u", "m")
        assert denied.value.environment and denied.value.code == "TOOL_UNAVAILABLE"
        assert "offline-sentinel" not in denied.value.output
        box = await eval_sandbox(SimpleNamespace(), "u", spec())
        report = await run_spec_tests(spec=spec(), model=model, judge_model=model, discovered=DISCOVERED,
            run_tool=AsyncMock(side_effect=AssertionError("No connector IO allowed")), sandbox=box)
    assert report["publishable"] is False
    assert all(result["error_kind"] == "environment" and not result["passed"] for result in report["results"])
    assert all("TOOL_UNAVAILABLE" in result["error"] for result in report["results"])
    model.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled,review", [(False, "approved"), (True, "candidate"), (True, "revoked")])
async def test_inactive_or_unreviewed_cached_skill_is_rejected_before_archive_decode(enabled, review):
    record = SkillRecord(user_id="admin", name="safe-skill", enabled=enabled, review_status=review,
        archive_base64="invalid-offline-cache-that-must-not-be-decoded", archive_format="tar")
    workspace = object()
    service = SimpleNamespace(resolve=AsyncMock(return_value=workspace), install_skill=AsyncMock())
    with patch("agentscope.app._router._workspace.resolve_catalog_resource", new=AsyncMock(return_value=record)):
        result = await add_skills_from_library(AddSkillsFromLibraryRequest(skill_ids=[record.id]),
            agent_id="a", session_id="s", user_id="u", storage=SimpleNamespace(),
            workspace_service=service, skill_hubs={})
    assert not result.added and record.id in result.failed
    service.install_skill.assert_not_awaited()
