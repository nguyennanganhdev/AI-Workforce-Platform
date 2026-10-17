# workflows — PHH Phase B

Owner: **Phan Huy Hoàng**. Phạm vi PHH-14/15: workflow state, immutable ticket binding, checkpoint, trigger, continuation, lease/fence/revision và close. Module không lưu provider inbox và không cung cấp fake production.

Exports chính nằm trong `__init__.py`: `WorkflowService`, `WorkflowContinuation`, `ExecutionGuard`, `WorkflowAggregate`, `WorkflowPattern`, repository/bootstrap/authorization/operation ports và `next_action`.

Production persistence, migration và composition thuộc Phase C. Xem [bàn giao Phase B](../../../../../../docs/workforce/handoffs/phan-huy-hoang/PHASE_B.md) và [integration request](../../../../../../docs/workforce/handoffs/phan-huy-hoang/INTEGRATION_REQUEST_PHH_PHASE_B.md).

Phase C4 đã bổ sung production-facing SQL repository/runtime adapter ở package
cha. Migration và global composition vẫn thuộc C7; xem
[bàn giao C4](../../../../../../docs/workforce/handoffs/phan-huy-hoang/PHASE_C_C4.md).
