"""Conservative reuse proposals using scope-first canonical ports."""

import json

from .async_capabilities._models import Blocker
from .async_capabilities._requirements import AgentRequirement
from ..contracts import (
    AgentReusePort,
    MatchType,
    ReuseAction,
    ReuseDecision,
    ReuseStatus,
    Scope,
)


def requirement_profile(req: AgentRequirement):
    """Include policy requirements explicitly in existing profile constraints."""
    profile = req.business_profile
    constraints = profile.required_constraints
    semantics = json.dumps(
        {
            "tracking_intent": req.tracking_intent,
            "policy": (
                req.policy_proposal.model_dump(mode="json")
                if req.policy_proposal
                else None
            ),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return profile.model_copy(
        update={"required_constraints": (*constraints, "builder.async:" + semantics)}
    )


def business_key(req: AgentRequirement) -> str:
    """Exact semantic profile equality only; never merge on display name."""
    return json.dumps(requirement_profile(req).model_dump(mode="json"), sort_keys=True)


class ReuseMatcher:
    def __init__(self, port: AgentReusePort):
        self.port = port

    async def propose(self, scope: Scope, req: AgentRequirement):
        profile = requirement_profile(req)
        check = await self.port.find_candidates(scope, profile, include_drafts=True)
        same = [c for c in check.candidates if c.match_type == MatchType.SAME_BUSINESS]
        blockers = []
        target = same[0] if len(same) == 1 else None
        if len(same) > 1:
            action = ReuseAction.CLARIFY
            blockers.append(
                Blocker(
                    code="AMBIGUOUS_REUSE",
                    message="Multiple identities claim the same business; resolve before continuing",
                )
            )
        elif target:
            required = {c.capability for c in req.capabilities if c.required}
            coverage_missing = required - set(target.covered_requirements)
            # Port must confirm policy constraints too; missing metadata never implies readiness.
            if req.tracking_intent == "track_to_completion":
                coverage_missing |= set(profile.required_constraints) - set(
                    target.covered_requirements
                )
            if target.blockers or target.reuse_status in (
                ReuseStatus.BLOCKED,
                ReuseStatus.INACTIVE,
            ):
                action = ReuseAction.REPAIR
                blockers.append(
                    Blocker(
                        code="REUSE_BLOCKED",
                        message="Existing identity must be repaired; creating a clone is not allowed",
                    )
                )
            elif target.reuse_status == ReuseStatus.DRAFT and target.draft_id:
                action = ReuseAction.RESUME
            elif target.missing_requirements or coverage_missing:
                action = ReuseAction.REVISE
            elif target.version_id:
                action = ReuseAction.REUSE
            else:
                action = ReuseAction.CLARIFY
                blockers.append(
                    Blocker(
                        code="CANDIDATE_METADATA_REQUIRED",
                        message="Published version or draft reference is missing",
                    )
                )
        elif any(
            c.match_type in (MatchType.UNCERTAIN, MatchType.PARTIAL_OVERLAP)
            for c in check.candidates
        ):
            action = ReuseAction.CLARIFY
            blockers.append(
                Blocker(
                    code="CLARIFICATION_REQUIRED",
                    message="Clarify business differences before creating another identity",
                )
            )
        else:
            action = ReuseAction.CREATE
        candidates = check.candidates
        if target is not None and action == ReuseAction.REVISE:
            missing = set(target.missing_requirements) | {
                "async_handling_policy" if value.startswith("builder.async:") else value
                for value in coverage_missing
            }
            target = target.model_copy(
                update={
                    "missing_requirements": tuple(sorted(missing)),
                    "reason": target.reason
                    + "; nâng cấp cùng identity để đáp ứng capability/policy còn thiếu",
                }
            )
            candidates = tuple(
                target if c.agent_id == target.agent_id else c for c in candidates
            )
        decision = ReuseDecision(
            agent_key=req.agent_key,
            action=action,
            reuse_check_id=check.reuse_check_id,
            agent_id=target.agent_id if target else None,
            version_id=target.version_id if target else None,
            draft_id=target.draft_id if target else None,
            expected_catalog_revision=check.agent_catalog_revision,
            reason=(
                target.reason
                if target
                else "No unambiguous equivalent identity; decision is scope-bound"
            ),
        )
        return decision, candidates, tuple(blockers)
