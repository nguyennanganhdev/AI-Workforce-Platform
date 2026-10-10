# Bàn giao — Nguyễn Phương Đông

Branch đề xuất: `feat/wf-registry`. Đầu việc: **NPD-01–NPD-12**.

Phạm vi: MCP catalog, kết nối, discovery và kho tool đã đăng ký.

## Phase A — 2026-10-10

Đã triển khai phần nhịp A mục 17.9: cấu hình protocol có validation, ordering/mapping,
snapshot hash, JSON Schema/samples và fake `AsyncProtocolPort` trong test. Xem
[PHASE_A.md](PHASE_A.md), [STATUS.md](STATUS.md) và
[INTEGRATION_REQUEST_NPD_PHASE_A.md](INTEGRATION_REQUEST_NPD_PHASE_A.md).
NPD-10–12 chưa hoàn thành toàn bộ; service/DB/normalizer production/UI thuộc nhịp sau.

## Điểm tiếp tục kế hoạch endpoint MCP — 2026-10-10

Kế hoạch endpoint MCP vẫn dừng tại Bước 1 để chờ contracts/SDK dùng chung. Gate này độc lập với Phase A protocol đã triển khai bằng contracts hiện có. Xem [INTEGRATION_REQUEST_NPD_ENDPOINT.md](INTEGRATION_REQUEST_NPD_ENDPOINT.md) để biết owner và điều kiện tiếp tục. Khi tiếp tục endpoint, ưu tiên wrapper MCP, contracts, SQL/session, transport frontend và UI components sẵn có; không tạo lớp thay thế.

Kế hoạch endpoint mới nhất giữ `workflow_state`/`next_action` cho Customer request/reply; không thêm hai field này vào response MCP/tool/skill, dù các hướng dẫn v1.4 tổng quát bên dưới viết “mọi response”.

[Kế hoạch và hợp đồng chung](../../KE_HOACH_TRIEN_KHAI.md) là tài liệu đầu vào cho AI. Gửi cả file kế hoạch và nói rõ: “Tôi là Nguyễn Phương Đông”.

Khi triển khai, tạo `STATUS.md` theo mẫu ở mục 16. Mỗi yêu cầu đổi contract/hook/file chung ghi vào `INTEGRATION_REQUEST_<task-id>.md` theo mục 14.

Hiện tại chưa có task được đánh dấu hoàn thành; việc tạo thư mục này không chứng minh module đã được code/test.

Nguyên tắc batch của bản 1.2 được giữ ở bản 1.3: Registry đăng ký tool cho Builder và kiểm tra availability của agent ứng viên. Agent tạo lẻ/hàng loạt dùng chung kho tool trong scope; batch không là phạm vi cấp tool hoặc group thực thi. Đọc mục 2.3, 2.5 và 6 của kế hoạch trước khi code; nội dung này thay thế cách hiểu team artifact ở bản trước. Đây là đầu việc cần triển khai, chưa phải tính năng đã hoàn thành.

## Cập nhật bắt buộc theo kế hoạch 1.3

Giữ một role `AREA_MANAGER` và chọn domain/area. Scope là `(tenant_id, domain_id, area_id, manager_account_id)`; partner request phải resolve mapping/grant tới đúng tài khoản đích trước khi chạy Leader, không broadcast theo area. Actor đối tác/cư dân không phải owner platform. Đọc mục 2.6 và hợp đồng mục 6; chỉ dẫn cũ yêu cầu bỏ domain/area không còn hợp lệ.

NPD-02/06/07 bảo đảm MCP connection, tool catalog và credential thuộc đủ manager Scope. Grant inbound không thay thế MCP binding. Hai manager cùng area không chia sẻ tool/secret mặc định; tiêu thụ contract đã xác minh, không tự resolve partner route.

Các bổ sung này là kế hoạch cần triển khai, không phải xác nhận code hoặc test đã hoàn thành.


## Bổ sung bắt buộc theo kế hoạch 1.4 — API và sự kiện

Đọc mục 2.6–2.7, 5.3, 6.7 và toàn bộ mục 17 của [kế hoạch 1.4.3](../../KE_HOACH_TRIEN_KHAI.md). Giữ nguyên scope/mapping v1.3 và contract hai ticket/hộp chat v1.4.3. Mọi response có `workflow_state` + `next_action`: response-only read-only có thể auto-close; interactive dùng reply/approval/explicit close; external-tracking và Provider Event/SSE chỉ dùng khi operation pending. `202` chỉ là HTTP timeout fallback. V1 không có HTTP sender từ platform sang endpoint đối tác.

Owner Nguyễn Phương Đông bổ sung **NPD-10–NPD-12**: protocol sự kiện của MCP/provider, normalization và UI khả năng theo dõi trạng thái. Thực hiện cả task cũ còn thiếu và task mới; cập nhật STATUS.md, không đánh dấu hoàn thành từ scaffold.

- [ ] **NPD-10 — Registry protocol và continuation capability:** lưu effect read/write, terminal/pending result, operation correlation, Provider Event/status-query nếu có, event schema và completion policy theo tool snapshot. Phải biểu diễn tool sync không tracking, interactive approval và async tracking; không gắn protocol vào tên ngành. Metadata do integration cấu hình/validate, không nhận arbitrary URL trong prompt.
- [ ] **NPD-11 — Chuẩn hóa event và kiểm tra năng lực:** Triển khai AsyncProtocolPort, adapter deterministic normalize event, version/snapshot-vs-delta rules và capability coverage cho Builder/Lifecycle/Execution. Protocol drift hoặc MCP bị tắt không sửa snapshot của job đang theo dõi; tách khả năng nhận Provider Event API hợp lệ cho job cũ với quyền gọi tool mới. Không sở hữu HTTP provider ingress, inbox, credentials hoặc workflow state.
- [ ] **NPD-12 — UI và contract tests protocol:** integrations/event_channels/ hiển thị hỗ trợ tạo job/nhận Provider Event API/status-query MCP, trạng thái cấu hình và blocker; không hiển thị secret. tests/workforce/registry/event_protocols/ kiểm tra create-only, provider-event-ready, query-only, schema drift, namespace và normalization/order cases. Bàn giao fake protocol cho Nghĩa/Anh/Dũng ngay nhịp A.

Các thư mục v1.4 đã chuẩn bị cho bạn:

- [src/agentscope/app/workforce/registry/event_protocols/](../../../../src/agentscope/app/workforce/registry/event_protocols/README.md) — Protocol snapshots/capabilities và deterministic normalization; không nhận HTTP Provider Event request hoặc ghi inbox.
- [examples/web_ui/frontend/src/features/workforce/integrations/event_channels/](../../../../examples/web_ui/frontend/src/features/workforce/integrations/event_channels/README.md) — UI theo dõi readiness Provider Event API/MCP query/correlation, không quản lý SSE transport của Chí Hoàng.
- [tests/workforce/registry/event_protocols/](../../../../tests/workforce/registry/event_protocols/README.md) — Protocol schema/ordering/drift/capability tests.

Bắt đầu bằng đọc hợp đồng 17.3–17.4, viết logic và test với fake port thuộc module mình, rồi bàn giao signature/schema/hook request cho owner cung cấp. Các fake chỉ trong test/demo, production không trả thành công giả. Mỗi người làm trong branch/worktree riêng; migration/core/shared contracts chỉ Chí Hoàng sửa.
