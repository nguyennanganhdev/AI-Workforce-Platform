from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Credentials(Strict):
    name: str = Field(min_length=1, max_length=100)
    secret: str = Field(min_length=1, max_length=8000)


class ModelSpec(Strict):
    name: str = Field(min_length=1, max_length=100)
    adapter: Literal["openai", "openai-responses", "anthropic", "dashscope", "gemini", "ollama"]
    model: str = Field(min_length=1, max_length=160)
    credential_id: str = ""
    base_url: str = ""
    capabilities: list[Literal["tools", "json", "vision", "audio"]] = ["tools", "json"]
    context_tokens: int = Field(default=32000, ge=2048, le=2000000)
    max_output_tokens: int = Field(default=2048, ge=128, le=32000)
    input_micros_per_million: int = Field(default=0, ge=0)
    output_micros_per_million: int = Field(default=0, ge=0)
    pricing_version: str = Field(min_length=1, max_length=100)
    rpm: int = Field(default=60, ge=1, le=100000)
    tpm: int = Field(default=120000, ge=2048, le=100000000)
    enabled: bool = True


class AgentSpec(Strict):
    name: str = Field(min_length=1, max_length=100)
    purpose: str = Field(min_length=10, max_length=4000)
    charter: str = Field(min_length=10, max_length=12000)
    specialties: list[str] = Field(default_factory=list, max_length=20)
    limits: str = Field(
        default="Không tự suy đoán dữ kiện thiếu; yêu cầu bằng chứng.", max_length=4000
    )
    model_id: str
    model_selection: Literal["manual", "lowest_cost"] = "manual"
    fallback_model_ids: list[str] = Field(default_factory=list, max_length=5)
    knowledge_ids: list[str] = Field(default_factory=list, max_length=30)
    tools: list[
        Literal["knowledge_search", "team_message", "board_read", "task_update", "memory_search"]
    ] = ["board_read", "knowledge_search", "team_message"]
    mcp_ids: list[str] = Field(default_factory=list, max_length=10)
    skill_ids: list[str] = Field(default_factory=list, max_length=10)
    memory_policy: Literal["off", "verified_private"] = "verified_private"
    max_iters: int = Field(default=4, ge=1, le=8)
    context_chars: int = Field(default=24000, ge=4000, le=48000)


class CreateAgent(Strict):
    spec: AgentSpec


class CreateSession(Strict):
    title: str = Field(min_length=1, max_length=200)
    agent_ids: list[str] = Field(min_length=1, max_length=3)
    budget_micros: int = Field(default=500000, ge=1, le=100000000)


class Chat(Strict):
    text: str = Field(min_length=1, max_length=24000)
    idempotency_key: str = Field(min_length=8, max_length=100)


class Claim(Strict):
    text: str = Field(max_length=4000)
    quote: str = Field(default="", max_length=2000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)


class AgentResult(Strict):
    status: Literal["complete", "needs_input", "needs_review", "blocked"]
    answer: str = Field(min_length=1, max_length=12000)
    claims: list[Claim] = Field(default_factory=list, max_length=30)
    unknowns: list[str] = Field(default_factory=list, max_length=20)
    next_action: str = Field(default="", max_length=2000)
    disagreement: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def uncertainty(self):
        if self.unknowns and self.status == "complete":
            self.status = "needs_review"
        return self


class KnowledgeSpec(Strict):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    visibility: Literal["private", "workspace"] = "private"
    embedding_model_id: str = ""


class DocumentSpec(Strict):
    title: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=1000000)
    source: str = Field(min_length=1, max_length=2000)
    expires: float | None = None


class MemorySpec(Strict):
    agent_id: str
    text: str = Field(min_length=1, max_length=4000)
    evidence_ids: list[str] = Field(min_length=1, max_length=20)
    session_id: str
    expires: float | None = None


class EmbeddingSpec(Strict):
    name: str = Field(min_length=1, max_length=100)
    adapter: Literal["openai", "ollama"]
    model: str = Field(min_length=1, max_length=160)
    credential_id: str = ""
    base_url: str = ""
    dimensions: int = Field(ge=1, le=10000)
    input_micros_per_million: int = Field(ge=0)
    pricing_version: str = Field(min_length=1, max_length=100)


class SkillSpec(Strict):
    name: str = Field(min_length=1, max_length=100)
    instructions: str = Field(min_length=10, max_length=12000)


class MCPConfig(Strict):
    name: str = Field(min_length=1, max_length=100)
    url: str
    credential_id: str = ""
    allowed_tools: list[str] = Field(min_length=1, max_length=30)
    read_only: bool = True
    enabled: bool = False


class WorkflowSpec(Strict):
    name: str = Field(min_length=1, max_length=100)
    agent_ids: list[str] = Field(min_length=1, max_length=3)
    steps: list[str] = Field(min_length=1, max_length=20)
    human_gate: bool = True


class ScheduleSpec(Strict):
    name: str = Field(min_length=1, max_length=100)
    workflow_id: str
    cron: str
    timezone: str = "Asia/Ho_Chi_Minh"
    enabled: bool = False


class ChannelSpec(Strict):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["webhook"] = "webhook"
    agent_ids: list[str] = Field(min_length=1, max_length=3)
    token: str = Field(min_length=32, max_length=256)
    enabled: bool = False


RESOURCE_SCHEMAS = {
    "models": ModelSpec,
    "knowledge": KnowledgeSpec,
    "embeddings": EmbeddingSpec,
    "skills": SkillSpec,
    "mcp": MCPConfig,
    "workflows": WorkflowSpec,
    "schedules": ScheduleSpec,
    "channels": ChannelSpec,
}
