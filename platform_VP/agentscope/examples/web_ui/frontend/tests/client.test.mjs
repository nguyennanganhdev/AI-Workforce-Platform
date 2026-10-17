import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

// Execute the actual client with only Vite's build-time env and browser I/O mocked.
function clientWith(fetch, { apiBase, savedServer = null } = {}) {
  const source = readFileSync(new URL('../src/api/client.ts', import.meta.url), 'utf8')
    .replace('import.meta.env.VITE_API_BASE_URL', JSON.stringify(apiBase) ?? 'undefined');
  const events = [];
  const context = {
    exports: {}, require: () => ({ toast: { error() {} } }),
    URL, AbortSignal, DOMException, Event, fetch,
    localStorage: { getItem: () => savedServer },
    window: {
      location: { origin: 'https://vagen-platform.duckdns.org' },
      dispatchEvent: (event) => events.push(event.type),
    },
  };
  vm.runInNewContext(ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText, context);
  return { ...context.exports, events };
}
const ok = (body) => new Response(JSON.stringify(body), { status: 200 });
const unauthorized = () => new Response('expired', { status: 401 });

test('bundled login uses its same-origin API despite a saved legacy server URL', async () => {
  for (const savedServer of ['http://localhost:8000', 'http://103.238.234.172:8000', 'https://old.example/api', '', null]) {
    const requests = [];
    const api = clientWith(async (url) => {
      requests.push(String(url));
      if (String(url) !== 'https://vagen-platform.duckdns.org/api/auth/login') {
        throw new TypeError('Failed to fetch');
      }
      return ok({ access_token: 'offline-fixture' });
    }, { apiBase: '/api', savedServer });
    const result = await api.client.post('/auth/login', { identity: 'offline', password: 'fixture' }, undefined, { silent: true });
    assert.equal(result.access_token, 'offline-fixture');
    assert.equal(api.getBaseUrl(), '/api');
    assert.deepEqual(requests, ['https://vagen-platform.duckdns.org/api/auth/login']);
  }
});

test('standalone frontend retains explicitly saved remote server support', () => {
  const api = clientWith(() => { throw new Error('No request expected'); }, {
    apiBase: 'http://localhost:8000', savedServer: 'https://remote.example/service',
  });
  assert.equal(api.getBaseUrl(), 'https://remote.example/service');
  assert.equal(api.getApiUrl('/auth/login').href, 'https://remote.example/service/auth/login');
});

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
