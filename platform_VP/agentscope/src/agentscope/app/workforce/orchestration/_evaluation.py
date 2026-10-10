"""EvaluationRunner facade over injected production runtime + eval guards.

No alternate interpreter/model loop. Composition supplies the same runtime
entrypoint and an evaluation-only Execution guard; callers cannot switch a
production run to mock mode with a request field.
"""

from ._models import detached, require, scope_key, snapshot, stored_scope


class EvaluationRunner:
    def __init__(self, identity, invoke_runtime_case, cancel_runtime_case, evaluation_guard_factory):
        self.identity, self.invoke = identity, invoke_runtime_case
        self.cancel, self.guard_factory = cancel_runtime_case, evaluation_guard_factory

    async def run_case(self, scope, version_snapshot, test_case, execution_mode):
        await self.identity.check_scope_active(scope)
        require(execution_mode in {"mock", "sandbox"}, "EVALUATION_MODE_INVALID")
        version_snapshot = snapshot(version_snapshot)
        require(bool(version_snapshot.get("manifest_hash")) and bool(version_snapshot.get("manifest")), "SNAPSHOT_INVALID")
        require(stored_scope(version_snapshot.get("scope")) == scope_key(scope), "SNAPSHOT_SCOPE_INVALID")
        # Authorization and clock are configured by backend guard factory, never test payload.
        guard = await self.guard_factory(scope, execution_mode)
        require(guard is not None, "EVALUATION_GUARD_REQUIRED")
        result = await self.invoke(scope, detached(version_snapshot), detached(test_case), guard)
        require(set(("transcript", "tool_traces", "cost_minor", "status")) <= set(result), "EVALUATION_RESULT_INVALID")
        require(result["status"] in {"completed", "failed", "cancelled"} and
                type(result["cost_minor"]) is int and result["cost_minor"] >= 0, "EVALUATION_RESULT_INVALID")
        return detached(result)

    async def cancel_case(self, scope, case_run_id):
        await self.identity.check_scope_active(scope)
        return await self.cancel(scope, case_run_id)
