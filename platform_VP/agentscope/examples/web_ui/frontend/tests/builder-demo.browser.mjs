// Run against Vite: BUILDER_DEMO_URL=http://127.0.0.1:5184/builder/demo
// Requires Playwright locally; BUILDER_PLAYWRIGHT_PATH may point to an existing installation.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.BUILDER_PLAYWRIGHT_PATH || 'playwright');
const browser = await chromium.launch({ headless: true });
try {
	const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
	page.setDefaultTimeout(12000);
	const errors = [];
	const apiRequests = [];
	page.on('pageerror', (error) => errors.push(error.message));
	page.on('request', (request) => {
		if (['fetch', 'xhr'].includes(request.resourceType())) apiRequests.push(request.url());
	});
	const base = process.env.BUILDER_DEMO_URL || 'http://127.0.0.1:5184/builder/demo';
	await page.goto(base);
	await page.getByRole('heading', { name: /Bạn muốn agent/ }).waitFor();
	await page.screenshot({
		path: process.env.BUILDER_SCREENSHOT || 'builder-demo-preview.png',
		fullPage: true,
	});
	const submit = () => page.getByRole('button', { name: 'Gửi yêu cầu', exact: true }).click();
	async function outline(scenario) {
		console.log('Scenario:', String(scenario));
		await page.getByRole('button', { name: scenario }).click();
		await submit();
		await page.getByRole('button', { name: 'Dùng câu trả lời mẫu' }).click();
		await submit();
		await page
			.locator('.bd-proposal-footer button')
			.filter({ hasText: 'Duyệt phương án' })
			.waitFor({ state: 'attached' });
	}
	await outline(/Trợ lý tri thức/);
	await page.getByRole('button', { name: 'Duyệt phương án', exact: true }).click();
	await page.getByLabel('Tên agent', { exact: true }).fill('Trợ lý tòa nhà');
	await page.reload();
	assert.equal(
		await page.getByLabel('Tên agent', { exact: true }).inputValue(),
		'Trợ lý tòa nhà',
	);
	await page.getByLabel('Tên agent', { exact: true }).fill('');
	assert.equal(await page.getByRole('button', { name: 'Tạo thử 1 agent' }).isDisabled(), true);
	await page.getByLabel('Tên agent', { exact: true }).fill('Trợ lý tòa nhà');
	await page.getByText('Tùy chọn demo', { exact: true }).click();
	await page.getByLabel('Giả lập lỗi ở thao tác tiếp theo').check();
	await page.getByRole('button', { name: 'Tạo thử 1 agent' }).click();
	await page.getByRole('button', { name: 'Thử lại', exact: true }).click();
	await page.getByRole('heading', { name: 'Đội ngũ của bạn đã sẵn sàng!' }).waitFor();
	await page.getByRole('button', { name: 'Bắt đầu lại', exact: true }).click();
	await outline(/Đội ngũ du lịch/);
	await page.getByRole('button', { name: 'Duyệt phương án', exact: true }).click();
	await page.getByLabel('Tên agent', { exact: true }).waitFor();
	assert.equal(await page.locator('.bd-agent-card').count(), 2);
	await page.locator('.bd-agent-card').nth(1).click();
	assert.equal(
		await page.getByLabel('Tên agent', { exact: true }).inputValue(),
		'Trợ lý đặt khách sạn',
	);
	await page.getByRole('button', { name: 'Tạo thử 2 agent' }).click();
	await page.getByRole('heading', { name: 'Đội ngũ của bạn đã sẵn sàng!' }).waitFor();
	await page.getByRole('button', { name: 'Bắt đầu lại', exact: true }).click();
	await outline(/Điều phối dịch vụ/);
	await page.getByRole('button', { name: 'Duyệt phương án', exact: true }).click();
	await page.getByLabel('Tên agent', { exact: true }).waitFor();
	assert.equal(await page.getByRole('button', { name: 'Tạo thử 1 agent' }).isDisabled(), true);
	await page.getByRole('button', { name: 'Bắt đầu lại', exact: true }).click();
	await page.getByRole('button', { name: /Trợ lý tri thức/ }).click();
	await submit();
	await page.getByRole('button', { name: 'Bắt đầu lại', exact: true }).click();
	await page.waitForTimeout(1100);
	assert.equal(
		await page.locator('.bd-message').count(),
		0,
		'Reset must discard pending replies',
	);
	await page.setViewportSize({ width: 390, height: 844 });
	await outline(/Đội ngũ du lịch/);
	await page.getByRole('button', { name: 'Đề xuất (2)', exact: true }).click();
	await page.getByRole('button', { name: 'Duyệt phương án', exact: true }).click();
	await page.getByLabel('Tên agent', { exact: true }).waitFor();
	assert.equal(
		await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
		true,
	);
	await page.getByRole('button', { name: 'Hội thoại', exact: true }).click();
	await page.locator('.bd-demo-options').evaluate(element => element.open = true);
	await page.getByLabel('Giả lập lỗi ở thao tác tiếp theo').check();
	await page.getByRole('button', { name: 'Đề xuất (2)', exact: true }).click();
	await page.getByRole('button', { name: 'Tạo thử 2 agent' }).click();
	await page.getByRole('button', { name: 'Thử lại', exact: true }).click();
	await page.getByRole('heading', { name: 'Đội ngũ của bạn đã sẵn sàng!' }).waitFor();
	assert.deepEqual(errors, [], 'No browser runtime errors');
	assert.deepEqual(apiRequests, [], 'Demo must not call backend APIs');
	console.log(
		'PASS: single/multi-agent, missing tool, validation, retry, reload, reset race, mobile, no API calls',
	);
} catch (error) {
	console.error(error);
	for (const context of browser.contexts()) {
		for (const page of context.pages()) {
			console.error(await page.locator('body').innerText());
		}
	}
	process.exitCode = 1;
} finally {
	await browser.close();
}
