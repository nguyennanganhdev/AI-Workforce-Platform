"""D3 browser evidence against the owned test-only Builder demo."""

from tests.workforce.builder.async_capabilities import test_ui as phase_b_ui


def expect(locator):
    # Preserve the existing optional browser dependency boundary.
    from playwright.sync_api import expect as browser_expect

    return browser_expect(locator)


class BuilderD3UiTests(phase_b_ui.BuilderUiTests):
    def test_catalog_refresh_requires_another_confirmation(self):
        self.prepare("refresh")
        self.page.get_by_role("button", name="Xác nhận lựa chọn").click()
        expect(
            self.page.get_by_text("TEST catalog changed.", exact=False)
        ).to_be_visible()
        expect(self.page.get_by_role("status")).to_contain_text("Sẵn sàng xác nhận")
        expect(
            self.page.get_by_role("button", name="Xác nhận lựa chọn")
        ).to_be_enabled()
        self.page.get_by_role("button", name="Xác nhận lựa chọn").click()
        expect(self.page.get_by_role("status")).to_contain_text("Đã xác nhận đề xuất")

    def test_permission_failure_does_not_report_confirmation_success(self):
        self.prepare("permission")
        self.page.get_by_role("button", name="Xác nhận lựa chọn").click()
        expect(self.page.get_by_role("alert")).to_contain_text(
            "Chưa xử lý được yêu cầu"
        )
        expect(self.page.get_by_role("status")).to_contain_text("Sẵn sàng xác nhận")
        self.page.get_by_role("button", name="Xác nhận lựa chọn").click()
        expect(self.page.get_by_role("alert")).to_be_visible()
        expect(self.page.get_by_role("status")).not_to_contain_text("Đã xác nhận")

    def test_optional_missing_keeps_confirmation_available(self):
        self.prepare("optional_missing")
        expect(
            self.page.get_by_text("optional · Tùy chọn · Còn thiếu", exact=False)
        ).to_be_visible()
        expect(
            self.page.get_by_role("button", name="Xác nhận lựa chọn")
        ).to_be_enabled()

    def test_cancel_ignores_late_confirm_response_after_new_prepare(self):
        self.prepare("late_confirm")
        self.page.get_by_role("button", name="Xác nhận lựa chọn").click()
        expect(
            self.page.get_by_role("button", name="Xác nhận lựa chọn")
        ).to_be_disabled()
        self.page.get_by_role("button", name="Hủy / bắt đầu lại").click()
        self.page.get_by_label("Bạn muốn tạo agent hỗ trợ việc gì?").fill("New build")
        self.page.get_by_role("button", name="Xem đề xuất").click()
        expect(self.page.get_by_role("status")).to_contain_text("Sẵn sàng xác nhận")
        # Wait for the demo promise and React's following render turn, without sleep.
        self.page.evaluate("""async () => {
            window.dispatchEvent(new Event('builder-demo-release'));
            await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        }""")
        expect(self.page.get_by_role("status")).to_contain_text("Sẵn sàng xác nhận")
        expect(
            self.page.get_by_role("button", name="Xác nhận lựa chọn")
        ).to_be_enabled()

    def test_tracking_policy_revise_and_mobile_layout(self):
        # Keep the inherited behavioral checks, without overwriting the Phase-B screenshot.
        self.page.set_viewport_size({"width": 390, "height": 844})
        self.prepare("tracking")
        expect(
            self.page.get_by_text("Theo dõi đến hoàn tất", exact=True)
        ).to_be_visible()
        expect(
            self.page.get_by_text("Nâng cấp agent hiện có:", exact=False)
        ).to_be_visible()
        expect(
            self.page.get_by_role("button", name="Xác nhận lựa chọn")
        ).to_be_enabled()
        self.assertFalse(
            self.page.evaluate("document.documentElement.scrollWidth > innerWidth")
        )
