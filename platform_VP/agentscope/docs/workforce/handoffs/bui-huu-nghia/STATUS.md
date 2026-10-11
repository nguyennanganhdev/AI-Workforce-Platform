# Trạng thái — Bùi Hữu Nghĩa

## Cập nhật C3 — 2026-10-11 (trạng thái hiện hành)

Baseline `67ff8715e4a40a37538b727442b3b66f2c9223e1`, branch `feat/wf-builder`,
đã chứa C1/C2 merge. Code C3 ban đầu đã commit/push tại `304c39a`, mở
[PR #62](https://github.com/nguyennanganhdev/AI-Workforce-Platform/pull/62).
Bản sửa review hiện chưa commit/push; chờ review lại và merge.

**Chỉ C3 theo trình tự chung: Protocol validation ↔ Builder.** Đã triển khai
exact C2 readiness adapter, RegistryCapabilitySelector và ProtocolBuildValidator
trước draft write. Tái sử dụng ProposalService/validator Phase B, canonical UOW
C1 và SQL protocol C2; bản sửa code/test sẵn sàng bàn giao review lại.

Sửa review PR #62: protocol effect/mode mismatch bị chặn ngay ở proposal;
bindings dedup theo tool version, coverage lưu đầy đủ theo tool và recheck
không bỏ qua capability phụ. Bổ sung 10 regression tests trong vùng Nghĩa.

Đã gỡ phần mở rộng SQL session/message, durable service, generator, journal/
recovery và DDL Builder; service/reuse Phase B giữ nguyên. Không thay module
owner khác, không làm root/migration hoặc task Phase D.

Tests: **31 Builder A/B + 26 Builder C3 + 29 Registry + 29 Foundation pass**.
Registry có 1 PostgreSQL gate skipped. Lifecycle **24 pass, 1 baseline failure**
ở test policy legacy; đã tái hiện với Builder nguyên bản HEAD. Không sửa test Anh.

Output C1/C2 cùng Phase B đã đủ cho C3 này; không chờ C5 hoặc toàn bộ Builder
production. Model/catalog/reuse/policy resolver là test doubles; protocol/UOW/
validator dùng thật. Chưa kiểm tra PostgreSQL concurrency/runtime E2E. Pending
create-only/query-only thiếu semantics bị block theo contract hiện hữu. Root/
API/migration C7 và provider production không phải blocker review C3 hẹp.

Chi tiết: [PHASE_C_C3.md](PHASE_C_C3.md),
[requests C3](INTEGRATION_REQUEST_BHN_C3.md),
[PLAN_C3.md](PLAN_C3.md). Không tuyên bố BHN-01–14 hoàn thành toàn bộ.

## Lịch sử Phase B và hướng dẫn trước khi triển khai C3

Các ghi chú bên dưới phản ánh thời điểm bàn giao cũ. Các câu “C2 chờ merge” và
số test Phase B không phải trạng thái C3 hiện tại. Session vẫn process-local;
C3 này không triển khai durable Builder persistence.

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

## Điều phối Phase C — cập nhật từ C1 ngày 2026-10-11

Bạn thuộc lane **C3/Builder**, chạy song song với lane C3 của Phan Hoàng Dũng
nhưng chỉ sau khi C2 của Nguyễn Phương Đông đã merge. Pull baseline C2 và ghi
commit đầu vào trong STATUS; không bắt đầu từ output protocol fake Phase B.

C1 đã cung cấp UOW/identity/routing/jobs/bootstrap và migration Foundation.
C3 của bạn nối exact protocol validation/readiness thật vào Builder, durable
proposal/draft handoff và scope từ verified principal. Dùng session/UOW được
inject; không tạo DB engine, Scope từ body, migration hoặc policy contract thứ
hai. Bàn giao schema/index cần thêm cho Chí Hoàng, và public output cần cho C5.

Bạn không cần chờ lane C3 của Dũng để code, nhưng C4 chỉ mở khi **cả hai lane
C3** đã merge. Theo dõi [../PHASE_C_SEQUENCE.md](../PHASE_C_SEQUENCE.md).

### Output C2 đang chờ merge

C2 đã tạo `SqlAsyncProtocolProvider`/`SqlAsyncProtocolRepository` và exact
pinned resolver trong working tree dựa trên baseline C1. Khi C2 đã merge lên
`develop2`, pull commit đó rồi dùng public `AsyncProtocolPort`/
`AsyncProtocolService` để recheck protocol, capability và revision trước khi
tạo/sửa draft. Không query trực tiếp hai bảng Registry và không mang fake
protocol Phase B vào production. Chi tiết producer:
[../nguyen-phuong-dong/INTEGRATION_REQUEST_NPD_C2.md](../nguyen-phuong-dong/INTEGRATION_REQUEST_NPD_C2.md).
