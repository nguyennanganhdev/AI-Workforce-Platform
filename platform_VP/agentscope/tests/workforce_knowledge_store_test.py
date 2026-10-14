"""Knowledge vectors written by one store instance survive a restart."""

import asyncio
import tempfile

from agentscope.rag import QdrantStore


def test_on_disk_qdrant_keeps_collections_across_instances() -> None:
    async def run(path: str) -> bool:
        first = QdrantStore(path=path)
        await first.create_collection("kb_demo", dimensions=4)
        await first.get_client().close()
        second = QdrantStore(path=path)
        try:
            return await second.has_collection("kb_demo")
        finally:
            await second.get_client().close()

    with tempfile.TemporaryDirectory() as path:
        assert asyncio.run(run(path)) is True
