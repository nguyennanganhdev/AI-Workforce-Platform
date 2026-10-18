"""The personal Leader's service-request tool. Consent has no model surface."""

import json
from typing import Literal
from uuid import UUID

from pydantic import Field

from ._team_tool_base import _TeamToolBase
from ...message import TextBlock, ToolResultState
from ...tool import ParamsBase, ToolChunk
from .._service import _customer_cases as cases
from ..vin_platform._contracts import PlatformError


class _Params(ParamsBase):
    operation: Literal["context", "create", "progress"]
    # Platform link IDs are opaque strings (the producer currently stores
    # uuid.hex). UUID coercion inserts hyphens and breaks the owner lookup.
    link_id: str | None = Field(default=None, min_length=1, max_length=255)
    apartment_id: UUID | None = None
    description: str = Field(default="", max_length=4000)
    location: str = Field(default="", max_length=500)
    category_id: UUID | None = None


class CustomerService(_TeamToolBase):
    name = "CustomerService"
    description = """Manage the current customer's own Domain service requests.
context: read verified links, owned apartments and service categories first.
create: only after the customer asks to submit, use exact IDs from context and
their description/location. Ask if apartment/category is ambiguous. Supply a
category_id to send the request to Domain staff; never invite a BQL Leader.
progress: read the current session's requests and canonical staff timeline.
Pass ticket_ids from these receipts to customer-granted Domain MCP tools; never
guess a ticket ID or pass a Platform case ID as a Domain ticket ID.
Report sync_status/as_of/next_action honestly; unavailable is not completion.
This tool cannot confirm, approve, cancel, reschedule or sign consent. Ask the
customer to review the request card and click its button themselves. Never
claim that a chat message has confirmed a quote or completed service."""
    input_schema = _Params.model_json_schema()
    is_read_only = False

    async def __call__(self, **kwargs):
        try:
            params = _Params.model_validate(kwargs)
            args = (self._storage, self._user_id, self._agent_id, self._session_id)
            if params.operation == "context":
                result = await cases.linked_context(*args)
            elif params.operation == "progress":
                result = await cases.session_cases(*args)
            else:
                if params.link_id is None or params.apartment_id is None or len(params.description.strip()) < 8 or len(params.location.strip()) < 3:
                    raise PlatformError("REQUEST_DETAILS_REQUIRED", 422)
                result = await cases.create_request(*args, link_id=str(params.link_id), apartment_id=str(params.apartment_id),
                    description=params.description.strip(), location=params.location.strip(),
                    category_id=str(params.category_id) if params.category_id else None)
            metadata = {}
            if params.operation in {"create", "progress"}:
                items = [result] if params.operation == "create" else result.get("items", [])
                fields = ("id", "code", "sync_status", "service_status", "canonical_version", "as_of", "next_action")
                receipts = [{key: item[key] for key in fields if key in item} for item in items
                    if item.get("id") and item.get("sync_status") == "applied"]
                if receipts:
                    metadata["customer_service_receipt"] = {
                        "user_id": self._user_id, "agent_id": self._agent_id, "session_id": self._session_id,
                        "operation": params.operation, "cases": receipts,
                    }
            return ToolChunk(content=[TextBlock(text=json.dumps(result, ensure_ascii=False, default=str))], metadata=metadata)
        except PlatformError as exc:
            return ToolChunk(content=[TextBlock(text=exc.code)], state=ToolResultState.ERROR)
        except ValueError:
            return ToolChunk(content=[TextBlock(text="INVALID_REQUEST_DETAILS")], state=ToolResultState.ERROR)
