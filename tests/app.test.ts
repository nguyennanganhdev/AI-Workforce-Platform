import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createApp } from '../server/src/app.js';

test('health works without database, runtime or domain implementations', async () => {
  const response = await createApp().request('/api/platform/health');
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { status: 'ok', mode: 'scaffold' });
});

test('unimplemented business routes do not return fake success', async () => {
  const response = await createApp().request('/api/domains/vinhomes/actions', {
    method: 'POST',
    body: '{}',
    headers: { 'content-type': 'application/json' },
  });
  assert.equal(response.status, 404);
});
