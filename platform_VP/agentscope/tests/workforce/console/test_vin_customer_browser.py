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


@pytest.mark.parametrize('width', [375, 1280])
def test_plan_review_stale_versions_reload_and_explicit_final_click(browser_app, width):
    from pathlib import Path
    from playwright.sync_api import expect
    from agentscope.app._service._customer_cases import decision_actions
    fixture = json.loads((Path(__file__).resolve().parents[5] / 'docs/vin-platform/fixtures/c07-plan-decision-v1.json').read_text(encoding='utf-8'))
    page, _, external, _ = browser_app(width=width)
    calls = []
    def respond(route):
        path = urlsplit(route.request.url).path.removeprefix('/api')
        if path == '/workforce/console/leader/bootstrap':
            result = {'agent_id': 'leader-a', 'session_id': 'session-a', 'name': 'Leader'}
        elif path.endswith('/service-cases'):
            result = {'items': [{**fixture, 'id': 'fixture-platform-case', 'sync_status': 'applied',
                'as_of': '2026-10-18T10:00:00Z', 'next_action': 'review_current_decision', 'events': [], 'actions': decision_actions(fixture)}]}
        elif path.endswith('/decisions'):
            calls.append(route.request.post_data_json)
            if len(calls) == 1:
                fixture['canonical_version'] = 18
                fixture['plans'][0].update(version=4, title='Phương án đã cập nhật')
                route.fulfill(status=409, content_type='application/json', body='{"detail":"STALE_PLAN_VERSION"}')
                return
            fixture['plans'][0].update(status='approved', canDecide=False)
            result = {'status': 'approved'}
        elif path == '/sessions/':
            result = {'sessions': []}
        else:
            route.fallback()
            return
        route.fulfill(status=200, content_type='application/json', body=json.dumps(result))
    page.route('**/api/**', respond)
    page.goto(URL + '/workforce/leader')
    page.get_by_test_id('customer-cases').locator('summary').click()
    name = 'Đồng ý phương án: ' + fixture['plans'][0]['title']
    page.get_by_role('button', name=name, exact=True).click()
    expect(page.get_by_role('dialog')).to_contain_text('Thay gioăng và kiểm tra vòi nước')
    expect(page.get_by_role('dialog')).to_contain_text('120000.00')
    expect(page.get_by_role('button', name='Xác nhận gửi quyết định', exact=True)).to_be_disabled()
    page.get_by_role('button', name='Quay lại', exact=True).click()
    assert calls == []
    page.get_by_role('button', name=name, exact=True).click()
    page.get_by_role('dialog').locator('textarea').fill('Tôi đã xem đầy đủ phương án.')
    page.get_by_role('button', name='Xác nhận gửi quyết định', exact=True).click()
    expect(page.get_by_role('dialog').get_by_role('alert')).to_be_visible()
    assert len(calls) == 1 and calls[0]['expected_version'] == 17 and calls[0]['payload']['expectedVersion'] == 3
    page.get_by_role('button', name='Quay lại', exact=True).click()
    page.get_by_role('button', name='Tải lại tiến độ', exact=True).click()
    page.get_by_role('button', name='Đồng ý phương án: Phương án đã cập nhật', exact=True).click()
    page.get_by_role('dialog').locator('textarea').fill('Tôi đồng ý phương án vừa cập nhật.')
    page.get_by_role('button', name='Xác nhận gửi quyết định', exact=True).click()
    expect(page.get_by_text('Dịch vụ đã ghi nhận quyết định của bạn.', exact=True)).to_be_visible()
    assert len(calls) == 2 and calls[1]['expected_version'] == 18 and calls[1]['payload']['expectedVersion'] == 4
    assert calls[0]['idempotency_key'] != calls[1]['idempotency_key']
    assert calls[1]['payload']['decision'] == 'approve' and calls[1]['payload']['note'] == 'Tôi đồng ý phương án vừa cập nhật.'
    assert not {'intent_proof', 'ticket_grant', 'owner_id'} & calls[1].keys()
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
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
