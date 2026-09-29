# Bàn giao backend — App cư dân

**Trạng thái: đề xuất tích hợp v0.1, chưa phải contract đã được các team phê duyệt.**
Tài liệu đối chiếu với code tại thời điểm viết sau khi merge nhánh nhân viên,
commit nền `fea244d`. Không có backend cư dân được tạo bởi bộ tài liệu này.

## Đọc theo thứ tự

| Tài liệu | Người đọc / mục đích |
|---|---|
| [01 — Nghiệp vụ và dữ liệu](01-business-and-data.md) | BE lead, domain team: hiểu flow, ownership, status và mapping ERD |
| [02 — API contract đề xuất](02-api-contract.md) | BE/FE: endpoint, JSON, lỗi, auth, upload, retry và concurrency |
| [OpenAPI cốt lõi](resident-api.openapi.yaml) | BE/QA: mô tả máy đọc được cho hồ sơ, ảnh, tạo/theo dõi/xác nhận/xử lý lại |
| [03 — Tích hợp và nghiệm thu](03-integration-and-acceptance.md) | Team triển khai: vị trí code, thứ tự công việc, FE cần sửa, acceptance tests |

Các quyết định chưa chốt được đánh dấu **Cần chốt**. Đội BE không nên suy ra rằng
database, auth, API hoặc chatbot production đã có chỉ vì UI đang thao tác được.

## Sản phẩm cần đạt được

Cư dân dùng hai tab: **Trợ lý** và **Tiện ích**. Chat là nơi hỏi thông tin và soạn
phản ánh; chỉ thao tác **Gửi phản ánh** mới gửi business command tạo hồ sơ.
Thông tin sau đó đi vào hàng đợi nhân viên, được xử lý, QC và trả kết quả cho cư dân.

```text
Cư dân → Xác nhận phản ánh → API cư dân → Intake/Case dùng chung
                                            ↓
Nhân viên ← Hàng đợi tiếp nhận ← Incident / Task / WorkOrder
                                            ↓
Cư dân ← API trạng thái / thông báo ← Kết quả công khai sau QC
   ↓
Xác nhận hoàn tất hoặc yêu cầu kiểm tra lại
```

## Hiện có và còn thiếu

| Hạng mục | Hiện tại | BE cần cung cấp |
|---|---|---|
| Danh tính/căn hộ | Một hồ sơ mẫu trong `src/mocks/seed.ts` | User xác thực, tenant, membership và căn hộ có quyền |
| Chat | Hàm `reply()` nhận diện từ khóa, state trên trình duyệt | P0 giữ soạn draft ở FE; chatbot có ngữ cảnh/AI là bước riêng |
| Tạo phản ánh | `submitDraft()` tạo ID local và sửa state | API transactional, ID thật, idempotency, ảnh và intake nhân viên |
| Danh sách/chi tiết | Đọc `ResidentState.requests` | API scoped, phân trang, tìm kiếm và timeline công khai |
| Xác nhận/xử lý lại | `resolveRequest()` sửa state local | Command có kiểm tra actor, version, trạng thái và resolution revision |
| Ảnh | Data URL, thu nhỏ, lưu localStorage | Upload thật vào private storage; file ownership và đọc có kiểm quyền |
| Thông báo | Suy ra từ event cuối của mỗi yêu cầu | P0 vẫn suy ra; thông báo bền vững/read state/push là P1 |
| Tiện ích/nội quy/danh bạ | Nội dung minh họa hoặc chưa công bố | Nội dung được BQL duyệt; không suy đoán giờ mở cửa/số điện thoại |
| Nhân viên | Mock/localStorage riêng | Dùng cùng application services và dữ liệu với API cư dân |

Backend chung đặt trong Hono server hiện tại. **Không yêu cầu tạo backend service mới
cho từng app.** Hai app vẫn giữ code riêng, không import component/hook của nhau.

## Phạm vi giao hàng

**P0:** một flow thật xuyên suốt cư dân → tiếp nhận → nhân viên xử lý → QC → cư dân xác nhận,
kèm upload, phân quyền, retry, version và xử lý lỗi.

**P1:** trao đổi theo yêu cầu, conversation server-side/AI, notification feed/read state,
cập nhật realtime, nội dung tòa nhà và danh mục tiện ích có quản trị.
P1 cần API và phần UI bổ sung; không mặc định đã có trong frontend.

**Ngoài phạm vi hiện tại:** thanh toán, hóa đơn, đặt chỗ tiện ích, đăng ký khách,
biểu quyết cư dân, voice input và tự động điều phối bởi AI.

## Tài liệu nguồn có thẩm quyền

- [ERD Vinhomes](../../docx/02_VINHOMES_DOMAIN_ERD.md): các entity và quan hệ nghiệp vụ.
- [Kiến trúc hệ thống](../../docx/04_SYSTEM_DESIGN_STRUCTURE_ARCHITECTURE.md).
- [Quy ước team](../../docs/architecture/TEAM_GUIDE.md): transaction, RequestContext, boundaries.
- [RequestContext](../../shared/platform/context.ts): tạo từ middleware tin cậy.
- [Router Vinhomes hiện tại](../../server/src/domains/vinhomes/routes.ts): chưa có use case.
- [OpenAPI domain hiện tại](../../docs/contracts/domains/vinhomes.openapi.yaml): `paths: {}`.
- [View model FE cư dân](../src/services/types.ts), [adapter demo](../src/services/resident-service.ts).
- [Mock nghiệp vụ nhân viên](../../app/src/features/vinhomes-operations/hooks/use-operations-data.ts).

Khi thống nhất contract, đưa API chuẩn vào `docs/contracts/domains/vinhomes.openapi.yaml`
và DTO thuần vào `shared/domains/vinhomes/` trong cùng PR với producer/consumer.
Sau đó chuyển file OpenAPI đề xuất tại đây thành đường dẫn tham chiếu hoặc sinh từ nguồn
chuẩn, tránh duy trì hai contract độc lập.
