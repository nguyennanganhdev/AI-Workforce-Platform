# PHH workflow and continuation

Owner: **Phan Huy Hoàng**. Plan tasks PHH-14/PHH-15; Phase B implementation with injected dependencies.

`WorkflowService` enforces ticket/chat/group binding, accepts replies on the original context, applies verified operation events, dedupes cause jobs and closes with revision checks. `WorkflowContinuation` loads pinned checkpoints, serializes via leases/fences, invokes outside the UOW and atomically commits checkpoint/message/result/event. `ExecutionGuard` must be called before every provider/tool side effect. Response-only, interactive and external-tracking use verified policy/facts, not domain keywords.

Repository/bootstrap/authorization/operation interfaces are in `_boundary.py`; public exports are in `__init__.py`. No production fake store/runtime is created here. Only owner paths are changed; shared contracts, migrations, job/inbox ownership and concrete composition remain with their owners. Phase A proposal files remain unchanged.

[Phase B handoff](../../../../../../docs/workforce/handoffs/phan-huy-hoang/PHASE_B.md) and [integration requests](../../../../../../docs/workforce/handoffs/phan-huy-hoang/INTEGRATION_REQUEST_PHH_PHASE_B.md) describe exact adapter guarantees and limits.
