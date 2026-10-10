# PHH public conversation events

Owner: **Phan Huy Hoàng**. Plan task PHH-16; Phase B replay/history/snapshot/SSE implementation.

`ConversationEventService` authorizes persisted scope/audience on every read, validates closed public envelopes/payloads, requires ordered pages and returns consistent snapshots supplied by the repository. `PublicEventWriter` builds public projections from a pinned workflow binding. Provider inbox/facts, prompts and credentials are not copied into public events.

Foundation `ConversationSseService` is reused. A bounded advisory-signal adapter allows periodic durable catch-up during notification outages and propagates cancellation. Heartbeat is finite and at most 60 seconds for repeated authorization checks. Public stream/subscription revalidates authorization and immutable binding before every frame, including cached replay items and heartbeats. Disconnect closes the nested replay iterator; HTTP/proxy bounded queues/timeouts still belong to integration. After-commit notification never substitutes event persistence.

`EventRepository` must implement atomic sequence allocation, scoped cursor/retention handling and one consistent snapshot. Phase B exercises these interfaces with test-only fakes; PostgreSQL/HTTP/proxy/retention implementation is a later integration requirement. No HTTP sender to partner endpoints is added.

[Phase B handoff](../../../../../../docs/workforce/handoffs/phan-huy-hoang/PHASE_B.md) / [integration requests](../../../../../../docs/workforce/handoffs/phan-huy-hoang/INTEGRATION_REQUEST_PHH_PHASE_B.md).
