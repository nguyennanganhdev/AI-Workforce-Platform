"""Reviewed text references which never enqueue an embedding job."""
import hashlib
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from ..deps import get_current_user_id, get_storage, get_current_principal
from ..storage import KnowledgeBaseRecord, KnowledgeBaseData, EmbeddingModelConfig, KnowledgeDocumentRecord, KnowledgeDocumentData

reference_router = APIRouter(tags=["knowledge_bases"])


class ReferenceBaseRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)


class ReferenceRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=20, max_length=100000)
    source_ref: str = Field(min_length=1, max_length=1000)
    effective_from: date | None = None
    effective_until: date | None = None

    @model_validator(mode="after")
    def dates_are_ordered(self):
        if self.effective_from and self.effective_until and self.effective_until < self.effective_from:
            raise ValueError("Ngày hết hiệu lực phải sau ngày có hiệu lực")
        return self


class ReviewReferenceRequest(BaseModel):
    status: Literal["approved", "retired"]


@reference_router.post("/lexical", status_code=201)
async def create_reference_base(body: ReferenceBaseRequest, user_id=Depends(get_current_user_id), storage=Depends(get_storage)):
    record = KnowledgeBaseRecord(user_id=user_id, data=KnowledgeBaseData(
        name=body.name, description=body.description, retrieval_mode="lexical", collection_name="",
        embedding_model_config=EmbeddingModelConfig(type="lexical", credential_id="", model="lexical-no-embedding", dimensions=1)))
    await storage.upsert_knowledge_base(user_id, record)
    return {"knowledge_base_id": record.id, "retrieval_mode": "lexical"}


@reference_router.post("/{kb_id}/references", status_code=201)
async def create_reference(kb_id: str, body: ReferenceRequest, user_id=Depends(get_current_user_id), storage=Depends(get_storage)):
    kb = await storage.get_knowledge_base(user_id, kb_id)
    if kb is None:
        raise HTTPException(404, "Không có kho tài liệu của bạn.")
    if kb.data.retrieval_mode != "lexical":
        raise HTTPException(409, "Tài liệu tham chiếu cần kho tìm kiếm văn bản.")
    payload = body.text.encode()
    doc = KnowledgeDocumentRecord(user_id=user_id, knowledge_base_id=kb_id, status="ready", data=KnowledgeDocumentData(
        filename=body.filename, size=len(payload), content_type="text/markdown", blob_uri="inline://reference",
        text_content=body.text, source_ref=body.source_ref, version=hashlib.sha256(payload).hexdigest(), review_status="candidate",
        effective_from=body.effective_from.isoformat() if body.effective_from else None,
        effective_until=body.effective_until.isoformat() if body.effective_until else None,
        chunk_count=(len(body.text) + 1799) // 1800))
    await storage.upsert_knowledge_document(user_id, doc)
    return {"document_id": doc.id, "review_status": doc.data.review_status, "version": doc.data.version}


@reference_router.post("/{kb_id}/references/{document_id}/review")
async def review_reference(kb_id: str, document_id: str, body: ReviewReferenceRequest,
                           principal=Depends(get_current_principal), storage=Depends(get_storage)):
    if principal.role not in {"AREA_MANAGER", "DOMAIN_ADMIN", "PLATFORM_ADMIN"}:
        raise HTTPException(403, "Chỉ người quản lý được duyệt tài liệu.")
    doc = await storage.get_knowledge_document(principal.user_id, kb_id, document_id)
    if doc is None or doc.data.text_content is None:
        raise HTTPException(404, "Không có tài liệu tham chiếu của bạn.")
    doc.data.review_status, doc.data.reviewed_by = body.status, principal.user_id
    await storage.upsert_knowledge_document(principal.user_id, doc)
    return {"document_id": doc.id, "review_status": doc.data.review_status, "version": doc.data.version}
