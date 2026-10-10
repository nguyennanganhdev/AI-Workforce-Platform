# Trạng thái — Bùi Hữu Nghĩa

Ngày kiểm tra: 2026-10-10. Branch: `feat/wf-builder`. Baseline Phase B: `818554114c0a8f72107df9625c8e4b3e21883171`; thay đổi Phase B chưa commit.

## Phạm vi đã làm

Hoàn thành phần độc lập của **Phase B bổ sung mục 17.9**: requirement extraction, capability checks, pinned protocol readiness, reuse/revise/resume/clarify, proposal edit/confirm/recheck và UI với fake ports. Liên quan phần Phase B của BHN-12–14 và các phần hỗ trợ BHN-02/03/07/09/10/11. Policy đã theo schema proposal Tiến Anh. Tái sử dụng DTO/ports, AgentScope message/model API, UI primitives và Registry handed-off fake.

BHN-01–BHN-14 chưa hoàn thành end-to-end. Proposal session chỉ process-local preview; chưa có durable persistence, manifest/draft generation, KB/skill selection, full eval/publish/progress UI, migration, HTTP/root-route hoặc production wiring. Confirm không báo agent đã tạo. Query-only policy còn bị block khi event semantics chưa có metadata/chưa chốt. Không đánh dấu gate tích hợp chung hoặc production readiness từ fake tests.

Files nằm trong bốn vùng owned: backend `src/agentscope/app/workforce/builder/`, frontend `examples/web_ui/frontend/src/features/workforce/builder/`, tests `tests/workforce/builder/`, handoff `docs/workforce/handoffs/bui-huu-nghia/`. Không sửa module khác, contracts chung, root route, migration, dependency hay lockfile.

Backend public exports: RequirementExtractor/ExtractionResult/ExtractionError, CapabilitySelector, ProposalService, BuildProposal, ProtocolReadiness. UI export BuilderPanel/BuilderClient. Policy proposal version 1; timeout_behavior=status_query|needs_attention; không có timeout_seconds trong policy. Public API chưa đăng ký. Signatures, demo và limitations: [PHASE_B.md](PHASE_B.md).

## Kiểm tra

```powershell
# Từ platform_VP/agentscope, với dependency của repo đã cài trong .venv
.\.venv\Scripts\python.exe -m unittest tests.workforce.builder.async_capabilities.test_phase_a tests.workforce.builder.async_capabilities.test_phase_b tests.workforce.foundation.test_contracts -v
.\.venv\Scripts\python.exe -m compileall -q src/agentscope/app/workforce/builder tests/workforce/builder
git diff --check
```

Kết quả review lại ngày 2026-10-10: **40 Builder/Foundation + 14 Registry + 8 Lifecycle + 4 Edge UI = 66 tests pass**. Bổ sung 7 regression tests và sửa lỗi mất clarification, capability/effect drift, tool bị xóa, query binding và mutable proposal response. Chi tiết từng lỗi đã tái hiện/sửa trong [PHASE_B.md](PHASE_B.md). TypeScript build và ESLint vùng Builder pass; compileall/schema export/whitespace pass. Browser UI checks có edit/confirm/cancel/reuse/blocked và mobile không tràn ngang, không lỗi JavaScript. Artifact QA: phase-b-ui.png. Môi trường Python 3.12/Pydantic 2.14/Node 22.18. Chi tiết lệnh và dependencies chỉ cài trong môi trường local nằm trong PHASE_B.md.

Tests dùng fake model/Registry/AsyncProtocol/AgentReuse và demo client; production không export fake. Chưa kiểm tra provider/model thật, transactional races, recovery sau restart hoặc runtime worker. TypeScript types và UI proposal là local view, shared contracts giữ nguyên.

## Yêu cầu tích hợp và bước tiếp theo

Xem [INTEGRATION_REQUEST_BHN_PHASE_B.md](INTEGRATION_REQUEST_BHN_PHASE_B.md): canonical policy/ref/storage; detailed snapshot accessor; query-only event_types semantics; typed async reuse coverage; durable sessions và HTTP/UI composition. Chí Hoàng sở hữu shared DTO/schema/TypeScript/migration, Đông protocol và Anh lifecycle. Integration request Phase A giữ làm lịch sử; policy mới đã theo Anh.

Bước tiếp theo: chốt các điểm nối, triển khai BHN-01 durable storage và BHN-04/05/06 còn thiếu rồi nối Registry/Draft/Reuse thật trong Phase C. Không dùng preview marker builder.async hoặc fake readiness làm contract production chưa review. Không hạ tracking scope tự động khi thiếu capability; Lifecycle vẫn chịu trách nhiệm atomic identity allocation.
