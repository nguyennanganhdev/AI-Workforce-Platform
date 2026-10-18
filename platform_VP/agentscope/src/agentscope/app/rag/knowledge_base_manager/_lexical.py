"""Owner-scoped lexical retrieval of reviewed inline references; no embedding."""
import re
import unicodedata
from datetime import datetime, timezone

from ....message import TextBlock
from ....rag import Chunk, VectorSearchResult


def terms(text):
    normalized = unicodedata.normalize("NFKD", text.casefold().replace("đ", "d"))
    return set(re.findall(r"\w+", "".join(c for c in normalized if not unicodedata.combining(c))))


class LexicalKnowledge:
    def __init__(self, storage, record):
        self.storage, self.record = storage, record
        self.name, self.description = record.data.name, record.data.description

    async def list_chunks(self, document_id, offset=0, limit=30):
        doc = await self.storage.get_knowledge_document(self.record.user_id, self.record.id, document_id)
        if doc is None or not doc.data.text_content:
            return []
        parts = [doc.data.text_content[i:i + 1800] for i in range(0, len(doc.data.text_content), 1800)]
        return [Chunk(content=TextBlock(text=part), source=doc.data.filename,
                      chunk_index=i, total_chunks=len(parts), metadata={"source_ref": doc.data.source_ref,
                      "version": doc.data.version, "review_status": doc.data.review_status})
                for i, part in enumerate(parts) if offset <= i < offset + limit]

    async def search(self, queries, top_k=5, score_threshold=None, **_):
        query_terms = terms(" ".join(queries) if not isinstance(queries, str) else queries)
        if not query_terms:
            return []
        docs = await self.storage.list_knowledge_documents(self.record.user_id, self.record.id)
        now = datetime.now(timezone.utc).date().isoformat()
        hits = []
        for doc in docs:
            if doc.status != "ready" or doc.data.review_status != "approved":
                continue
            if (doc.data.effective_from and doc.data.effective_from > now) or (doc.data.effective_until and doc.data.effective_until < now):
                continue
            for chunk in await self.list_chunks(doc.id, limit=100):
                overlap = query_terms & terms(chunk.content.text + " " + doc.data.filename)
                score = len(overlap) / len(query_terms)
                if overlap and score >= (score_threshold or 0):
                    hits.append(VectorSearchResult(document_id=doc.id, chunk=chunk, score=score))
        return sorted(hits, key=lambda hit: (-hit.score, hit.document_id, hit.chunk.chunk_index))[:top_k]

    async def delete_document(self, document_id):
        # Records are deleted by KnowledgeBaseService after this hook.
        return None
