# DomainAdapter là điểm tích hợp

Status: baseline theo thiết kế nguồn; implementation theo từng phase.

Nguồn: [Business analysis P0](../../erd/02_BUSINESS_ANALYSIS_IMPLEMENTATION.md).

## Quyết định

Domain expose resolveSubject, validateAction, submitAction, listCapabilities, resolveActorScope, getEvidence.

## Hệ quả cho code

Draft code thêm RequestContext cho mọi method; review liên team signature trước transport. Platform không import repository domain.

