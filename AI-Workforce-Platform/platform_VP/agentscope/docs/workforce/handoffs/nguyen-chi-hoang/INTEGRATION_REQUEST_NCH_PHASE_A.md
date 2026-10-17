# Integration requests sau Phase A — Nguyễn Chí Hoàng

Các output dưới đây **không chặn contract Phase A**. Chúng cần được chủ module bàn giao trước khi Nguyễn Chí Hoàng nối composition root, migration và runtime ở các phase sau. Không yêu cầu thành viên khác sửa `contracts/`; nếu cần thay đổi hãy ghi đề xuất và sample vào handoff của mình.

## Nguyễn Phương Đông — Registry

- Task liên quan: NPD-07, NPD-10, NPD-11.
- Cần bàn giao: chữ ký triển khai `RegistryPort` và `AsyncProtocolPort`; sample `ToolDescriptor`; protocol snapshot/version/hash; quy tắc normalize event và capability `create`, `receive_status`, `status_query`.
- Điều kiện tích hợp: normalize deterministic, không LLM; không trả credential secret; protocol đã pin không bị sửa khi MCP catalog thay đổi.

## Bùi Hữu Nghĩa — Builder

- Task liên quan: BHN-03, BHN-07, BHN-09, BHN-13.
- Cần bàn giao: schema requirement/capability mà Builder truyền cho Registry, Lifecycle; cách biểu diễn lựa chọn create/reuse/revise và async handling policy trong `AgentManifest`.
- Điều kiện tích hợp: thiếu tool/capability phải trả lỗi rõ; không tạo agent trùng nghiệp vụ; batch không tạo group/team artifact.

## Phó Tiến Anh — Lifecycle

- Task liên quan: PTA-04, PTA-09, PTA-11, PTA-13, PTA-15.
- Cần bàn giao: DTO thật cho draft/version/deployment (hiện port tạm trả `object` tại các aggregate chưa được chốt), schema publish selection và evaluation snapshot/report cuối cùng.
- Điều kiện tích hợp: auto-eval theo từng agent sau validate; publish chỉ khi hard gates đạt và người dùng xác nhận; agent fail không làm mất kết quả item khác trong batch.

## Phan Huy Hoàng — Orchestration

- Task liên quan: PHH-12–PHH-17.
- Cần bàn giao: DTO thật cho claim command/trigger/checkpoint/runtime turn (hiện một số port dùng `object` hoặc mapping ổn định tạm thời), transaction ordering và adapter `PartnerIngressPort`/`WorkflowPort`/`ConversationEventPort`.
- Điều kiện tích hợp: resolve binding trước Leader; reply của ticket A không chạy group B; POST timeout không tạo run thứ hai; event public chỉ đọc sau commit.

## Phan Hoàng Dũng — Execution

- Task liên quan: PHD-14–PHD-17.
- Cần bàn giao: DTO call/result cho `ExternalOperationPort`, provider inbox/receipt semantics, sample event duplicate/out-of-order/unknown và approval binding.
- Điều kiện tích hợp: persist operation/correlation trước network call; provider event không tự chọn manager/group; không lặp side effect khi retry.

## Cách đề xuất sửa contract

Mỗi owner ghi trong handoff của mình:

1. task ID và port/model cần đổi;
2. chữ ký cũ/mới;
3. JSON mẫu hợp lệ và lỗi;
4. invariants/test chứng minh;
5. migration hoặc compatibility impact.

Nguyễn Chí Hoàng sẽ tích hợp thay đổi dùng chung sau khi đối chiếu cả producer và consumer, tránh hai nhánh cùng sửa file contract.
