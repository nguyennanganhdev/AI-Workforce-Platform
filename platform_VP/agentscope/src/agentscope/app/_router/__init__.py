# -*- coding: utf-8 -*-
"""App routers."""
from ._agent import agent_router
from ._auth import auth_router
from ._business import business_router
from ._channel import channel_router
from ._chat import chat_router
from ._credential import credential_router
from ._embedding_model import embedding_model_router
from ._health import health_router
from ._hub import hub_router
from ._knowledge_base import knowledge_base_router
from ._mcp import mcp_router
from ._openapi import bridge_router, openapi_router
from ._mcp_oauth import oauth_callback_router, oauth_start_router
from ._agent_eval import agent_eval_router
from ._schedule import schedule_router
from ._session import session_router
from ._skill import skill_router
from ._sop import sop_router
from ._model import model_router
from ._tts_model import tts_model_router
from ._workspace import workspace_router
from ._workforce_console import workforce_console_router

__all__ = [
    "agent_router",
    "auth_router",
    "business_router",
    "channel_router",
    "model_router",
    "embedding_model_router",
    "tts_model_router",
    "chat_router",
    "credential_router",
    "health_router",
    "hub_router",
    "knowledge_base_router",
    "mcp_router",
    "bridge_router",
    "openapi_router",
    "oauth_callback_router",
    "oauth_start_router",
    "agent_eval_router",
    "schedule_router",
    "session_router",
    "skill_router",
    "sop_router",
    "workspace_router",
    "workforce_console_router",
]
