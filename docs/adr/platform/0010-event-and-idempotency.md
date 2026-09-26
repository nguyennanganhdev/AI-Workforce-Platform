# Event và idempotency

Status: baseline theo thiết kế nguồn; implementation theo từng phase.

Nguồn: [03_PLATFORM_ERD.md](../../../docx/03_PLATFORM_ERD.md).

## Quyết định

Platform event và domain event là hai stream. Command quan trọng cần idempotency; state/outbox persist trong PostgreSQL.

## Hệ quả cho code

Unique tenant/key theo ERD; retry cùng key phải kiểm payload hash. Consumer idempotent; không gộp event vào một model untyped.

