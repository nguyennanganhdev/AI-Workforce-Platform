# Agent Factory

**Current status — 2026-10-02:** Factory runs independently. Production BE wiring
has been removed at the user's request; `/api/agent-factory/*` is not mounted.
The BE team owns reconnection using the
[Vietnamese integration specification](docs/backend-integration-spec.md).
Existing adapter seams/tests and stored-artifact guards remain available.

Standalone construction service at the repository root, alongside `agent-report`,
`agent-coordination` and `agent-reception`. This folder can be copied, installed,
tested and started without `server/`, `app/` or `shared/`.

```text
agent-factory/
  src/contracts.ts       request, draft/spec, catalogue and API DTOs
  src/spec.ts            schemas, exact resource resolution, compiler and hash
  src/verification.ts    static checks, semantic review and repair scope
  src/service.ts         bounded construction pipeline
  src/index.ts           public construction helpers for existing BE adapters
  src/client.ts          BE HTTP client with bounded, validated responses
  src/http.ts            authenticated construction endpoint
  src/model.ts           outbound model HTTP adapter
  src/server.ts          standalone Bun server
  tests/                 offline HTTP/model checks and construction fixtures
```

## Run independently

Use Bun 1.3.14, matching the repository's pinned runtime:

```sh
cd agent-factory
bun install --frozen-lockfile --ignore-scripts
# Set FACTORY_SERVICE_TOKEN, FACTORY_MODEL_API_KEY and FACTORY_MODEL in ../.env.
# start/dev load that repository root .env, shared with BE.
bun run check
bun run start
```

From the repository root, use `bun run --cwd agent-factory start` (or `dev`
for watch mode). Configure only the root `.env`; no `agent-factory/.env` is needed.
If this folder is copied outside the repository, copy its `.env.example` to a local
`.env` and run `bun --env-file=.env src/server.ts` directly.

The service listens on `127.0.0.1:4010` by default. `GET /health` checks that the
HTTP process is running; it does not call the model. Configure
`FACTORY_HOST=0.0.0.0` when running behind a private service network or container.

`FACTORY_MODEL_PROVIDER=openai` sends `max_completion_tokens=4096`.
`openai-compatible` sends `max_tokens=4096` to the configured full chat-completions
URL. Neither option silently changes the model or falls back to another provider.
The standalone transport supports this chat-completions protocol; the existing
BE's Anthropic transport remains in BE and is not copied into this module.
Model requests use native `fetch`, with the unchanged core's 20-second call cap,
90-second construction deadline and at most one scoped repair.

