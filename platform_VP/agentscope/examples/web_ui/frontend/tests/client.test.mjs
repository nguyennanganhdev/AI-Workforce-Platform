import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

// Execute the actual client with only Vite's build-time env and browser I/O mocked.
function clientWith(fetch, language = 'vi') {
  const source = readFileSync(new URL('../src/api/client.ts', import.meta.url), 'utf8')
    .replace('import.meta.env.VITE_API_BASE_URL', 'undefined');
  const events = [];
  const notifications = [];
  const translations = JSON.parse(readFileSync(
    new URL(`../src/i18n/locales/${language}.json`, import.meta.url), 'utf8'));
  const context = {
    exports: {}, require: (name) => {
      if (name === 'sonner') return { toast: { error: (message) => notifications.push(message) } };
      if (name === '../i18n') return { __esModule: true, default: {
        t: (key) => key.split('.').reduce((value, part) => value[part], translations),
      } };
      throw new Error(`Unexpected import: ${name}`);
    },
    URL, AbortSignal, DOMException, Event, fetch,
    localStorage: { getItem: () => null },
    window: { dispatchEvent: (event) => events.push(event.type) },
  };
  vm.runInNewContext(ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText, context);
  return { ...context.exports, events, notifications };
}
const ok = (body) => new Response(JSON.stringify(body), { status: 200 });
const unauthorized = () => new Response('expired', { status: 401 });

test('a late 401 reuses the already refreshed token without rotating again', async () => {
  let late;
  let refreshes = 0;
  const api = clientWith(async (url, options) => {
    if (String(url).endsWith('/auth/refresh')) {
      refreshes++;
      return ok({ access_token: 'new' });
    }
    if (options.headers.Authorization === 'Bearer new') return ok({ ready: true });
    if (String(url).endsWith('/slow')) return new Promise((resolve) => { late = resolve; });
    return unauthorized();
  });
  api.setAccessToken('old');
  const slow = api.client.get('/slow', undefined, { silent: true });
  await api.client.get('/fast', undefined, { silent: true });
  late(unauthorized());
  assert.equal((await slow).ready, true);
  assert.equal(refreshes, 1);
  assert.deepEqual(api.events, []);
});

test('failed refresh and rejected replacement token both expire the session', async () => {
  for (const refreshOK of [false, true]) {
    const api = clientWith(async (url) =>
      String(url).endsWith('/auth/refresh') && refreshOK
        ? ok({ access_token: 'still-invalid' }) : unauthorized());
    api.setAccessToken('old');
    await assert.rejects(api.client.get('/credential/', undefined, { silent: true }),
      (error) => error.status === 401);
    assert.equal(api.getAccessToken(), null);
    assert.deepEqual(api.events, [api.AUTH_EXPIRED_EVENT]);
  }
});

test('concurrent 401s share one refresh request', async () => {
  let release;
  let refreshes = 0;
  const api = clientWith(async (url, options) => {
    if (String(url).endsWith('/auth/refresh')) {
      refreshes++;
      return new Promise((resolve) => { release = () => resolve(ok({ access_token: 'new' })); });
    }
    return options.headers.Authorization === 'Bearer new' ? ok({}) : unauthorized();
  });
  api.setAccessToken('old');
  const a = api.client.get('/a', undefined, { silent: true });
  const b = api.client.get('/b', undefined, { silent: true });
  await new Promise((resolve) => setImmediate(resolve));
  release();
  await Promise.all([a, b]);
  assert.equal(refreshes, 1);
});

test('a missing credential shows one localized notification with recovery instructions', async () => {
  const messages = {
    vi: 'Không tìm thấy API key đã cấu hình hoặc bạn không có quyền sử dụng. Vui lòng thêm/chọn lại key trong mục Thông tin xác thực và cập nhật cấu hình Agent.',
    en: 'The configured API key credential was not found or you do not have access. Add or select a key in Credentials and update the Agent configuration.',
    zh: '找不到已配置的 API 密钥凭证，或你无权使用。请在凭证中添加或重新选择密钥，并更新智能体配置。',
  };
  for (const [language, message] of Object.entries(messages)) {
    const api = clientWith(async () => new Response(JSON.stringify({
      detail: "Credential 'a22ed48656284671ad4827f519a93373' not found.",
    }), { status: 404 }), language);
    await assert.rejects(api.client.post('/agent/', {}),
      (error) => error.status === 404 && error.detail === message && error.message === message);
    assert.deepEqual(api.notifications, [message]);
  }
});

test('silent missing-credential requests keep the helpful error without a notification', async () => {
  const api = clientWith(async () => new Response(JSON.stringify({
    detail: "Credential 'missing' not found.",
  }), { status: 404 }));
  await assert.rejects(api.client.post('/agent/', {}, undefined, { silent: true }),
    (error) => error.status === 404 && error.detail.includes('Vui lòng thêm/chọn lại key'));
  assert.deepEqual(api.notifications, []);
});

test('other errors keep their original detail and notification', async () => {
  for (const [status, detail] of [
    [404, "Agent 'missing' not found."],
    [429, 'insufficient_quota'],
    [500, "Credential 'missing' not found."],
  ]) {
    const api = clientWith(async () => new Response(JSON.stringify({ detail }), { status }));
    await assert.rejects(api.client.get('/agent/'),
      (error) => error.status === status && error.detail === detail);
    assert.deepEqual(api.notifications, [detail]);
  }
});
