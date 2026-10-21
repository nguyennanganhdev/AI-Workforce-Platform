# -*- coding: utf-8 -*-
"""Records an agent accumulates outside its configuration."""
from typing import Literal

from pydantic import Field

from ._base import _RecordBase

AgentArtifactKind = Literal["eval_case", "eval_run", "memory"]


class AgentArtifactRecord(_RecordBase):
    """An eval case, an eval run or a memory belonging to one agent.

    ``data`` is validated by the service that owns the kind, so the storage
    stays one small table and one index per agent and kind.
    """

    user_id: str = Field(description="Owner user id.")
    agent_id: str = Field(description="The agent the record belongs to.")
    kind: AgentArtifactKind = Field(description="What the record is.")
    data: dict = Field(default_factory=dict, description="Kind-specific payload.")
