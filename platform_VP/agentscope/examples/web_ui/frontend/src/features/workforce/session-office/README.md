# Shared session presentation

Both mock replay and backend sessions use `ChatContent` (SDK message bubbles,
tool-call/results, reasoning, composer and stop button) inside `SessionWorkspace`.
The workspace keeps Chat mounted and mounts the office only while visible.

## Sources and contracts

- `../session/presentation.ts`: `SessionPresentation` contains SDK `Msg[]`, explicit
  participant IDs, active agent and lifecycle phase. `officeFromSession` derives the
  office from this model, deduplicating message IDs for snapshot/reconnect updates.
- `pages/mock/session-adapter.ts`: translates the existing script into SDK messages.
  Scripts, branching, approvals and timings remain local fixtures; no fake backend
  requests or database writes. The existing Workforce approval card and reply/provider
  gates use local callbacks. These are not fabricated agent-tool approval events.
- `../session/live-adapter.ts`: consumes the already-open `useMessages` history/SSE,
  `SessionView.status` and team roster inside `ChatViewport`. No second SSE stream.
  Pending confirmation/external execution takes priority over running. Tool results
  clear stale pending calls. Loading a different session hides previous messages.

Both sources select `motion: 'events'`: working screens, speech and activity reflect
chat, with no unrelated meetings or handoffs. Explicit movement events can be added
later; text is never interpreted as a command to animate a meeting. The standalone
`runDemo` remains available internally but is not used by session workspaces.

## Limits

The current backend stream belongs to the owner of the viewed session. Other team
members are displayed, but their live status is not invented from names or the owner's
status. Per-member activity needs explicit backend events or a separate subscription.
The backend does not expose all mock workflow gates on the same stream yet. Mock
provider delivery and workforce approval gates remain clearly local simulations.

The tab preference persists per session; mock playback is in memory. `/mock/chat`
remains a redirect through normal authentication; there is no public mock route.

## Validation

From frontend, Node 24:

```sh
node --experimental-strip-types tests/session-presentation.test.mjs
node --experimental-strip-types tests/session-office.test.mjs
pnpm exec tsc -b
pnpm run build
```
