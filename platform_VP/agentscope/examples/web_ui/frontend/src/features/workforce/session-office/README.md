# Session office

`SessionWorkspace` keeps Chat mounted, defaults to Chat and stores the view preference
under a namespaced session ID. Only the visible office is mounted. The small chat in
Office uses the same composer, approvals and playback as the full Chat view.

`SessionOfficeSnapshot` is the presentation boundary. It contains participant identity,
status, current speech, phase and recent activity. It has no transport or backend types.

- `pages/mock/office-adapter.ts` supplies the session roster from existing mock chat events.
  Chat scripts remain unchanged.
- `preview-adapter.ts` supplies known members of real backend sessions. Chat continues
  to use the existing authenticated API and SSE connections.
- Both adapters select `motion: 'demo'` to preserve the original office choreography,
  including walking, meetings, work, approvals, pause, speed and restart. These are
  explicitly labeled simulated movements, independent of actual backend execution.
- `motion: 'events'` is the integration boundary for a future backend activity adapter;
  this disables the demo and applies snapshot state through `OfficeSim.applySession`.
  Network calls do not belong in drawing components.

There is no standalone unauthenticated mock page. `/mock/chat` is a legacy redirect
to `/chat` behind the normal auth flow. Existing sample conversations remain available
inside the normal chat page, with their existing scripts.

Only the view preference persists across reloads. Mock playback remains in-memory as
before. `/agents/office` redirects to `/chat`, where a session can be selected.

Validation: `node --experimental-strip-types --test tests/session-office.test.mjs`
from the frontend directory (Node 24).
