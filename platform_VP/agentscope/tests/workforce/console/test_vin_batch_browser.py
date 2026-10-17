"""Builder keeps queued/failed publication visible across page reload."""

import copy
import json
from urllib.parse import urlsplit

import pytest

from test_vin_shell_browser import URL, browser_app as browser_app  # noqa: F401

pytestmark = pytest.mark.skipif(not URL, reason="VIN_UI_TEST_URL requires the local Vin-enabled frontend")


def test_builder_publication_reloads_checkpoint_and_repairs_without_prepare_or_eval(browser_app):
    from playwright.sync_api import expect
    page, _, external, _ = browser_app()
    calls = []
    proposal = {"conversation_id": "conversation-a", "proposal_id": "proposal-a", "revision": 1, "status": "ready",
        "assistant_message": "Đề xuất fixture", "clarification_question": None, "planned_agents": [],
        "chat_model_config": {"type": "openai_credential", "credential_id": "fixture", "model": "fixture", "parameters": {}},
        "fixed_config": {"ownership": "private", "context_config": {}, "react_config": {}, "runtime_note": "fixture"},
        "agents": [{"name": "Fixture agent", "objective": "Trả lời từ fixture", "system_prompt": "Only fixture facts.",
            "selected_tools": [], "skill_name": "", "skill_markdown": "", "knowledge": [], "library_skills": [], "tests": [],
            "evaluation": {"passed": True, "checks": {}}, "reuse_agent_id": None, "reuse_agent_name": None}]}
    state = {"publication": None}
    def respond(route):
        path = urlsplit(route.request.url).path.removeprefix("/api")
        calls.append((route.request.method, path))
        if path == "/workforce/console/agents":
            result = []
        elif path == "/workforce/console/builder/conversations":
            result = [{"conversation_id": "conversation-a", "title": "Fixture build", "updated_at": "2026-10-18T10:00:00Z"}]
        elif path == "/workforce/console/builder/conversations/conversation-a":
            result = {"conversation_id": "conversation-a", "title": "Fixture build", "messages": [], "proposal": proposal}
        elif path == "/workforce/console/builder/conversations/conversation-a/publication":
            assert route.request.url.endswith("proposal_id=proposal-a")
            result = {"publication": state["publication"]}
        elif path == "/workforce/console/builder/conversations/conversation-a/progress":
            result = None
        elif path == "/workforce/console/builder/publish":
            state["publication"] = {"job_id": "job-a", "status": "queued", "phase": "staging", "cursor": 1, "total": 2,
                "agents": [], "error": None, "can_repair": False}
            result = copy.deepcopy(state["publication"])
        elif path == "/workforce/console/builder/publications/job-a/repair":
            state["publication"] = {"job_id": "repair-a", "status": "published", "phase": "published", "cursor": 2, "total": 2,
                "agents": [], "error": None, "can_repair": False}
            proposal["status"] = "published"
            result = state["publication"]
        else:
            route.fallback()
            return
        route.fulfill(status=200, content_type="application/json", body=json.dumps(result))
    page.route("**/api/**", respond)
    page.goto(URL + "/workforce/builder?conversation_id=conversation-a")
    page.get_by_role("button", name="Phát hành toàn bộ agent", exact=True).click()
    expect(page.get_by_text("Đang chuẩn bị tài nguyên riêng · 1/2", exact=True)).to_be_visible()
    assert proposal["status"] == "ready"
    state["publication"].update(status="failed", error="OUTCOME_UNKNOWN", can_repair=True)
    page.reload()
    page.get_by_role("button", name="Khôi phục phát hành", exact=True).click()
    expect(page.get_by_text("Cấu hình chờ duyệt", exact=False)).to_be_visible()
    expect(page.get_by_role("button", name="Khôi phục phát hành", exact=True)).to_have_count(0)
    assert not any("/prepare" in path or "/evaluate" in path for _, path in calls)
    assert sum(method == "POST" and path.endswith("/publish") for method, path in calls) == 1
    assert external == []
