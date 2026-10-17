import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

let runtimeErrors: string[] = [];

test.beforeEach(async ({ page }) => {
  runtimeErrors = [];
  page.on("pageerror", (error) => runtimeErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error")
      runtimeErrors.push(`${message.text()} ${message.location().url}`);
  });
});

test.afterEach(() => {
  expect(runtimeErrors, "The page must not produce browser errors").toEqual([]);
});

async function openStatic(page: Page) {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("data-motion", "paused");
  await page.evaluate(() => document.fonts.ready);
}

async function assertNoOverflow(page: Page) {
  const dimensions = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
    body: document.body.scrollWidth,
  }));
  expect(dimensions.document, JSON.stringify(dimensions)).toBeLessThanOrEqual(
    dimensions.viewport,
  );
  expect(dimensions.body, JSON.stringify(dimensions)).toBeLessThanOrEqual(
    dimensions.viewport,
  );
}

async function loadPageImages(page: Page) {
  for (const section of await page.locator("main > section").all()) {
    await section.scrollIntoViewIfNeeded();
    for (const image of await section.locator("img").all()) {
      await expect
        .poll(() =>
          image.evaluate(
            (element: HTMLImageElement) =>
              element.complete && element.naturalWidth > 0,
          ),
        )
        .toBeTruthy();
    }
  }
}

for (const width of [360, 375, 600, 900, 1100, 1440]) {
  test(`white landing layout and assets at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: width <= 600 ? 812 : 900 });
    await openStatic(page);
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(
      "Một ý tưởng.Cả đội ngũ AIcùng hành động.",
    );
    const cta = page.getByRole("link", { name: "Tạo đội Agent đầu tiên" });
    await expect(cta).toBeInViewport();
    await expect(cta).toHaveAttribute("href", "/register");
    await expect(page.locator("body")).toHaveCSS(
      "background-color",
      "rgb(255, 255, 255)",
    );
    await expect(
      page.locator('link[rel="preload"][as="image"][href*="hero-squad"]'),
    ).toHaveCount(1);
    await expect(page.locator(".hero-picture img")).not.toHaveAttribute(
      "loading",
      "lazy",
    );
    await assertNoOverflow(page);
    await loadPageImages(page);
    await assertNoOverflow(page);
    await expect(page.locator(".team-image")).toHaveCount(5);
    const imageSources = await page
      .locator(".team-image")
      .evaluateAll((images) =>
        images.map((image) => image.getAttribute("src")),
      );
    expect(new Set(imageSources).size).toBe(5);
    await page.locator("footer").scrollIntoViewIfNeeded();
    await assertNoOverflow(page);
    if (width === 1440 || width === 375) {
      await page.evaluate(() =>
        window.scrollTo({ top: 0, behavior: "instant" }),
      );
      const name = width === 1440 ? "desktop" : "mobile";
      await page.screenshot({ path: `.artifacts/white-${name}-hero.png` });
      await page.screenshot({
        path: `.artifacts/white-${name}-full.png`,
        fullPage: true,
      });
    }
  });
}

test("all twelve page sections, Vietnamese content, SEO and honest placeholders are present", async ({
  page,
}) => {
  await openStatic(page);
  await expect(page.locator("html")).toHaveAttribute("lang", "vi");
  await expect(page).toHaveTitle(
    "VAgents — Một ý tưởng. Cả đội ngũ AI cùng hành động.",
  );
  await expect(page.locator('meta[name="description"]')).toHaveAttribute(
    "content",
    "Giao một mục tiêu, VAgents tự lập đội agent chuyên trách, kết nối công cụ bạn đang dùng và vận hành quy trình từ đầu đến cuối.",
  );
  await expect(page.locator('meta[property="og:image"]')).toHaveCount(1);
  await expect(page.locator("header")).toHaveCount(1);
  await expect(page.locator("main > section")).toHaveCount(10);
  await expect(page.locator("footer")).toHaveCount(1);
  for (const id of [
    "how",
    "team",
    "demo",
    "connect",
    "faq",
    "cta",
    "contact",
  ]) {
    await expect(page.locator(`#${id}`)).toHaveCount(1);
  }
  await expect(page.locator(".step-card")).toHaveCount(3);
  await expect(page.locator(".team-card")).toHaveCount(5);
  await expect(page.locator(".orbit-node")).toHaveCount(12);
  await expect(page.locator(".bento-small")).toHaveCount(6);
  await expect(page.locator(".stat-card")).toHaveCount(4);
  await expect(page.locator('#pricing, a[href="#pricing"]')).toHaveCount(0);
  await expect(page.locator(".faq-item")).toHaveCount(5);
  await expect(page.locator(".cta-mascots img")).toHaveCount(5);
  for (const text of [
    "[X]+",
    "[Số doanh nghiệp đang dùng]",
    "[Bổ sung danh sách tích hợp chính thức]",
    "[Tài liệu]",
    "[Blog]",
    "[Email]",
    "[Số điện thoại]",
    "[Địa chỉ]",
    "© 2026 VAgents. [Tên pháp nhân]",
  ]) {
    await expect(
      page.getByText(text, {
        exact: text !== "[Bổ sung danh sách tích hợp chính thức]",
      }),
    ).toBeVisible();
  }
  const localAnchors = await page
    .locator('a[href^="#"]')
    .evaluateAll((links) => links.map((link) => link.getAttribute("href")));
  for (const href of new Set(localAnchors)) {
    expect(
      await page.locator(href!).count(),
      `Anchor ${href} must resolve`,
    ).toBe(1);
  }
  await expect(page.locator('a[href="/register"]')).not.toHaveCount(0);
});

