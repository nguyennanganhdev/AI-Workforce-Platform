# Architecture Decision Records

Các ADR ghi lại quyết định trong tài liệu gốc để team tra cứu. Trạng thái là
**baseline theo thiết kế**, không phải xác nhận implementation production hoặc phê duyệt mới.
Draft contract cụ thể vẫn cần review producer/consumer trước triển khai.

- [Platform và domain độc lập](platform/0001-platform-vs-domain-boundary.md)
- [OpenBot là product shell](platform/0002-openbot-product-shell.md)
- [AgentScope 2.0 sau RuntimeAdapter](platform/0003-runtime-adapter-agentscope2.md)
- [DomainAdapter là điểm tích hợp](platform/0004-domain-adapter-contract.md)
- [Agent đề xuất, domain thực thi](platform/0005-action-proposal-boundary.md)
- [AgentVersion bất biến](platform/0006-agent-version-immutability.md)
- [Evaluation và publish gate](platform/0007-evaluation-publish-gate.md)
- [PostgreSQL authoritative, Qdrant semantic](platform/0008-memory-postgres-qdrant.md)
- [Reference xuyên ranh giới](platform/0009-cross-domain-reference-policy.md)
- [Event và idempotency](platform/0010-event-and-idempotency.md)
- [Incident là canonical Ticket](domains/vinhomes/0001-incident-is-canonical-ticket.md)
- [Intake tách khỏi Incident](domains/vinhomes/0002-case-issuecandidate-intake.md)
- [Approval thuộc domain action](domains/vinhomes/0003-action-request-approval.md)
- [WorkOrder, redo và QC](domains/vinhomes/0004-workorder-redo-qc.md)
- [A5 dùng versioned CleaningPlan JSON](domains/vinhomes/0005-a5-cleaning-plan-json.md)


- [Unified OpenBot database and PostgreSQL transcript](platform/0013-unified-openbot-database.md)
