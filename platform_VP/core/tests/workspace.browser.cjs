// Real HTTP + AgentScope acceptance, using the isolated scripted-model server.
const {
  chromium,
} = require("../../apps/platform-web/node_modules/@playwright/test");
const assert = require("node:assert/strict");
const path = require("node:path");
const fs = require("node:fs");

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const artifacts = path.resolve(__dirname, "../.local/workspace-browser");
  fs.mkdirSync(artifacts, { recursive: true });
  try {
    await page.goto("http://127.0.0.1:8098/console");
    await page.getByLabel("Tên đăng nhập").fill("browser-admin");
    await page
      .getByLabel("Mật khẩu", { exact: true })
      .fill("browser-test-only");
    await page.getByRole("button", { name: "Vào workspace" }).click();
    await page.getByRole("heading", { name: "Không gian làm việc" }).waitFor();
    await page.screenshot({
      path: path.join(artifacts, "overview-desktop.png"),
      fullPage: true,
    });

    await page
      .getByRole("link", { name: "Đội ngũ agent", exact: true })
      .click();
    await page.getByRole("button", { name: "Tạo agent", exact: false }).click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Mã định danh").fill("reviewer");
    await dialog
      .getByLabel("Tên agent", { exact: true })
      .fill("Chuyên viên kiểm chứng");
    await dialog
      .getByLabel("Tôi là ai")
      .fill("Kiểm chứng bằng chứng và chỉ ra phần chưa biết.");
    await dialog
      .getByLabel("Phạm vi xử lý")
      .fill("Kiểm tra nguồn\nĐối chiếu báo cáo");
    await dialog
      .getByLabel("Việc không được")
      .fill("Không tự phê duyệt thay người dùng");
    await dialog.getByLabel("Memory riêng").selectOption("true");
    await dialog.getByRole("button", { name: "Tạo bản nháp" }).click();
    await dialog.waitFor({ state: "hidden" });
    const card = page.locator(".agent-card").filter({
      has: page.getByRole("heading", { name: "Chuyên viên kiểm chứng" }),
    });
    await card.getByRole("link", { name: "Mở hồ sơ" }).click();
    await page.getByRole("heading", { name: "Danh tính & phạm vi" }).waitFor();
    assert(
      (await page.locator("#content").innerText()).includes(
        "Không tự phê duyệt thay người dùng",
      ),
    );
    await page.getByRole("button", { name: "Công bố", exact: true }).click();
    await page.waitForFunction(() =>
      document.querySelector("#content").textContent.includes("Đã công bố"),
    );
    await page.screenshot({
      path: path.join(artifacts, "agent-profile.png"),
      fullPage: true,
    });

    await page.getByRole("link", { name: "Thiết lập", exact: true }).click();
    await page.getByLabel("Supervisor mặc định").selectOption("supervisor");
    await page.getByLabel("Ngân sách mỗi công việc").fill("5");
    await page.getByLabel("Trần token mỗi công việc").fill("1000000");
    await page.getByRole("button", { name: "Lưu thiết lập" }).click();
    await page.waitForFunction(() =>
      document.querySelector("#toast").textContent.includes("Đã lưu"),
    );
    await page.getByRole("link", { name: "Công việc", exact: true }).click();
    await page
      .getByRole("button", { name: "Giao việc", exact: false })
      .first()
      .click();
    await dialog.getByLabel("Bạn cần giải quyết").waitFor();
    assert.equal(await dialog.locator("select").count(), 0);
    assert.equal(await dialog.locator("textarea").count(), 1);
    await dialog
      .getByLabel("Bạn cần giải quyết")
      .fill(
        "Kiểm tra ticket T-1001 và chi phí sửa ống nước; đối chiếu bằng chứng trước khi kết luận.",
      );
    await dialog.getByRole("button", { name: "Bắt đầu xử lý" }).click();
    await page.waitForURL(/#work\//);
    const id = page.url().split("#work/")[1];
    let detail;
    for (let i = 0; i < 90; i++) {
      detail = await page.evaluate(
        async (id) =>
          await (
            await fetch("/workforce/v1/admin/workspace/sessions/" + id)
          ).json(),
        id,
      );
      if (detail.workflow?.state === "closed") break;
      await page.waitForTimeout(1000);
    }
    assert.equal(
      detail.workflow.state,
      "closed",
      JSON.stringify(detail.requests.map((x) => x.error)),
    );
    assert.equal(detail.team.length, 3);
    assert(detail.items.some((x) => x.kind === "question"));
    assert(detail.items.some((x) => x.kind === "answer"));
    assert(
      detail.items.some(
        (x) => x.kind === "note" && JSON.stringify(x.data).includes("2000000"),
      ),
    );
    assert(detail.cost.totals.calls > 0);
    await page.getByRole("button", { name: "Cập nhật", exact: true }).click();
    await page
      .getByRole("button", { name: "Phối hợp agent", exact: true })
      .click();
    await page.getByText("Is the unit occupied?", { exact: true }).waitFor();
    await page.screenshot({
      path: path.join(artifacts, "team-discussion.png"),
      fullPage: true,
    });
    await page.getByRole("button", { name: "Bằng chứng", exact: true }).click();
    await page
      .getByRole("button", { name: "Memory riêng", exact: true })
      .click();
    await page.getByRole("heading", { name: "Chưa có memory" }).waitFor();
    await page.getByRole("button", { name: "Thực thi", exact: true }).click();
    await page.getByRole("heading", { name: "Chi phí theo agent" }).waitFor();
    for (const [name, heading] of [
      ["Kho tri thức", "Kho tri thức"],
      ["Model & provider", "Model & provider"],
      ["Công cụ MCP", "Công cụ MCP"],
      ["Định tuyến", "Định tuyến đối tác"],
      ["Đối tác & khóa", "Đối tác & quyền truy cập"],
      ["Nhật ký", "Nhật ký quản trị"],
    ]) {
      await page.getByRole("link", { name, exact: true }).click();
      await page.getByRole("heading", { name: heading, exact: true }).waitFor();
      assert.equal(
        await page
          .getByRole("heading", { name: "Không tải được dữ liệu" })
          .count(),
        0,
      );
    }
    await page.getByRole("link", { name: "Kho tri thức", exact: true }).click();
    await page
      .getByRole("button", { name: "Công bố tài liệu", exact: false })
      .click();
    await dialog.getByLabel("Mã kho tri thức").fill("workspace_browser");
    await dialog.getByLabel("Mã tài liệu").fill("review_policy");
    await dialog.getByLabel("Tiêu đề").fill("Quy trình kiểm chứng");
    await dialog
      .getByLabel("Nội dung đã được duyệt")
      .fill("Đối chiếu nguồn trước khi kết luận. <img src=x onerror=alert(1)>");
    await dialog.getByRole("button", { name: "Công bố", exact: true }).click();
    await dialog.waitFor({ state: "hidden" });
    const document = page
      .locator("tr")
      .filter({ has: page.getByText("Quy trình kiểm chứng", { exact: true }) })
      .first();
    await document.getByRole("button", { name: "Đọc", exact: true }).click();
    await dialog
      .getByText("Đối chiếu nguồn trước khi kết luận.", { exact: false })
      .waitFor();
    assert.equal(await dialog.locator("img").count(), 0);
    await page.getByRole("button", { name: "Đóng", exact: true }).click();
    await page.getByRole("link", { name: "Công cụ MCP", exact: true }).click();
    await page
      .getByRole("button", { name: "Thêm kết nối", exact: false })
      .click();
    await dialog.getByLabel("Mã kết nối").fill("browser_mcp_" + Date.now());
    await dialog
      .getByLabel("Địa chỉ MCP")
      .fill("https://partner.example.test/mcp");
    await dialog
      .getByLabel("Khóa ký context")
      .fill("test-only-signing-key-with-at-least-32-chars");
    await dialog.getByLabel("Tên header xác thực").fill("Authorization");
    await dialog
      .getByLabel("Giá trị header xác thực")
      .fill("Bearer browser-test-only-secret");
    await dialog.getByLabel("Tên tool").fill("lookup_case");
    await dialog
      .getByRole("button", { name: "Thêm kết nối", exact: true })
      .click();
    await dialog.waitFor({ state: "hidden" });
    assert(
      !(await page.locator("#content").innerText()).includes(
        "browser-test-only-secret",
      ),
    );
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole("button", { name: "Mở điều hướng" }).click();
    await page
      .getByRole("link", { name: "Đội ngũ agent", exact: true })
      .click();
    await page
      .getByRole("heading", { name: "Đội ngũ agent", exact: true })
      .waitFor();
    await page.waitForFunction(
      () =>
        document.querySelector("#sidebar").getBoundingClientRect().right <= 0,
    );
    assert(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    );
    await page.screenshot({
      path: path.join(artifacts, "agents-mobile.png"),
      fullPage: true,
    });
    assert.deepEqual(errors, []);
    console.log(
      JSON.stringify(
        {
          passed: true,
          agents: detail.team.length,
          case_items: detail.items.length,
          model_calls: detail.cost.totals.calls,
          viewport_checks: ["1440x1000", "390x844"],
          artifacts,
        },
        null,
        2,
      ),
    );
  } finally {
    await browser.close();
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
