# Trạng thái bàn giao — Bùi Hữu Nghĩa

Cập nhật: 10/10/2026. Branch hiện tại: `devTeamDong/Nghia`; baseline đọc `6bc7d60d1bcf0d1bf49ad9214fad22791b29c274`. Branch đề xuất trong kế hoạch: `feat/wf-builder`. Không đổi branch/commit/push trong phiên.

Baseline mới sau pull: HEAD `a99d506`, Foundation Phase A commit `1ff8fb6`. Đã đối chiếu và cập nhật gói bàn giao theo [PULL_UPDATE.md](phase_a/PULL_UPDATE.md).

## Kết quả và task IDs

- Hoàn thành phần độc lập Phase A: [gói đề xuất requirement/policy](phase_a/README.md), schema machine-readable, mẫu dữ liệu, prompt extraction, khảo sát API/component tái sử dụng, test artifact và ba integration requests.
- BHN-12: có đề xuất requirement/AsyncHandlingPolicy và bộ mẫu được kiểm tra local; chưa freeze DTO hoặc triển khai extraction runtime.
- BHN-05/13/14: đã đặc tả model sinh, coverage/reuse và ca kiểm tra làm đầu vào triển khai; chưa hoàn thành task.
- Sau pull: đã cung cấp BusinessProfile/manifest/create-reuse-revise samples dùng contract version 1, thêm kiểm tra schema canonical và sửa chữ ký caller. Foundation contracts nền đã có; không còn chờ xuất lại những DTO này.
- BHN-01–14 chưa có task được đánh dấu hoàn thành toàn bộ. Phase A toàn nhóm/gate MA còn chờ owner thống nhất contract và fake canonical; không coi test schema đề xuất là bằng chứng production.

## Files, exports và contracts

- Handoff cá nhân: README.md, PLAN_PHASE_A.md, STATUS.md.
- `phase_a/`: README.md, builder.schema.json, samples.json, reuse_inventory.md, builder_prompt.md.
- Bổ sung sau pull: `phase_a/canonical_samples.json`, `phase_a/PULL_UPDATE.md`, test_canonical_handoff.py và cập nhật các tài liệu/requests liên quan.
- INTEGRATION_REQUEST_BHN-05.md: Chí Hoàng, model/credential adapter và budget.
- INTEGRATION_REQUEST_BHN-12.md: Chí Hoàng/Tiến Anh, canonical DTO/policy/manifest/eval/reuse.
- INTEGRATION_REQUEST_BHN-13.md: Đông, snapshot/coverage signature và fake protocol.
- Test riêng: `tests/workforce/builder/async_capabilities/test_phase_a_schema.py` và README cùng thư mục.
- Không có public Python/TypeScript/API export mới; JSON Schema `bhn.phase-a.proposal.1` là review artifact trong handoff, không import vào production. Baseline nghiệp vụ kế hoạch 1.4.3.
- Không sửa module của owner khác, shared contracts, migration, dependency/lockfile hoặc kế hoạch chung.

## Kiểm tra đã chạy

Từ `platform_VP/agentscope`:

```powershell
& "$env:TEMP\wf-bhn-phase-a-venv\Scripts\python.exe" -B -m unittest discover -s tests/workforce/builder/async_capabilities -p "test_*.py" -v
```

- Python 3.12.10, jsonschema 4.26.0 trong venv tạm; jsonschema đã được khai báo trong pyproject.toml, không thêm dependency mới cho repo.
- Kết quả mới: **40 tests pass**, 0 fail, **1 skip** trong tổng 41 tests. 31 kiểm tra schema đề xuất + 9 kiểm tra mẫu/shape theo canonical export. Protocol-ref schema test skip do Foundation chưa thêm AsyncProtocolSnapshotRef vào schema bundle; Python DTO đã có.
- Kiểm tra tài liệu: local links, JSON parse, diff whitespace và owned paths.
- Đã kiểm tra mẫu canonical bằng JSON Schema export thật (gồm ToolBinding/BusinessProfile trong $defs của AgentManifest). Chưa chạy Foundation Python suite/Pydantic validators hoặc framework regression, UI/API, model/provider thật, semantic coverage/reuse service, concurrency và idempotency runtime. Export JSON không thay các model_validator của Python.
- Inbox/checkpoint/outbox/replay/close/restart tests: chưa chạy, ngoài phần implementation Phase A của Builder.

## Đầu vào và giới hạn

- Đã dùng kế hoạch, source thật và Foundation DTO/ports/schema export version 1 sau pull. Chưa gọi port implementation thật; samples là dữ liệu giả minh họa, chưa phải fake Registry/AsyncProtocolPort được owner chứng nhận.
- API/protocol samples: policy lookup/interactive/create-only/confirmed/pending event/query/fallback trong samples.json. Không tạo provider event/receipt/event ID nghiệp vụ hoặc operation thật.
- Không đọc secret; fixture credential/model không phải credential/model hoạt động. Không kiểm chứng tích hợp đối tác/booking/live provider. Phase A chưa cần credential đối tác thật.
- Schema kiểm tra hình dạng và một số ràng buộc; authorization, cross-resource references, Parameters, capability coverage và runtime state vẫn cần service checks. Chi tiết ở Phase A README.

## Các điểm chờ và việc tiếp theo

1. Owner review ba integration requests, chốt DTO/signature/error/policy location và fake protocol. Chưa có xác nhận; chưa gửi tin nhắn ra ngoài repo.
2. Contracts nền đã có và mẫu được kiểm tra theo export. Còn Chí Hoàng chốt/export typed policy/requirement/model sinh và schema protocol-ref, Đông bàn giao detailed snapshot/fake, Anh chốt validation/evaluation/reuse. Chỉ giữ schema đề xuất cho phần chưa có counterpart canonical, không giữ hai nguồn DTO production.
3. Sau khi chốt Phase A, triển khai lát cắt một agent theo plan: chọn model sinh → extraction/reuse → proposal/confirm → draft/validate/eval; dùng ports và fake trong test khi module thật chưa sẵn sàng. Giữ batch sau luồng một agent.
4. Khi code dùng ChatModelBase/Agent, LlmSelect/useAvailableModels và cấu trúc config đã khảo sát; không viết lại client/parser/model picker. Nếu cần hook/core/shared thay đổi thì để đúng owner thực hiện.
