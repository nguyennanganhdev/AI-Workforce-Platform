"""Scope-filtered reuse decisions rechecked before identity mutations."""

from typing import Any, Dict, Optional, Sequence

from ..contracts import (
    BusinessProfile,
    MatchType,
    ReuseAction,
    ReuseCandidate,
    ReuseCheck,
    ReuseDecision,
    ReuseStatus,
    Scope,
)
from ._deduplication import business_key, covers
from ._models import (
    AgentDefinition,
    LifecycleError,
    PublishedVersion,
    canonical_hash,
    new_id,
    now,
)


class ReuseMixin:
    async def find_candidates(
        self,
        scope: Scope,
        business_profile: BusinessProfile,
        include_drafts: bool = True,
    ) -> ReuseCheck:
        async with self.repository.transaction(scope) as tx:
            revision = await tx.catalog_revision()
            agents = [
                AgentDefinition.model_validate(x)
                for x in await tx.list("agents")
            ]
        candidates = []
        for agent in agents:
            same = business_key(agent.business_profile) == business_key(
                business_profile
            )
            overlap = set(agent.business_profile.capabilities).intersection(
                business_profile.capabilities
            )
            if not same and not overlap:
                continue
            if not include_drafts and not agent.active_version_id:
                continue
            status = ReuseStatus.DRAFT
            blockers = []
            profile = agent.business_profile
            if agent.status in ("disabled", "revoked"):
                status = ReuseStatus.BLOCKED
                blockers.append("AGENT_BLOCKED")
            elif agent.status == "archived":
                status = ReuseStatus.INACTIVE
                blockers.append("AGENT_ARCHIVED")
            elif agent.active_version_id:
                version = await self.get_version(
                    scope, agent.active_version_id
                )
                profile = version.manifest.business_profile
                validation = await self.version_compatibility(scope, version)
                status = (
                    ReuseStatus.READY
                    if validation.valid
                    else ReuseStatus.BLOCKED
                )
                blockers.extend(validation.blockers)
            match = (
                MatchType.SAME_BUSINESS
                if same and covers(profile, business_profile)
                else MatchType.PARTIAL_OVERLAP if same else MatchType.UNCERTAIN
            )
            covered = set(profile.capabilities).intersection(
                business_profile.capabilities
            )
            candidates.append(
                ReuseCandidate(
                    agent_id=agent.agent_id,
                    version_id=agent.active_version_id,
                    draft_id=agent.draft_id,
                    match_type=match,
                    reuse_status=status,
                    covered_requirements=tuple(sorted(covered)),
                    missing_requirements=tuple(
                        sorted(set(business_profile.capabilities) - covered)
                    ),
                    differences=(
                        ()
                        if covers(profile, business_profile)
                        else ("BUSINESS_OR_POLICY_DIFFERS",)
                    ),
                    blockers=tuple(blockers),
                    reason="Deterministic profile and availability comparison",
                )
            )
        action = ReuseAction.CREATE
        if candidates:
            first = sorted(
                candidates,
                key=lambda x: (
                    x.match_type != MatchType.SAME_BUSINESS,
                    x.agent_id,
                ),
            )[0]
            if first.match_type == MatchType.UNCERTAIN:
                action = ReuseAction.CLARIFY
            elif first.reuse_status in (
                ReuseStatus.BLOCKED,
                ReuseStatus.INACTIVE,
            ):
                action = ReuseAction.REPAIR
            elif first.reuse_status == ReuseStatus.DRAFT:
                action = ReuseAction.RESUME
            elif first.match_type == MatchType.SAME_BUSINESS:
                action = ReuseAction.REUSE
            else:
                action = ReuseAction.REVISE
        check = ReuseCheck(
            reuse_check_id=new_id(),
            requirement_hash=canonical_hash(business_profile),
            agent_catalog_revision=revision,
            candidates=tuple(candidates),
            recommended_action=action,
            created_at=now(),
        )
        async with self.repository.transaction(scope) as tx:
            await tx.insert(
                "reuse_checks",
                check.reuse_check_id,
                check.model_dump(mode="json"),
            )
        return check

    async def _decision(
        self, tx: Any, profile: BusinessProfile, decision: ReuseDecision
    ) -> Optional[AgentDefinition]:
        check = ReuseCheck.model_validate(
            await tx.get("reuse_checks", decision.reuse_check_id)
        )
        if check.requirement_hash != canonical_hash(profile):
            raise LifecycleError("REUSE_REQUIREMENT_MISMATCH")
        agents = [
            AgentDefinition.model_validate(x) for x in await tx.list("agents")
        ]
        same = [x for x in agents if x.business_key == business_key(profile)]
        if decision.action == ReuseAction.CREATE:
            if same:
                agent = same[0]
                raise LifecycleError(
                    (
                        "AGENT_BUILD_IN_PROGRESS"
                        if agent.draft_id
                        else "AGENT_ALREADY_EXISTS"
                    ),
                    details={
                        "agent_id": agent.agent_id,
                        "draft_id": agent.draft_id,
                    },
                )
        revision = await tx.catalog_revision()
        if (
            revision != decision.expected_catalog_revision
            or revision != check.agent_catalog_revision
        ):
            raise LifecycleError("REUSE_DECISION_STALE")
        if decision.action == ReuseAction.CREATE:
            if any(
                x.match_type == MatchType.UNCERTAIN for x in check.candidates
            ):
                raise LifecycleError("BUSINESS_CLARIFICATION_REQUIRED")
            return None
        if not decision.agent_id:
            raise LifecycleError("AGENT_REFERENCE_REQUIRED", 422)
        agent = AgentDefinition.model_validate(
            await tx.get("agents", decision.agent_id)
        )
        if agent.business_key != business_key(profile):
            raise LifecycleError("BUSINESS_IDENTITY_MISMATCH")
        if agent.status in ("revoked", "disabled", "archived"):
            raise LifecycleError("AGENT_UNAVAILABLE")
        if decision.action in (ReuseAction.REUSE, ReuseAction.REVISE):
            if (
                not decision.version_id
                or decision.version_id != agent.active_version_id
            ):
                raise LifecycleError("REUSE_DECISION_STALE")
            version = PublishedVersion.model_validate(
                await tx.get("versions", decision.version_id)
            )
            if version.agent_id != agent.agent_id:
                raise LifecycleError("VERSION_OWNER_MISMATCH")
            if decision.action == ReuseAction.REUSE:
                if not covers(version.manifest.business_profile, profile):
                    raise LifecycleError("REUSE_CAPABILITY_MISMATCH")
        elif decision.action == ReuseAction.RESUME:
            if decision.draft_id != agent.draft_id or not decision.draft_id:
                raise LifecycleError("REUSE_DECISION_STALE")
        else:
            raise LifecycleError("REUSE_ACTION_REQUIRES_USER", 422)
        return agent

    async def validate_decisions(
        self,
        scope: Scope,
        requirements: Sequence[BusinessProfile],
        reuse_decisions: Sequence[ReuseDecision],
        expected_catalog_revision: int,
    ) -> None:
        if not requirements or len(requirements) != len(reuse_decisions):
            raise LifecycleError("REUSE_DECISION_COUNT", 422)
        # Network/resource checks are outside the transaction.
        for decision in reuse_decisions:
            if decision.action == ReuseAction.REUSE and decision.version_id:
                version = await self.get_version(scope, decision.version_id)
                await self.require_version_compatible(scope, version)
        async with self.repository.transaction(scope) as tx:
            if await tx.catalog_revision() != expected_catalog_revision:
                raise LifecycleError("REUSE_DECISION_STALE")
            for requirement, decision in zip(requirements, reuse_decisions):
                if (
                    decision.expected_catalog_revision
                    != expected_catalog_revision
                ):
                    raise LifecycleError("REUSE_DECISION_STALE")
                await self._decision(tx, requirement, decision)

    async def get_candidate(
        self, scope: Scope, agent_id: str, version_id: Optional[str] = None
    ) -> Dict[str, Any]:
        agent = AgentDefinition.model_validate(
            await self.repository.get(scope, "agents", agent_id)
        )
        result: Dict[str, Any] = {"agent": agent.model_dump(mode="json")}
        if version_id:
            version = await self.get_version(scope, version_id)
            if version.agent_id != agent_id:
                raise LifecycleError("VERSION_OWNER_MISMATCH")
            result["version"] = version.model_dump(mode="json")
        return result
