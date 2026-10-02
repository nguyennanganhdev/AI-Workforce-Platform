"""Required production ports. No in-memory/default permissive implementations."""
from typing import Any, Dict, Optional, Protocol
from groupchat.reception import ReceptionMessage, SupervisorMessage
from groupchat.models import Context
from .models import Action, AuthorityView, Reconciliation, SupervisorState, VerifiedReception


class StateStore(Protocol):
    async def load(self, context: Context) -> Optional[SupervisorState]: ...

    async def commit(self, state: SupervisorState, expected_version: Optional[int],
                     *, delivery_id: Optional[str] = None) -> bool:
        """Atomic CAS + optional delivery ACK + full checkpoint/journal.

        Composed inbox workers defer delivery ACK by passing delivery_id=None;
        their claim ACK atomically completes source delivery only after dependent
        D07 durable decisions/enqueue. Roll back ACK on failed CAS/lease.

        Scope key includes tenant/ticket/generation; check domain/workspace/binding
        and current generation under a durable fence. expected=None means create.
        Persist state.version=expected+1 (initial=0) as supplied by caller.
        Return False on contention; never acknowledge on failed CAS. Cross-replica
        serializability required. No external I/O inside this transaction.
        Action sending is a durable dispatch fence. A takeover MUST reconcile,
        never assume absence of receipt means absence of effect. Prevent an old
        worker dispatch after a not_applied reconciliation (remote fencing).
        """
        ...


class Authority(Protocol):
    async def inspect(self, state: SupervisorState) -> AuthorityView:
        """Reauthorize current binding/generation; read allowed facts/catalog,
        pinned ContextItem content/reader ACL, canonical IDs, recipients/expiry,
        current approvals/execution permission, QC/publication and closure.
        Context items must reflect current permission and ticket facts; removing
        the last reader requires DEV-2 deletion/fencing before any further turn.
        Snapshot must match state.version. Missing capability raises
        SupervisorError('dependency_unavailable:<capability>').
        """
        ...

    async def authorize_action(self, state: SupervisorState, action: Action) -> None:
        """Immediately before dispatch: verify current rights, exact plan/result,
        binding/generation, approvals, ContextItem content/ACL and remote fence.
        Backend must enforce these
        again atomically at application. Reject revoked/stale work, never bless
        an action merely because this process has a service credential.
        """
        ...

    async def reconcile(self, state: SupervisorState, action: Action) -> Reconciliation:
        """Trusted lookup by saved operation/key. not_applied must fence old sender;
        receipt uses bridge format. Missing lookup -> unknown, never guessed retry.
        Room completion remains owned by DEV-2's trusted adapter/storage callback.
        """
        ...


class ModelClient(Protocol):
    async def generate(self, prompt: Dict) -> str:
        """Return structured decision JSON using injected provider/configuration.
        No tools, credentials, endpoints or approval authority in model output.
        Must honor cancellation/deadline. No implicit retry/fallback.
        """
        ...


class ReceptionPort(Protocol):
    async def verify(self, message: 'ReceptionMessage', authentication: object) -> 'VerifiedReception':
        """Backend authenticates source_message_id, tenant, current generation,
        exact displayed ticket version and pending step, and deduplicates BOTH
        message identity/content and the decision for that step. Return only an
        accepted snapshot; never upgrade a stale reply to the latest version.
        Resolve routing/run IDs explicitly; do not rename V1 envelope fields.
        """
        ...

    async def send(self, message: 'SupervisorMessage', context: Context) -> 'Dict[str, Any]':
        """Backend atomically validates version/rights and stores the exact pending
        question/plan before delivery. Return message_id and accepted/completed
        status. Retries use the unchanged wire and message_id. Authority's existing
        authorize_action/reconcile must support channel='reception'.
        """
        ...
