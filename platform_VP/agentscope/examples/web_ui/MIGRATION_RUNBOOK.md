# Run and validate the integrated frontend

Use Node 22.23.3 and pnpm 10.34.7 (see `.nvmrc` and `packageManager`).
From `examples/web_ui`, run each command to completion before the next:

```bash
export NODE_OPTIONS=--max-old-space-size=1536
pnpm install --frozen-lockfile --child-concurrency=1 --network-concurrency=4
pnpm --filter frontend build
pnpm --filter frontend lint
pnpm --filter frontend test
pnpm --filter backend build
pnpm dev
```

`pnpm dev` now starts only Vite. Start the existing AgentScope FastAPI service
separately on port 8000. The legacy backend package is compiled for regression
checking only; it is not the runtime backend. No Express service is added.

Vite proxies `/api` to FastAPI and rewrites the refresh cookie path. By default
all browser calls are same-origin. An existing localStorage `server_url` still
overrides this; clear that setting to return to the proxy. Explicit
`VITE_API_BASE_URL` values may be `/api` or an absolute FastAPI base URL.

Agent management and chat creation use the existing AgentScope forms. Advanced
Studio/admin pages remain source-only. Room polling is off; enable
`VITE_ENABLE_WORKFORCE_ROOM=true` only with a compatible backend. A 404 disables
room requests for the page lifetime and keeps the existing fallback.

## Browser fixture smoke

`frontend/tests/browser.smoke.mjs` uses Playwright and a running production
preview. Install Playwright in an external tooling directory if it is not
available; pass the absolute `playwright/index.mjs` path in `PLAYWRIGHT_MODULE`.
It uses fake API responses and makes no calls to a real backend.

```bash
pnpm --filter frontend exec vite preview --host 127.0.0.1 --port 4173
# In another shell, after the preview is ready:
CHROME_PATH=/usr/bin/google-chrome PLAYWRIGHT_MODULE=/path/to/tooling/node_modules/playwright/index.mjs node frontend/tests/browser.smoke.mjs
```

`SMOKE_BASE_URL` optionally overrides `http://127.0.0.1:4173`. Without
`CHROME_PATH`, Playwright uses its installed Chromium. Stop the preview before
Docker work on the 8 GB host.

This checks routing, empty module states, locale, mobile width and unexpected
API calls. It does not validate real login, persisted CRUD, SSE or uploads.
Use the full checklist in `KeHoach.md` against a configured FastAPI deployment
before rollout. Never substitute fixtures for that acceptance test.

## Container

From the AgentScope root (two directories above this file):

```bash
docker compose config --quiet
docker compose build web
docker compose up -d web
```

Use the deployment's existing secret configuration. Do not commit it. `web`
uses nginx, `/api` points to `app:8000`, and SPA deep links fall back to index.html.
The build context excludes dependencies, build outputs and environment files.
Only run this after native build passes; build one service at a time on 8 GB.

## Rollback

Starting snapshot in this exported repo is `a82f400`; pre-overlay source is
`af66bae`. Preserve new local edits, revert only the verified migration commits,
then rebuild and restart `web`. Never delete database/Redis/MinIO volumes.
