"""Capability selection over the entire published library, independent of batch."""

from ._models import OrchestrationError, detached, read, require, scope_key, snapshot, stored_scope


class CapabilityRouter:
    def __init__(self, catalog, identity):
        self.catalog, self.identity = catalog, identity

    async def validate_version(self, scope, candidate):
        candidate = snapshot(candidate)
        require(stored_scope(read(candidate, "scope", ())) == scope_key(scope), "CANDIDATE_SCOPE_INVALID")
        require(read(candidate, "status") == "published", "AGENT_NOT_PUBLISHED")
        version = await self.catalog.get_version(scope, candidate["version_id"])
        deployment = await self.catalog.get_deployment(scope, candidate["deployment_id"])
        require(version is not None and deployment is not None, "AGENT_UNAVAILABLE")
        require(stored_scope(read(version, "scope", ())) == scope_key(scope), "CANDIDATE_SCOPE_INVALID")
        require(stored_scope(read(deployment, "scope", ())) == scope_key(scope), "CANDIDATE_SCOPE_INVALID")
        require(read(version, "agent_id") == candidate["agent_id"] == read(deployment, "agent_id"), "VERSION_BINDING_INVALID")
        require(read(deployment, "status") == "active" and
                read(deployment, "active_version_id") == candidate["version_id"], "AGENT_UNAVAILABLE")
        require(read(version, "manifest_hash") == candidate["manifest_hash"], "VERSION_BINDING_INVALID")
        manifest = read(version, "manifest")
        spec = read(manifest, "agent")
        require(spec is not None and set(candidate["capabilities"]) <= set(read(spec, "capabilities", [])), "CAPABILITY_INVALID")
        return snapshot(version)

    async def select(self, scope, requirements):
        await self.identity.check_scope_active(scope)
        require(bool(requirements) and all(isinstance(x, str) and x for x in requirements), "CAPABILITY_REQUIRED")
        needs = set(requirements)
        response = await self.catalog.list_candidates(scope, tuple(sorted(needs)))
        require(bool(read(response, "catalog_revision")), "CATALOG_REVISION_REQUIRED")
        candidates = []
        for candidate in read(response, "items", []):
            try:
                candidate = snapshot(candidate)
                candidate["scope"] = stored_scope(read(candidate, "scope", ()))
                if candidate["scope"] != scope_key(scope) or read(candidate, "status") != "published":
                    continue
                if not needs.intersection(read(candidate, "capabilities", [])):
                    continue
                version = await self.validate_version(scope, candidate)
            except OrchestrationError:
                continue
            candidates.append({**detached(candidate), "manifest": detached(read(version, "manifest"))})
        selected = []
        while needs:
            ranked = sorted(candidates, key=lambda c: (-len(needs.intersection(c["capabilities"])), c["agent_id"]))
            require(bool(ranked) and bool(needs.intersection(ranked[0]["capabilities"])), "CAPABILITY_MISSING")
            best = ranked[0]
            # Equal-ranked agents with overlapping coverage need an explicit decision.
            # Inspect the entire top rank so renaming IDs cannot hide that overlap.
            # Disjoint capabilities are complementary members, not alternatives.
            top = len(needs.intersection(best["capabilities"]))
            covered = set()
            for candidate in ranked:
                coverage = needs.intersection(candidate["capabilities"])
                if len(coverage) != top:
                    break
                require(not covered.intersection(coverage), "CAPABILITY_AMBIGUOUS")
                covered.update(coverage)
            best["selection_reason"] = sorted(needs.intersection(best["capabilities"]))
            selected.append(best)
            needs.difference_update(best["capabilities"])
            candidates = [c for c in candidates if c["agent_id"] != best["agent_id"]]
        return selected, read(response, "catalog_revision")
