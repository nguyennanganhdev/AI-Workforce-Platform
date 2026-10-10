"""Builder-owned Phase-A schemas; not shared production contracts."""

from typing import Literal

from pydantic import Field, model_validator

from ...contracts import BusinessProfile, ToolEffect, WorkforceModel


class CapabilityRequirement(WorkforceModel):
    """Business capability requested before selecting a concrete tool."""

    capability: str = Field(min_length=1, max_length=200)
    required: bool = True
    reason: str = Field(min_length=1, max_length=2000)


class HandlingPolicyProposal(WorkforceModel):
    """Proposed portable policy awaiting shared-contract integration."""

    schema_version: Literal["1"] = "1"
    capabilities: tuple[str, ...] = Field(min_length=1)
    event_types: tuple[str, ...] = ()
    required_facts: tuple[str, ...] = ()
    completion_condition: str = Field(min_length=1, max_length=2000)
    human_confirmation: bool
    timeout_seconds: int = Field(gt=0)
    timeout_behavior: Literal["request_attention", "query_status"]


class AgentRequirement(WorkforceModel):
    """Structured extraction output, without owner or runtime identifiers."""

    agent_key: str = Field(min_length=1, max_length=200)
    business_profile: BusinessProfile
    capabilities: tuple[CapabilityRequirement, ...] = Field(min_length=1)
    effect: ToolEffect
    tracking_intent: Literal["create_only", "track_to_completion", "unspecified"]
    clarification_questions: tuple[str, ...] = ()
    policy_proposal: HandlingPolicyProposal | None = None

    @model_validator(mode="after")
    def validate_requirements(self) -> "AgentRequirement":
        names = [item.capability for item in self.capabilities]
        if len(set(names)) != len(names) or any(not name.strip() for name in names):
            raise ValueError("capability names must be nonblank and unique")
        if not set(names).issubset(self.business_profile.capabilities):
            raise ValueError("capabilities must belong to the business profile")
        if self.tracking_intent == "unspecified" and not self.clarification_questions:
            raise ValueError("unspecified tracking requires clarification")
        if self.tracking_intent == "track_to_completion":
            if self.effect != ToolEffect.EXTERNAL_OPERATION:
                raise ValueError("tracking requires an external-operation capability")
            if self.policy_proposal is None and not self.clarification_questions:
                raise ValueError("tracking requires a policy or clarification")
        elif self.policy_proposal is not None:
            raise ValueError("only tracking requirements carry an async policy")
        if self.policy_proposal is not None:
            if not set(self.policy_proposal.capabilities).issubset(names):
                raise ValueError("policy capabilities must belong to requirements")
        return self


class BuildRequirements(WorkforceModel):
    """One build request proposes independent agents, never a runtime group."""

    schema_version: Literal["1"] = "1"
    mode: Literal["single", "batch"]
    agents: tuple[AgentRequirement, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_agents(self) -> "BuildRequirements":
        if self.mode == "single" and len(self.agents) != 1:
            raise ValueError("single mode requires exactly one agent")
        keys = [item.agent_key for item in self.agents]
        if len(set(keys)) != len(keys):
            raise ValueError("agent keys must be unique")
        return self
