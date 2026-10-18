// Browser layout smoke with mocked APIs. This does not validate a live FastAPI service.
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE ?? 'playwright');
const base = process.env.SMOKE_BASE_URL ?? 'http://127.0.0.1:4173';
import assert from 'node:assert/strict';
const browser = await chromium.launch({
	executablePath: process.env.CHROME_PATH || undefined,
	headless: true,
	args: ['--no-sandbox', '--disable-dev-shm-usage'],
});
const errors = [],
	unexpected = [];
const context = await browser.newContext();
await context.addInitScript(() => {
	if (!localStorage.getItem('agentscope-ui-language'))
		localStorage.setItem('agentscope-ui-language', 'en');
});
let authenticated = false;
let agents = [];
const sessionRequests = [];
await context.route('**/api/**', async (route) => {
	const url = new URL(route.request().url());
	const path = url.pathname.slice(4);
	if (path.startsWith('/sessions/')) sessionRequests.push(url.searchParams.get('agent_id'));
	let body;
	if (path === '/auth/refresh') {
		if (!authenticated) return route.fulfill({ status: 401, json: { detail: 'anonymous' } });
		body = { access_token: 'mock-token' };
	} else if (path === '/auth/me')
		body = {
			id: 'u',
			tenant_id: 'default',
			email: 'smoke@example.test',
			username: 'Smoke',
			status: 'active',
			role: 'MANAGER',
			domain_id: 'd',
			area_id: 'a',
		};
	else if (path === '/directory/domains') body = [];
	else if (path === '/agent/') body = { agents, total: agents.length };
	else if (path === '/agent/schema/v2')
		body = { schema: { type: 'object', properties: {} }, defaults: {} };
	else if (path === '/credential/') body = { credentials: [], total: 0 };
	else if (path === '/schedule/') body = { schedules: [], total: 0 };
	else if (path === '/knowledge_bases/')
		body = { knowledge_bases: [], total: 0, page: 1, page_size: 100 };
	else if (path === '/workforce/console/leader/bootstrap')
		body = { agent_id: 'leader', session_id: null };
	else if (path === '/sessions/') body = { sessions: [], total: 0 };
	else if (path === '/knowledge_bases/middleware/parameters_schema')
		body = { parameter_schema: {} };
	else if (path === '/knowledge_bases/embedding_models') body = { providers: [], policy: {} };
	else if (path === '/knowledge_bases/chunkers') body = { chunkers: [] };
	else if (path === '/credential/schemas') body = { schemas: [] };
	else if (path === '/health') body = { status: 'ok' };
	else if (
		[
			'/channels/',
			'/channels/types',
			'/mcp',
			'/skill',
			'/hub/mcp',
			'/hub/skill',
			'/workforce/console/agents',
			'/workforce/console/builder/conversations',
		].includes(path)
	)
		body = [];
	else {
		unexpected.push(path);
		return route.fulfill({ status: 404, json: { detail: 'unmocked' } });
	}
	return route.fulfill({ json: body });
});
const page = await context.newPage();
page.on('pageerror', (error) => errors.push(String(error)));
page.on('console', (msg) => {
	if (msg.type() === 'error' && !msg.text().includes('401')) errors.push(msg.text());
});
try {
	await page.goto(`${base}/`);
	await page.waitForTimeout(600);
	assert.ok((await page.locator('body').innerText()).length > 100);
	console.log('PASS anonymous landing');
	authenticated = true;
	for (const path of [
		'/workforce/agents',
		'/workforce/agents/missing',
		'/chat',
		'/workforce/builder',
		'/workforce/leader',
		'/mcp',
		'/skill',
		'/knowledge',
		'/credential',
		'/channel',
		'/schedule',
		'/settings',
		'/agents/map',
	]) {
		await page.goto(base + path);
		await page.waitForTimeout(500);
		assert.ok((await page.locator('body').innerText()).length > 10, path);
		console.log('VISITED', path);
	}
	for (const locale of ['vi', 'en', 'zh']) {
		await page.evaluate(
			(locale) => localStorage.setItem('agentscope-ui-language', locale),
			locale,
		);
		await page.reload();
		await page.waitForTimeout(250);
		assert.equal(await page.locator('html').getAttribute('lang'), locale);
	}
	await page.setViewportSize({ width: 390, height: 844 });
	await page.goto(`${base}/workforce/agents`);
	await page.waitForTimeout(300);
	assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
	console.log('PASS locales and mobile width');
	agents = [
		{
			id: 'draft-agent',
			user_id: 'u',
			editable: true,
			created_at: '2026-10-18T00:00:00Z',
			updated_at: '2026-10-18T00:00:00Z',
			data: {
				id: 'draft-agent',
				name: 'Private Draft',
				lifecycle_state: 'draft',
				system_prompt: '',
				context_config: {},
				react_config: {},
				invite_config: {},
			},
		},
	];
	await page.goto(`${base}/chat/draft-agent`);
	await page.getByText('Chưa có agent đã publish', { exact: true }).waitFor();
	assert.equal(sessionRequests.includes('draft-agent'), false);
	console.log('PASS unpublished agent deep link cannot open a session');
	console.log(JSON.stringify({ errors, unexpected }, null, 2));
	assert.deepEqual(unexpected, []);
	assert.deepEqual(errors, []);
} finally {
	await browser.close();
}
