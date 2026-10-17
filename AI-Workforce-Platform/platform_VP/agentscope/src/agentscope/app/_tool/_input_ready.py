"""Server-enforced customer-input readiness gate for coordinators."""

import unicodedata
from typing import Any

from ...message import TextBlock, ToolResultState
from ...tool import ToolChunk
from ..storage._utils import _resolve_team_leader
from ._team_tool_base import _TeamToolBase

_INPUT_VALUE_SCHEMA = {
    "type": "object",
    "properties": {
        "value": {
            "type": "string",
            "minLength": 1,
            "description": "The customer-owned value, without defaults or alternatives.",
        },
        "evidence_quote": {
            "type": "string",
            "minLength": 1,
            "description": "An exact quote from a customer message that supports the value.",
        },
    },
    "required": ["value", "evidence_quote"],
    "additionalProperties": False,
}


def _normalise_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


class InputReady(_TeamToolBase):
    """Prove that customer-owned required inputs exist before delegation."""

    name = "InputReady"
    is_concurrency_safe = False
    is_read_only = True

    def __init__(
        self,
        *args: Any,
        required_inputs: tuple[dict[str, str], ...] = (),
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._required_inputs = {
            item["key"]: item["description"] for item in required_inputs
        }
        if self._required_inputs:
            properties = {
                key: {**_INPUT_VALUE_SCHEMA, "description": description}
                for key, description in self._required_inputs.items()
            }
            inputs_schema = {
                "type": "object",
                "properties": properties,
                "required": list(properties),
                "additionalProperties": False,
            }
            declared = "; ".join(
                f"{key}: {description}"
                for key, description in self._required_inputs.items()
            )
        else:
            inputs_schema = {
                "type": "object",
                "additionalProperties": _INPUT_VALUE_SCHEMA,
                "minProperties": 1,
            }
            declared = "legacy contract: audit every customer-owned value needed by downstream work"
        self.input_schema = {
            "type": "object",
            "properties": {"inputs": inputs_schema},
            "required": ["inputs"],
            "additionalProperties": False,
        }
        self.description = f"""Confirm customer input readiness before any lookup or peer handoff.

Required intake: {declared}.
Call this tool in a separate step, then wait for success before doing business
work. Each evidence_quote must be copied exactly from a customer message and
must unambiguously support its value. Never use a guess, default, example,
provider result or peer message. If one value is missing, do not call this tool;
call TeamSay(to=null, kind=requires_user_input) with one grouped question."""

    async def __call__(self, inputs: dict[str, dict[str, str]]) -> ToolChunk:
        if self._required_inputs and set(inputs) != set(self._required_inputs):
            missing = sorted(set(self._required_inputs) - set(inputs))
            extra = sorted(set(inputs) - set(self._required_inputs))
            return ToolChunk(
                content=[
                    TextBlock(
                        text=f"InputReady rejected: missing={missing}, extra={extra}. Ask the customer for missing values.",
                    ),
                ],
                state=ToolResultState.ERROR,
            )
        if not inputs:
            return ToolChunk(
                content=[
                    TextBlock(text="InputReady rejected: no inputs were audited.")
                ],
                state=ToolResultState.ERROR,
            )

        try:
            team = await self._require_team()
            leader = await _resolve_team_leader(self._storage, self._user_id, team)
            if leader is None:
                raise ValueError("team leader conversation is unavailable")
            messages, _ = await self._storage.list_messages(
                self._user_id,
                leader.session_id,
                limit=200,
            )
            customer_messages = [
                _normalise_text(block.text)
                for message in messages
                if message.role == "user"
                for block in message.get_content_blocks()
                if isinstance(block, TextBlock) and block.text.strip()
            ]
            unsupported: list[str] = []
            for key, item in inputs.items():
                value = str(item.get("value", "")).strip()
                quote = str(item.get("evidence_quote", "")).strip()
                normalised_quote = _normalise_text(quote)
                if (
                    not value
                    or not normalised_quote
                    or not any(
                        normalised_quote in customer_message
                        for customer_message in customer_messages
                    )
                ):
                    unsupported.append(key)
            if unsupported:
                return ToolChunk(
                    content=[
                        TextBlock(
                            text=(
                                "InputReady rejected: exact customer evidence was not found for "
                                f"{sorted(unsupported)}. Ask the customer instead of guessing."
                            ),
                        ),
                    ],
                    state=ToolResultState.ERROR,
                )
            return ToolChunk(
                content=[
                    TextBlock(
                        text="Customer input readiness verified. Continue with bounded work."
                    )
                ],
                state=ToolResultState.SUCCESS,
                metadata={"input_ready": True, "input_keys": sorted(inputs)},
            )
        except Exception as exc:  # noqa: BLE001  # tool boundary returns safe error
            return ToolChunk(
                content=[TextBlock(text=f"InputReady failed: {exc}")],
                state=ToolResultState.ERROR,
            )