test("FAQ first answer is open and keyboard controls reveal placeholders", async ({
  page,
}) => {
  await openStatic(page);
  const first = page.getByRole("button", {
    name: "VAgents là gì?",
    exact: true,
  });
  await expect(first).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator("#faq-answer-0")).toBeVisible();
  const second = page.getByRole("button", {
    name: "Tôi có cần biết lập trình để dùng không?",
    exact: true,
  });
  await second.focus();
  await page.keyboard.press("Enter");
  await expect(second).toHaveAttribute("aria-expanded", "true");
  await expect(first).toHaveAttribute("aria-expanded", "false");
  await expect(page.locator("#faq-answer-1")).toContainText("[Câu trả lời]");
  await expect(page.locator("#faq-answer-1")).toHaveAttribute(
    "aria-hidden",
    "false",
  );
  await page.keyboard.press("Enter");
  await expect(second).toHaveAttribute("aria-expanded", "false");
});

test("demo types, pauses outside the viewport, synchronizes five nodes, and replays", async ({
  page,
}) => {
  test.setTimeout(45_000);
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("data-motion", "active");
  await expect(page.locator(".demo-messages")).toHaveAttribute(
    "aria-live",
    "polite",
  );
  const typedPrompt = page.locator(
    '.console-prompt p > span[aria-hidden="true"]',
  );
  await expect(typedPrompt).toHaveText("");
  await page.locator("#demo").scrollIntoViewIfNeeded();
  await expect
    .poll(async () => (await typedPrompt.innerText()).length)
    .toBeGreaterThan(3);
  await page
    .getByRole("button", { name: "Tạm dừng demo", exact: true })
    .click();
  const pausedPrompt = await typedPrompt.innerText();
  await page.waitForTimeout(180);
  expect(await typedPrompt.innerText()).toBe(pausedPrompt);
  await page
    .getByRole("button", { name: "Tiếp tục demo", exact: true })
    .click();
  await page.locator("h1").scrollIntoViewIfNeeded();
  await expect(page.locator("#demo")).toHaveAttribute("data-in-view", "false");
  const offscreenPrompt = await typedPrompt.innerText();
  await page.waitForTimeout(180);
  expect(await typedPrompt.innerText()).toBe(offscreenPrompt);
  await page.locator("#demo").scrollIntoViewIfNeeded();
  for (let count = 1; count <= 5; count += 1) {
    await expect(page.locator(".agent-message")).toHaveCount(count, {
      timeout: count === 1 ? 10_000 : 3000,
    });
    await expect(page.locator(".workflow-nodes .is-complete")).toHaveCount(
      count,
    );
    await expect(page.locator(".console-status")).toContainText(
      `${count}/5 bước`,
    );
  }
  await expect(page.locator(".console-status")).toContainText(
    "Hoàn tất · quy trình đang chạy tự động",
  );
  await expect(page.locator(".agent-message").nth(4)).toContainText(
    "Quy trình đã lưu và sẽ chạy tự động.",
  );
  await page
    .getByRole("button", { name: "Chạy lại demo", exact: true })
    .click();
  await expect(page.locator(".agent-message")).toHaveCount(0);
  await expect(page.locator(".workflow-nodes .is-complete")).toHaveCount(0);
  await expect(page.locator(".console-status")).toContainText("0/5 bước");
});

