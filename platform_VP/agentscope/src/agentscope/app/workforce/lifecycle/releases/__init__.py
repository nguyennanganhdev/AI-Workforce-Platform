"""Release DTOs and lazily imported SQL adapters owned by Lifecycle."""

from importlib import import_module
from typing import Any

from ._models import (
    PublishedVersion,
    ReleaseContext,
    ReleaseSelection,
    ReleaseValidator,
    VersionUsageReader,
)
from ._schema import phase_d_schema_bundle

__all__ = [
    "PublishedVersion",
    "ReleaseContext",
    "ReleaseSelection",
    "ReleaseValidator",
    "VersionUsageReader",
    "SqlReleaseService",
    "PinnedVersionAuthorization",
    "get_release_metadata",
    "phase_d_schema_bundle",
]


def __getattr__(name: str) -> Any:
    modules = {
        "SqlReleaseService": "_service",
        "PinnedVersionAuthorization": "_authorization",
        "get_release_metadata": "_tables",
    }
    if name not in modules:
        raise AttributeError(name)
    return getattr(import_module("." + modules[name], __name__), name)
