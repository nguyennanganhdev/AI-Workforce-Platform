"""Optional live demo UI tests. Start the owned Vite demo server first.

Requires Playwright in the test environment and installed Microsoft Edge.
No provider/model calls; the page uses generated fake proposal fixtures only.
"""

import os
from pathlib import Path
import unittest


@unittest.skipUnless(
    os.environ.get("BUILDER_UI_TEST_URL"), "Optional UI test needs running demo URL"
)
class BuilderUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright

        cls.runtime = sync_playwright().start()
        cls.browser = cls.runtime.chromium.launch(channel="msedge", headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.runtime.stop()

    def setUp(self):
        self.page = self.browser.new_page(viewport={"width": 1100, "height": 900})
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.goto(os.environ["BUILDER_UI_TEST_URL"])
        self.page.get_by_label("Kịch bản kiểm tra").wait_for()

    def tearDown(self):
        self.assertFalse(self.errors, self.errors)
        self.page.close()

    def prepare(self, scenario):
        self.page.get_by_label("Kịch bản kiểm tra").select_option(scenario)
        self.page.get_by_label("Bạn muốn tạo agent hỗ trợ việc gì?").fill(
            "Tạo agent hỗ trợ nghiệp vụ"
        )
        self.page.get_by_role("button", name="Xem đề xuất").click()
        self.page.get_by_role("status").wait_for()

    def test_confirm_reuse_and_cancel(self):
        self.prepare("reused")
        self.assertTrue(
            self.page.get_by_role("button", name="Xác nhận lựa chọn").is_enabled()
        )
        self.page.get_by_role("button", name="Xác nhận lựa chọn").click()
        self.page.get_by_text(
            "Đã có agent phù hợp trong thư viện", exact=False
        ).wait_for()
        self.assertTrue(
            self.page.get_by_role("button", name="Xác nhận lựa chọn").is_disabled()
        )
        self.page.get_by_role("button", name="Hủy / bắt đầu lại").click()
        self.page.get_by_label("Bạn muốn tạo agent hỗ trợ việc gì?").wait_for()

    def test_missing_capability_and_query_only_block_confirmation(self):
        for scenario in ("missing", "query_only"):
            with self.subTest(scenario=scenario):
                self.prepare(scenario)
                self.assertTrue(
                    self.page.get_by_role(
                        "button", name="Xác nhận lựa chọn"
                    ).is_disabled()
                )
                self.page.get_by_text("Chưa thể xác nhận").wait_for()

    def test_tracking_policy_revise_and_mobile_layout(self):
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.prepare("tracking")
        self.page.get_by_text("Theo dõi đến hoàn tất", exact=True).wait_for()
        self.page.get_by_text("Hoàn tất khi:", exact=False).wait_for()
        self.page.get_by_text("Nâng cấp agent hiện có:", exact=False).wait_for()
        self.assertTrue(
            self.page.get_by_role("button", name="Xác nhận lựa chọn").is_enabled()
        )
        self.assertFalse(
            self.page.evaluate("document.documentElement.scrollWidth > innerWidth")
        )
        output = (
            Path(__file__).resolve().parents[4]
            / "docs/workforce/handoffs/bui-huu-nghia/phase-b-ui.png"
        )
        self.page.screenshot(path=str(output), full_page=True)

    def test_edit_and_create_confirmation(self):
        self.prepare("ready")
        self.page.get_by_label("Bổ sung hoặc sửa toàn bộ yêu cầu tạo agent").fill(
            "Thêm phạm vi dữ liệu"
        )
        self.page.get_by_role("button", name="Xem đề xuất").click()
        self.page.get_by_role("button", name="Xác nhận lựa chọn").click()
        self.page.get_by_text("Đã xác nhận đề xuất", exact=False).wait_for()


if __name__ == "__main__":
    unittest.main()
