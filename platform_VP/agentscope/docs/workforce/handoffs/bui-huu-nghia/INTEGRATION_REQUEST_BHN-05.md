# BHN-05 — Model sinh và adapter tái sử dụng model hiện có

- **Task ID:** BHN-05; liên quan BHN-01/02/08.
- **Người gửi / người nhận:** Bùi Hữu Nghĩa → Nguyễn Chí Hoàng.
- **Trạng thái:** đề xuất để review, chưa được owner xác nhận; chưa gửi ra kênh liên lạc ngoài repo.

## Hiện trạng và lý do

Cập nhật sau pull `a99d506`: contracts/ports Foundation đã có, nhưng chưa có BuildModelPort, ChatModelConfig trong Workforce exports hoặc adapter sinh model theo scope. Request này giữ nguyên phần cần bổ sung; model runtime canonical nằm ở AgentSpec.model_config_ref. DTO request ở schema handoff vẫn chỉ là đề xuất.

Người dùng yêu cầu chọn model dùng để sinh agent, làm một agent trước. Repo đã có ChatModelConfig, LlmSelect và get_model; Workforce composition vẫn chưa có adapter này. Builder không được import private service hoặc dựng credential client riêng.

## File/module của người nhận cần sửa

- `src/agentscope/app/workforce/contracts/`: contract model adapter/build request khi chốt.
- `src/agentscope/app/workforce/integrations/`: adapter bọc model service hiện có, inject vào Builder.
- `_service/_model.py` hoặc resource access hook chỉ khi thực sự thiếu khả năng; ưu tiên dùng nguyên implementation hiện có.
- Shared TypeScript/API types tương ứng; không tạo bộ model config song song.

## Port/export/hook đề xuất

Giữ ChatModelConfig hiện tại (type, credential_id, model, parameters). Đề xuất port nội bộ tên tạm `BuildModelPort`:

```text
async resolve(scope, config: ChatModelConfig) -> ChatModelBase
```

Adapter dùng manager_account_id qua mapping legacy đã xác minh để gọi get_model. Guard revalidate scope hiện hành và quyền credential; verify config.type khớp provider của credential, validate Parameters/allowlist, chặn secret hoặc endpoint override không được cấp quyền. Không dùng list model cards để chứng minh credential hợp lệ.

Sau resolve, Builder gọi method public `generate_structured_output(messages, canonical_schema)` của ChatModelBase. Cần cấu hình nội bộ hữu hạn max_retries/deadline/token/cost budget; không cho client tăng vô hạn. Xác nhận cách adapter áp dụng ngân sách trên toàn bộ strategy để không nhân số lần retry ở nhiều tầng.

## Input/output + error + scope

- Proposed body trong [GenerationRequest](phase_a/builder.schema.json), fixture tại [samples.json](phase_a/samples.json). Scope ở backend, không có trong body.
- Lưu `generation_model` trong build session; không ghi vào AgentSpec.model_config_ref (runtime).
- Có model object hợp lệ chỉ ở interface nội bộ; không serialize credential/model object ra API. Không silent fallback sang model khác.
- Errors đề xuất: BUILD_MODEL_UNAVAILABLE, BUILD_MODEL_INCOMPATIBLE, BUILD_OUTPUT_INVALID, BUILD_BUDGET_EXCEEDED, cần map vào error envelope chung. Credential inaccessible không tiết lộ owner hoặc nội dung credential.
- Model ID/type/credential ID là dữ liệu hiện có, không ép UUID mới hoặc hardcode provider.

## Transaction / retry / concurrency

Không giữ transaction khi gọi model. Builder giữ idempotency `(scope, build_session_id, client_message_id)` và expected_revision; cùng key khác message/model trả conflict. Model đổi cần revision mới; kết quả invocation cũ không ghi đè đề xuất mới. Revalidate trước dùng credential, không coi lần resolve cũ là grant vĩnh viễn.

## Ví dụ caller trong module của tôi

```python
model = await build_model_port.resolve(scope, session.generation_model)
result = await model.generate_structured_output(messages, canonical_schema)
# Builder validates semantic references and proposal revision before storing.
```

Đây là pseudo-caller cho Phase B, chưa phải export chạy được; canonical_schema phải từ contracts sau khi freeze, không import schema handoff.

## Test chứng minh yêu cầu

Local proposal tests đã xác minh body cần lựa chọn model, output không ghi đè model sinh, không có scope/secret top-level. Cần adapter tests: credential khác quyền bị chặn, provider mismatch, Parameters invalid, model error không đổi model, retry/deadline hữu hạn và đổi model không làm đổi runtime config. Các test adapter chưa chạy vì chưa có port.

## Phần đã hoàn thành và đang chờ

Đã đọc source, bàn giao [inventory](phase_a/reuse_inventory.md), proposal schema/input/output và tests. Chờ Foundation chốt tên/signature, errors và composition adapter. UI Phase B sẽ tái sử dụng LlmSelect/useAvailableModels; không cần xây picker mới.
