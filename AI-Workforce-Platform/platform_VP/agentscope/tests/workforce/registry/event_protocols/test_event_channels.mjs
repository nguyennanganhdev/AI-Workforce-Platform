import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const frontend = new URL('../../../../examples/web_ui/frontend/', import.meta.url);
const require = createRequire(new URL('package.json', frontend));
// Use the repo's Vite transforms/aliases to render actual house components.
const { createServer } = await import(require.resolve('vite'));
const server = await createServer({
  root: fileURLToPath(frontend),
  server: { middlewareMode: true, watch: null, hmr: false, ws: false },
});
try {
  const { channelReadiness } = await server.ssrLoadModule(
    '/src/features/workforce/integrations/event_channels/readiness.ts',
  );
  const channel = {
    tool_version_id: 'tool-1', name: 'Demo', protocol_version: '1',
    capabilities: ['create', 'receive_status'], status: 'configured',
    create_ready: true, provider_events_ready: true,
    status_query_ready: true, correlation_ready: true, blockers: [],
  };
  assert.deepEqual(channelReadiness(channel), {
    create: 'ready', providerEvent: 'ready', statusQuery: 'unsupported', correlation: 'ready',
  });
  assert.equal(channelReadiness({ ...channel, capabilities: ['create'] }).providerEvent, 'unsupported');
  assert.equal(channelReadiness({ ...channel, capabilities: ['create', 'status_query'] }).statusQuery, 'ready');
  assert.equal(channelReadiness({ ...channel, provider_events_ready: false }).providerEvent, 'blocked');
  assert.equal(channelReadiness({ ...channel, status: 'disabled' }).create, 'blocked');
  assert.equal(channelReadiness({ ...channel, status: 'disabled' }).providerEvent, 'ready');
  assert.equal(channelReadiness({ ...channel, status: 'drifted' }).create, 'blocked');
  assert.equal(channelReadiness({ ...channel, correlation_ready: false }).providerEvent, 'blocked');
  assert.equal(channelReadiness({ ...channel, capabilities: ['terminal', 'approval'] }).providerEvent, 'not_required');
  assert.equal(channelReadiness({ ...channel, capabilities: [], status: 'unconfigured' }).providerEvent, 'blocked');

  const { EventChannelsPanel } = await server.ssrLoadModule(
    '/src/features/workforce/integrations/event_channels/EventChannelsPanel.tsx',
  );
  const { createElement } = require('react');
  const { renderToStaticMarkup } = require('react-dom/server');
  const render = (props) => renderToStaticMarkup(createElement(EventChannelsPanel, props));
  assert.match(render({ channels: [], loading: true }), /role="status"/);
  assert.match(render({ channels: [], error: true, onRetry() {} }), /Thử lại/);
  assert.match(render({ channels: [] }), /Chưa có protocol/);
  const html = render({ channels: [{ ...channel, capabilities: ['create'],
    blockers: ['PROVIDER_AUTH_NOT_READY'], credential_ref: 'SECRET-MUST-NOT-RENDER',
  }] });
  assert.match(html, /chưa hỗ trợ theo dõi tiến độ/);
  assert.match(html, /Chưa sẵn sàng xác thực Provider Event API/);
  assert.doesNotMatch(html, /SECRET-MUST-NOT-RENDER/);
  assert.match(render({ channels: [{ ...channel, capabilities: ['terminal', 'approval'] }] }), /Cần xác nhận/);
  console.log('Event channel readiness and component rendering checks passed.');
} finally {
  await server.close();
}
