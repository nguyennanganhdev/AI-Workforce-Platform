# Agent đề xuất, domain thực thi

Status: baseline theo thiết kế nguồn; implementation theo từng phase.

Nguồn: [Business analysis P0](../../erd/02_BUSINESS_ANALYSIS_IMPLEMENTATION.md).

## Quyết định

ActionProposal không phải permission. Domain giữ rule, approval và execution grant trước MCP WRITE.

## Hệ quả cho code

submitAction phải revalidate trong transaction; kiểm idempotency, actor, scope và version.

