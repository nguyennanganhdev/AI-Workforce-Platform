"""Shared runtime type definitions for agent-runtime contracts."""

from __future__ import annotations

from typing import Any, Union

# JsonValue mirrors the JSON-compatible type used across the platform.
# Matches the TypeScript `JsonValue` from shared/platform/runtime-contracts.ts.
JsonValue = Union[str, int, float, bool, None, list[Any], dict[str, Any]]
