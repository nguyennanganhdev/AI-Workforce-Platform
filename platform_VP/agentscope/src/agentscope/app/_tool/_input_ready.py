"""Server-enforced customer-input readiness gate for coordinators."""

from typing import Any

from ...message import TextBlock, ToolResultState
from ...tool import ToolChunk
from .._shared_context import SharedContextService
from ._team_tool_base import _TeamToolBase

_INPUT_VALUE_SCHEMA = {
    "type": "object",
    "properties": {
        "value": {
            "type": "string",
            "minLength": 1,
            "description": "The customer-owned value, without defaults or alternatives.",
        },
        "source_message_id": {
            "type": "string",
            "minLength": 1,
            "description": (
                "The source_message_id of the supporting customer_message "
                "event in Shared Context."
            ),
        },
    },
    "required": ["value", "source_message_id"],
    "additionalProperties": False,
}


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
work. For each value, copy source_message_id from its supporting
kind=customer_message event, or from source_message_ids on its customer-confirmed
authoritative item, in Shared Context. Never use an agent/peer message, guess,
default, example or provider result. If one value is missing, do not call this
tool; send TeamSay(kind=requires_user_input) to the reply owner with one grouped
question. If a source ID is rejected, reload Shared Context and correct the
reference; do not ask the customer to repeat information already present."""

    async def __call__(self, inputs: dict[str, dict[str, str]]) -> ToolChunk:
        if self._required_inputs and set(inputs) != set(self._required_inputs):
            missing = sorted(set(self._required_inputs) - set(inputs))
            extra = sorted(set(inputs) - set(self._required_inputs))
            return ToolChunk(
                content=[
                    TextBlock(
                        text=f"InputReady rejected: missing={missing}, extra={extra}. Send one grouped question to the reply owner.",
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
            shared_context = self._shared_context or SharedContextService(
                self._storage,
                self._message_bus,
            )
            record = await shared_context.storage.get_team_shared_context(
                self._user_id,
                team.id,
            )
            if record is None or record.state.active_task_id is None:
                raise ValueError("shared customer context is unavailable")
            active_task_id = record.state.active_task_id
            customer_source_ids = {
                event.source_message_id or event.id
                for event in record.state.events
                if event.kind == "customer_message"
                and event.task_id == active_task_id
                and not event.stale
            }
            unsupported: list[str] = []
            for key, item in inputs.items():
                value = str(item.get("value", "")).strip()
                source_message_id = str(item.get("source_message_id", "")).strip()
                if not value or source_message_id not in customer_source_ids:
                    unsupported.append(key)
            if unsupported:
                return ToolChunk(
                    content=[
                        TextBlock(
                            text=(
                                "InputReady rejected: valid customer source_message_id "
                                f"was not found for {sorted(unsupported)}. Reload "
                                "Shared Context and correct the source reference. "
                                "Do not ask the customer to repeat information "
                                "already present."
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
