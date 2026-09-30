"""Required production ports. No in-memory/default permissive implementations."""
from typing import Protocol
from groupchat.models import Context
from .models import Action, AuthorityView, Reconciliation, SupervisorState


class StateStore(Protocol):
    async def load(self, context: Context) -> SupervisorState | None: ...

    async def commit(self, state: SupervisorState, expected_version: int | None,
                     *, delivery_id: str | None = None) -> bool:
        """Atomic CAS + inbox ACK + full checkpoint/journal, rollback on failure.

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
    async def generate(self, prompt: dict) -> str:
        """Return structured decision JSON using injected provider/configuration.
        No tools, credentials, endpoints or approval authority in model output.
        Must honor cancellation/deadline. No implicit retry/fallback.
        """
        ...
