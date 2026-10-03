"""The Supervisor's ports over the business API, and the ports that have no producer yet."""
from __future__ import annotations

import json

from adapters.backend.errors import AdapterError
from groupchat.models import Context
from groupchat.reception import ReceptionMessage, SupervisorMessage
from supervisor.models import AuthorityView, Reconciliation, SupervisorError, VerifiedReception

from .backend import Backend, Refused

NOT_BOUND = "dependency_unavailable:"


class Reception:
    """ReceptionPort: the backend holds the message; the runtime only accepts what it stored."""

    def __init__(self, backend: Backend):
        self.backend = backend

    async def verify(self, message: ReceptionMessage, authentication: object) -> VerifiedReception:
        # `authentication` is the team the inbox delivered this message under.
        if authentication != message.team_id:
            raise AdapterError("reception_not_authorized")
        data = await self.backend.verify(message.team_id, message.message_id)
        stored = ReceptionMessage.model_validate(data["message"])
        if stored != message:
            # The backend never rebases a message; a difference means this is not the stored one.
            raise AdapterError("verified_message_mismatch")
        return VerifiedReception(context=Context.model_validate(data["context"]), message=stored,
                                 supervisor_run_id=data["supervisor_run_id"])

    async def send(self, message: SupervisorMessage, context: Context) -> dict:
        receipt = await self.backend.send(message.model_dump(mode="json", exclude_none=True))
        return {"message_id": receipt["message_id"], "status": receipt["status"]}


class Authority:
    """Authority: what the backend holds now. Nothing is inferred from the checkpoint."""

    def __init__(self, backend: Backend):
        self.backend = backend

    @staticmethod
    def _team(state) -> str:
        if state.reception is None:
            raise SupervisorError(NOT_BOUND + "reception_v2")
        return state.reception.team_id

    async def view(self, state) -> dict:
        try:
            return await self.backend.view(self._team(state))
        except Refused as error:
            # The team finished, moved to a new generation, or lost its service identity.
            raise SupervisorError(f"session_not_current:{error.status}") from None

    async def inspect(self, state) -> AuthorityView:
        view = await self.view(state)
        if Context.model_validate(view["context"]) != state.context:
            raise SupervisorError("scope_mismatch")
        # No specialist is bound to a room yet, so the catalog is empty; see ports.NoSpecialists.
        return AuthorityView(context=state.context, state_version=state.version,
                             ticket_version=view["ticket_version"],
                             reception_readers=[view["supervisor_version_id"]])

    async def authorize_action(self, state, action) -> None:
        try:
            await self.backend.authorize(self._team(state), action.action_id, action.channel, action.operation)
        except Refused:
            raise SupervisorError("action_not_authorized") from None

    async def reconcile(self, state, action) -> Reconciliation:
        if action.channel != "reception":
            return Reconciliation(outcome="unknown")
        found = await self.backend.result(self._team(state), action.wire["message_id"])
        if found.get("found") is True:
            return Reconciliation(outcome="receipt", receipt={"message_id": found["message_id"], "status": found["status"]})
        # The backend stores a result under its message id and refuses that id with other content,
        # so sending the unchanged wire again cannot apply twice, whoever sends it.
        return Reconciliation(outcome="not_applied")

    async def group_pin(self, context: Context, team_id: str) -> str:
        """The Supervisor version the backend pinned for the team; kept for the whole session."""
        return (await self.backend.view(team_id))["supervisor_version_id"]


class NoSpecialists:
    """Planner model for this stage: there is nobody to plan with, so no provider is called.

    A plan needs a room, and a room needs published specialists. Until the backend publishes
    specialist versions and the room ports are bound, the Supervisor hands the ticket to
    management with this reason instead of asking a model to choose among zero agents.
    """

    async def generate(self, prompt: dict) -> str:
        return json.dumps({"kind": "pause", "reason": "no_specialist_available"})

    async def close(self) -> None:
        return None


class _Unbound:
    """A port with no producer contract yet. It refuses; it never fakes a result."""

    def __init__(self, capability: str):
        self.capability = capability

    def _refuse(self, *args, **kwargs):
        raise SupervisorError(NOT_BOUND + self.capability)


class UnboundResolver(_Unbound):
    async def authorize(self, context, operation, room):
        self._refuse()

    async def resolve(self, context, groupchat_version_id, spec, room):
        self._refuse()

    async def invocation_run(self, context, room, participant, operation_id):
        self._refuse()


class UnboundInvocation(_Unbound):
    async def prepare(self, invocation):
        self._refuse()

    async def invoke(self, invocation):
        self._refuse()

    async def cancel(self, invocation):
        return False


class UnboundBackendActions(_Unbound):
    async def dispatch(self, action):
        raise AdapterError("operation_not_configured")


class UnboundEvents(_Unbound):
    async def resolve(self, event, authentication):
        self._refuse()
