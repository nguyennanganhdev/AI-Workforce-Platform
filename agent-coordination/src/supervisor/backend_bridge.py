"""Single send path per action via real DEV-3 adapters."""
from dataclasses import asdict
from adapters.backend.approval_client import ApprovalClient
from adapters.backend.messages import validate_request
from adapters.reception.reception_gateway import ReceptionGateway
from adapters.tools.tool_client import ToolClient
from .models import Action, require


class BackendBridge:
    def __init__(self, approvals: ApprovalClient, reception: ReceptionGateway, tools: ToolClient):
        self.operations = {
            "approval.requested": approvals.request_plan,
            "completion.requested": approvals.request_completion,
            "resident.question": reception.ask_question,
            "resident.update": reception.send_update,
            "assignment.offered": tools.offer_assignment,
        }

    async def dispatch(self, action: Action) -> dict:
        require(action.operation in self.operations and action.wire["type"] == action.operation,
                "backend_operation_denied")
        validate_request(action.wire)
        return asdict(await self.operations[action.operation](action.wire))
