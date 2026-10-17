import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';

import { destinationsFor, homeFor, mayVisit, parseCapabilities, workspacesFor } from '../src/features/workforce/shell/access.ts';

const user = { id: 'resident-a', tenant_id: 'tenant-a' };
const c01 = (capabilities = {}, extra = {}) => ({ contract_version: 'vin-platform-1',
  tenant_id: user.tenant_id, initiator_user_id: user.id, billing_subject_id: user.id,
  workspace_id: `personal:${user.id}`, role: 'VIN_USER', authorization_revision: 1,
  purpose: 'chat', environment: 'production', eligible: true,
  capabilities: { 'personal.read': true, 'personal.create': true, ...capabilities }, ...extra });

test('C01 matches the producer version, principal and boolean capability map', () => {
  const view = parseCapabilities(c01(), user);
  assert.equal(view.contract_version, 'vin-platform-1');
  assert.deepEqual(workspacesFor(view).map(s => s.kind), ['personal']);
  assert.equal(homeFor(workspacesFor(view)[0]), '/workforce/leader');
  for (const extra of [{ contract_version: 'future' }, { initiator_user_id: 'resident-b' },
    { tenant_id: 'tenant-b' }, { authorization_revision: 0 }, { authorization_revision: 1.5 },
    { eligible: 'true' }, { capabilities: { 'catalog.manage': 'true' } }, { workspace_id: '' }]) {
    assert.throws(() => parseCapabilities(c01({}, extra), user), /CAPABILITIES_UNAVAILABLE/);
  }
});

test('role claims alone never create management or administration navigation', () => {
  for (const role of ['VIN_USER', 'AREA_MANAGER', 'DOMAIN_ADMIN', 'PLATFORM_ADMIN']) {
    const spaces = workspacesFor(parseCapabilities(c01({}, { role }), user));
    assert.deepEqual(spaces.map(s => s.kind), ['personal']);
    for (const path of ['/admin']) {
      assert.equal(mayVisit(spaces[0], path), false, `${role}: ${path}`);
    }
  }
});

test('customers use the existing pages in one server workspace', () => {
  const [workspace] = workspacesFor(parseCapabilities(c01({ 'knowledge.private.manage': true }), user));
  assert.equal(workspace.id, 'personal:resident-a');
  for (const path of ['/mcp', '/mcp/hub', '/skill', '/credential', '/channel', '/schedule', '/knowledge', '/workforce/builder', '/chat/agent/session']) {
    assert.equal(mayVisit(workspace, path), true, path);
  }
  for (const path of ['/admin', '/chat-unauthorized', '/unknown']) assert.equal(mayVisit(workspace, path), false, path);
  const [admin] = workspacesFor(parseCapabilities(c01({ 'accounts.manage': true }), user));
  assert.equal(mayVisit(admin, '/admin'), true);
});

test('revocation removes affected destinations and preserves valid partial grants', () => {
  const after = workspacesFor(parseCapabilities(c01({ 'personal.create': false },
    { authorization_revision: 2, eligible: false }), user));
  assert.equal(after.length, 1);
  assert.equal(mayVisit(after[0], '/workforce/builder'), false);
  assert.equal(mayVisit(after[0], '/account'), true);
  assert.equal(destinationsFor(after[0]).some(d => d.path === '/schedule'), true);
});

test('C01 public projection excludes incidental sensitive server fields', () => {
  const safe = parseCapabilities(c01({}, { secret: 'offline-sentinel', model_config: { api_key: 'offline-sentinel' } }), user);
  assert.equal(JSON.stringify(safe).includes('offline-sentinel'), false);
});

function personalModule() {
  const source = readFileSync(new URL('../src/api/personal.ts', import.meta.url), 'utf8');
  const context = { exports: {}, require: () => ({ client: {} }), URL };
  vm.runInNewContext(ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText, context);
  return context.exports;
}

test('usage validates unknown counters instead of reporting zero or negative usage', () => {
  const { parseUsage } = personalModule();
  assert.equal(parseUsage({ timezone: 'Asia/Ho_Chi_Minh', pending_reconciliation: 1,
    buckets: [{ window: 'day:2026-10-18', used: 10, reserved: 5 }] }).buckets[0].reserved, 5);
  for (const used of [undefined, null, -1, '0', 1.2, Infinity]) {
    assert.throws(() => parseUsage({ timezone: 'Asia/Ho_Chi_Minh', pending_reconciliation: 0,
      buckets: [{ window: 'day:2026-10-18', used, reserved: 0 }] }), /INVALID_CONTRACT/);
  }
});

test('link public projection excludes secret refs and validates revision/scopes', () => {
  const { parseLinks } = personalModule();
  const link = { id: 'l', provider_id: 'vinhomes', status: 'active', revision: 1,
    scopes: ['self', 'requests'], secret_ref: 'offline-sentinel' };
  assert.equal(JSON.stringify(parseLinks({ items: [link] })).includes('offline-sentinel'), false);
  assert.throws(() => parseLinks({ items: [{ ...link, revision: 0 }] }), /INVALID_CONTRACT/);
  assert.throws(() => parseLinks({ items: [{ ...link, scopes: [null] }] }), /INVALID_CONTRACT/);
});

test('Domain redirects reject executable URLs, userinfo and missing transaction state', () => {
  const { parseLinkStart } = personalModule();
  const state = 's'.repeat(43);
  for (const authorization_url of ['javascript:alert(1)', 'data:text/html,bad',
    `https://user:password@example.test/auth?state=${state}`, `http://example.test/auth?state=${state}`,
    `https://example.test/auth?state=${state}#fragment`, 'https://example.test/auth']) {
    assert.throws(() => parseLinkStart({ transaction_id: 't', authorization_url }, 'http://localhost'));
  }
  assert.equal(parseLinkStart({ transaction_id: 't', authorization_url: `https://domain.example/auth?state=${state}` }, 'https://platform.example').state, state);
});
