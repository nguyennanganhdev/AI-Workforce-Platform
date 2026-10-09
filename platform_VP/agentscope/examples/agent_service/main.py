# -*- coding: utf-8 -*-
"""The example script to start the agent service."""

import os
import sys
from datetime import timedelta

import uvicorn
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware

from agentscope.app import BusinessService, SubAgentTemplate, create_app
from agentscope.app.auth import AuthService
from agentscope.app.channel import (
    DingTalkChannel,
    DiscordChannel,
    FeishuChannel,
)
from agentscope.app.hub import ClawSkillHub, GitHubMCPHub
from agentscope.app.message_bus import InMemoryMessageBus
from agentscope.app.rag.blob_store import S3BlobStore
from agentscope.app.rag.knowledge_base_manager import CollectionPerKbManager
from agentscope.app.storage import RedisStorage
from agentscope.app.workspace_manager import LocalWorkspaceManager
from agentscope.credential import OpenAICredential
from agentscope.embedding import OpenAIEmbeddingModel
from agentscope.mcp import HttpMCPConfig, MCPClient, StdioMCPConfig
from agentscope.permission import PermissionContext, PermissionMode
from agentscope.rag import ApproxTokenChunker, QdrantStore

default_mcps = [
    MCPClient(
        name="playwright",
        mcp_config=StdioMCPConfig(
            command="npx",
            args=["@playwright/mcp@latest"],
        ),
        is_stateful=True,
    ),
]

cors_allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

if os.getenv("AMAP_API_KEY"):
    default_mcps.append(
        MCPClient(
            name="amap",
            mcp_config=HttpMCPConfig(
                url=f"https://mcp.amap.com/mcp?key={os.environ['AMAP_API_KEY']}",
            ),
            is_stateful=False,
        ),
    )

storage = RedisStorage(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    db=int(os.getenv("REDIS_DB", "0")),
    password=os.getenv("REDIS_PASSWORD") or None,
)

s3_endpoint = os.getenv("S3_ENDPOINT")
s3_enabled = os.getenv("S3_ENABLED", "false").lower() in {
    "1",
    "true",
    "yes",
}
blob_store = (
    S3BlobStore(
        bucket=os.getenv("S3_BUCKET", "agentscope"),
        endpoint_url=s3_endpoint,
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        session_token=os.getenv("AWS_SESSION_TOKEN"),
        use_ssl=s3_endpoint is None or s3_endpoint.startswith("https://"),
    )
    if s3_enabled
    else None
)

vector_store = QdrantStore(location=":memory:")

auth_service = None
business_service = None
if os.getenv("AUTH_ENABLED", "false").lower() in {"1", "true", "yes"}:
    auth_service = AuthService(
        database_url=os.environ["AGENTSCOPE_SQL_URL"],
        jwt_secret=os.environ["AUTH_JWT_SECRET"],
        refresh_pepper=os.environ["AUTH_REFRESH_PEPPER"],
        issuer=os.getenv("AUTH_JWT_ISSUER", "agentscope"),
        audience=os.getenv("AUTH_JWT_AUDIENCE", "agentscope-api"),
        default_tenant_id=os.getenv("AUTH_DEFAULT_TENANT_ID", "default"),
        access_ttl=timedelta(
            minutes=int(os.getenv("AUTH_ACCESS_TTL_MINUTES", "15")),
        ),
        refresh_ttl=timedelta(
            days=int(os.getenv("AUTH_REFRESH_TTL_DAYS", "30")),
        ),
        cookie_secure=os.getenv("AUTH_COOKIE_SECURE", "true").lower()
        in {"1", "true", "yes"},
    )
    memory_embedding_model = None
    memory_embedding_key = os.getenv("MEMORY_EMBEDDING_API_KEY") or os.getenv(
        "OPENAI_API_KEY",
    )
    if memory_embedding_key:
        memory_embedding_model = OpenAIEmbeddingModel(
            credential=OpenAICredential(
                api_key=memory_embedding_key,
                base_url=os.getenv("MEMORY_EMBEDDING_BASE_URL") or None,
            ),
            model=os.getenv(
                "MEMORY_EMBEDDING_MODEL",
                "text-embedding-3-small",
            ),
            dimensions=int(os.getenv("MEMORY_EMBEDDING_DIMENSIONS", "1536")),
            pass_dimensions=os.getenv(
                "MEMORY_EMBEDDING_PASS_DIMENSIONS",
                "true",
            ).lower()
            in {"1", "true", "yes"},
        )
    business_service = BusinessService(
        database_url=os.environ["AGENTSCOPE_SQL_URL"],
        api_key_pepper=os.environ["PARTNER_API_KEY_PEPPER"],
        provisioning_secret=os.getenv("PARTNER_API_PROVISIONING_SECRET") or None,
        memory_embedding_model=memory_embedding_model,
        memory_embedding_dimensions=int(
            os.getenv("MEMORY_EMBEDDING_DIMENSIONS", "1536"),
        ),
    )

