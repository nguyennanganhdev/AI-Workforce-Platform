# -*- coding: utf-8 -*-
"""The example script to start the agent service."""

import os
import sys
from datetime import timedelta

import uvicorn
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware

from agentscope.app import BusinessService, create_app
from agentscope.app.auth import AuthService
from agentscope.app.channel import (
    DingTalkChannel,
    DiscordChannel,
    FeishuChannel,
)
from agentscope.app.hub import ClawSkillHub, GitHubMCPHub
from agentscope.app.message_bus import RedisMessageBus
from agentscope.app.rag.blob_store import S3BlobStore
from agentscope.app.rag.knowledge_base_manager import CollectionPerKbManager
from agentscope.app.storage import AsyncSQLAlchemyStorage, RedisStorage
from agentscope.app.workforce.integrations.async_runtime import WorkforceBootstrap
from agentscope.app.workforce.integrations.unified import (
    ChatLeaderTurnRunner,
    build_unified_runtime,
    resolve_signing_secret,
    unified_mode_enabled,
)
from agentscope.app.workspace_manager import LocalWorkspaceManager
from agentscope.credential import OpenAICredential
from agentscope.embedding import OpenAIEmbeddingModel
from agentscope.mcp import HttpMCPConfig, MCPClient, StdioMCPConfig
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

shared_context_backend = os.getenv(
    "SHARED_CONTEXT_STORAGE_BACKEND",
    "sql" if os.getenv("AGENTSCOPE_SQL_URL") else "primary",
).strip().lower()
if shared_context_backend == "sql":
    shared_context_sql_url = os.getenv("AGENTSCOPE_SQL_URL")
    if not shared_context_sql_url:
        raise RuntimeError(
            "SHARED_CONTEXT_STORAGE_BACKEND=sql requires AGENTSCOPE_SQL_URL",
        )
    # Alembic is the schema owner. Keeping create_tables disabled prevents a
    # web replica from racing another replica during startup.
    shared_context_storage = AsyncSQLAlchemyStorage(
        shared_context_sql_url,
        create_tables=False,
        auto_migrate=False,
    )
elif shared_context_backend == "primary":
    shared_context_storage = storage
else:
    raise RuntimeError(
        "SHARED_CONTEXT_STORAGE_BACKEND must be 'sql' or 'primary'",
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
        public_endpoint_url=os.getenv("S3_PUBLIC_ENDPOINT") or None,
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
        # New BQL accounts wait for an administrator; one per area.
        require_approval=os.getenv("AUTH_REGISTRATION_APPROVAL", "true").lower()
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

# Inbox, wake-up, context-mode directives and their distributed locks
# must survive process boundaries; the same Redis deployment may back
# StorageBase while these keys remain transport-only and namespaced.
message_bus = RedisMessageBus(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", "6379")),
    db=int(os.getenv("REDIS_DB", "0")),
    password=os.getenv("REDIS_PASSWORD") or None,
)

# Partner API (/workforce/v1) in unified mode: partner tickets are answered by
# the same Leader and Agent Studio agents as the web console. Needs the SQL
# database and partner API keys (AUTH_ENABLED=true).
workforce_bootstrap = None
partner_runner: dict = {}
if unified_mode_enabled():
    if business_service is None or not os.getenv("AGENTSCOPE_SQL_URL"):
        raise RuntimeError(
            "WORKFORCE_PARTNER_API=true requires AUTH_ENABLED=true and AGENTSCOPE_SQL_URL",
        )

    def _unified_runtime(foundation):
        runner = ChatLeaderTurnRunner(foundation.uows)
        partner_runner["runner"] = runner
        # Partner photos live in the same S3/MinIO store as knowledge documents.
        return build_unified_runtime(foundation, runner, asset_store=blob_store)

    workforce_bootstrap = WorkforceBootstrap(
        database_url=os.environ["AGENTSCOPE_SQL_URL"],
        message_bus=message_bus,
        runtime_factory=_unified_runtime,
        # Provider events (contract section 10): API key + HMAC signing key.
        authenticate_provider_api_key=business_service.authenticate_partner_api_key,
        resolve_provider_signing_secret=resolve_signing_secret,
    )


async def _partner_case_middlewares(user_id, agent_id, session_id):
    """Case tools for sessions of partner workflows; nothing elsewhere."""
    runner = partner_runner.get("runner")
    if runner is None:
        return []
    return await runner.case_middlewares(user_id, agent_id, session_id)


app = create_app(
    storage=storage,
    shared_context_storage=shared_context_storage,
    auth_service=auth_service,
    business_service=business_service,
    message_bus=message_bus,
    workforce_bootstrap=workforce_bootstrap,
    extra_agent_middlewares=_partner_case_middlewares,
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

if "runner" in partner_runner:
    partner_runner["runner"].bind(app)


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
