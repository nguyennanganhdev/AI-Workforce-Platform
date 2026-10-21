"""Propose a durable fact for the user to approve as this agent's memory."""
from typing import TYPE_CHECKING, Any

from pydantic import Field

from ...message import TextBlock, ToolResultState
from ...permission import PermissionBehavior, PermissionContext, PermissionDecision
from ...tool import ParamsBase, ToolBase, ToolChunk

if TYPE_CHECKING:
    from ..storage import StorageBase


class _MemoryProposeParams(ParamsBase):
    content: str = Field(
        description="One short sentence stating the fact, e.g. 'Khách thường bay từ Hà Nội.'",
        max_length=300,
    )
    reason: str = Field(
        default="",
        description="Why it is durable: what the customer said or which result confirmed it.",
        max_length=300,
    )


class MemoryPropose(ToolBase):
    """Queue a memory proposal; the user approves it before it is used."""

    name = "MemoryPropose"
    description = (
        "Propose one durable fact about the customer or a confirmed lasting "
        "outcome for this agent to remember in future conversations. The user "
        "reviews every proposal; it is not remembered until approved."
    )
    input_schema: dict[str, Any] = _MemoryProposeParams.model_json_schema()
    is_concurrency_safe: bool = True
    is_read_only: bool = True
    is_state_injected: bool = False
    is_external_tool: bool = False
    is_mcp: bool = False
    mcp_name: str | None = None

    def __init__(self, storage: "StorageBase", user_id: str, agent_id: str, session_id: str) -> None:
        super().__init__()
        self._storage = storage
        self._user_id = user_id
        self._agent_id = agent_id
        self._session_id = session_id

    async def check_permissions(
        self,
        tool_input: dict[str, Any],
        context: PermissionContext,
    ) -> PermissionDecision:
        """A proposal changes nothing the agent uses until the user approves it."""
        del tool_input, context
        return PermissionDecision(behavior=PermissionBehavior.ALLOW, message="Memory proposals need user approval.")

    async def __call__(self, content: str, reason: str = "") -> ToolChunk:
        # Imported here: the service package imports the tools.
        # pylint: disable-next=import-outside-toplevel
        from .._service._agent_memory import MemoryRejected, propose

        try:
            outcome, _ = await propose(
                self._storage, self._user_id, self._agent_id, content, reason, self._session_id,
            )
        except MemoryRejected as error:
            return ToolChunk(content=[TextBlock(text=str(error))], state=ToolResultState.ERROR)
        text = {
            "proposed": "Đã gửi đề xuất ghi nhớ; người dùng sẽ duyệt. Đừng nói với khách là đã lưu.",
            "reinforced": "Ghi nhớ này đã được duyệt trước đó; đã ghi nhận lần xác nhận mới.",
            "duplicate": "Đề xuất giống hệt đang chờ người dùng duyệt.",
        }[outcome]
        return ToolChunk(content=[TextBlock(text=text)], state=ToolResultState.SUCCESS)
