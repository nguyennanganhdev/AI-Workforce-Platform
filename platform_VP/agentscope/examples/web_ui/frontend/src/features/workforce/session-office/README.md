# Shared session presentation

Backend sessions use `ChatContent` (SDK message bubbles,
tool-call/results, reasoning, composer and stop button) inside `SessionWorkspace`.
The workspace keeps Chat mounted and mounts the office only while visible.

## Sources and contracts

- `../session/presentation.ts`: `SessionPresentation` contains SDK `Msg[]`, explicit
  participant IDs, active agent and lifecycle phase. `officeFromSession` derives the
  office from this model, deduplicating message IDs for snapshot/reconnect updates.
- `model.ts`: the same `SessionOfficeSnapshot` also accepts explicitly labelled mock
  snapshots for local UI verification, without backend requests or database writes.
- `../session/live-adapter.ts`: consumes the already-open `useMessages` history/SSE,
  `SessionView.status` and team roster inside `ChatViewport`. No second SSE stream.
  Pending confirmation/external execution takes priority over running. Tool results
  clear stale pending calls. Loading a different session hides previous messages.

Snapshots select `motion: 'events'`: working screens, speech and activity reflect
chat. Movement follows structured events of the current request only (since the
customer's last message ID). The members the host's `AgentInvite` calls or `TeamSay`
handoffs name are
`called`: they meet the host at the table once, then work at their own desks and
report progress from there as speech. A member who needs another (`exchanges`)
walks to that one's desk and back. The host takes the result to your office while
the session waits for approval. Members nobody called never move; text is never
interpreted as a command to animate anything. A name two members share calls
neither.

Progress messages keep called members working; only structured `result` or `error`
reports end their pending work. A later handoff starts their work again. The live
host's actual ID occupies the host desk. New requests, completion and unmount cancel
outstanding movement and timers so old choreography cannot enter the next request.

The 3D scene is loaded only while the office is visible and renders on demand.
Camera controls include rotation, zoom and reset without requiring a drag gesture.
The team popover provides keyboard selection even when WebGL 2 is unavailable or
the graphics context is lost. Reduced motion places people directly and skips waits.

A member's `TeamSay` to another member reaches only that member's session, not the
host's stream, so live sessions have no `exchanges` yet; the backend has to expose
member-to-member messages (sender, recipient) to the host's stream first.

## Limits

The current backend stream belongs to the owner of the viewed session. Other team
members are displayed, with pending work inferred from explicit assignments and
reports, rather than measured execution telemetry. Per-member execution activity
needs explicit backend events or a separate subscription.
The backend does not expose all mock workflow gates on the same stream yet. Mock
provider delivery and workforce approval gates remain clearly local simulations.

The tab preference persists across sessions. Chat stays mounted while changing views;
there is no public mock route.

## Validation

From frontend, Node 24:

```sh
pnpm run test:office
pnpm exec tsc -b
pnpm run build
```
