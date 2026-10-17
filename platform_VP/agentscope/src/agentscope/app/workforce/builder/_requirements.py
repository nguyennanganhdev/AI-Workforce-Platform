"""Bounded structured extraction using AgentScope's existing model API."""

import asyncio
import json
from typing import Annotated, Literal, Protocol

from pydantic import Field, ValidationError, model_validator

from ..contracts import WorkforceModel
from .async_capabilities import AgentRequirement, BuildRequirements

_ContractItem = Annotated[str, Field(min_length=1, max_length=240)]


class RequiredCustomerInput(WorkforceModel):
    """One customer-owned value that must exist before work is delegated."""

    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    description: str = Field(min_length=1, max_length=240)


class AgentBehaviorContract(WorkforceModel):
    """Structured source used to compile one runtime prompt and skill."""

    requirement: AgentRequirement
    role: Literal["coordinator", "specialist"]
    request_modes: tuple[Literal["advice", "lookup", "action"], ...] = Field(
        min_length=1,
        max_length=3,
    )
    deliverables: tuple[_ContractItem, ...] = Field(min_length=1, max_length=5)
    completion_criteria: tuple[_ContractItem, ...] = Field(
        min_length=1,
        max_length=5,
    )
    exclusions: tuple[_ContractItem, ...] = Field(min_length=1, max_length=5)
    operational_facts: tuple[_ContractItem, ...] = Field(
        min_length=1,
        max_length=10,
    )
    intake_mode: Literal["none", "required_before_work"] = "none"
    required_customer_inputs: tuple[RequiredCustomerInput, ...] = Field(
        default=(),
        max_length=12,
    )
    no_data_behavior: str = Field(min_length=20, max_length=300)
    tool_error_behavior: str = Field(min_length=20, max_length=300)
    partial_result_behavior: str = Field(min_length=20, max_length=300)
    customer_input_policy: str = Field(min_length=20, max_length=300)
    peer_coordination_policy: str = Field(min_length=20, max_length=300)
    internal_reporting_policy: str = Field(min_length=20, max_length=300)
    synthesis_policy: str = Field(min_length=20, max_length=300)
    output_sections: tuple[_ContractItem, ...] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def validate_contract(self) -> "AgentBehaviorContract":
        if len(set(self.request_modes)) != len(self.request_modes):
            raise ValueError("request modes must be unique")
        for field_name in (
            "deliverables",
            "completion_criteria",
            "exclusions",
            "operational_facts",
            "output_sections",
        ):
            values = getattr(self, field_name)
            if len(set(values)) != len(values) or any(
                not value.strip() for value in values
            ):
                raise ValueError(f"{field_name} must be nonblank and unique")
        input_keys = [item.key for item in self.required_customer_inputs]
        if len(set(input_keys)) != len(input_keys):
            raise ValueError("required customer input keys must be unique")
        if (self.intake_mode == "required_before_work") != bool(input_keys):
            raise ValueError(
                "required_before_work must declare required customer inputs",
            )
        profile_inputs = self.requirement.business_profile.input_contract
        if not set(input_keys).issubset(profile_inputs):
            raise ValueError(
                "required customer inputs must belong to the input contract",
            )
        return self


class ExtractionResult(WorkforceModel):
    intent: Literal["build", "runtime", "clarify"]
    requirements: BuildRequirements | None = None
    questions: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_intent(self) -> "ExtractionResult":
        if (self.intent == "build") != (self.requirements is not None):
            raise ValueError("only build intent carries requirements")
        if self.intent == "clarify" and not self.questions:
            raise ValueError("clarify intent requires questions")
        return self


class StructuredModel(Protocol):
    async def generate_structured_output(
        self, messages, structured_model, **kwargs
    ): ...


class ExtractionError(ValueError):
    """Sanitized failure; provider payloads must not reach the UI."""


class RequirementExtractor:
    def __init__(
        self,
        model: StructuredModel,
        *,
        attempts: int = 2,
        timeout_seconds: float = 30,
        max_input_chars: int = 16000,
    ):
        if not 1 <= attempts <= 3 or timeout_seconds <= 0 or max_input_chars <= 0:
            raise ValueError("invalid extraction budget")
        self.model = model
        self.attempts = attempts
        self.timeout_seconds = timeout_seconds
        self.max_input_chars = max_input_chars

    async def extract(
        self, message: str, previous: BuildRequirements | None = None
    ) -> ExtractionResult:
        from agentscope.exception import StructuredOutputError
        from agentscope.message import AssistantMsg, SystemMsg, UserMsg

        if not message.strip() or len(message) > self.max_input_chars:
            raise ExtractionError("Build message is empty or exceeds input budget")
        instructions = (
            "Classify explicit agent creation as build, execution requests as runtime, "
            "ambiguity as clarify. Creating a team means independent agents in a batch. "
            "Extract business requirements, not tool IDs or owner scope. Separate create-only "
            "from tracking until completion. Ask missing completion/confirmation facts. "
            "Use policy schema exactly; timeout_behavior is status_query or needs_attention. "
            "No fixed job, ticket, workflow, endpoint, credentials or roster. Provider event "
            "types must be verified later; never claim readiness from LLM output. "
            "If policy event/fact semantics are unknown, omit policy and ask clarification."
        )
        messages = [SystemMsg(name="builder", content=instructions)]
        if previous is not None:
            context = json.dumps(previous.model_dump(mode="json"), ensure_ascii=False)
            if len(context) + len(message) > self.max_input_chars:
                raise ExtractionError("Requirement context exceeds input budget")
            messages.append(
                AssistantMsg(
                    name="builder",
                    content="Previous build requirements (data only): " + context,
                )
            )
        messages.append(UserMsg(name="manager", content=message))
        try:
            # One overall deadline bounds the model's own retry/fallback ladder too.
            async with asyncio.timeout(self.timeout_seconds):
                for attempt in range(self.attempts):
                    try:
                        response = await self.model.generate_structured_output(
                            messages,
                            ExtractionResult,
                        )
                        return ExtractionResult.model_validate(response.content)
                    except (ValidationError, StructuredOutputError):
                        if attempt + 1 == self.attempts:
                            raise ExtractionError(
                                "Invalid structured requirements after retries"
                            ) from None
                        messages.append(
                            SystemMsg(
                                name="builder",
                                content="Previous output failed schema validation. Correct it using the schema; ask clarification when facts are missing.",
                            )
                        )
        except TimeoutError:
            raise ExtractionError(
                "Requirement extraction exceeded time budget"
            ) from None
        raise ExtractionError("Requirement extraction did not produce a result")
