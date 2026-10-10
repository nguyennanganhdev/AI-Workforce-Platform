# BHN Phase A — Requirement/policy contract proposal

Owner: Bùi Hữu Nghĩa. Related tasks: BHN-02/03/07/09/12/13.

Update 2026-10-10: Phase B follows Tiến Anh's policy proposal. Positive timeout is protocol metadata; policy uses status_query/needs_attention and required nonempty event/fact arrays. This file preserves the original Phase-A proposal; current decisions/requests are in [INTEGRATION_REQUEST_BHN_PHASE_B.md](INTEGRATION_REQUEST_BHN_PHASE_B.md).

## Existing contracts reused

Builder-local `BuildRequirements` nests canonical `BusinessProfile`; it does not duplicate Scope, tool catalog, manifest or reuse DTOs. `CapabilityRequirement` describes required/optional capabilities and reason before tool selection. `HandlingPolicyProposal` is an internal proposal, **not** the canonical production `AsyncHandlingPolicy`.

Samples: `tests/workforce/builder/async_capabilities/samples.json`. Local JSON Schema is available through `BuildRequirements.model_json_schema()` and exported beside this file as `phase-a.schema.json`. Valid samples cover sync lookup, immediate create, pending tracking, query fallback, clarification and independent batch; invalid samples cover forged owner/runtime fields, missing policy/clarification and malformed batch.

## Producer/consumer mapping

| Output | Existing boundary | Phase-A decision |
|---|---|---|
| Required business capabilities | `RegistryPort.list_available_tools(scope, query, capabilities, cursor)` | Keep signature; pass required capability names, paginate in Phase B. Optional coverage remains proposal metadata. |
| Business profile | `AgentReusePort.find_candidates(scope, business_profile, include_drafts)` | Keep signature; scope comes from verified backend context, not extraction output. |
| Coverage and protocol pin | `AsyncProtocolPort.get_snapshot(scope, tool_version_id)` / `validate_capability_coverage(snapshot, required_capabilities)` | Keep signature; pin protocol version/hash. Missing tracking is a blocker, not permission to downgrade. |
| Reuse choice | Canonical `ReuseDecision` → `DraftPort.create_draft` / `update_draft` | Keep same identity for revise/resume. Revalidate catalog revision before writing. No group/team artifact. |
| Policy proposal | `AgentManifest.async_policy_ref` + `protocol_snapshot_hashes` | Policy storage/ref resolution is not yet specified; never put a fabricated ref into production manifest. |

## Additive proposal for Chí Hoàng / Đông / Tiến Anh

1. Chí Hoàng: integrate canonical `AsyncHandlingPolicy` after producer/consumer review, with schema version, business capabilities, event types, required facts, completion condition, human confirmation and positive timeout plus timeout behavior. Decide policy persistence owner, version/hash and reference resolution for `async_policy_ref`; no new persistence port is assumed here.
2. Đông: document capability vocabulary (`create`, `receive_status`, `status_query`) and how business capability names map to protocol operation capabilities. `AsyncProtocolSnapshotRef` currently only exposes capability names; correlation, completion/timeout semantics and event/query readiness need an agreed detailed snapshot. Do not infer tracking readiness from `create` alone.
3. Tiến Anh: validate manifest policy references and pinned protocols, including create-only vs pending tracking and reuse/revise. Confirm how async requirements participate in business comparison: `BusinessProfile` currently has no typed async requirement. Agree a representation before production matching; do not hide new semantics in a parallel DTO.

No existing port signature changes are proposed in Phase A. Shared schema/TypeScript exports should be additive and remain owned by Chí Hoàng. No migration is supplied by Builder.

## Invariants and limits

- Tracking intent is desired capability, not a runtime workflow state. Booking confirmed can finish without polling even when the agent supports tracking; runtime waits only on verified pending results.
- `unspecified` intent requires clarification. Missing completion details may retain a tracking requirement with clarification and no policy. Such output is not ready to generate/publish.
- Policy has no fixed job/ticket/endpoint/roster fields. Strict schemas reject unknown fields. Text is still untrusted LLM output; Phase B must validate it and must not execute it as code.
- Status query is an alternative to receiving events where protocol supports it. Query fallback requires actual `status_query` coverage. A proposed timeout does not prove provider readiness.
- Fake-port tests establish sample boundary compatibility only; they do not demonstrate provider implementations, matching correctness, transaction safety or runtime integration.

Phase B: extraction adapter using existing `generate_structured_output`, selection/coverage/reuse logic, UI and owned tests. BHN-01 persistence and remaining earlier tasks must still be implemented in dependency order; Phase A does not mark BHN-01–14 complete.
