"""CAS shared facts: source observations cannot overwrite user intent."""

from copy import deepcopy

from ._models import detached, require, scope_key


class SharedStateService:
    def __init__(self, repository, identity):
        self.repository, self.identity = repository, identity

    async def patch_facts(self, scope, conversation_id, expected_revision,
                          facts, *, source_kind, source_ref):
        require(source_kind in ("user", "tool"), "FACT_SOURCE_INVALID")
        require(bool(source_ref) and isinstance(facts, dict), "FACT_SOURCE_REQUIRED")
        require(set(facts) <= {
            "destination", "dates", "travelers", "origin", "budget", "reserve",
            "preferences", "candidates", "quote_refs", "constraints",
        }, "FACT_FIELD_INVALID")
        for key in ("budget", "reserve"):
            if key in facts:
                require(type(facts[key]) is int and facts[key] >= 0, "MONEY_INVALID")
        async with self.repository.transaction() as uow:
            await self.identity.check_scope_active(scope, uow)
            state = await self.repository.get("conversation", scope_key(scope), conversation_id, uow)
            require(state is not None, "RESOURCE_NOT_FOUND")
            require(state.state_revision == expected_revision, "REVISION_CONFLICT")
            changed = False
            for key, value in facts.items():
                previous = state.provenance.get(key, {})
                if source_kind == "tool" and previous.get("kind") == "user":
                    require(state.facts.get(key) == value, "USER_FACT_PROTECTED")
                    continue
                changed |= key not in state.facts or state.facts[key] != value
                state.facts[key] = deepcopy(value)
                state.provenance[key] = {"kind": source_kind, "ref": source_ref}
            require(state.facts.get("reserve", 0) <= state.facts.get("budget", 0), "RESERVE_EXCEEDS_BUDGET")
            if changed:
                for proposal in state.proposals.values():
                    proposal["status"] = "stale"
                state.selected_refs.clear()
            return detached(await self.repository.save("conversation", state, expected_revision, uow))

    async def select_proposal(self, scope, conversation_id, expected_revision,
                              proposal_id, *, now):
        async with self.repository.transaction() as uow:
            await self.identity.check_scope_active(scope, uow)
            state = await self.repository.get("conversation", scope_key(scope), conversation_id, uow)
            require(state is not None, "RESOURCE_NOT_FOUND")
            require(state.state_revision == expected_revision, "REVISION_CONFLICT")
            proposal = state.proposals.get(proposal_id)
            require(proposal is not None and proposal.get("status") == "current", "PROPOSAL_STALE")
            require(proposal.get("expires_at", 0) > now, "QUOTE_EXPIRED")
            state.selected_refs["proposal_id"] = proposal_id
            return detached(await self.repository.save("conversation", state, expected_revision, uow))
