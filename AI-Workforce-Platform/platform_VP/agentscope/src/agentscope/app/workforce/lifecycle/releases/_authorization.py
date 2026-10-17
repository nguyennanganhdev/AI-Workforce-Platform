"""Lifecycle pin checks composed with Orchestration's authorization port."""

from typing import Any, Set

from ..async_evaluation import canonical_hash
from ._service import SqlReleaseService


class PinnedVersionAuthorization:
    """Delegate actor/route/consent checks, then recheck every exact agent pin.

    Inject into WorkflowService.authorization. ExecutionGuard calls this port
    before model/tool effects and again before committing a turn. Execution's
    separate binding/tool/credential checks remain required.
    """

    def __init__(self, delegate: Any, releases: SqlReleaseService) -> None:
        self.delegate = delegate
        self.releases = releases

    async def authorize(
        self, scope: Any, actor: Any, audience: Any, operation: str, uow: Any = None
    ) -> None:
        await self.delegate.authorize(scope, actor, audience, operation, uow)

    async def _pins(self, aggregate: Any, uow: Any = None) -> None:
        expected: Set[str] = set()
        for pin in sorted(
            aggregate.checkpoint.agent_version_pins, key=lambda item: item.agent_id
        ):
            version = await self.releases.assert_usable(
                aggregate.workflow.scope, pin.version_id, pin.agent_id, uow
            )
            expected.update(
                canonical_hash(ref)
                for ref in version.frozen.read(aggregate.workflow.scope)[
                    "dependencies"
                ]["protocol_refs"]
            )
        actual = {
            canonical_hash(pin.model_dump(mode="json"))
            for pin in aggregate.checkpoint.protocol_pins
        }
        if actual != expected:
            raise ValueError("WORKFLOW_PROTOCOL_PIN_MISMATCH")

    async def authorize_trigger(
        self, aggregate: Any, trigger: Any, uow: Any = None
    ) -> None:
        await self.delegate.authorize_trigger(aggregate, trigger, uow)
        await self._pins(aggregate, uow)

    async def can_publish_external_event(
        self, aggregate: Any, event: Any, uow: Any
    ) -> bool:
        if not await self.delegate.can_publish_external_event(aggregate, event, uow):
            return False
        try:
            await self._pins(aggregate, uow)
        except (PermissionError, KeyError):
            # Execution still commits the real provider fact. PHH suppresses
            # public delivery/wakeup after revoke; never discard the fact.
            return False
        return True
