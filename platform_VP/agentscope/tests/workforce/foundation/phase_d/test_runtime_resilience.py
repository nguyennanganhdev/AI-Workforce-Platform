# -*- coding: utf-8 -*-
"""D1 fault harness for restartable workers and stable metric names."""

from __future__ import annotations

import asyncio
import unittest

from agentscope.app.workforce.foundation import (
    DurableWorkerSupervisor,
    InMemoryMetricSink,
    WORKER_ITERATIONS,
    WORKER_RESTARTS,
    WorkerOutcome,
    WorkerOutcomeStatus,
)


class _FailOnceWorker:
    def __init__(self) -> None:
        self.calls = 0
        self.recovered = asyncio.Event()

    async def run_once(self) -> WorkerOutcome:
        self.calls += 1
        if self.calls == 1:
            raise ConnectionError("simulated database restart")
        self.recovered.set()
        return WorkerOutcome(status=WorkerOutcomeStatus.IDLE)


class DurableWorkerSupervisorTests(unittest.IsolatedAsyncioTestCase):
    async def test_transient_crash_restarts_without_losing_loop(self) -> None:
        worker = _FailOnceWorker()
        metrics = InMemoryMetricSink()
        supervisor = DurableWorkerSupervisor(
            worker,
            idle_seconds=0.001,
            restart_seconds=0.001,
            metrics=metrics,
        )

        async with supervisor:
            await asyncio.wait_for(worker.recovered.wait(), timeout=1)
            self.assertTrue(supervisor.running)

        self.assertGreaterEqual(worker.calls, 2)
        self.assertEqual(
            1,
            metrics.value(WORKER_RESTARTS, error_type="ConnectionError"),
        )
        self.assertGreaterEqual(
            metrics.value(WORKER_ITERATIONS, outcome="idle"),
            1,
        )
        self.assertFalse(supervisor.running)

    async def test_supervisor_rejects_busy_spin_delays(self) -> None:
        with self.assertRaises(ValueError):
            DurableWorkerSupervisor(_FailOnceWorker(), idle_seconds=0)


if __name__ == "__main__":
    unittest.main()
