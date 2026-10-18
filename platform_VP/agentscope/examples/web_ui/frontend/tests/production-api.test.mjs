import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import test from 'node:test';

// Run against the actual artifact being packaged, not a second source build.
const directory = process.env.WEB_DIST_DIR;
test('bundled production client targets /api and contains no loopback API default', { skip: !directory }, () => {
  const assets = resolve(directory, 'assets');
  const clients = readdirSync(assets)
    .filter((name) => name.endsWith('.js'))
    .map((name) => readFileSync(resolve(assets, name), 'utf8'))
    .filter((source) => source.includes('Cannot reach the server. Check the server address and your network.'));
  assert.equal(clients.length, 1, 'Expected exactly one built API client chunk');
  assert.equal(/https?:\/\/(?:localhost|127\.0\.0\.1):8000/.test(clients[0]), false,
    'Production artifact embeds a loopback API address; rebuild with VITE_API_BASE_URL=/api');
  assert.match(clients[0], /["'`]\/api["'`]/, 'Production artifact must embed the /api proxy prefix');
});
