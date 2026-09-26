# PostgreSQL authoritative, Qdrant semantic

Status: baseline theo thiết kế nguồn; implementation theo từng phase.

Nguồn: [04_SYSTEM_DESIGN_STRUCTURE_ARCHITECTURE.md](../../../docx/04_SYSTEM_DESIGN_STRUCTURE_ARCHITECTURE.md).

## Quyết định

Memory identity/revision/review/redaction/sync metadata ở PostgreSQL; Qdrant giữ vector.

## Hệ quả cho code

Retrieval re-check revision, approval và quyền ở PostgreSQL sau vector search; không lưu workflow state trong Qdrant.

