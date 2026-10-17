"""Independent Phase-B proposal orchestration; durable build/draft wiring follows."""

import asyncio
import hashlib
import json
from uuid import uuid4

from ..contracts import (
    AgentReusePort,
    Scope,
    WorkforceContractError,
    WorkforceErrorCode,
)
from ._requirements import RequirementExtractor
from ._reuse_matcher import ReuseMatcher, business_key, requirement_profile
from .async_capabilities import BuildRequirements
from .async_capabilities._models import AgentProposal, Blocker, BuildProposal
from .async_capabilities._selector import CapabilitySelector


class ProposalService:
    """Process-local preview sessions; never a replacement for durable BHN-01 storage.

    Scope must be resolved by the composition root. The service owns confirmation
    state, so callers cannot submit fabricated selections or decisions. No draft,
    version, runtime group, provider job or side effect is created here.
    """

    def __init__(
        self,
        extractor: RequirementExtractor,
        selector: CapabilitySelector,
        reuse: AgentReusePort,
        *,
        max_sessions: int = 100,
    ):
        if max_sessions < 1:
            raise ValueError("invalid session budget")
        self.extractor, self.selector = extractor, selector
        self.reuse, self.matcher = reuse, ReuseMatcher(reuse)
        self.max_sessions = max_sessions
        self._entries = {}
        self._messages = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _owner(scope: Scope):
        return scope.model_dump_json()

    async def prepare(
        self,
        scope: Scope,
        message: str,
        client_message_id: str,
        *,
        proposal_id: str | None = None,
        expected_revision: int | None = None,
    ):
        if not client_message_id.strip() or len(client_message_id) > 200:
            raise ValueError("invalid client message ID")
        owner = self._owner(scope)
        key = (owner, client_message_id)
        payload = hashlib.sha256(
            f"{proposal_id}:{expected_revision}:{message}".encode()
        ).hexdigest()
        async with self._lock:
            previous = None
            if key in self._messages:
                previous_hash, previous = self._messages[key]
                if payload != previous_hash:
                    raise WorkforceContractError(
                        WorkforceErrorCode.IDEMPOTENCY_CONFLICT,
                        "Message ID reused with different input",
                    )
                return self._owned(scope, previous.proposal_id)[1].model_copy(deep=True)
            if len(self._messages) >= self.max_sessions * 20:
                raise ValueError("Proposal message budget exhausted")
            if proposal_id is not None:
                previous = self._owned(scope, proposal_id)[1]
                if expected_revision != previous.revision or previous.status in (
                    "confirmed",
                    "completed_reused",
                ):
                    raise WorkforceContractError(
                        WorkforceErrorCode.REVISION_CONFLICT,
                        "Proposal changed or is already confirmed",
                    )
                revision = previous.revision + 1
            else:
                if len(self._entries) >= self.max_sessions:
                    raise ValueError("Proposal session budget exhausted")
                proposal_id, revision = str(uuid4()), 1
            context = (
                BuildRequirements(
                    mode="batch", agents=tuple(i.requirement for i in previous.items)
                )
                if previous is not None and previous.items
                else None
            )
            extraction = await self.extractor.extract(message, context)
            if extraction.intent != "build":
                questions = extraction.questions or (
                    "Đây là yêu cầu thực hiện nghiệp vụ. Bạn có muốn tạo agent hỗ trợ nghiệp vụ này không?",
                )
                proposal = BuildProposal(
                    proposal_id=proposal_id,
                    revision=revision,
                    items=(),
                    status="needs_input",
                    questions=questions,
                )
            else:
                proposal = await self._build(
                    scope,
                    extraction.requirements,
                    proposal_id,
                    revision,
                    questions=extraction.questions,
                )
            self._entries[proposal_id] = (owner, proposal)
            self._messages[key] = (payload, proposal)
            return proposal.model_copy(deep=True)

    def _owned(self, scope: Scope, proposal_id: str):
        entry = self._entries.get(proposal_id)
        if entry is None or entry[0] != self._owner(scope):
            raise PermissionError("Proposal is unavailable in this scope")
        return entry

    async def _build(
        self,
        scope: Scope,
        requirements: BuildRequirements,
        proposal_id: str,
        revision: int,
        *,
        questions: tuple[str, ...] = (),
    ):
        items, index, identities = [], {}, {}
        for req in requirements.agents:
            key = business_key(req)
            if key in index:
                position = index[key]
                item = items[position]
                # Only identical requirement coverage can be collapsed safely.
                if (
                    item.requirement.capabilities == req.capabilities
                    and item.requirement.effect == req.effect
                    and item.requirement.clarification_questions
                    == req.clarification_questions
                ):
                    items[position] = item.model_copy(
                        update={"duplicate_keys": (*item.duplicate_keys, req.agent_key)}
                    )
                    continue
                items[position] = item.model_copy(
                    update={
                        "blockers": (
                            *item.blockers,
                            Blocker(
                                code="BATCH_REQUIREMENT_CONFLICT",
                                message="Same business has different requirements; consolidate before generating",
                            ),
                        )
                    }
                )
            index[key] = len(items)
            selection = await self.selector.select(scope, req)
            decision, candidates, blockers = await self.matcher.propose(scope, req)
            identity = json.dumps(
                {
                    name: req.business_profile.model_dump(mode="json")[name]
                    for name in (
                        "objective",
                        "responsibilities",
                        "input_contract",
                        "output_contract",
                        "business_scope",
                    )
                },
                sort_keys=True,
            )
            if identity in identities:
                duplicate_blocker = Blocker(
                    code="BATCH_REQUIREMENT_CONFLICT",
                    message="Potential duplicate business has differing policy/capabilities; consolidate or clarify before generating",
                )
                position = identities[identity]
                original = items[position]
                items[position] = original.model_copy(
                    update={"blockers": (*original.blockers, duplicate_blocker)}
                )
                blockers = (*blockers, duplicate_blocker)
            else:
                identities[identity] = len(items)
            items.append(
                AgentProposal(
                    requirement=req,
                    selection=selection,
                    reuse_decision=decision,
                    candidates=candidates,
                    blockers=blockers,
                )
            )
        blocked = any(i.blockers or i.selection.blockers for i in items)
        questions = questions + tuple(
            q for i in items for q in i.requirement.clarification_questions
        )
        return BuildProposal(
            proposal_id=proposal_id,
            revision=revision,
            items=tuple(items),
            status="needs_input" if blocked or questions else "ready",
            questions=questions,
        )

    async def confirm(self, scope: Scope, proposal_id: str, expected_revision: int):
        async with self._lock:
            previous = self._owned(scope, proposal_id)[1]
            if expected_revision != previous.revision:
                raise WorkforceContractError(
                    WorkforceErrorCode.REVISION_CONFLICT, "Refresh the current proposal"
                )
            if previous.status in ("confirmed", "completed_reused"):
                return previous.model_copy(deep=True)
            if not previous.can_confirm:
                raise ValueError("Resolve blockers and clarification before confirming")
            try:
                for item in previous.items:
                    await self.selector.recheck(scope, item.requirement, item.selection)
                    await self.reuse.validate_decisions(
                        scope,
                        (requirement_profile(item.requirement),),
                        (item.reuse_decision,),
                        item.reuse_decision.expected_catalog_revision,
                    )
            except WorkforceContractError as exc:
                if exc.code not in (
                    WorkforceErrorCode.REUSE_DECISION_STALE,
                    WorkforceErrorCode.AGENT_ALREADY_EXISTS,
                    WorkforceErrorCode.AGENT_BUILD_IN_PROGRESS,
                    WorkforceErrorCode.MISSING_REQUIRED_CAPABILITY,
                ):
                    raise
                requirements = BuildRequirements(
                    mode="batch", agents=tuple(i.requirement for i in previous.items)
                )
                refreshed = await self._build(
                    scope, requirements, proposal_id, previous.revision + 1
                )
                refreshed = refreshed.model_copy(
                    update={
                        "notices": (
                            "Catalog hoặc khả năng theo dõi đã thay đổi. Kiểm tra và xác nhận lại đề xuất mới.",
                        )
                    }
                )
                self._entries[proposal_id] = (self._owner(scope), refreshed)
                return refreshed.model_copy(deep=True)
            reused = all(i.reuse_decision.action == "reuse" for i in previous.items)
            confirmed = previous.model_copy(
                update={"status": "completed_reused" if reused else "confirmed"}
            )
            self._entries[proposal_id] = (self._owner(scope), confirmed)
            return confirmed.model_copy(deep=True)

    async def cancel(self, scope: Scope, proposal_id: str):
        async with self._lock:
            self._owned(scope, proposal_id)
            del self._entries[proposal_id]
            self._messages = {
                k: v
                for k, v in self._messages.items()
                if v[1].proposal_id != proposal_id
            }
