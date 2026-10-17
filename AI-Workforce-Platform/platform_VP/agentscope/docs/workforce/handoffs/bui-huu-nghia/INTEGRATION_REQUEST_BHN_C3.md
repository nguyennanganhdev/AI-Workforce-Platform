# Điểm nối và lưu ý bàn giao — BHN C3

Ngày **2026-10-11**. Owner: **Bùi Hữu Nghĩa**. Baseline `67ff871`.
Phạm vi theo [trình tự chung](../PHASE_C_SEQUENCE.md): Protocol validation ↔ Builder.
Tài liệu nằm trong repo, chưa gửi thông báo cho thành viên khác.

## Đầu vào C3

| Đầu vào | Trạng thái |
|---|---|
| C1 UOW/database, identity boundary | Có trong baseline; SQL tests dùng canonical UOW C1 |
| C2 protocol provider/exact resolver | Đã dùng thật trong selector/proposal/pre-write validation tests |
| Requirements/ports/validator Phase B | Đã có; tái sử dụng, không cần output C5 |

**Không còn request bổ sung làm blocker implementation/test C3 hẹp.** Provider
tool catalog/reuse/policy được inject qua hợp đồng hiện có; test doubles được
khai báo trong handoff. C3 không triển khai toàn bộ luồng Builder production.

## C7 — Hook để composition dùng sau khi C3 review/merge

- Nghĩa export `RegistryProtocolReadiness`, `RegistryCapabilitySelector` và
  `ProtocolBuildValidator`; signatures/examples tại [PHASE_C_C3.md](PHASE_C_C3.md).
- Root resolve/check active membership bằng C1, bind protocol port C2 đúng Scope
  request. Không nhận Scope/selection/confirmation từ body làm bằng chứng.
- Inject selector vào ProposalService Phase B. Caller chỉ gọi pre-write hook
  với item server-held đã confirm đúng revision và manifest từ đường build server.
- Caller phải chặn khi exception hoặc `report.valid == False` trước canonical
  DraftPort create/update. Hook không dispatch draft hoặc mở transaction riêng.
- Không có metadata/DDL Builder mới trong thay đổi C3 đã thu gọn. Migration,
  HTTP/auth/UI/root wiring thuộc C7, không chuyển thành task Nghĩa trong C3.

## Lưu ý contract hiện hữu, không cản bàn giao C3

- Đông/Chí Hoàng: disabled protocol và wrong Scope đều trả PermissionError;
  Builder fail closed. Ref chưa expose head revision nên không tuyên bố atomic
  CAS protocol-check + draft write. Typed errors/revision API cần owner chốt
  nếu bước tích hợp sau yêu cầu, không tự đổi shared contract.
- Anh/Đông: query-only thiếu event/fact semantics và create-only pending bị
  block theo hợp đồng hiện có. Không tự thêm polling/policy để qua gate. Nới
  hành vi cần quyết định contract ở bước sau, không bắt C3 chờ C5.
- Anh: Lifecycle legacy test `test_builder_query_only_dialect_explicit` fail
  trên cả baseline; chi tiết trong handoff. Không sửa test Anh trong nhánh Nghĩa.

## Các request rộng trước đây đã bỏ khỏi C3

Canonical policy writer/profile, concrete Draft/Reuse/Batch providers, full
generation/session persistence, idempotency/reconciliation draft và full
API/UI production không nằm trong gate C3 này. Không tiếp tục triển khai chúng
trong lượt được giới hạn C3, không yêu cầu các owner bàn giao chúng trước C3.

Thay đổi C3 được review/bàn giao với phạm vi thật/fake và các giới hạn trên;
không đồng nghĩa toàn BHN-01–14 hoặc Phase D hoàn thành.
