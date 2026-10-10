# Bàn giao — Phó Tiến Anh

Branch đề xuất: `feat/wf-lifecycle`. Đầu việc: **PTA-01–PTA-16**.

Phạm vi: vòng đời riêng từng agent, batch publish, thư viện chung, Settings và version/rollback.

[Kế hoạch và hợp đồng chung](../../KE_HOACH_TRIEN_KHAI.md) là tài liệu đầu vào cho AI. Gửi cả file kế hoạch và nói rõ: “Tôi là Phó Tiến Anh”.

Khi triển khai, tạo `STATUS.md` theo mẫu ở mục 16. Mỗi yêu cầu đổi contract/hook/file chung ghi vào `INTEGRATION_REQUEST_<task-id>.md` theo mục 14.

Hiện tại chưa có task được đánh dấu hoàn thành; việc tạo thư mục này không chứng minh module đã được code/test.

Nguyên tắc batch của bản 1.2 được giữ ở bản 1.3: PTA-01/07–PTA-13 quản lý identity/draft/eval/version/deployment của từng agent; BuildBatchPort hỗ trợ phát hành nhiều agent đạt. PTA-13 là batch + eval từng agent, thay yêu cầu team reference/eval cũ. Mọi agent xuất hiện độc lập trong thư viện. Đọc mục 2.3, 2.5 và 6 của kế hoạch trước khi code; nội dung này thay thế cách hiểu team artifact ở bản trước. Đây là đầu việc cần triển khai, chưa phải tính năng đã hoàn thành.

## Cập nhật bắt buộc theo kế hoạch 1.3

Giữ một role `AREA_MANAGER` và chọn domain/area. Scope là `(tenant_id, domain_id, area_id, manager_account_id)`; partner request phải resolve mapping/grant tới đúng tài khoản đích trước khi chạy Leader, không broadcast theo area. Actor đối tác/cư dân không phải owner platform. Đọc mục 2.6 và hợp đồng mục 6; chỉ dẫn cũ yêu cầu bỏ domain/area không còn hợp lệ.

PTA-01/02/06/09/12 lưu/filter đủ manager Scope trên identity/draft/version/eval và unique business_key trong scope. Không trả candidate của manager khác cùng area; migration/backfill qua Chí Hoàng. Batch vẫn tạo agent độc lập, không sinh team artifact.

Các bổ sung này là kế hoạch cần triển khai, không phải xác nhận code hoặc test đã hoàn thành.


## Bổ sung bắt buộc theo kế hoạch 1.4 — API và sự kiện

Đọc mục 2.6–2.7, 5.3, 6.7 và toàn bộ mục 17 của [kế hoạch 1.4.3](../../KE_HOACH_TRIEN_KHAI.md). Giữ nguyên scope/mapping v1.3 và contract hai ticket/hộp chat v1.4.3. Mọi response có `workflow_state` + `next_action`: response-only read-only có thể auto-close; interactive dùng reply/approval/explicit close; external-tracking và Provider Event/SSE chỉ dùng khi operation pending. `202` chỉ là HTTP timeout fallback. V1 không có HTTP sender từ platform sang endpoint đối tác.

Owner Phó Tiến Anh bổ sung **PTA-14–PTA-16**: validation/eval nhiều lượt sự kiện và giữ version cho workflow đang chờ. Thực hiện cả task cũ còn thiếu và task mới; cập nhật STATUS.md, không đánh dấu hoàn thành từ scaffold.

- [ ] **PTA-14 — Validation và snapshot async:** lifecycle/async_evaluation/ validate AsyncHandlingPolicy và protocol/hash/coverage trên draft, đóng băng vào evaluation snapshot. Tái dùng gate/publish từng agent; không thêm team deployment hay đưa runtime ticket vào AgentDefinition.
- [ ] **PTA-15 — Eval lifecycle đa pattern:** suite response-only, interactive plan→selection→approval→booking→confirmation và external-tracking. Assert workflow_state/next_action đúng; ca sync không tạo tracking giả, ca async không gọi LLM khi chưa có trigger, không lặp side effect hoặc lẫn audience. UI report từng lượt/pattern, chi phí và blocker.
- [ ] **PTA-16 — Version và retention khi chờ:** Giữ immutable version/protocol references mà workflow mở cần; publish/rollback không đổi pin đang chờ. Archive chỉ ngăn chọn mới; disable/revoke chặn continuation/tool theo policy, không hard-delete reference. Phối hợp usage/checkpoint qua port Huy Hoàng, không tự ghi wf_workflows. tests/workforce/lifecycle/async_evaluation/ kiểm tra restart/pin/drift/stale eval và availability trước resume.

Các thư mục v1.4 đã chuẩn bị cho bạn:

- [src/agentscope/app/workforce/lifecycle/async_evaluation/](../../../../src/agentscope/app/workforce/lifecycle/async_evaluation/README.md) — Async snapshot/policy validation và multi-event eval; runtime workflow thuộc Huy Hoàng.
- [examples/web_ui/frontend/src/features/workforce/agents/async_evaluation/](../../../../examples/web_ui/frontend/src/features/workforce/agents/async_evaluation/README.md) — Report nhiều event/turn và hard gates.
- [tests/workforce/lifecycle/async_evaluation/](../../../../tests/workforce/lifecycle/async_evaluation/README.md) — Fake clock/runner, pin version qua chờ và stale evaluation.

Bắt đầu bằng đọc hợp đồng 17.3–17.4, viết logic và test với fake port thuộc module mình, rồi bàn giao signature/schema/hook request cho owner cung cấp. Các fake chỉ trong test/demo, production không trả thành công giả. Mỗi người làm trong branch/worktree riêng; migration/core/shared contracts chỉ Chí Hoàng sửa.

