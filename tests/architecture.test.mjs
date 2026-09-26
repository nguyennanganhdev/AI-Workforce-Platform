import assert from 'node:assert/strict';
import { test } from 'node:test';
import { checkArchitecture, dependencyViolation, externalViolation, importSpecifiers } from '../scripts/check-architecture.mjs';

test('platform cannot access domain code, domain DTOs or domain schema', () => {
  for (const target of [
    'server/src/domains/vinhomes/incidents/repository.ts',
    'shared/domains/vinhomes/events.ts',
    'server/src/db/schema/domains/vinhomes/operations.ts',
  ]) assert.ok(dependencyViolation('server/src/platform/runtime/gateway.ts', target));
});

test('composition and public contracts keep domain integration possible', () => {
  assert.equal(dependencyViolation('server/src/app.ts', 'server/src/domains/vinhomes/routes.ts'), null);
  assert.equal(dependencyViolation('server/src/platform/runtime/gateway.ts', 'shared/platform/domain-contracts.ts'), null);
  assert.equal(dependencyViolation('server/src/domains/vinhomes/actions/service.ts', 'shared/platform/action-contracts.ts'), null);
});

test('business schema may reference identity but cannot hard-link runtime schema', () => {
  const from = 'server/src/db/schema/domains/vinhomes/operations.ts';
  assert.equal(dependencyViolation(from, 'server/src/db/schema/platform/identity.ts'), null);
  assert.ok(dependencyViolation(from, 'server/src/db/schema/platform/runtime.ts'));
});

test('UI and MCP cannot import backend repositories or database clients', () => {
  for (const from of ['domain-tools/vinhomes/technical-mcp/src/tools.ts', 'app/src/features/domains/vinhomes/resident/api.ts']) {
    assert.ok(dependencyViolation(from, 'server/src/domains/vinhomes/incidents/repository.ts'));
    assert.ok(externalViolation(from, 'pg'));
    assert.ok(externalViolation(from, '@qdrant/js-client-rest'));
  }
});

test('domain isolation covers UI and backend modules', () => {
  assert.ok(dependencyViolation('server/src/domains/vinhomes/actions/service.ts', 'server/src/domains/vinpearl/actions/service.ts'));
  assert.ok(dependencyViolation('app/src/features/platform/admin/page.ts', 'shared/domains/vinhomes/events.ts'));
  assert.ok(dependencyViolation('app/src/features/domains/vinhomes/resident/page.ts', 'app/src/features/domains/vinpearl/guest/page.ts'));
});

test('scanner checks re-exports, dynamic imports, require and type imports', () => {
  assert.deepEqual(importSpecifiers(`
    import type { A } from './a.js';
    export { B } from './b.js';
    const c = import('./c.js');
    const d = require('./d.js');
    type E = import('./e.js').E;
    const unknown = import(variable);
  `), ['./a.js', './b.js', './c.js', './d.js', './e.js', null]);
});

test('current repository respects import boundaries', () => {
  assert.deepEqual(checkArchitecture(), []);
});
