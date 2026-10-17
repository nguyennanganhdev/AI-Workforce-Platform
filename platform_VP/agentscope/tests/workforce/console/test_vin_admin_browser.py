"""Admin forms use the C02/C03 contract, existing pages and capability gates."""

import json
from urllib.parse import unquote, urlsplit

import pytest

from test_vin_shell_browser import URL, browser_app as browser_app  # noqa: F401

pytestmark = pytest.mark.skipif(not URL, reason="VIN_UI_TEST_URL requires the local Vin-enabled frontend")


def admin_app(browser_app, *, privileged=True):
    page, _, external, _ = browser_app(role="PLATFORM_ADMIN", capabilities={"accounts.manage": True,
        **({"quota.manage": True, "catalog.manage": True} if privileged else {})})
    writes = []
    def respond(route):
        path = unquote(urlsplit(route.request.url).path.removeprefix("/api"))
        method = route.request.method
        if method in {"POST", "PUT", "DELETE"} and path.startswith("/admin/vin/"):
            writes.append((method, path, route.request.post_data_json if route.request.post_data else None))
            result = {"id": "fixture-grant" if path.endswith("grants") else "fixture-entry", "updated": True}
        elif path == "/admin/accounts":
            result = [{"id": "resident-b", "email": "fixture@invalid.test", "username": "Cư dân fixture", "status": "active", "role": "VIN_USER",
                "domain_id": None, "area_id": None, "created_at": "2026-10-18T10:00:00Z", "last_login_at": None}]
        elif path == "/admin/directory":
            result = []
        elif path.startswith("/catalog/"):
            result = {"items": []}
        elif path == "/knowledge_bases/":
            result = {"total": 1, "knowledge_bases": [{"id": "fixture-kb", "name": "KB Vin fixture", "description": "Approved KB fixture", "editable": True,
                "document_count": 2, "chunk_count": 8, "status_counts": {"ready": 2, "error": 0, "pending": 0, "parsing": 0, "chunking": 0, "indexing": 0}}]}
        else:
            route.fallback()
            return
        route.fulfill(status=200, content_type="application/json", body=json.dumps(result))
    page.route("**/api/**", respond)
    page.goto(URL + "/admin")
    return page, writes, external


def test_admin_quota_requires_full_values_and_posts_exact_policy(browser_app):
    from playwright.sync_api import expect
    page, writes, external = admin_app(browser_app)
    page.get_by_role("button", name="Quota & thư viện Vin", exact=True).click()
    page.get_by_role("button", name="Áp dụng chính sách thay thế", exact=True).click()
    assert writes == []  # Native required constraints must not send zero defaults.
    values = {"Token mỗi ngày": "10000", "Token mỗi tháng": "100000", "Token đầu ra tối đa mỗi lượt": "1024",
        "Số lượt đồng thời tối đa": "2", "Token embedding mỗi ngày": "2000", "Dung lượng lưu trữ (byte)": "1000000", "Kích thước tối đa mỗi file (byte)": "100000"}
    for label, value in values.items():
        page.get_by_label(label, exact=True).fill(value)
    page.get_by_label("Model được phép (cách nhau bằng dấu phẩy)", exact=True).fill("fixture-a, fixture-b")
    page.get_by_label("Cho phép dùng chính sách này", exact=True).check()
    page.get_by_role("button", name="Áp dụng chính sách thay thế", exact=True).click()
    expect(page.get_by_text("Đã lưu chính sách quota.", exact=True)).to_be_visible()
    assert writes == [("PUT", "/admin/vin/quota-policies/role:VIN_USER", {"daily_tokens": 10000, "monthly_tokens": 100000,
        "max_output_tokens": 1024, "max_concurrency": 2, "embedding_daily_tokens": 2000, "storage_bytes": 1000000,
        "max_file_bytes": 100000, "models": ["fixture-a", "fixture-b"], "enabled": True})]
    assert not external


def test_admin_kb_to_catalog_and_grant_uses_safe_ids_and_customer_permissions(browser_app):
    from playwright.sync_api import expect
    page, writes, external = admin_app(browser_app)
    page.get_by_role("button", name="Quota & thư viện Vin", exact=True).click()
    page.get_by_role("tab", name="Thư viện KB Vin", exact=True).click()
    expect(page.get_by_role("link", name="Mở Knowledge", exact=True)).to_have_attribute("href", "/knowledge")
    page.get_by_role("button", name="Chuẩn bị KB vào catalog", exact=True).click()
    expect(page.get_by_label("ID tài nguyên", exact=True)).to_have_value("fixture-kb")
    page.get_by_label("ID chủ tài nguyên", exact=True).fill("resident-a")
    page.get_by_role("button", name="Ghi phiên bản catalog", exact=True).click()
    expect(page.get_by_text("Đã ghi phiên bản catalog. Chỉ đối tượng được cấp quyền mới được dùng.", exact=True)).to_be_visible()
    assert writes[0][2]["kind"] == "knowledge_base" and writes[0][2]["resource_id"] == "fixture-kb"
    page.get_by_role("tab", name="Cấp quyền & nhóm", exact=True).click()
    expect(page.get_by_label("Catalog ID", exact=True)).to_have_value("fixture-entry")
    page.get_by_label("ID nhận quyền", exact=True).fill("resident-b")
    page.get_by_label("Chọn/gắn", exact=True).check()
    page.get_by_label("Sử dụng", exact=True).check()
    page.get_by_role("button", name="Cấp quyền", exact=True).click()
    expect(page.get_by_label("Grant ID vừa tạo hoặc cần thu hồi", exact=True)).to_have_value("fixture-grant")
    assert writes[1][2] == {"catalog_id": "fixture-entry", "subject_kind": "user", "subject_id": "resident-b",
        "permissions": ["view", "bind", "execute"], "expires_at": None}
    assert not external


def test_role_without_server_capabilities_gets_no_vin_administration(browser_app):
    from playwright.sync_api import expect
    page, writes, external = admin_app(browser_app, privileged=False)
    expect(page.get_by_role("button", name="Quota & thư viện Vin", exact=True)).to_have_count(0)
    expect(page.get_by_role("button", name="Áp dụng chính sách thay thế", exact=True)).to_have_count(0)
    assert writes == [] and not external


@pytest.mark.parametrize("width", [375, 1280])
def test_account_shows_effective_remaining_and_pending_reconciliation(browser_app, width):
    from playwright.sync_api import expect
    page, _, external, _ = browser_app(width=width)
    def respond(route):
        path = urlsplit(route.request.url).path
        if path != "/api/me/usage":
            route.fallback()
            return
        route.fulfill(status=200, content_type="application/json", body=json.dumps({"timezone": "Asia/Ho_Chi_Minh",
            "pending_reconciliation": 1, "policy_revision": 3, "buckets": [], "effective_limits": [
                {"subject": "user:resident-a", "window": "day:2026-10-18", "limit": 10000, "used": 1200, "reserved": 300, "remaining": 8500}]}))
    page.route("**/api/**", respond)
    page.goto(URL + "/account")
    expect(page.get_by_text("Hạn mức khả dụng · chính sách v3", exact=True)).to_be_visible()
    expect(page.get_by_role("cell", name="8.500", exact=True)).to_be_visible()
    expect(page.get_by_text("1 lượt đang chờ đối soát.", exact=False)).to_be_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert not external
