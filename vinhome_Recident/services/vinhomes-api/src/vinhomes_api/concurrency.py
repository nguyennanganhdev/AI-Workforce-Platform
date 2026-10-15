"""Reusable optimistic concurrency checks for versioned aggregates."""


class VersionConflictError(Exception):
    """Raised when a command uses a stale aggregate version."""

    def __init__(self, expected_version: int, current_version: int | None = None):
        self.expected_version = expected_version
        self.current_version = current_version
        super().__init__("The resource changed since it was read")


def require_expected_version(current_version: int, expected_version: int) -> None:
    """Reject a command whose expected version is no longer current."""

    if current_version != expected_version:
        raise VersionConflictError(
            expected_version=expected_version,
            current_version=current_version,
        )
