"""Dong Builder review/confirmation/publication in the real React application."""
import json
from urllib.parse import urlsplit

import pytest

from test_vin_shell_browser import URL, browser_app as browser_app  # noqa: F401

pytestmark = pytest.mark.skipif(not URL, reason="VIN_UI_TEST_URL requires the local frontend")


def test_dong_plan_requires_explicit_confirmation_and_publication(browser_app):
    from playwright.sync_api import expect

    page, _, external, _ = browser_app()
    config = {"type": "openai_credential", "credential_id": "offline", "model": "offline-fixture", "parameters": {}}
    plan = {"name": "Fixture Planner", "objective": "Summarize supplied facts", "suggested_tools": [],
            "suggested_knowledge_bases": [], "missing_resources": [], "peer_dependencies": [], "reuse_agent_id": None}
    proposal = {"conversation_id": "builder", "proposal_id": None, "revision": 1, "status": "needs_input",
                "assistant_message": "Review fixture plan", "clarification_question": None,
                "planned_agents": [plan], "agents": [], "chat_model_config": config,
                "fixed_config": {"runtime_note": "Offline fixture"}, "resources_locked": True, "resource_selection": "jev"}
    calls = []

    def respond(route):
        path = urlsplit(route.request.url).path.removeprefix("/api")
        body = route.request.post_data_json if route.request.post_data else None
        if path == "/workforce/console/builder/conversations":
            result = [{"conversation_id": "builder", "title": "Fixture", "updated_at": "2026-10-19T00:00:00Z"}]
        elif path == "/workforce/console/builder/conversations/builder":
            result = {"conversation_id": "builder", "title": "Fixture", "messages": [], "proposal": proposal}
        elif path == "/workforce/console/builder/prepare":
            calls.append((path, body))
            assert body["confirm_outline"] is True
            assert body["expected_revision"] == 1
            proposal.update(status="ready", revision=2, proposal_id="proposal", agents=[{
                "name": plan["name"], "objective": plan["objective"], "execution_mode": "context_only",
                "system_prompt": "Use only supplied facts.", "skill_name": "planner", "skill_markdown": "# Supplied facts",
                "selected_tools": [], "selected_knowledge_bases": [], "reuse_agent_id": None, "reuse_agent_name": None,
                "evaluation": {"passed": True, "score": 1, "checks": {"skill": True}},
            }])
            result = proposal
        elif path == "/workforce/console/builder/publish":
            calls.append((path, body))
            assert body == {"conversation_id": "builder", "proposal_id": "proposal", "expected_revision": 2,
                            "knowledge_base_selections": [[]]}
            proposal["status"] = "published"
            result = {"agents": [{"agent_id": "new", "session_id": "s", "name": plan["name"], "reused": False}]}
        elif path == "/workforce/console/agents":
            result = []
        elif path == "/knowledge/":
            result = {"knowledge_bases": []}
        else:
            route.fallback()
            return
        route.fulfill(status=200, content_type="application/json", body=json.dumps(result))

    page.route("**/api/**", respond)
    page.goto(URL + "/workforce/builder?conversation_id=builder")
    confirm = page.get_by_role("button", name="Chốt định hướng và sinh cấu hình", exact=True)
    expect(confirm).to_be_visible()
    assert calls == []
    confirm.click()
    publish = page.get_by_role("button", name="Phát hành", exact=True)
    expect(publish).to_be_visible()
    expect(page.get_by_text("Cấu hình đạt", exact=True)).to_be_visible()
    assert len(calls) == 1
    publish.click()
    expect(page.get_by_text("Đã phát hành", exact=True)).to_be_visible()
    assert len(calls) == 2
    assert not external
