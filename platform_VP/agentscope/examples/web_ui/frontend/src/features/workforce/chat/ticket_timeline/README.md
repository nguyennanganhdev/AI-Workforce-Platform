# PHH ticket timeline — Phase B

Owner: **Phan Huy Hoàng**. PHH-17; local baseline `develop2@8487404`.

Exports: TicketTimeline, WorkflowStatus, createTimeline/applyReceipt/applyEvent/applySnapshot, createTimelineApi and followTimeline. Reuses shared/event_transport and Execution WorkforceApprovalCard.

State/cursor keys contain authenticated identity, conversation, workflow, ticket, user and external chat. Wrong binding or a conflicting event/message fails before cursor advancement. Receipts retain next_action; snapshots and public payloads are validated. A closed receipt permits historical replay; a delivered close event establishes the boundary against later new messages. Refresh retries the same serialized command once on 401; abort prevents updates to detached chat.

Host integration keeps a synchronous state ref:

```typescript
const stateRef = { current: createTimeline(binding) };
const publish = (next: TimelineState) => {
	stateRef.current = next;
	setState(next);
};
// A POST result also goes through this same ref:
publish(applyReceipt(stateRef.current, receipt));
await followTimeline(
	api,
	stateRef.current,
	publish,
	abort.signal,
	cursorStore,
	() => stateRef.current,
);
```

Abort the follower when authenticated identity/binding changes. onClose receives the exact binding, revision and stopTrackingOnly; host creates and retains a stable command ID for retries. Failed close never marks the ticket closed locally. Stop-tracking permits closing an open ticket with pending approvals without submitting a consent decision; ordinary completion close still requires no unresolved approval. Supply a manager JWT/BFF token approved by the shared-auth owner; do not expose machine partner keys in the browser. API baseUrl is supplied by the host, for example an approved BFF mapping.

71 reducer/API/transport/static-render/interaction tests live in the PHH test folder. Eleven tests mount React in Happy DOM and exercise close/approval clicks, loading/double-submit, error/retry, late completion and ticket switches. Global mounting, real token/quote feeds and actual browser checks remain in Phase C. No demo page or global App.tsx changes are added.

[Status](../../../../../../../../docs/workforce/handoffs/phan-huy-hoang/STATUS.md) / [integration requests](../../../../../../../../docs/workforce/handoffs/phan-huy-hoang/INTEGRATION_REQUEST_PHH_PHASE_B.md).

A stale snapshot caused by an in-flight POST is retried with abortable backoff (50ms increasing to at most 1s). Current POST state stays intact; the cursor advances only after a valid current snapshot. Foreign bindings, same-revision state conflicts and permission failures still stop the follower.
