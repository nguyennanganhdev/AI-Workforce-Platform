"""Real React app with labelled HTTP fixtures; no model or Domain connection."""

import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest


URL = os.getenv("VIN_UI_TEST_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="VIN_UI_TEST_URL requires the local Vin-enabled frontend")


@pytest.fixture
def browser_app():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        contexts = []
        asset_errors = []

        def open_app(*, role="VIN_USER", capabilities=None, width=1280, capability_error=False, anonymous=False):
            context = browser.new_context(viewport={"width": width, "height": 900}, reduced_motion="reduce")
            contexts.append(context)
            context.on("response", lambda response: asset_errors.append(response.url)
                if response.status >= 400 and urlsplit(response.url).path.endswith((".woff", ".woff2", ".css", ".js")) else None)
            calls, external = [], []
            user = dict(id="resident-a", tenant_id="tenant-a", username="cu-dan-a",
                email="resident-a@example.test", status="active", role=role, domain_id=None, area_id=None)
            view = dict(contract_version="vin-platform-1", tenant_id=user["tenant_id"],
                initiator_user_id=user["id"], billing_subject_id=user["id"], workspace_id="personal:resident-a",
                authorization_revision=1, role=role, purpose="chat", environment="production", eligible=True,
                capabilities={"personal.read": True, "personal.create": True,
                    "knowledge.private.manage": True, **(capabilities or {})})
            state = {"links": [], "view": view, "anonymous": anonymous}

            def respond(route):
                parsed, base = urlsplit(route.request.url), urlsplit(URL)
                if (parsed.scheme, parsed.netloc) != (base.scheme, base.netloc):
                    external.append(route.request.url)
                    route.abort()
                    return
                if not parsed.path.startswith("/api/"):
                    route.continue_()
                    return
                path = parsed.path.removeprefix("/api")
                body = route.request.post_data_json if route.request.post_data else None
                calls.append((route.request.method, path, body))
                status, result = 200, {}
                if path == "/auth/refresh":
                    status, result = (401, {"detail": "fixture-anonymous"}) if state["anonymous"] else (200, {"access_token": "offline-browser-fixture"})
                elif path == "/auth/me":
                    result = user
                elif path == "/me/capabilities":
                    status, result = (503, {"detail": "fixture-unavailable"}) if capability_error else (200, state["view"])
                elif path == "/me/usage":
                    result = {"timezone": "Asia/Ho_Chi_Minh", "pending_reconciliation": 1,
                        "buckets": [{"window": "day:2026-10-18", "used": 1200, "reserved": 300}]}
                elif path == "/me/domain-links":
                    result = {"items": state["links"]}
                elif path == "/me/domain-links/vinhomes/complete":
                    state["links"] = [dict(id="link-a", provider_id="vinhomes", status="active", scopes=["self", "requests"], revision=1)]
                    result = {"id": "link-a", "provider_id": "vinhomes", "status": "active"}
                elif path == "/me/domain-links/link-a" and route.request.method == "DELETE":
                    state["links"][0]["status"] = "revoked"
                    status, result = 204, None
                elif path == "/auth/register-personal":
                    status, result = 201, {**user, "status": "pending"}
                elif path == "/workforce/console/leader/bootstrap":
                    status, result = 503, {"detail": "offline fixture: no model configured"}
                else:
                    status, result = 501, {"detail": "offline fixture: endpoint unavailable"}
                route.fulfill(status=status, content_type="application/json",
                    body=json.dumps(result) if result is not None else "")

            context.route("**/*", respond)
            page = context.new_page()
            return page, calls, external, state

        yield open_app
        for context in contexts:
            context.close()
        browser.close()
        assert not asset_errors, "Frontend font/code assets failed to load"


@pytest.mark.parametrize("width", [375, 1280])
def test_account_real_app_responsive_keyboard_and_usage(browser_app, width):
    from playwright.sync_api import expect

    page, calls, external, _ = browser_app(width=width)
    page.goto(URL + "/account")
    expect(page.get_by_role("heading", name="Tài khoản và hạn mức", exact=True)).to_be_visible()
    if width >= 768:
        expect(page.get_by_role("button", name="Chat riêng và nhóm", exact=True)).to_be_visible()
        expect(page.get_by_role("button", name="Agent của tôi", exact=True)).to_be_visible()
    expect(page.get_by_text("1 lượt đang chờ đối soát.", exact=False)).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    update = page.get_by_role("button", name="Cập nhật", exact=True)
    update.focus()
    page.keyboard.press("Enter")
    expect(update).to_be_enabled()
    assert len([call for call in calls if call[1] == "/me/usage"]) >= 2
    folder = Path(".artifacts/vin-shell-browser")
    folder.mkdir(parents=True, exist_ok=True)
    page.evaluate("document.fonts.ready.then(() => true)")
    page.screenshot(path=str(folder / f"account-{width}.png"), full_page=True)
    assert not external


@pytest.mark.parametrize("role", ["VIN_USER", "AREA_MANAGER", "DOMAIN_ADMIN", "PLATFORM_ADMIN"])
def test_direct_privileged_url_cannot_be_granted_by_role(browser_app, role):
    from playwright.sync_api import expect

    page, calls, external, _ = browser_app(role=role)
    page.goto(URL + "/mcp/guessed-hub")
    expect(page.get_by_role("heading", name="Bạn chưa được cấp quyền cho trang này")).to_be_visible()
    assert not [call for call in calls if call[1].startswith(("/mcp", "/credential", "/admin"))]
    assert not external


def test_unavailable_authority_mounts_no_private_page(browser_app):
    from playwright.sync_api import expect

    page, calls, external, _ = browser_app(capability_error=True)
    page.goto(URL + "/account")
    expect(page.get_by_role("heading", name="Chưa xác minh được quyền truy cập")).to_be_visible()
    assert not [call for call in calls if call[1] == "/me/usage"]
    assert not external


def test_switch_rechecks_capability_then_displays_correct_space(browser_app):
    from playwright.sync_api import expect

    page, calls, external, _ = browser_app(capabilities={"management.read": True})
    page.goto(URL + "/account")
    account = page.get_by_role("button", name="Tài khoản cu-dan-a", exact=True)
    expect(account).to_be_visible()
    account.click()
    page.get_by_role("menuitem", name="Vận hành", exact=True).click()
    expect(page.get_by_role("button", name="Về trang bắt đầu · Vận hành", exact=True)).to_be_visible()
    expect(page).to_have_url(URL + "/workforce/leader")
    assert len([call for call in calls if call[1] == "/me/capabilities"]) >= 2
    page.get_by_role("button", name="Tài khoản cu-dan-a", exact=True).click()
    page.get_by_role("menuitem", name="Cá nhân", exact=True).click()
    expect(page.get_by_role("button", name="Về trang bắt đầu · Cá nhân", exact=True)).to_be_visible()
    assert page.get_by_role("combobox").count() == 0
    assert not external


def test_customer_enters_the_shared_leader_shell_as_default(browser_app):
    from playwright.sync_api import expect

    page, calls, external, _ = browser_app()
    page.goto(URL + "/")
    expect(page).to_have_url(URL + "/workforce/leader")
    expect(page.get_by_role("button", name="Chat riêng và nhóm", exact=True)).to_be_visible()
    expect(page.get_by_role("button", name="Agent của tôi", exact=True)).to_be_visible()
    assert page.get_by_role("combobox").count() == 0
    assert not [call for call in calls if call[1] == "/me/usage"]
    assert not external


def test_link_callback_consumed_once_and_revoke_refetches_canonical_state(browser_app):
    from playwright.sync_api import expect

    page, calls, external, _ = browser_app()
    state, code = "s" * 43, "c" * 43
    page.goto(URL + "/account")
    expect(page.get_by_role("heading", name="Tài khoản và hạn mức", exact=True)).to_be_visible()
    page.evaluate("([key, value]) => sessionStorage.setItem(key, value)",
        [f"vin-link:tenant-a:resident-a:vinhomes:{state}", "transaction-a"])
    page.goto(URL + f"/connections/callback/vinhomes?state={state}&code={code}")
    complete = page.get_by_role("button", name="Hoàn tất liên kết", exact=True)
    expect(complete).to_be_visible()
    assert "code=" not in page.url
    complete.click()
    expect(page.get_by_text("Đã liên kết", exact=True)).to_be_visible()
    completions = [call for call in calls if call[1].endswith("/complete")]
    assert len(completions) == 1
    assert completions[0][2] == {"transaction_id": "transaction-a", "state": state, "code": code}
    page.get_by_role("button", name="Thu hồi liên kết", exact=True).click()
    page.get_by_role("button", name="Xác nhận thu hồi", exact=True).click()
    expect(page.get_by_text("Đã thu hồi", exact=True)).to_be_visible()
    assert not external


def test_registration_never_submits_a_role_or_management_scope(browser_app):
    from playwright.sync_api import expect

    page, calls, external, _ = browser_app(anonymous=True)
    page.goto(URL + "/register")
    page.get_by_label("Email", exact=True).fill("resident-new@example.test")
    page.locator("#username").fill("resident-new")
    page.locator("#password").fill("offline-fixture-password")
    page.get_by_role("button", name="Tạo tài khoản", exact=True).click()
    expect(page.get_by_text("Đã gửi đăng ký. Tài khoản đang chờ xác minh.", exact=True)).to_be_visible()
    registrations = [call for call in calls if call[1] == "/auth/register-personal"]
    assert len(registrations) == 1
    assert set(registrations[0][2]) == {"email", "username", "password"}
    assert not [call for call in calls if call[1].startswith("/directory/") or call[1] == "/auth/register"]
    assert not external
