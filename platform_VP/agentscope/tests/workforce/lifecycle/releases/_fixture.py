"""TEST ONLY transactional Registry facade and C5/D3 reuse for D4."""

from contextlib import asynccontextmanager
from typing import Any, Dict, Optional, Tuple
from unittest.mock import patch

from sqlalchemy import update

from agentscope.app.workforce.contracts import (
    AgentManifest,
    EvaluationSnapshot,
    Scope,
    ToolDescriptor,
)
from agentscope.app.workforce.lifecycle import ValidationReport
from agentscope.app.workforce.lifecycle.async_evaluation import (
    AsyncEvaluationService,
    FrozenEvaluation,
    RuntimeEvaluationRunner,
    canonical_hash,
    freeze_evaluation,
    validate_async_draft,
)
from agentscope.app.workforce.lifecycle.releases import (
    ReleaseContext,
    ReleaseSelection,
    SqlReleaseService,
    get_release_metadata,
)
from agentscope.app.workforce.registry.event_protocols import SqlAsyncProtocolRepository
from agentscope.app.workforce.registry.event_protocols._tables import (
    async_protocol_heads,
)
from tests.workforce.fixtures.phase_c_e2e import SCOPE


class TransactionalValidator:
    """Real SQL protocol current head; tool/policy catalog is a test double.

    The Registry facade joins C1's UOW; this fixture is not a production
    provider of RegistryPort or a second protocol repository.
    """

    def __init__(self, frozen: FrozenEvaluation) -> None:
        self.dependencies = frozen.read(SCOPE)["dependencies"]
        self.tools = [
            ToolDescriptor.model_validate(value) for value in self.dependencies["tools"]
        ]

    async def validate(
        self, scope: Scope, manifest: AgentManifest, uow: Any
    ) -> Tuple[ValidationReport, Dict[str, Any]]:
        @asynccontextmanager
        async def bound() -> Any:
            yield uow

        repository = SqlAsyncProtocolRepository(bound)
        protocols = []
        for tool in self.tools:
            # Owner metadata used only to demonstrate a transactional lock in
            # the test composition; Lifecycle production never imports it.
            await uow.execute(
                update(async_protocol_heads)
                .where(
                    *[
                        async_protocol_heads.c[key] == value
                        for key, value in scope.model_dump().items()
                    ],
                    async_protocol_heads.c.tool_version_id == tool.tool_version_id,
                )
                .values(revision=async_protocol_heads.c.revision)
            )
            protocol, enabled = await repository.get_current(
                scope, tool.tool_version_id
            )
            if not enabled:
                raise PermissionError("PROTOCOL_DISABLED")
            protocols.append(protocol)
        return validate_async_draft(
            scope,
            manifest,
            self.tools,
            protocols,
            self.dependencies["policy"],
            scope,
            manifest.async_policy_ref,
            self.dependencies["policy_schema"],
        )


class ReleaseSupport:
    async def setup_release(self) -> None:
        self.scope = SCOPE
        self.frozen = self.driver.frozen
        self.initial_snapshot = self.driver.snapshot
        self.validator = TransactionalValidator(self.frozen)
        self.releases = SqlReleaseService(
            self.driver.env.uows,
            self.validator,
            self.driver.env.ingress.identity,
            clock=self.driver.env.clock,
        )
        payload = self.frozen.read(SCOPE)
        self.context = ReleaseContext(
            runtime_profile=payload["runtime_profile"],
            test_context=payload["test_context"],
            suite=payload["suite"],
        )
        async with self.driver.env.engine.begin() as connection:
            await connection.run_sync(get_release_metadata().create_all)
        await self.releases.stage_candidate(SCOPE, self.frozen)

    async def evaluate(
        self, frozen: Optional[FrozenEvaluation] = None, evaluation_id: str = "eval-D4"
    ) -> str:
        frozen = frozen or self.frozen
        self.driver.frozen = frozen
        self.driver.snapshot = EvaluationSnapshot.model_validate(
            frozen.read(SCOPE)["snapshot"]
        )
        # A new snapshot gets new isolated workflows. Keep old persisted
        # workflows/checkpoints; never edit their pins to prepare the next eval.
        self.driver.opened = {}
        self.driver.observations = {}
        original_open = self.driver.open_case
        previous = getattr(self, "evaluated_snapshot", None)

        async def isolated_open(scope: Any, snapshot: Any, case: Any, bind: Any) -> Any:
            if previous is not None and previous != snapshot.snapshot_id:
                case = {**case, "case_id": snapshot.snapshot_id + ":" + case["case_id"]}
            return await original_open(scope, snapshot, case, bind)

        service = AsyncEvaluationService(
            RuntimeEvaluationRunner(self.driver.repo, self.driver),
            self.driver.env.clock,
        )
        with patch.object(self.driver, "open_case", isolated_open):
            record = await service.run(SCOPE, frozen, evaluation_id)
        if record.report.status != "passed":
            raise AssertionError(record.model_dump_json())
        await self.driver.repo.register(SCOPE, evaluation_id, frozen)
        await self.driver.repo.save_record(record)
        self.evaluated_snapshot = self.driver.snapshot.snapshot_id
        return evaluation_id

    def selection(
        self,
        *,
        frozen: Optional[FrozenEvaluation] = None,
        evaluation_id: str = "eval-D4",
        deployment_revision: int = 0,
    ) -> ReleaseSelection:
        snapshot = (frozen or self.frozen).read(SCOPE)["snapshot"]
        return ReleaseSelection(
            draft_id=snapshot["draft_id"],
            draft_revision=snapshot["draft_revision"],
            evaluation_id=evaluation_id,
            deployment_revision=deployment_revision,
        )

    async def publish(self) -> str:
        await self.evaluate()
        return (
            await self.releases.publish_selected(
                SCOPE, [self.selection()], self.context, "publish-v1"
            )
        )[0]

    def next_candidate(
        self, *, agent_id: Optional[str] = None, draft_id: Optional[str] = None
    ) -> FrozenEvaluation:
        payload = self.frozen.read(SCOPE)
        snapshot = EvaluationSnapshot.model_validate(payload["snapshot"])
        manifest = snapshot.manifest.model_copy(
            update={
                "spec": snapshot.manifest.spec.model_copy(
                    update={
                        "system_prompt": snapshot.manifest.spec.system_prompt
                        + " Revised."
                    }
                )
            }
        )
        snapshot = snapshot.model_copy(
            update={
                "snapshot_id": self.driver.env.ids(),
                "candidate_version_id": self.driver.env.ids(),
                "draft_revision": 1 if draft_id else snapshot.draft_revision + 1,
                "manifest": manifest,
                "manifest_hash": canonical_hash(manifest.model_dump(mode="json")),
                "source_draft_hash": canonical_hash(manifest.model_dump(mode="json")),
                "agent_id": agent_id or snapshot.agent_id,
                "draft_id": draft_id or snapshot.draft_id,
            }
        )
        return freeze_evaluation(
            snapshot,
            ValidationReport.model_validate(payload["validation"]),
            payload["dependencies"],
            payload["runtime_profile"],
            payload["test_context"],
            self.context.suite,
        )
