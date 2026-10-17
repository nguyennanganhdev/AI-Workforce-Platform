"""Server-owned execution attribution propagated into RAG and provider calls."""

from contextlib import contextmanager
from contextvars import ContextVar

execution_context = ContextVar("vin_execution_context", default=None)


@contextmanager
def execution_scope(context):
    token = execution_context.set(context)
    try:
        yield context
    finally:
        execution_context.reset(token)
