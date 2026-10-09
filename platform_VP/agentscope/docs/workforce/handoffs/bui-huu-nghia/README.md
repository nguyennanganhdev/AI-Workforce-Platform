# Bàn giao — Bùi Hữu Nghĩa

Branch đề xuất: `feat/wf-builder`. Đầu việc: **BHN-01–BHN-14**.

Phạm vi: chat tạo một/nhiều agent độc lập, phát hiện trùng, chọn tool và sinh manifest từng agent.

[Kế hoạch và hợp đồng chung](../../KE_HOACH_TRIEN_KHAI.md) là tài liệu đầu vào cho AI. Gửi cả file kế hoạch và nói rõ: “Tôi là Bùi Hữu Nghĩa”.

Khi triển khai, tạo `STATUS.md` theo mẫu ở mục 16. Mỗi yêu cầu đổi contract/hook/file chung ghi vào `INTEGRATION_REQUEST_<task-id>.md` theo mục 14.

Hiện tại chưa có task được đánh dấu hoàn thành; việc tạo thư mục này không chứng minh module đã được code/test.

Nguyên tắc batch của bản 1.2 được giữ ở bản 1.3: BHN-02/04/05/08–BHN-11 tạo một hoặc nhiều agent độc lập vào thư viện chung; batch chỉ theo dõi tiến độ/reuse. Builder không tạo roster/group production hay prompt phụ thuộc đồng đội cùng batch. Đọc mục 2.3, 2.5 và 6 của kế hoạch trước khi code; nội dung này thay thế cách hiểu team artifact ở bản trước. Đây là đầu việc cần triển khai, chưa phải tính năng đã hoàn thành.

## Cập nhật bắt buộc theo kế hoạch 1.3

Giữ một role `AREA_MANAGER` và chọn domain/area. Scope là `(tenant_id, domain_id, area_id, manager_account_id)`; partner request phải resolve mapping/grant tới đúng tài khoản đích trước khi chạy Leader, không broadcast theo area. Actor đối tác/cư dân không phải owner platform. Đọc mục 2.6 và hợp đồng mục 6; chỉ dẫn cũ yêu cầu bỏ domain/area không còn hợp lệ.

BHN-01/03/06/09 chỉ build/chọn tool/KB/reuse trong manager Scope. Hai tài khoản cùng area có cùng nghiệp vụ vẫn được tạo agent riêng. Partner request là runtime, không cấp quyền build/publish và không đổi owner theo nội dung chat.

Các bổ sung này là kế hoạch cần triển khai, không phải xác nhận code hoặc test đã hoàn thành.


## Bổ sung bắt buộc theo kế hoạch 1.4 — API và sự kiện

Đọc mục 2.6–2.7, 5.3, 6.7 và toàn bộ mục 17 của [kế hoạch 1.4.3](../../KE_HOACH_TRIEN_KHAI.md). Giữ nguyên scope/mapping v1.3 và contract hai ticket/hộp chat v1.4.3. Mọi response có `workflow_state` + `next_action`: response-only read-only có thể auto-close; interactive dùng reply/approval/explicit close; external-tracking và Provider Event/SSE chỉ dùng khi operation pending. `202` chỉ là HTTP timeout fallback. V1 không có HTTP sender từ platform sang endpoint đối tác.

Owner Bùi Hữu Nghĩa bổ sung **BHN-12–BHN-14**: Builder hiểu yêu cầu theo dõi dài hạn, chọn năng lực async và tái sử dụng agent. Thực hiện cả task cũ còn thiếu và task mới; cập nhật STATUS.md, không đánh dấu hoàn thành từ scaffold.

- [ ] **BHN-12 — Nhận diện nghiệp vụ chờ trạng thái:** builder/async_capabilities/ phân biệt chỉ tạo công việc với theo dõi tới hoàn tất/xác nhận đóng. Sinh requirement/AsyncHandlingPolicy qua structured output, hỏi phần thiếu theo nhu cầu; không nhét workflow/job/URL bên ngoài/roster cụ thể vào manifest.
- [ ] **BHN-13 — Binding và reuse có async capability:** Dùng AsyncProtocolPort + RegistryPort + AgentReusePort kiểm tra create và receive-status/status-query, correlation, completion/timeout policy; không cam kết theo dõi nếu chỉ có tool create. Thiếu bắt buộc thì MISSING_REQUIRED_CAPABILITY; chỉ giảm phạm vi khi người dùng đồng ý. Agent cũ đủ thì reuse, thiếu khả năng theo dõi thì đề xuất revise cùng identity, không clone agent chỉ để chờ event.
- [ ] **BHN-14 — UI và test lifecycle capability:** trình bày response-only/interactive/external-tracking support, effect, completion/close policy và Event/status-query chỉ khi cần. Test tool tra cứu sync không bị đòi event channel, booking confirmed không bị ép polling, booking pending cần tracking, reuse/revise và batch không sinh production job. Không hardcode domain.

Các thư mục v1.4 đã chuẩn bị cho bạn:

- [src/agentscope/app/workforce/builder/async_capabilities/](../../../../src/agentscope/app/workforce/builder/async_capabilities/README.md) — Requirements và sinh policy theo dõi; reuse/revise, missing capability.
- [examples/web_ui/frontend/src/features/workforce/builder/async_capabilities/](../../../../examples/web_ui/frontend/src/features/workforce/builder/async_capabilities/README.md) — Hiển thị phạm vi theo dõi và blocker trong đề xuất build.
- [tests/workforce/builder/async_capabilities/](../../../../tests/workforce/builder/async_capabilities/README.md) — Create-only vs tracking, fake ports và chống sinh workflow lúc build.

Bắt đầu bằng đọc hợp đồng 17.3–17.4, viết logic và test với fake port thuộc module mình, rồi bàn giao signature/schema/hook request cho owner cung cấp. Các fake chỉ trong test/demo, production không trả thành công giả. Mỗi người làm trong branch/worktree riêng; migration/core/shared contracts chỉ Chí Hoàng sửa.

