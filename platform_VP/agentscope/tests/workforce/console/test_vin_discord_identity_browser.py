"""The channel page consumes a bound OAuth callback once, using HTTP fixtures."""

import json
from urllib.parse import urlencode, urlsplit

import pytest

from test_vin_shell_browser import URL, browser_app as browser_app  # noqa: F401

pytestmark = pytest.mark.skipif(not URL, reason="VIN_UI_TEST_URL requires the local Vin-enabled frontend")


@pytest.mark.parametrize("valid", [True, False])
def test_discord_callback_is_bound_to_current_account_and_consumed_once(browser_app, valid):
    from playwright.sync_api import expect
    page, _, external, _ = browser_app()
    completed = []
    nonce = "fixture-bound-state-for-resident-a"
    page.add_init_script("sessionStorage.setItem('discord-oauth:tenant-a:resident-a', " + json.dumps(nonce) + ")")
    def respond(route):
        path = urlsplit(route.request.url).path.removeprefix("/api")
        if path == "/channels/discord/identity/complete":
            completed.append(route.request.post_data_json)
            result = {"verified": True, "discord_user_id": "100", "verified_at": 1, "revision": 1}
        elif path == "/channels/discord/identity":
            result = {"verified": bool(completed), "discord_user_id": "100", "verified_at": 1, "revision": 1}
        else:
            route.fallback()
            return
        route.fulfill(status=200, content_type="application/json", body=json.dumps(result))
    page.route("**/api/**", respond)
    page.goto(URL + "/channel?" + urlencode({"state": nonce if valid else "foreign-state", "code": "fixture-code", "iss": "https://discord.com"}))
    if valid:
        expect(page.get_by_text("Đã xác minh tài khoản Discord.", exact=True)).to_be_visible()
        assert completed == [{"state": nonce, "code": "fixture-code", "issuer": "https://discord.com"}]
    else:
        expect(page.get_by_text("Không xác minh được phiên Discord. Hãy bắt đầu liên kết lại.", exact=True)).to_be_visible()
        assert completed == []
    assert page.evaluate("location.search") == ""
    assert page.evaluate("sessionStorage.getItem('discord-oauth:tenant-a:resident-a')") is None
    assert external == []
