"""Vin user authority. Runtime consumers use these services, never raw grants."""

import os

from ._contracts import ExecutionContext, PlatformError, QuotaPolicy


def enabled():
    """One fail-closed parser shared by bootstrap, storage and consumers."""
    return os.getenv("VIN_PLATFORM_ENABLED", "false").strip().lower() == "true"


def __getattr__(name):
    # Legacy Redis-only installations do not need optional SQL/auth dependencies.
    if name == "VinPlatformService":
        from ._service import VinPlatformService
        return VinPlatformService
    raise AttributeError(name)

__all__ = ["ExecutionContext", "PlatformError", "QuotaPolicy", "VinPlatformService", "enabled"]
