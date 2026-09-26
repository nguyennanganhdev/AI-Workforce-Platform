# Platform và domain độc lập

Status: baseline theo thiết kế nguồn; implementation theo từng phase.

Nguồn: [04_SYSTEM_DESIGN_STRUCTURE_ARCHITECTURE.md](../../../docx/04_SYSTEM_DESIGN_STRUCTURE_ARCHITECTURE.md).

## Quyết định

Platform giữ Agent Factory/runtime/memory; Vinhomes giữ business state.

## Hệ quả cho code

Module platform chỉ gọi DomainAdapter; composition root nối implementation.

