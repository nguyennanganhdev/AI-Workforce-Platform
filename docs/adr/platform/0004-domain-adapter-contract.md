# DomainAdapter là điểm tích hợp

Status: baseline theo thiết kế nguồn; implementation theo từng phase.

Nguồn: [04_SYSTEM_DESIGN_STRUCTURE_ARCHITECTURE.md](../../../docx/04_SYSTEM_DESIGN_STRUCTURE_ARCHITECTURE.md).

## Quyết định

Domain expose resolveSubject, validateAction, submitAction, listCapabilities, resolveActorScope, getEvidence.

## Hệ quả cho code

Draft code thêm RequestContext cho mọi method; review liên team signature trước transport. Platform không import repository domain.

