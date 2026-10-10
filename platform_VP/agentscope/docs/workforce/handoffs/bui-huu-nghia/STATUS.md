# Trạng thái — Bùi Hữu Nghĩa

Ngày kiểm tra: 2026-10-10. Branch: `feat/wf-builder`. Baseline commit: `3270ef3f61bba29af869ed833485fac9379a91fc`; thay đổi Phase A chưa commit.

## Phạm vi đã làm

Hoàn thành phần thiết kế/schema nội bộ Phase A của BHN-02/BHN-12: requirement single/batch, capability bắt buộc/tùy chọn, tracking intent, clarification và policy proposal. Tái sử dụng BusinessProfile/WorkforceModel/ToolEffect. Chuẩn bị boundary samples cho BHN-03/07/09/13; không đánh dấu các task này hoàn thành toàn bộ.

BHN-01–BHN-14 chưa hoàn thành end-to-end. Chưa có build persistence, extraction bằng LLM, selection/reuse service, manifest generation, UI, migration hay production wiring. MA còn phụ thuộc owner hợp đồng chốt schema/policy reference và detailed protocol.

Files: `src/agentscope/app/workforce/builder/async_capabilities/{__init__.py,_requirements.py,README.md}`, `tests/workforce/builder/async_capabilities/{test_phase_a.py,samples.json}`, handoff cá nhân gồm integration request và `phase-a.schema.json` xuất từ schema nội bộ.

Public exports nội bộ: `BuildRequirements`, `AgentRequirement`, `CapabilityRequirement`, `HandlingPolicyProposal`; schema proposal version `1`. Không sửa contracts chung, global frontend, module khác hoặc dependency/lockfile. Không đăng ký API.

## Kiểm tra

```powershell
# Từ platform_VP/agentscope, với dependency của repo đã cài trong .venv
.\.venv\Scripts\python.exe -m unittest tests.workforce.builder.async_capabilities.test_phase_a tests.workforce.foundation.test_contracts -v
.\.venv\Scripts\python.exe -m compileall -q src/agentscope/app/workforce/builder/async_capabilities tests/workforce/builder/async_capabilities
git diff --check
```

Kết quả: **17 tests pass** (8 Builder Phase A + 9 Foundation contract regression), 6 valid samples validate/round-trip/JSON Schema pass, 13 invalid samples bị từ chối. Compileall, schema export và diff whitespace pass. Python 3.12.10, Pydantic 2.14.0. Môi trường ban đầu chưa có dependency; đã tạo `.venv` và cài editable repo với extras `service,storage-sql` theo pyproject, không sửa dependency/lockfile. Các lần test trước khi cài xong không import được package; kết quả trên là lần chạy sau khi cài hoàn tất.

Tests dùng fake Registry/AsyncProtocol/AgentReuse/Draft trong vùng Builder tests, không chạy MCP server hay gọi provider/model thật. Fake tests chỉ chứng minh cách trao đổi DTO/scope/revision và biểu diễn blocker; chưa chứng minh matching, DB race hoặc runtime behavior.

## Yêu cầu tích hợp và bước tiếp theo

Xem `INTEGRATION_REQUEST_BHN_PHASE_A.md`: chốt canonical policy, persistence/ref/hash, protocol readiness/capability vocabulary và typed async requirements trong reuse comparison. Chí Hoàng sở hữu shared DTO/schema/TypeScript/migration; Đông sở hữu detailed protocol; Tiến Anh sở hữu draft validation/lifecycle.

Sau Phase A, triển khai BHN-01 rồi BHN-02/03 cùng fake ports, nối BHN-09 trước generate, tiếp tục proposal/manifest/validation/UI theo kế hoạch. Tận dụng model structured-output API, catalog/reuse/draft contracts, KB/skill và UI primitives hiện hữu. Không hạ tracking scope tự động khi thiếu capability.
