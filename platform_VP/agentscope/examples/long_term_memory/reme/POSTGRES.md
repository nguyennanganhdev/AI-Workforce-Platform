# PostgreSQL/pgvector memory persistence

`PostgresReMeMemoryStore` stores only business facts approved by an
`AREA_MANAGER`; it does not embed chat messages or customer preferences.
The Agent Service example disables automatic file-backed conversation memory.
Use the `/memories/candidates` review APIs described in
`../../../docs/area_platform_api_vi.md` for the normal application flow.

## Provisioning

Run the packaged Alembic migrations against PostgreSQL:

```powershell
$env:AGENTSCOPE_SQL_URL = "postgresql+asyncpg://agentscope:password@localhost:5432/agentscope"
alembic -c src/agentscope/app/storage/_sql/_alembic/alembic.ini upgrade head
```

Migration `0005_reme_memories` enables pgvector and creates the base table.
Migration `0008_area_platform` adds domain/area review metadata and a database
constraint that prevents an unreviewed row from becoming active. The embedding
dimension is fixed at 1536.

## Query service

```python
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import create_async_engine

from agentscope.middleware import PostgresReMeMemoryStore, ReMeMemory

engine = create_async_engine(database_url)
store = PostgresReMeMemoryStore(engine)

memory_id, created = await store.add_or_merge(
    ReMeMemory(
        tenant_id="tenant-1",
        user_id="manager-1",
        domain_id="vinhomes",
        area_id="ocean-park-1",
        approved_by="manager-1",
        approved_at=datetime.now(timezone.utc),
        source_candidate_id="candidate-id",
        agent_id="assistant-1",
        source_session_id="session-1",
        content="The project must use PostgreSQL 17.",
        embedding=embedding,  # exactly 1536 floats
        memory_type="decision",
        importance=0.9,
    ),
)

results = await store.search(
    tenant_id="tenant-1",
    domain_id="vinhomes",
    area_id="ocean-park-1",
    agent_id="assistant-1",
    query_embedding=query_embedding,
    limit=5,
    min_similarity=0.65,
)

await store.mark_accessed(
    tenant_id="tenant-1",
    domain_id="vinhomes",
    area_id="ocean-park-1",
    memory_ids=[item.id for item in results],
)
```

All queries require `tenant_id`, `domain_id`, and `area_id`. Agent-specific
searches also include reviewed area memories whose `agent_id` is null.

