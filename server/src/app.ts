import { Hono } from 'hono';
import { platformRoutes } from './platform/routes.js';
import { vinhomesRoutes } from './domains/vinhomes/routes.js';

// Composition root: the only layer that wires platform and concrete domains.
export function createApp() {
  const app = new Hono();
  app.route('/api/platform', platformRoutes());
  app.route('/api/domains/vinhomes', vinhomesRoutes());
  return app;
}
