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

| Area                         | Decision                                                                                                                                                                                                                                                                                                               |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Auth, session, SSE           | Keep the AgentScope API contract and existing application router.                                                                                                                                                                                                                                                      |
| API base URL                 | Use `getApiUrl` so a configured reverse-proxy prefix such as `/api` is preserved.                                                                                                                                                                                                                                      |
| Workforce builder and leader | Keep the existing pages and API adapter. The source UI calls endpoints not exposed by the current FastAPI backend.                                                                                                                                                                                                     |
| Admin UI                     | Source files are retained for future integration, but the page is not connected to the main application because `/admin/*` endpoints are not present.                                                                                                                                                                  |
| Studio/agent management      | The source fills routes already declared by the existing application router, but `/workforce/console/studio/*` is not part of the current FastAPI contract. The main routes now load `pages/workforce/agents/compatible.tsx`, using `agentApi` and the existing AgentScope dialogs. Studio source remains unconnected. |
| Express backend              | Excluded. No backend or database schema was changed.                                                                                                                                                                                                                                                                   |

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

## Verification batch — 2026-10-17, Fuq-export

Actual starting state: clean `main` at `a82f400`, not the uncommitted Windows
handoff state. No branch switch, reset, secret reads, or database/backend changes.

| Frontend surface                             | FastAPI router / decision                                                                                                                                                                           |
| -------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Auth/directory                               | `_auth.py`, `_business.py`: register/login/refresh/logout/me and directory unchanged.                                                                                                               |
| Agent management and chat creation           | `_agent.py`: GET/POST `/agent/`, GET `/agent/schema/v2`, PATCH/DELETE `/agent/{id}`. Reuse AgentScope forms; honor `editable`.                                                                      |
| Builder-managed tool/knowledge selection     | `_workforce_console.py`: GET/PATCH `/agents/{id}/tools`. Restored original dialog and `execution_mode` typing lost in overlay.                                                                      |
| Builder/leader/lifecycle                     | `_workforce_console.py`: existing prepare/publish/conversations/agents/lifecycle/bootstrap/tickets. No evaluate or progress-extension calls. Progress comes from existing conversation response.    |
| Sessions/chat                                | `_session.py`, `_chat.py`: CRUD/messages/stream/interrupt and POST `/chat/` unchanged. Backend supports leading mentions.                                                                           |
| MCP/Skill/hubs                               | `_mcp.py`, `_skill.py`, `_hub.py`: existing library, browse and install contracts retained.                                                                                                         |
| Knowledge/upload                             | `_knowledge_base.py`: CRUD, schema/models/chunkers, document upload/status/download/search. Multipart and credential handling retained.                                                             |
| Workspace                                    | `_workspace.py`: status/directories/files, MCP/skill attachment and multipart skill upload retained.                                                                                                |
| Credentials/channels/schedules/models/health | Corresponding existing `_router` modules; paths/methods retained.                                                                                                                                   |
| Admin and Studio extensions                  | Source retained, no main route or chat shortcut reaches these APIs. No Express service.                                                                                                             |
| Room                                         | `VITE_ENABLE_WORKFORCE_ROOM` defaults off. If explicitly enabled, first 404 returns null and suppresses subsequent calls for the page lifetime. Other errors propagate to the existing UI fallback. |

Transport uses same-origin `/api` by default and retains explicit absolute server
URLs. Vite strips `/api` before proxying to FastAPI port 8000 and rewrites refresh
cookie Path `/auth` to `/api/auth`. nginx already preserves streaming and rewrites
cookie paths. URL/refresh tests cover credentials and single `/api` prefixes.
The retained partner timeline modules use injected partner API bases and are not
mounted by the main router; no migration change to their contracts.

Native TypeScript/Vite build passed on Node 22.23.3, pnpm 10.34.7 with 1536 MB
heap. Frontend lint passed with one pre-existing debug-file Fast Refresh warning.
Seven test files (including API contract and retained ticket timeline suites) passed; backend TypeScript package build passed.
Browser smoke used explicit fixtures, visited landing and 13 authenticated routes,
checked vi/en/zh and 390px layout, and found no JS errors or unexpected requests.
This does **not** establish real auth, persisted CRUD, upload, or SSE parity.
The first sandbox probe could not reach localhost:8000. A later authorized host probe confirmed FastAPI health is OK; the user confirmed no active test account/model is available. Live E2E remains a release blocker.

Live OpenAPI comparison: 99 literal/template client calls match the running
service; GET/PATCH `/workforce/console/agents/{id}/tools` are absent there, although
both are declared in this repository's `_workforce_console.py`. The running
service exposes room/evaluation extensions not in this checkout. It is therefore
not the exact backend revision being integrated. Do not change frontend contracts
to match this unrelated runtime; live E2E needs the matching FastAPI revision plus
an active test account and model. No existing service was redeployed.