References: [Bun HTTP server](https://bun.sh/docs/runtime/http/server) and
[OpenAI Docs: Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions).

## HTTP contract

```http
POST /v1/constructions
Authorization: Bearer <FACTORY_SERVICE_TOKEN>
Content-Type: application/json
```

```json
{
  "request": {
    "name": "Notes",
    "role": "Summarizer",
    "description": "Summarize only text supplied by the user and identify its main points."
  },
  "catalogue": { "tools": [], "defaultToolRefs": [] }
}
```

For requests that need external resources, BE supplies its current actor-scoped
catalogue: exact tool refs, descriptions, schemas and declared effects, plus the
optional `defaultToolRefs` naming the tools BE attaches to every generated agent
(its knowledge-retrieval tool, for example). Never include provider keys, tool
credentials or grant mutations. Factory chooses tools only from this snapshot,
computes their fingerprints, and returns a verified artifact.

**Skills are generated, not selected.** Construction writes the agent's own
`generatedSkill` (procedure, per-tool usage guidance, constraints, completion
criteria) into the spec and the compiled prompt, and checks it against the resolved
tools: a skill may guide only a tool the spec holds. A `skills` key in the catalogue
is accepted and ignored unread. A default tool is available, not required; it
becomes an entry of `spec.resources` only when a requirement binds it. The Factory
names no default tool itself, and with none declared the artifact carries the
`NO_DEFAULT_TOOL` warning. Artifacts stored by compiler version 1 (with a selected
skill resource) are still read and run unchanged. The service key stays on BE/Factory; browsers and
end users do not call this endpoint directly or choose their own catalogue.

**200 response:** `FactoryConstructionResponse` contains `spec`, `systemPrompt`,
`specHash`, `intent` and `verification`. It means construction passed; it is not a
persisted agent or permission to execute. There is no `agentId` or readiness verdict.

**Errors:** `{error, code, issues, retryable}`. Authentication is 401, unsupported
content type 415, invalid request 400, body over 128 KiB 413, invalid catalogue or
construction refusal 422, unavailable model/reviewer or cancellation 503, and the
outer deadline 504. Unknown paths are 404; this route allows POST only.
Provider payloads and secrets are never returned. `NEEDS_INPUT` issues describe
missing information that BE can ask the user to provide.

## BE integration boundary

```text
BE: authenticate user and tenant -> read current scoped catalogue
                                      |
                       POST Factory /v1/constructions
                                      |
BE: validate spec/hash/prompt -> save with idempotency -> grants/readiness -> runtime
```

BE owns storage, user/tenant authorization, idempotent stored creation, audit,
credentials, resource connections and fresh owner-scoped readiness. Revalidate
resource fingerprints/access before persistence and execution: a construction
snapshot is not a grant. Existing BE read/recheck endpoints remain BE use cases.
Preserve generated-artifact integrity, immutable editing/copying and runtime guards.

Production BE currently does not construct/inject a Factory service or call Factory.
The optional `createApp` adapter and `createFactoryClient` remain available for the
BE team's implementation. The specification defines the future request, response,
integrity, idempotency and readiness behavior. Keeping those helpers or setting
environment variables does not reconnect BE. No local construction fallback is enabled.

Set these in the repository root `.env` (shared by BE and Factory):

```dotenv
FACTORY_SERVICE_URL=http://127.0.0.1:4010
FACTORY_SERVICE_TOKEN=<private-token-at-least-32-characters>
FACTORY_MODEL_PROVIDER=openai
FACTORY_MODEL_API_URL=https://api.openai.com/v1/chat/completions
FACTORY_MODEL_API_KEY=<model-api-key>
FACTORY_MODEL=<model-name>
```

Generate a token once with `openssl rand -hex 32` and put it in the root `.env`.
The model name, URL and API key live in that same file; BE does not send them in
construction requests. Factory reads `FACTORY_MODEL_*` explicitly; existing
`OPENAI_API_KEY`/`BOT_MODEL` values are not automatically substituted.
Recognized OpenAI project/service-account keys are accepted only with `openai`
and `https://api.openai.com/v1/chat/completions`. Recognized OpenRouter keys
require `openai-compatible` and `https://openrouter.ai/api/v1/chat/completions`.
Credential/provider/endpoint mismatches and URLs carrying credentials, query
parameters or fragments fail before any model HTTP request; errors contain no values.
Start Factory using the standalone command above. The BE team must explicitly wire
its client/use cases/routes before any Backend construction request is available.
For that future containerized BE, use Factory's reachable private service URL instead
of the container's loopback.

The future BE integration must fail safely without writes or fallback when Factory
is unavailable or authentication fails. The retained adapter maps these failures to
503, deadlines to 504 and invalid artifacts to 409 `ARTIFACT_INVALID`. Model-stage
observations remain in Factory; the BE team owns creation/outcome audits and storage.

## Docker

Build with this folder as the entire build context:

```sh
docker build -t agent-factory ./agent-factory
docker run --rm --env-file .env -e FACTORY_HOST=0.0.0.0 \
  -p 127.0.0.1:4010:4010 agent-factory
```

## Verification

`bun run check` typechecks and runs offline tests, including a real HTTP request to
a fake model server. It needs no database, network model credentials or BE process.
Existing comprehensive core/BE regression tests are still under `server/tests/`;
the golden data is owned here and the configured-model evaluation remains a BE tool.
Legacy database tests require the repository's dedicated `TEST_DATABASE_URL`.

The implementation plan is in [docs/implementation-plan.md](docs/implementation-plan.md).
[Legacy integration evidence](docs/legacy-integration.md) retains the existing P0
acceptance limits; offline checks do not establish real-model quality or deployment
approval. See [docs/verification.md](docs/verification.md) for actual executed checks.

HTTP integration evidence: [docs/http-integration-verification.md](docs/http-integration-verification.md).

The following is a historical integration smoke, usable only after the BE team
reconnects the existing local single-user deployment:

```sh
rtk bunx bun@1.3.14 --env-file=.env server/scripts/factory-http-smoke.ts
```

It currently exits with a clear detachment message before any paid model call.
Once reconnected, it reads the current scoped catalogue, verifies service authentication, builds
the Web Researcher using the real model, and checks BE persistence/integrity,
readiness, unchanged grants and secret-free responses/audits. It keeps one new
private generated agent per run; it grants no resources. Evidence is saved in
`.logs/factory-real-http-smoke.json`. It does not execute the generated agent.
