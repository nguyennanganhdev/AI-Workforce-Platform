# -*- coding: utf-8 -*-
"""Small, dependency-free metric convention for Workforce runtime seams."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from threading import Lock
from typing import Protocol


WORKER_ITERATIONS = "workforce_worker_iterations_total"
WORKER_RESTARTS = "workforce_worker_restarts_total"
SSE_CONNECTIONS = "workforce_sse_connections_total"
SSE_REPLAYS = "workforce_sse_replays_total"
PROVIDER_EVENTS = "workforce_provider_events_total"


class MetricSink(Protocol):
    """Counter port; Prometheus/OpenTelemetry adapters stay external."""

    def increment(
        self,
        name: str,
        *,
        labels: Mapping[str, str] | None = None,
        value: int = 1,
    ) -> None: ...


class NullMetricSink:
    """Production-safe default when no metrics backend is configured."""

    def increment(
        self,
        name: str,
        *,
        labels: Mapping[str, str] | None = None,
        value: int = 1,
    ) -> None:
        del name, labels, value


class InMemoryMetricSink:
    """Deterministic sink for fault harnesses and adapter conformance tests."""

    def __init__(self) -> None:
        self._values: Counter[
            tuple[str, tuple[tuple[str, str], ...]]
        ] = Counter()
        self._lock = Lock()

    def increment(
        self,
        name: str,
        *,
        labels: Mapping[str, str] | None = None,
        value: int = 1,
    ) -> None:
        if value < 0:
            raise ValueError("counter increments must not be negative")
        key = (name, tuple(sorted((labels or {}).items())))
        with self._lock:
            self._values[key] += value

    def value(self, name: str, **labels: str) -> int:
        key = (name, tuple(sorted(labels.items())))
        with self._lock:
            return self._values[key]


__all__ = [
    "InMemoryMetricSink",
    "MetricSink",
    "NullMetricSink",
    "PROVIDER_EVENTS",
    "SSE_CONNECTIONS",
    "SSE_REPLAYS",
    "WORKER_ITERATIONS",
    "WORKER_RESTARTS",
]
