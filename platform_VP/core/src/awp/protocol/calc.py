"""A calculator the agents call instead of adding numbers themselves."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import Field

from agentscope.message import TextBlock, ToolResultState
from agentscope.permission import PermissionBehavior, PermissionDecision
from agentscope.tool import ParamsBase, ToolBase, ToolChunk



class NotANumber(ValueError):
    """An amount the model wrote that is not a number; the message is for the model to read."""


def to_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value).replace(" ", "").replace(",", ""))
    except InvalidOperation:
        raise NotANumber(f"{value!r} is not a number") from None


def total_of(values: list) -> Decimal:
    """The exact sum, as calc_sum computes it (CaseAskConsent checks the resident's total with the same arithmetic)."""
    return sum((to_decimal(v) for v in values), start=to_decimal(0))


class _SumP(ParamsBase):
    label: str = Field(description="What is being added up, e.g. materials.")
    values: list[str] = Field(description="The amounts to add, copied from evidence.")


class calc_sum(ToolBase):  # noqa: N801 - the tool name the model sees
    """Adds amounts exactly. Its result becomes evidence like any tool output."""

    name = "calc_sum"
    description = ("Add up amounts exactly (no rounding errors). Always use this for totals "
                   "instead of adding in your head.")
    input_schema = _SumP.model_json_schema()
    is_read_only = True
    is_concurrency_safe = True

    def __init__(self, *_: Any) -> None:
        super().__init__()

    async def check_permissions(self, *args: Any, **kwargs: Any) -> PermissionDecision:
        return PermissionDecision(behavior=PermissionBehavior.ALLOW, message="pure function")

    async def call(self, label: str, values: list[str]) -> ToolChunk:
        try:
            total = total_of(values)
        except NotANumber as e:
            return ToolChunk(content=[TextBlock(text=str(e))], state=ToolResultState.ERROR)
        shown = int(total) if total == total.to_integral() else total.normalize()
        return ToolChunk(content=[TextBlock(
            text=f"sum of {label}: {shown} (from {len(values)} amounts: {', '.join(values)})")])
