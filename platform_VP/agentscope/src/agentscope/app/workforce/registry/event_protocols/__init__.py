# -*- coding: utf-8 -*-
"""Public Registry protocol configuration and service exports."""

from importlib import import_module

from ._models import AsyncToolProtocol, EventMapping
from ._repository import AsyncProtocolRepository
from ._service import AsyncProtocolService

__all__ = [
    "AsyncToolProtocol",
    "EventMapping",
    "AsyncProtocolRepository",
    "AsyncProtocolService",
    "SqlAsyncProtocolProvider",
    "SqlAsyncProtocolRepository",
]


_LAZY_EXPORTS = {
    "SqlAsyncProtocolProvider": (
        "._provider",
        "SqlAsyncProtocolProvider",
    ),
    "SqlAsyncProtocolRepository": (
        "._sql_repository",
        "SqlAsyncProtocolRepository",
    ),
}


def __getattr__(name: str):
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attribute = target
    value = getattr(import_module(module_name, __name__), attribute)
    globals()[name] = value
    return value
