# Frontend migration audit

Date: 2026-10-17
Branch: `web-ui-new-integration`

## Integration boundary

- The AgentScope FastAPI application remains the only backend used by the integrated UI.
- The `web_ui_new/backend` Express application was not copied or added to Compose.
- Existing AgentScope-only frontend files were retained, including ticket timeline,
  event channels, team activity, chat hooks, and platform adapters.
- Shared and new frontend files from `web_ui_new/frontend` were overlaid onto the
  existing frontend. This brings across the updated design system, chat experience,
  localization, assets, office/graph views, and supporting components.

## Compatibility decisions

| Area | Decision |
| --- | --- |
| Auth, session, SSE | Keep the AgentScope API contract and existing application router. |
| API base URL | Use `getApiUrl` so a configured reverse-proxy prefix such as `/api` is preserved. |
| Workforce builder and leader | Keep the existing pages and API adapter. The source UI calls endpoints not exposed by the current FastAPI backend. |
| Admin UI | Source files are retained for future integration, but the page is not connected to the main application because `/admin/*` endpoints are not present. |
| Studio/agent management | The source fills routes already declared by the existing application router, but `/workforce/console/studio/*` is not part of the current FastAPI contract. These screens remain a runtime blocker until an adapter or matching FastAPI contract is supplied. |
| Express backend | Excluded. No backend or database schema was changed. |

## Route mapping

The existing router remains authoritative for `/`, `/chat`, workforce leader and
builder, schedule, channel, credential, MCP, skill, knowledge, settings, agent
routes, and `/setup`. Deep-link handling therefore stays compatible with the
current deployment. The agent-management routes existed before this overlay but
their source modules were missing; the imported modules require the unsupported
Studio API noted above.

## Validation status

- `git diff --check`: passed.
- Secret check: no `.env` file is included in the migration diff.
- Frontend build, backend build, lint, Docker Compose validation, and browser smoke
  tests could not be executed in this environment because Node.js/pnpm, Docker, and
  WSL are unavailable.

Run in a development environment with the project toolchain:

```bash
pnpm install --frozen-lockfile
pnpm --filter frontend build
pnpm --filter backend build
pnpm format:check
```