test("global motion toggle pauses animations, restores them, and respects reduced motion", async ({
  page,
}) => {
  await page.goto("/");
  const pause = page.getByRole("button", {
    name: "Tạm dừng chuyển động",
    exact: true,
  });
  await pause.click();
  await expect(page.locator("html")).toHaveAttribute("data-motion", "paused");
  const play = page.getByRole("button", {
    name: "Bật chuyển động",
    exact: true,
  });
  await expect(play).toHaveAttribute("aria-pressed", "true");
  await page.waitForTimeout(1500);
  expect(
    await page.evaluate(
      () =>
        document
          .getAnimations()
          .filter((animation) => animation.playState === "running").length,
    ),
  ).toBe(0);
  await expect(page.locator(".agent-message")).toHaveCount(5);
  await play.click();
  await expect(page.locator("html")).toHaveAttribute("data-motion", "active");
  await page.emulateMedia({ reducedMotion: "reduce" });
  await expect(page.locator("html")).toHaveAttribute("data-motion", "paused");
  await expect(page.locator(".agent-message")).toHaveCount(5);
  await expect(page.locator(".console-status")).toContainText("5/5 bước");
  await page.waitForTimeout(1500);
  expect(
    await page.evaluate(
      () =>
        document
          .getAnimations()
          .filter((animation) => animation.playState === "running").length,
    ),
  ).toBe(0);
});

test("mobile menu supports Escape, focus restoration and anchor navigation", async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await openStatic(page);
  const menu = page.getByRole("button", { name: "Mở menu", exact: true });
  await menu.click();
  await expect(
    page.getByRole("button", { name: "Đóng menu", exact: true }),
  ).toHaveAttribute("aria-expanded", "true");
  await expect(
    page.getByRole("navigation", { name: "Điều hướng di động" }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(menu).toBeFocused();
  await expect(menu).toHaveAttribute("aria-expanded", "false");
  await menu.click();
  await page
    .getByRole("navigation", { name: "Điều hướng di động" })
    .getByRole("link", { name: "Đội ngũ Agent", exact: true })
    .click();
  await expect(menu).toHaveAttribute("aria-expanded", "false");
  await expect(page).toHaveURL(/#team$/);
  await expect(
    page.getByRole("heading", { name: "Năm agent, một tinh thần đồng đội." }),
  ).toBeInViewport();
  await assertNoOverflow(page);
});

test("mobile buttons, links and form controls provide 44px touch targets", async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await openStatic(page);
  const undersized = await page
    .locator("a, button, input, summary")
    .evaluateAll((elements) =>
      elements.flatMap((element) => {
        const rect = element.getBoundingClientRect();
        if (
          !rect.width ||
          !rect.height ||
          (rect.width >= 43.5 && rect.height >= 43.5)
        )
          return [];
        return [
          {
            tag: element.tagName,
            class: element.className,
            text: element.textContent || element.getAttribute("aria-label"),
            width: rect.width,
            height: rect.height,
          },
        ];
      }),
    );
  expect(undersized).toEqual([]);
});

test("newsletter validates email and reports that the unconnected form does not submit data", async ({
  page,
}) => {
  await openStatic(page);
  const posted: string[] = [];
  page.on("request", (request) => {
    if (request.method() === "POST") posted.push(request.url());
  });
  const email = page.getByRole("textbox", { name: "Nhận tin mới từ VAgents" });
  const subscribe = page.getByRole("button", { name: "Đăng ký nhận tin" });
  await subscribe.click();
  expect(
    await email.evaluate(
      (input: HTMLInputElement) => input.validity.valueMissing,
    ),
  ).toBe(true);
  await email.fill("demo@example.com");
  await subscribe.click();
  await expect(page.getByRole("status")).toContainText(
    "Chưa thể đăng ký: [Kết nối dịch vụ nhận tin]. Email của bạn chưa được gửi.",
  );
  expect(posted).toEqual([]);
});

for (const width of [375, 1440]) {
  test(`accessibility has no serious or critical findings at ${width}px including opened FAQ and footer`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: width < 600 ? 812 : 900 });
    await openStatic(page);
    await loadPageImages(page);
    await page
      .getByRole("button", {
        name: "Dữ liệu của doanh nghiệp có được bảo mật không?",
        exact: true,
      })
      .click();
    await page.getByText("Điều khoản", { exact: true }).click();
    await page.getByText("Bảo mật", { exact: true }).click();
    const results = await new AxeBuilder({ page }).analyze();
    expect(
      results.violations.filter(
        (violation) =>
          violation.impact === "critical" || violation.impact === "serious",
      ),
    ).toEqual([]);
  });
}
