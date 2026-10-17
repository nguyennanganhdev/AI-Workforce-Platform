"""Test-only adapters. Never installed by the production composition root."""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

from agentscope.app.workforce.builder.async_capabilities._models import (
    ProtocolReadiness,
)
from agentscope.app.workforce.contracts import (
    ReuseCheck,
    ReuseCandidate,
    ToolDescriptor,
    WorkforceContractError,
    WorkforceErrorCode,
)
from tests.workforce.builder.async_capabilities.test_phase_a import FakeRegistry


class Registry(FakeRegistry):
    def __init__(self, scope, tools, *, page_size=1):
        super().__init__(scope, tools)
        self.page_size = page_size
        self.queries = []

    async def get_tool_snapshot(self, scope, tool_version_id):
        if scope != self.scope:
            raise PermissionError("scope mismatch")
        for descriptor in self.tools:
            if descriptor.tool_version_id == tool_version_id:
                return descriptor
        raise LookupError(tool_version_id)

    async def list_available_tools(
        self, scope, query=None, capabilities=(), cursor=None
    ):
        self.queries.append((scope, tuple(capabilities), cursor))
        if scope != self.scope:
            raise PermissionError("scope mismatch")
        tools = [t for t in self.tools if set(capabilities) <= set(t.capabilities)]
        start = int(cursor or 0)
        end = start + self.page_size
        return tuple(tools[start:end]), str(end) if end < len(tools) else None

    async def check_bindings(self, scope, bindings):
        for binding in bindings:
            tool = await self.get_tool_snapshot(scope, binding.tool_version_id)
            if not tool.available or binding.schema_hash != tool.schema_hash:
                raise WorkforceContractError(
                    WorkforceErrorCode.REUSE_DECISION_STALE, "drift"
                )


class Details:
    """View built from Registry-owned public configuration, exact-pinned by hash."""

    def __init__(self, scope, configs):
        self.scope = scope
        self.configs = {p.snapshot_ref.schema_hash: p for p in configs}

    async def read(self, scope, snapshot):
        if scope != self.scope:
            raise PermissionError("scope mismatch")
        protocol = self.configs[snapshot.schema_hash]
        return ProtocolReadiness(
            snapshot=protocol.snapshot_ref,
            correlation_supported=bool(
                protocol.client_reference_field or protocol.external_job_id_field
            ),
            event_types=tuple(protocol.event_mappings),
            fact_fields=tuple(
                {f for m in protocol.event_mappings.values() for f in m.fact_fields}
            ),
            event_fact_fields={
                name: mapping.fact_fields
                for name, mapping in protocol.event_mappings.items()
            },
            completion_policy=protocol.completion_policy,
            timeout_seconds=protocol.timeout_seconds,
            status_query_tool_version_id=protocol.status_query_tool_version_id,
        )


class Model:
    def __init__(self, outputs, delay=0):
        self.outputs = list(outputs)
        self.calls = []
        self.delay = delay

    async def generate_structured_output(self, messages, structured_model, **kwargs):
        self.calls.append((messages, structured_model))
        await asyncio.sleep(self.delay)
        result = self.outputs.pop(0)
        if isinstance(result, Exception):
            raise result
        return SimpleNamespace(content=result)


class Reuse:
    def __init__(
        self,
        scope,
        *,
        match=None,
        status="ready",
        missing=(),
        blockers=(),
        fully_covered=True
    ):
        self.scope, self.match, self.status = scope, match, status
        self.missing, self.blockers, self.fully_covered = (
            missing,
            blockers,
            fully_covered,
        )
        self.revision = 1
        self.calls = []

    async def find_candidates(self, scope, business_profile, include_drafts=True):
        if scope != self.scope:
            raise PermissionError("scope mismatch")
        self.calls.append(business_profile)
        candidates = ()
        if self.match:
            covered = (
                (*business_profile.capabilities, *business_profile.required_constraints)
                if self.fully_covered
                else business_profile.capabilities
            )
            candidates = (
                ReuseCandidate(
                    agent_id="existing",
                    version_id="published" if self.status == "ready" else None,
                    draft_id="draft" if self.status == "draft" else None,
                    match_type=self.match,
                    reuse_status=self.status,
                    covered_requirements=covered,
                    missing_requirements=self.missing,
                    blockers=self.blockers,
                    reason="Compared objective, responsibilities, I/O, scope, constraints and policy",
                ),
            )
        return ReuseCheck(
            reuse_check_id="check",
            requirement_hash="fixture",
            agent_catalog_revision=self.revision,
            candidates=candidates,
            recommended_action="create",
            created_at=datetime.now(UTC),
        )

    async def get_candidate(self, scope, agent_id, version_id=None):
        raise NotImplementedError

    async def validate_decisions(
        self, scope, requirements, reuse_decisions, expected_catalog_revision
    ):
        if scope != self.scope:
            raise PermissionError("scope mismatch")
        if expected_catalog_revision != self.revision:
            raise WorkforceContractError(
                WorkforceErrorCode.REUSE_DECISION_STALE, "catalog changed"
            )


def tool(capability="lookup", effect="read", version="tool-v1", available=True):
    return ToolDescriptor(
        tool_id=version,
        tool_version_id=version,
        source_kind="mcp",
        provider_tool_name="fixture",
        llm_alias="fixture",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        schema_hash="tool-hash",
        capabilities=(capability,),
        effect=effect,
        available=available,
    )
