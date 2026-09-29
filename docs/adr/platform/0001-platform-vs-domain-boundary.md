# Platform và domain độc lập

Status: baseline theo thiết kế nguồn; implementation theo từng phase.

Nguồn: [Business analysis P0](../../erd/02_BUSINESS_ANALYSIS_IMPLEMENTATION.md).

## Quyết định

Platform giữ Agent Factory/runtime/memory; Vinhomes giữ business state.

## Hệ quả cho code

Module platform chỉ gọi DomainAdapter; composition root nối implementation.

