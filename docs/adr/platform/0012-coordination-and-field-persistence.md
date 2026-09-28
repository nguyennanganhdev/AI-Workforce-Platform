# ADR 0012: Persist coordination separately from field operations

Status: accepted for database implementation; application integration pending.

## Context

The 0046/0047 model covers the documented domain inventory but does not persist the entire reception → dispatcher → specialist group chat → technician → resident update loop. A workflow session is not a business incident, and an internal agent message is not a confirmed resident update.

## Decision

Add tenant-scoped conversations, a version-pinned participant roster, ordered internal messages, explicit handoffs, inbox receipts, session controls, checkpoints and waits to Platform. Keep subject references soft across the DomainAdapter boundary. Reuse OpenBot users; external conversation provider/thread references support shell integration without merging shell and governed agent registries.

Add domain-owned teams, staff skills/shifts, assets, assignments, appointments and immutable field progress to Vinhomes. Add per-report resident-safe projections and per-channel delivery attempts, verified provider event receipts, versioned elapsed-time SLA policies and escalation records.

Use outbox/inbox and stable idempotency keys across boundaries. Write business state, event, progress and outbox atomically within the domain. Project only authorized information for the report recipient; a receptionist reads the domain projection through authorized services. Missing or stale progress can initiate a FOLLOW_UP handoff, without inventing an ETA.

Maintain one Drizzle ledger. 0048 creates 25 tables; 0049 adds temporal/cross-row constraints and FORCE RLS; 0050 adds queue/deadline indexes. Existing shell tables and 0046/0047 remain intact. Generate catalog entries for all 190 tables, including existing shell tables.

## Consequences

- Restart recovery and handoff acknowledgement have durable state; runtime adapters still need implementation.
- Domain records have no FK to agent/session history. Internal messages and resident communication have different access rules.
- Lease fencing checks checkpoints; every external command additionally requires service-side lease checks and idempotency.
- Matching staff availability, executing state machines, verifying callbacks, generating public summaries and delivering notifications remain application responsibilities.
- SLA supports elapsed minutes only. Business calendars, comprehensive inventory/procurement, refunds and full HR require separate requirements.
- [System flow](../../erd/SYSTEM_FLOW.md), [completeness review](../../erd/COMPLETENESS_REVIEW.md) and [table catalog](../../erd/physical/TABLE_CATALOG.md) are the implementation handoff.
