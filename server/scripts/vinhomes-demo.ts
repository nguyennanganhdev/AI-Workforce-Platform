/** Local mock gateway shared by FE and HTTP clients used by agents. */
import { Hono } from 'hono';
import { cors } from 'hono/cors';

const app = new Hono();
const roles = new Set(['resident', 'management', 'technical', 'security', 'admin']);
const prefix = '/api/vinhomes-demo';
const target = 'http://127.0.0.1:8000';

app.use(`${prefix}/*`, cors({
  origin: ['http://localhost:5173', 'http://127.0.0.1:5173', 'http://localhost:3000'],
  allowHeaders: ['Content-Type', 'X-Demo-Actor'],
  allowMethods: ['GET', 'POST', 'PATCH', 'OPTIONS'],
}));
app.all(`${prefix}/*`, async (c) => {
  const actor = c.req.header('X-Demo-Actor') ?? 'resident';
  if (!roles.has(actor)) return c.json({ detail: 'Unknown demo actor' }, 422);
  try {
    const health = await fetch(`${target}/health`, { signal: AbortSignal.timeout(3000) });
    if (!health.ok || (await health.json()).dataMode !== 'faker-database') {
      return c.json({ detail: 'Gateway requires FastAPI database demo mode' }, 503);
    }
    const url = new URL(c.req.url);
    const path = url.pathname.slice(prefix.length);
    const headers = new Headers({ 'X-Demo-Actor': actor });
    const contentType = c.req.header('Content-Type');
    if (contentType) headers.set('Content-Type', contentType);
    const body = ['GET', 'HEAD'].includes(c.req.method) ? undefined : await c.req.arrayBuffer();
    if (body && body.byteLength > 1024 * 1024) return c.json({ detail: 'Request too large' }, 413);
    const upstream = await fetch(`${target}${path}${url.search}`, {
      method: c.req.method, headers, body, signal: AbortSignal.timeout(10000), redirect: 'error',
    });
    const responseHeaders = new Headers();
    for (const name of ['Content-Type', 'Content-Disposition', 'X-Vinhomes-Data-Mode']) {
      const value = upstream.headers.get(name);
      if (value) responseHeaders.set(name, value);
    }
    responseHeaders.set('Cache-Control', 'no-store');
    return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
  } catch {
    return c.json({ detail: 'Mock API unavailable; start FastAPI demo on port 8000' }, 502);
  }
});

const server = Bun.serve({ hostname: '127.0.0.1', port: 3001, fetch: app.fetch });
console.log(`Mock gateway: http://localhost:${server.port}${prefix}`);
