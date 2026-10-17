"""Timer query behavior, stale query fencing and no busy agent polling."""

import asyncio

from agentscope.app.workforce.execution.external_operations import (
    OperationReconciler,
)
from execution_fakes import (
    PROVIDER,
    SCOPE_A,
    approved_call,
    event_fixture,
    harness,
)


def test_query_timer_recovers_unknown_and_only_emits_changes():
    async def scenario():
        async with harness(tracking=True) as env:
            call = await approved_call(env)
            env.provider.fault = "timeout_after_write"
            await env.gateway.execute(SCOPE_A, call)
            op = (
                await env.operations.get_for_workflow(SCOPE_A, "workflow-A")
            )[0]

            class Queries:
                calls = 0

                async def query(self, scope, operation, timer_id):
                    self.calls += 1
                    assert operation["correlation_id"] == op["correlation_id"]
                    return {
                        "external_job_id": "FAKE-job-1",
                        "status": "assigned",
                        "provider_version": 1,
                    }

            queries = Queries()
            reconciler = OperationReconciler(
                env.repo, queries, env.protocols, env.workflow, env.jobs
            )
            async with env.repo.transaction() as uow:
                await reconciler.schedule(
                    SCOPE_A, op["id"], "timer-1", "2026-10-09T02:01:00Z", uow
                )
            assert queries.calls == 0 and env.provider.calls == 1
            assert (
                await reconciler.reconcile(SCOPE_A, op["id"], "timer-1")
                == "applied"
            )
            assert (
                await reconciler.reconcile(SCOPE_A, op["id"], "timer-1")
                == "unchanged"
            )
            current = await env.repo.read("operations", SCOPE_A, op["id"])
            assert (
                current["creation_status"] == "succeeded"
                and current["external_job_id"] == "FAKE-job-1"
            )
            assert env.provider.calls == 1

    asyncio.run(scenario())


def test_slow_query_does_not_overwrite_new_provider_fact():
    async def scenario():
        async with harness(tracking=True) as env:
            call = await approved_call(env)
            await env.gateway.execute(SCOPE_A, call)
            op = (
                await env.operations.get_for_workflow(SCOPE_A, "workflow-A")
            )[0]

            class Queries:
                async def query(self, scope, operation, timer_id):
                    receipt = await env.ingress.accept(
                        PROVIDER,
                        event_fixture(
                            job_id=op["external_job_id"],
                            version=3,
                            status="completed",
                        ),
                    )
                    await env.processor.process(receipt["receipt_id"])
                    return {
                        "external_job_id": op["external_job_id"],
                        "status": "assigned",
                        "provider_version": 1,
                    }

            reconciler = OperationReconciler(
                env.repo, Queries(), env.protocols, env.workflow, env.jobs
            )
            assert (
                await reconciler.reconcile(SCOPE_A, op["id"], "timer-1")
                == "stale_query"
            )
            assert (await env.repo.read("operations", SCOPE_A, op["id"]))[
                "job_status"
            ] == "completed"
            assert (
                await reconciler.reconcile(SCOPE_A, op["id"], "timer-2")
                == "terminal"
            )

    asyncio.run(scenario())
