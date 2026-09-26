import { Hono } from 'hono';

// Add authenticated routes as domain use cases are implemented.
export function vinhomesRoutes() {
  return new Hono();
}
