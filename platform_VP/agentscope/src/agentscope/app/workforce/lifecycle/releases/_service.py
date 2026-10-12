"""Atomic release actions over persisted C5 evidence and immutable versions.

Only explicit caller actions activate deployments. Versions/evaluations are
retained indefinitely; this module deliberately has no delete/TTL operation.
Authorization and current configuration must come from trusted composition.
"""

from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Sequence, Tuple

from sqlalchemy import select, update

from ...contracts import EvaluationSnapshot, IdentityPort, Scope, UnitOfWorkFactory
from ..async_evaluation import (
    FrozenEvaluation,
    SqlEvaluationRepository,
    canonical_hash,
    check_persisted_release,
    freeze_evaluation,
)
from ..async_evaluation._repository import scoped
from ._models import (
    PublishedVersion,
    ReleaseContext,
    ReleaseSelection,
    ReleaseValidator,
    VersionUsageReader,
)
from ._tables import candidates, commands, deployments, versions


def _insert(uow: Any, table: Any, values: Dict[str, Any]) -> Any:
    if uow.bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    elif uow.bind.dialect.name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert
    else:
        raise ValueError("UNSUPPORTED_RELEASE_DATABASE")
    return insert(table).values(**values).on_conflict_do_nothing()


class SqlReleaseService:
    """PublishedCatalogPort plus the D4 release seam.

    stage_candidate receives an already authorized canonical draft snapshot;
    it is not a replacement for Builder's DraftPort/business deduplication.
    Every mutable write uses SQL CAS. No workflow table is accessed here.
    """

    def __init__(
        self,
        uows: UnitOfWorkFactory,
        validator: ReleaseValidator,
        identity: IdentityPort,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.uows = uows
        self.validator = validator
        self.identity = identity
        self.clock = clock
        self.evaluations = SqlEvaluationRepository(uows)

    async def _read(
        self, table: Any, scope: Scope, keys: Dict[str, Any], uow: Any
    ) -> Dict[str, Any]:
        row = (
            (await uow.execute(select(table).where(*scoped(table, scope, keys))))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise KeyError("release reference not found in owner scope")
        return dict(row)

    async def stage_candidate(
        self,
        scope: Scope,
        frozen: FrozenEvaluation,
        expected_revision: Optional[int] = None,
        uow: Any = None,
    ) -> None:
        if uow is None:
            async with self.uows() as tx:
                await self.stage_candidate(scope, frozen, expected_revision, tx)
                await tx.commit()
                return
        await self.identity.check_scope_active(scope, uow=uow)
        payload = frozen.read(scope)
        snapshot = EvaluationSnapshot.model_validate(payload["snapshot"])
        if snapshot.scope != scope:
            raise ValueError("RELEASE_SCOPE_MISMATCH")
        values = {
            **scope.model_dump(),
            "draft_id": snapshot.draft_id,
            "agent_id": snapshot.agent_id,
            "revision": snapshot.draft_revision,
            "frozen": frozen.model_dump(mode="json"),
            "content_hash": frozen.content_hash,
        }
        tx = uow
        await tx.execute(
            _insert(
                tx,
                deployments,
                {
                    **scope.model_dump(),
                    "deployment_id": snapshot.agent_id,
                    "revision": 0,
                    "active_version_id": None,
                    "archived": False,
                    "enabled": True,
                },
            )
        )
        if expected_revision is None:
            await tx.execute(_insert(tx, candidates, values))
            stored = await self._read(
                candidates, scope, {"draft_id": snapshot.draft_id}, tx
            )
            if any(stored[key] != value for key, value in values.items()):
                raise ValueError("CANDIDATE_CONFLICT")
        else:
            if snapshot.draft_revision != expected_revision + 1:
                raise ValueError("DRAFT_REVISION_CONFLICT")
            # Serialize updates against publish and archive/disable.
            await self._lock_head(scope, snapshot.agent_id, tx)
            result = await tx.execute(
                update(candidates)
                .where(
                    *scoped(candidates, scope, {"draft_id": snapshot.draft_id}),
                    candidates.c.agent_id == snapshot.agent_id,
                    candidates.c.revision == expected_revision,
                )
                .values(
                    revision=snapshot.draft_revision,
                    frozen=values["frozen"],
                    content_hash=frozen.content_hash,
                )
            )
            if result.rowcount != 1:
                raise ValueError("DRAFT_REVISION_CONFLICT")

    async def _lock_head(self, scope: Scope, agent_id: str, tx: Any) -> Dict[str, Any]:
        # UPDATE takes a row lock on PostgreSQL and a writer lock on SQLite.
        result = await tx.execute(
            update(deployments)
            .where(*scoped(deployments, scope, {"deployment_id": agent_id}))
            .values(revision=deployments.c.revision)
        )
        if result.rowcount != 1:
            raise KeyError("deployment not found in owner scope")
        return await self._read(deployments, scope, {"deployment_id": agent_id}, tx)

    async def _current(
        self, scope: Scope, row: Dict[str, Any], context: ReleaseContext, tx: Any
    ) -> FrozenEvaluation:
        frozen = FrozenEvaluation.model_validate(row["frozen"])
        payload = frozen.read(scope)
        snapshot = EvaluationSnapshot.model_validate(payload["snapshot"])
        if (
            frozen.content_hash != row["content_hash"]
            or snapshot.agent_id != row["agent_id"]
            or snapshot.draft_id != row["draft_id"]
            or snapshot.draft_revision != row["revision"]
        ):
            raise ValueError("CANDIDATE_CONTENT_DRIFT")
        report, dependencies = await self.validator.validate(
            scope, snapshot.manifest, tx
        )
        snapshot = snapshot.model_copy(
            update={
                "tool_snapshot_hash": report.tool_snapshot_hash,
                "test_context_hash": canonical_hash(context.test_context),
            }
        )
        return freeze_evaluation(
            snapshot,
            report,
            dependencies,
            context.runtime_profile,
            context.test_context,
            context.suite,
        )

    async def _command(
        self, scope: Scope, command_id: str, request: Dict[str, Any], tx: Any
    ) -> Optional[Dict[str, Any]]:
        if not command_id or len(command_id) > 200:
            raise ValueError("RELEASE_COMMAND_ID_REQUIRED")
        digest = canonical_hash(request)
        await tx.execute(
            _insert(
                tx,
                commands,
                {
                    **scope.model_dump(),
                    "command_id": command_id,
                    "request_hash": digest,
                    "result": None,
                },
            )
        )
        row = await self._read(commands, scope, {"command_id": command_id}, tx)
        if row["request_hash"] != digest:
            raise ValueError("IDEMPOTENCY_CONFLICT")
        return row["result"]

    async def _finish(
        self, scope: Scope, command_id: str, result: Dict[str, Any], tx: Any
    ) -> None:
        await tx.execute(
            update(commands)
            .where(*scoped(commands, scope, {"command_id": command_id}))
            .values(result=result)
        )
        await tx.commit()

    async def publish_selected(
        self,
        scope: Scope,
        selections: Sequence[ReleaseSelection],
        context: ReleaseContext,
        command_id: str,
    ) -> Tuple[str, ...]:
        context = ReleaseContext.model_validate(context.model_dump(mode="json"))
        selected = sorted(selections, key=lambda item: item.draft_id)
        if not selected or len({item.draft_id for item in selected}) != len(selected):
            raise ValueError("DISTINCT_RELEASE_SELECTIONS_REQUIRED")
        request = {
            "action": "publish",
            "selections": [item.model_dump(mode="json") for item in selected],
            "context": context.model_dump(mode="json"),
        }
        async with self.uows() as tx:
            await self.identity.check_scope_active(scope, uow=tx)
            replay = await self._command(scope, command_id, request, tx)
            if replay is not None:
                return tuple(replay["version_ids"])
            rows = [
                await self._read(candidates, scope, {"draft_id": item.draft_id}, tx)
                for item in selected
            ]
            if len({row["agent_id"] for row in rows}) != len(rows):
                raise ValueError("ONE_SELECTION_PER_AGENT_REQUIRED")
            heads = {
                agent_id: await self._lock_head(scope, agent_id, tx)
                for agent_id in sorted(row["agent_id"] for row in rows)
            }
            released = []
            for item in selected:
                # Reload after the head lock: an edit may have won beforehand.
                row = await self._read(
                    candidates, scope, {"draft_id": item.draft_id}, tx
                )
                head = heads[row["agent_id"]]
                if row["revision"] != item.draft_revision:
                    raise ValueError("DRAFT_REVISION_CONFLICT")
                if head["revision"] != item.deployment_revision:
                    raise ValueError("DEPLOYMENT_REVISION_CONFLICT")
                if head["archived"] or not head["enabled"]:
                    raise PermissionError("AGENT_UNAVAILABLE")
                current = await self._current(scope, row, context, tx)
                record = await check_persisted_release(
                    self.evaluations, scope, item.evaluation_id, current, uow=tx
                )
                now = self.clock()
                if now.tzinfo is None or now.utcoffset() is None:
                    raise ValueError("AWARE_TIMESTAMP_REQUIRED")
                version = PublishedVersion(
                    scope=scope,
                    agent_id=row["agent_id"],
                    version_id=record.snapshot.candidate_version_id,
                    evaluation_id=item.evaluation_id,
                    frozen=current,
                    published_by=scope.manager_account_id,
                    published_at=now,
                )
                data = version.model_dump(mode="json")
                inserted = await tx.execute(
                    _insert(
                        tx,
                        versions,
                        {
                            **scope.model_dump(),
                            "version_id": version.version_id,
                            "agent_id": version.agent_id,
                            "payload": data,
                            "content_hash": canonical_hash(data),
                        },
                    )
                )
                if inserted.rowcount != 1:
                    raise ValueError("IMMUTABLE_VERSION_CONFLICT")
                await self._activate(scope, head, version.version_id, tx)
                released.append(version.version_id)
            await self._finish(scope, command_id, {"version_ids": released}, tx)
            return tuple(released)

    async def _activate(
        self, scope: Scope, head: Dict[str, Any], version_id: str, tx: Any
    ) -> None:
        result = await tx.execute(
            update(deployments)
            .where(
                *scoped(deployments, scope, {"deployment_id": head["deployment_id"]}),
                deployments.c.revision == head["revision"],
            )
            .values(active_version_id=version_id, revision=head["revision"] + 1)
        )
        if result.rowcount != 1:
            raise ValueError("DEPLOYMENT_REVISION_CONFLICT")

    async def _version(
        self, scope: Scope, version_id: str, tx: Any
    ) -> PublishedVersion:
        row = await self._read(versions, scope, {"version_id": version_id}, tx)
        if canonical_hash(row["payload"]) != row["content_hash"]:
            raise ValueError("VERSION_CONTENT_DRIFT")
        version = PublishedVersion.model_validate(row["payload"])
        if (
            version.scope != scope
            or version.version_id != version_id
            or version.agent_id != row["agent_id"]
        ):
            raise ValueError("VERSION_IDENTITY_DRIFT")
        snapshot = version.frozen.read(scope)["snapshot"]
        if (snapshot["agent_id"], snapshot["candidate_version_id"]) != (
            version.agent_id,
            version.version_id,
        ):
            raise ValueError("VERSION_IDENTITY_DRIFT")
        return version

    async def get_version(self, scope: Scope, version_id: str) -> PublishedVersion:
        async with self.uows() as tx:
            return await self._version(scope, version_id, tx)

    async def get_deployment(self, scope: Scope, deployment_id: str) -> Dict[str, Any]:
        async with self.uows() as tx:
            return await self._read(
                deployments, scope, {"deployment_id": deployment_id}, tx
            )

    async def list_candidates(
        self, scope: Scope, capabilities: Sequence[str]
    ) -> Tuple[PublishedVersion, ...]:
        async with self.uows() as tx:
            heads = (
                (
                    await tx.execute(
                        select(deployments)
                        .where(
                            *scoped(deployments, scope, {}),
                            deployments.c.enabled.is_(True),
                            deployments.c.archived.is_(False),
                            deployments.c.active_version_id.is_not(None),
                        )
                        .order_by(deployments.c.deployment_id)
                    )
                )
                .mappings()
                .all()
            )
            result = []
            for head in heads:
                version = await self._version(scope, head["active_version_id"], tx)
                if version.agent_id != head["deployment_id"]:
                    raise ValueError("VERSION_AGENT_MISMATCH")
                if not set(capabilities).issubset(version.manifest.spec.capabilities):
                    continue
                try:
                    report, dependencies = await self.validator.validate(
                        scope, version.manifest, tx
                    )
                except PermissionError:
                    continue
                if (
                    report.valid
                    and not report.blockers
                    and (dependencies == version.frozen.read(scope)["dependencies"])
                ):
                    result.append(version)
            return tuple(result)

    async def assert_usable(
        self, scope: Scope, version_id: str, agent_id: str, uow: Any = None
    ) -> PublishedVersion:
        if uow is None:
            async with self.uows() as tx:
                return await self.assert_usable(scope, version_id, agent_id, tx)
        await self.identity.check_scope_active(scope, uow=uow)
        version = await self._version(scope, version_id, uow)
        head = await self._lock_head(scope, agent_id, uow)
        if version.agent_id != agent_id:
            raise ValueError("VERSION_AGENT_MISMATCH")
        if not head["enabled"]:
            raise PermissionError("AGENT_DISABLED_OR_REVOKED")
        # Archive/current head intentionally do not affect an existing pin.
        return version

    async def rollback(
        self,
        scope: Scope,
        agent_id: str,
        version_id: str,
        expected_revision: int,
        context: ReleaseContext,
        command_id: str,
    ) -> str:
        context = ReleaseContext.model_validate(context.model_dump(mode="json"))
        request = {
            "action": "rollback",
            "agent_id": agent_id,
            "version_id": version_id,
            "revision": expected_revision,
            "context": context.model_dump(mode="json"),
        }
        async with self.uows() as tx:
            await self.identity.check_scope_active(scope, uow=tx)
            replay = await self._command(scope, command_id, request, tx)
            if replay is not None:
                return replay["version_id"]
            head = await self._lock_head(scope, agent_id, tx)
            if head["revision"] != expected_revision:
                raise ValueError("DEPLOYMENT_REVISION_CONFLICT")
            if head["archived"] or not head["enabled"]:
                raise PermissionError("AGENT_UNAVAILABLE")
            version = await self._version(scope, version_id, tx)
            if version.agent_id != agent_id:
                raise ValueError("VERSION_AGENT_MISMATCH")
            payload = version.frozen.read(scope)
            snapshot = payload["snapshot"]
            current = await self._current(
                scope,
                {
                    "frozen": version.frozen.model_dump(mode="json"),
                    "content_hash": version.frozen.content_hash,
                    "agent_id": agent_id,
                    "draft_id": snapshot["draft_id"],
                    "revision": snapshot["draft_revision"],
                },
                context,
                tx,
            )
            await check_persisted_release(
                self.evaluations, scope, version.evaluation_id, current, uow=tx
            )
            await self._activate(scope, head, version_id, tx)
            await self._finish(scope, command_id, {"version_id": version_id}, tx)
            return version_id

    async def set_availability(
        self,
        scope: Scope,
        agent_id: str,
        expected_revision: int,
        *,
        archived: bool,
        enabled: bool,
    ) -> int:
        if type(archived) is not bool or type(enabled) is not bool:
            raise ValueError("BOOLEAN_AVAILABILITY_REQUIRED")
        async with self.uows() as tx:
            await self.identity.check_scope_active(scope, uow=tx)
            head = await self._lock_head(scope, agent_id, tx)
            if head["revision"] != expected_revision:
                raise ValueError("DEPLOYMENT_REVISION_CONFLICT")
            revision = expected_revision + 1
            await tx.execute(
                update(deployments)
                .where(
                    *scoped(deployments, scope, {"deployment_id": agent_id}),
                    deployments.c.revision == expected_revision,
                )
                .values(archived=archived, enabled=enabled, revision=revision)
            )
            await tx.commit()
            return revision

    async def retention_references(
        self, scope: Scope, version_id: str, usage: VersionUsageReader
    ) -> Tuple[str, ...]:
        await self.get_version(scope, version_id)
        return tuple(await usage.references(scope, version_id))