app = create_app(
    storage=storage,
    auth_service=auth_service,
    business_service=business_service,
    message_bus=InMemoryMessageBus(),
    # -- To use a Redis-backed message bus instead (recommended for
    # -- multi-process / production deployments), uncomment the lines
    # -- below and replace the InMemoryMessageBus() above:
    #
    # from agentscope.app.message_bus import RedisMessageBus
    # message_bus=RedisMessageBus(
    #     host="localhost",
    #     port=6379,
    # ),
    workspace_manager=LocalWorkspaceManager(
        basedir=os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "workspaces",
        ),
        # The default MCP servers that will be added into the workspace
        default_mcps=default_mcps,
    ),
    # Knowledge base feature — backed by an in-memory Qdrant store. The
    # CollectionPerKbManager allocates one collection per knowledge base,
    # so any embedding dimension is allowed.
    knowledge_base_manager=CollectionPerKbManager(
        storage=storage,
        vector_store=vector_store,
    ),
    blob_store=blob_store,
    # Chunker classes users can pick from when creating a knowledge base;
    # the chosen type and parameters are pinned on the knowledge base.
    knowledge_chunkers=[ApproxTokenChunker],
    # Resource hubs the UI browses under /hub. Neither needs credentials
    # of its own — an individual MCP card declares whatever key it wants
    # from the user in its ``inputs_schema``. Passing a ClawHub token
    # only raises the rate limit.
    mcp_hubs=[GitHubMCPHub()],
    skill_hubs=[ClawSkillHub(api_token=os.getenv("CLAWHUB_API_TOKEN"))],
    # Customize your own subagent templates
    custom_subagent_templates=[
        SubAgentTemplate(
            type="explorer",
            description=(
                "Read-only agents specialized in exploration tasks. It can "
                "read files but cannot modify, create, or delete them. Use "
                "this agent type when you need to investigate the codebase, "
                "understand its structure, or gather information from files "
                "to support planning—without making any changes."
            ),
            system_prompt_template="""You are {member_name}, an explorer \
agent in team '{team_name}' led by {leader_name}.

Team purpose: {team_description}

Your role: {member_description}

## Responsibilities
- Complete the exploration tasks assigned by the team leader.
- You are read-only: you may inspect files and the codebase, but you must \
never modify, create, or delete anything.

## Reporting
- Always report the task result back to {leader_name} using the TeamSay \
tool, whether the task succeeds or fails.
- Keep your private reasoning private; only share conclusions and findings \
that the leader needs.

Note: `TeamSay` is your ONLY channel to communicate with {leader_name} and \
the other team members. Any other output you produce is invisible to them, \
so anything you want them to see MUST be sent through `TeamSay`.""",
            permission_context=PermissionContext(
                # Read-only
                mode=PermissionMode.EXPLORE,
            ),
        ),
    ],
    # Automatic conversation-memory middleware is intentionally disabled.
    # Only AREA_MANAGER-approved candidates are embedded by BusinessService.
    extra_middlewares=[
        Middleware(
            CORSMiddleware,
            allow_origins=cors_allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        ),
    ],
    channels=[
        DingTalkChannel,
        DiscordChannel,
        FeishuChannel,
    ],
)


if __name__ == "__main__":
    # Start the service
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        # Hot reload forces a SelectorEventLoop on Windows, which cannot
        # spawn the subprocesses that the builtin tools rely on
        reload=sys.platform != "win32",
    )
