"""Real customer request cards: view/preview cannot send a signed decision."""

import json
from urllib.parse import urlsplit

import pytest

from test_vin_shell_browser import URL, browser_app as browser_app  # noqa: F401

pytestmark = pytest.mark.skipif(not URL, reason="VIN_UI_TEST_URL requires the local Vin-enabled frontend")


@pytest.mark.parametrize("width", [375, 1280])
def test_customer_confirmation_requires_final_click_and_keeps_platform_chat(browser_app, width):
    from playwright.sync_api import expect
    page, _, external, _ = browser_app(width=width)
    calls = []
    case = {"id": "case-a", "code": "FIXTURE-01", "description": "Vòi nước rò rỉ", "service_status": "waiting_for_customer",
        "sync_status": "applied", "as_of": "2026-10-18T10:00:00Z", "next_action": "review_current_decision",
        "resolution": {"summary": "Đã thay vòi nước ở bếp", "photos": []},
        "events": [{"id": "event-a", "sequence": 1, "at": "2026-10-18T10:00:00Z", "label": "Nhân viên đã hoàn tất"}],
        "actions": [{"action": "confirm", "label": "Xác nhận hoàn tất", "expected_version": 7, "payload": {"resolutionRevision": "resolution-a"}}]}

    def respond(route):
        path = urlsplit(route.request.url).path.removeprefix("/api")
        if path == "/workforce/console/leader/bootstrap":
            result = {"agent_id": "leader-a", "session_id": "session-a", "name": "Leader"}
        elif path.endswith("/service-cases"):
            result = {"items": [case]}
        elif path == "/service-cases/case-a/decisions":
            calls.append(route.request.post_data_json)
            case["actions"] = []
            case["service_status"] = "closed"
            result = {"status": "closed"}
        elif path == "/sessions/":
            result = {"sessions": []}
        elif path.startswith("/sessions/") and path.endswith("/messages"):
            result = {"messages": [], "is_running": False, "has_more": False}
        else:
            route.fallback()
            return
        route.fulfill(status=200, content_type="application/json", body=json.dumps(result))

    page.route("**/api/**", respond)
    page.goto(URL + "/workforce/leader")
    page.get_by_text("Yêu cầu dịch vụ của bạn (1)", exact=True).click()
    expect(page.get_by_text("Đã thay vòi nước ở bếp", exact=True)).to_be_visible()
    expect(page.get_by_text("Đã đồng bộ", exact=False)).to_be_visible()
    assert calls == []
    page.get_by_role("button", name="Xác nhận hoàn tất", exact=True).click()
    expect(page.get_by_role("dialog")).to_be_visible()
    assert calls == []
    page.get_by_role("button", name="Quay lại", exact=True).click()
    assert calls == []
    page.get_by_role("button", name="Xác nhận hoàn tất", exact=True).click()
    page.get_by_role("button", name="Xác nhận gửi quyết định", exact=True).click()
    expect(page.get_by_text("Dịch vụ đã ghi nhận quyết định của bạn.", exact=True)).to_be_visible()
    assert len(calls) == 1 and calls[0]["expected_version"] == 7
    assert calls[0]["payload"] == {"resolutionRevision": "resolution-a"}
    assert set(calls[0]) == {"case_id", "action", "expected_version", "payload", "idempotency_key"}
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert external == []


def test_customer_sync_pending_offers_no_decision(browser_app):
    from playwright.sync_api import expect
    page, _, external, _ = browser_app()
    def respond(route):
        path = urlsplit(route.request.url).path.removeprefix("/api")
        if path == "/workforce/console/leader/bootstrap":
            result = {"agent_id": "leader-a", "session_id": "session-a", "name": "Leader"}
        elif path.endswith("/service-cases"):
            result = {"items": [{"id": "case-a", "sync_status": "sync_pending", "as_of": None,
                "next_action": "retry_sync", "events": [], "actions": []}]}
        elif path == "/sessions/":
            result = {"sessions": []}
        else:
            route.fallback()
            return
        route.fulfill(status=200, content_type="application/json", body=json.dumps(result))
    page.route("**/api/**", respond)
    page.goto(URL + "/workforce/leader")
    page.get_by_text("Yêu cầu dịch vụ của bạn (1)", exact=True).click()
    expect(page.get_by_text("Chưa đồng bộ đầy đủ", exact=True)).to_be_visible()
    assert page.get_by_role("button", name="Xác nhận hoàn tất", exact=True).count() == 0
    assert external == []
