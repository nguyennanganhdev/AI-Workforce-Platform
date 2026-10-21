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

test('apiUrl keeps the base path for relative and absolute API bases', () => {
  const { apiUrl } = clientWith(async () => ok({}));
  assert.equal(apiUrl('/auth/login', '/api').pathname, '/api/auth/login');
  assert.equal(apiUrl('/auth/login', 'https://example.test/api/').toString(), 'https://example.test/api/auth/login');
  assert.equal(apiUrl('/sessions/', 'http://localhost:8000').toString(), 'http://localhost:8000/sessions/');
  assert.equal(apiUrl('/x?a=1#top', '/api').search, '?a=1');
  assert.equal(apiUrl('/x?a=1#top', '/api').pathname, '/api/x');
  assert.equal(apiUrl('/items/a:b', '/api').pathname, '/api/items/a:b');
});

test('knowledge document links stay under a relative /api base', () => {
  const source = readFileSync(new URL('../src/api/knowledgeBase.ts', import.meta.url), 'utf8');
  const { apiUrl } = clientWith(async () => ok({}));
  const context = {
    exports: {},
    require: () => ({ apiUrl: (path) => apiUrl(path, '/api'), client: {}, ApiError: Error, getAccessToken: () => null }),
    URL,
  };
  vm.runInNewContext(ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText, context);
  const api = Object.values(context.exports).find((value) => value?.documentContentUrl);
  const url = new URL(api.documentContentUrl('kb1', 'doc1', 'tok', true));
  assert.equal(url.pathname, '/api/knowledge_bases/kb1/documents/doc1');
  assert.equal(url.searchParams.get('token'), 'tok');
  assert.equal(url.searchParams.get('download'), 'true');
});

test('requests go under a relative /api base instead of throwing', async () => {
  const seen = [];
  const source = readFileSync(new URL('../src/api/client.ts', import.meta.url), 'utf8')
    .replace('import.meta.env.VITE_API_BASE_URL', "'/api'");
  const context = {
    exports: {}, require: () => ({ toast: { error() {} } }),
    URL, AbortSignal, DOMException, Event,
    fetch: async (url) => { seen.push(String(url)); return ok({ ready: true }); },
    localStorage: { getItem: () => null },
    location: { origin: 'https://app.example.test' },
    window: { dispatchEvent() {} },
  };
  vm.runInNewContext(ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText, context);
  context.globalThis = context;
  await context.exports.client.get('/auth/me', undefined, { silent: true });
  assert.deepEqual(seen, ['https://app.example.test/api/auth/me']);
});

test('a proxy HTML error page becomes a short status, not the page', async () => {
  const html = '<html><head><title>502 Bad Gateway</title></head><body><center>nginx</center></body></html>';
  const api = clientWith(async () => new Response(html, { status: 502, statusText: 'Bad Gateway' }));
  await assert.rejects(api.client.get('/sessions'), (error) => {
    assert.equal(error.detail, '502 Bad Gateway');
    return true;
  });
  assert.deepEqual(api.notifications, ['502 Bad Gateway']);
});

test('a short plain-text error is still shown as sent', async () => {
  const api = clientWith(async () => new Response('Quota exceeded', { status: 429, statusText: 'Too Many Requests' }));
  await assert.rejects(api.client.get('/x'), (error) => error.detail === 'Quota exceeded');
});

test('a refresh that hits a restarting server keeps the user signed in', async () => {
  const api = clientWith(async (url) =>
    String(url).endsWith('/auth/refresh')
      ? new Response('<html>502</html>', { status: 502, statusText: 'Bad Gateway' })
      : unauthorized());
  api.setAccessToken('current');
  await assert.rejects(api.client.get('/sessions', undefined, { silent: true }));
  assert.deepEqual(api.events, []);
});
