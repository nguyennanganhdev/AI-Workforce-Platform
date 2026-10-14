# -*- coding: utf-8 -*-
"""Restartable background loop around the single-job durable worker."""

from __future__ import annotations

import asyncio
from contextlib import AbstractAsyncContextManager, suppress
from typing import Self

from ._metrics import (
    MetricSink,
    NullMetricSink,
    WORKER_ITERATIONS,
    WORKER_RESTARTS,
)
from ._worker import DurableJobWorker, WorkerOutcomeStatus


class DurableWorkerSupervisor(AbstractAsyncContextManager):
    """Keep polling after transient repository/transport failures.

    Handler failures are already converted into durable retry state by
    :class:`DurableJobWorker`.  This outer boundary covers failures before a
    claim or while committing its fenced outcome; on restart the database is
    still the source of truth and an expired lease can be reclaimed safely.
    """

    def __init__(
        self,
        worker: DurableJobWorker,
        *,
        idle_seconds: float = 0.25,
        restart_seconds: float = 0.5,
        metrics: MetricSink | None = None,
    ) -> None:
        if idle_seconds <= 0 or restart_seconds <= 0:
            raise ValueError("worker delays must be positive")
        self._worker = worker
        self._idle_seconds = idle_seconds
        self._restart_seconds = restart_seconds
        self._metrics = metrics or NullMetricSink()
        self._task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> Self:
        if self._task is not None:
            raise RuntimeError("worker supervisor is already running")
        self._task = asyncio.create_task(
            self._run(), name="workforce-durable-worker"
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        del args
        task, self._task = self._task, None
        if task is None:
            return
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def _run(self) -> None:
        while True:
            try:
                outcome = await self._worker.run_once()
                self._metrics.increment(
                    WORKER_ITERATIONS,
                    labels={"outcome": outcome.status.value},
                )
                if outcome.status == WorkerOutcomeStatus.IDLE:
                    await asyncio.sleep(self._idle_seconds)
            except asyncio.CancelledError:
                raise
            except Exception as error:  # restart boundary, never job handling
                self._metrics.increment(
                    WORKER_RESTARTS,
                    labels={"error_type": type(error).__name__},
                )
                await asyncio.sleep(self._restart_seconds)


__all__ = ["DurableWorkerSupervisor"]
