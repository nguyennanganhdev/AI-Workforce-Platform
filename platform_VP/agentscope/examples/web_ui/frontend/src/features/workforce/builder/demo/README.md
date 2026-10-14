# Builder Demo

Open `/builder/demo` on the frontend dev server, or choose **Builder Demo** on the Agents page. This route renders before the platform authentication component mounts: no backend, credentials or AI model are required.

Three deterministic scenarios cover a knowledge assistant, a two-agent travel team, and a service agent with a missing booking tool. The user describes a need, answers a clarification, approves an outline, edits agent settings and simulates publication. Free text is displayed in the conversation; it does not change the scripted agent templates.

`model.ts` owns demo views and fixtures; `mockBuilderClient.ts` owns asynchronous transitions; `useBuilderDemo.ts` owns cancellation, retry and versioned session storage. UI edits never write to real agents. Reset aborts pending work. A future backend adapter must map actual prepare/publish DTOs to these views; this is not a production API contract.

The demo is currently Vietnamese. Existing production Builder components and contracts remain separate.

## Validation

Run the normal frontend build and lint for the changed files. With Vite running and Playwright available, run `node tests/builder-demo.browser.mjs`. Optional environment variables:

- `BUILDER_DEMO_URL`: defaults to `http://127.0.0.1:5184/builder/demo`.
- `BUILDER_PLAYWRIGHT_PATH`: path to an existing Playwright package if not installed locally.
- `BUILDER_SCREENSHOT`: output screenshot path (default `builder-demo-preview.png`).

The browser check covers single and multi-agent creation, blockers, required fields, retry, reload persistence, cancellation on reset, mobile layout and absence of backend requests.
