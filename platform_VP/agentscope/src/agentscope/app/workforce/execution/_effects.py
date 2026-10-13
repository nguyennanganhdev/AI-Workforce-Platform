# -*- coding: utf-8 -*-
"""Explicit business effects; provider annotations never grant authority."""

from typing import Any

from ._utils import ExecutionError

EFFECTS = frozenset(
    {"read", "write", "booking", "cancel", "communicate", "ask_user"}
)
SIDE_EFFECTS = frozenset({"write", "booking", "cancel"})


def classify(descriptor: Any) -> Any:
    """
    Require a reviewed catalog effect rather than guessing from HTTP verbs.
    """
    effect = descriptor.get("effect")
    if effect not in EFFECTS or not descriptor.get("effect_reviewed", False):
        raise ExecutionError("TOOL_EFFECT_UNREVIEWED", 403)
    return effect
