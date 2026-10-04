"""Four read-only report tools."""

from .contracts import RuntimeContext

__all__ = ["ReportTools", "RuntimeContext"]


def __getattr__(name):
    if name == "ReportTools":
        from .facade import ReportTools

        return ReportTools
    raise AttributeError(name)
