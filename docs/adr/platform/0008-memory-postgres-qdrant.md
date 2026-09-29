# PostgreSQL authoritative, Qdrant semantic

Status: baseline theo thiết kế nguồn; implementation theo từng phase.

Nguồn: [Business analysis P0](../../erd/02_BUSINESS_ANALYSIS_IMPLEMENTATION.md).

## Quyết định

Memory identity/revision/review/redaction/sync metadata ở PostgreSQL; Qdrant giữ vector.

## Hệ quả cho code

Retrieval re-check revision, approval và quyền ở PostgreSQL sau vector search; không lưu workflow state trong Qdrant.

