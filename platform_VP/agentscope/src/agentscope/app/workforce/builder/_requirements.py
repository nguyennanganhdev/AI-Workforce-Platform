"""Bounded structured extraction using AgentScope's existing model API."""

import asyncio
import json
from typing import Literal, Protocol

from pydantic import ValidationError, model_validator

from ..contracts import WorkforceModel
from .async_capabilities import BuildRequirements


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
        max_input_chars: int = 16000
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
