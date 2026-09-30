# 03 — Kế hoạch tích hợp và tiêu chí nghiệm thu

## 1. Vị trí triển khai BE

Theo repository hiện tại, giữ Hono server chung và composition root `server/src/app.ts`.

| Vùng code | Công việc |
|---|---|
| `server/src/domains/vinhomes/routes.ts` | Mount router resident dưới `/resident` |
| `.../context/`, `.../property/` | Map auth actor sang tenant, membership, dự án/căn hộ |
| `.../cases/`, `.../intake/` | Tạo Case/inbound submission, triage, mapping report/Incident |
| `.../incidents/`, `.../tasks/`, `.../work-orders/`, `.../qc/` | Tái sử dụng service cho nhân viên và projection kết quả |
| `.../evidence/` | File metadata, upload/read authorization và bind ảnh |
| `.../events/` | Public timeline, outbox và consumer idempotent |
| `server/src/db/schema/domains/vinhomes/` | Schema/migrations do domain sở hữu, dùng cơ chế Drizzle hiện có |
| `shared/domains/vinhomes/` | DTO thuần sau khi chốt contract; không import Hono/ORM/React |

Các thư mục trên phần lớn vẫn là khung/README. Không giả định có repository/service
sẵn để gọi. `resident-services/` hiện định hướng booking/invoice; không dồn toàn bộ
intake, QC và evidence vào đó vì có chữ “resident”.

Router parse/validate → application service kiểm quyền và rule → repository/persistence.
Service sở hữu transaction; API resident và staff gọi cùng nghiệp vụ. UI không import backend.
Không tạo backend thứ hai chỉ để đọc các bản localStorage từ hai app.

## 2. Những thay đổi FE bắt buộc khi nối API

| Hiện tại | Chuyển sang |
|---|---|
| `mocks/seed.ts` cung cấp user/căn hộ | `GET /me`, loading/empty/error và chọn căn hộ có quyền |
| `loadState/saveState` chứa mọi dữ liệu | Query/cache API cho hồ sơ; local chỉ giữ draft theo user/căn hộ nếu chính sách cho phép |
| `reply()` tìm yêu cầu trong state local | Intent xem tiến độ gọi API list/detail; không dùng snapshot local làm nguồn thật |
| `submitDraft()` đồng bộ | Upload ảnh → POST request có key → cập nhật cache từ server |
| `resolveRequest()` đổi state tại client | POST confirm/reopen với version + resolutionRevision rồi refresh list/detail |
| `App.commit()` save trước setState | Async mutation có pending/error, chống double submit và retry có key |
| `Photo.url` bắt buộc là data URL trong validator | Tách `LocalPhoto` và `RemotePhoto`; không đưa response server qua validator localStorage hiện tại |
| Một `ResidentRequest` cho cả list/detail | Tách summary/detail DTO, thêm code/version/permissions/resolution |
| Notification lấy event cuối trong state | P0 thông tin từ request API, ghi rõ phạm vi; P1 feed notification riêng |
| Nút reset gọi initialState | Chỉ tồn tại ở demo mode; production không seed hoặc xóa hồ sơ server |

Frontend hiện chưa có login cho cư dân, proxy backend, HTTP client production,
pagination, polling, public-message UI hoặc xử lý quyền căn hộ thật.
Không thể chỉ đổi một URL trong `resident-service.ts` rồi coi như đã tích hợp xong.

Ví dụ interface client đề xuất (tài liệu, chưa phải code đang export):

```ts
interface ResidentApi {
  me(): Promise<ResidentProfile>;
  uploadPhoto(input: { file: File; apartmentId: string; key: string }): Promise<UploadedPhoto>;
  listRequests(query: RequestQuery): Promise<RequestPage>;
  getRequest(id: string, eventsCursor?: string): Promise<ResidentRequestView>;
  createRequest(input: CreateResidentRequest, key: string): Promise<ResidentRequestView>;
  confirm(id: string, input: ResolutionCommand, key: string): Promise<ResidentRequestView>;
  reopen(id: string, input: ReworkCommand, key: string): Promise<ResidentRequestView>;
}
```

Giao diện async nên có mock adapter riêng và HTTP adapter riêng với cùng contract.
Chọn adapter rõ ràng ở bootstrap; không tự fallback mock khi production API lỗi.
Biến như `VITE_RESIDENT_API_BASE_URL`/demo flag **chỉ là đề xuất**, chưa có trong code.

## 3. Thứ tự giao việc

### Bước 1 — Chốt contract và identity

- FE/BE/domain thống nhất mapping Case ↔ hồ sơ UI, endpoint, error và bốn status.
- Xác định nguồn tenant/membership và login flow cư dân, không dùng persona demo làm auth.
- Chốt schema bổ sung cho confirmation theo Case/report, resolution revision, file links.
- Chuẩn hóa OpenAPI/DTO về nguồn chung; tạo migration có thứ tự và tests scope.

**Đầu ra:** `GET /me` thật và tài khoản test thuộc ít nhất hai tenant/dự án, hai căn hộ.

### Bước 2 — Nhận yêu cầu thật

- Upload ảnh vào storage; metadata/private read/cleanup orphan.
- `POST /requests` có transaction/idempotency; `GET` list/detail có scope và pagination.
- Endpoint intake cho nhân viên đọc cùng Case vừa tạo, không copy mock.
- FE chuyển flow soạn → review → submit sang API; giữ draft khi lỗi.

**Đầu ra:** cư dân trên thiết bị A gửi; nhân viên trên thiết bị B thấy ngay khi tải danh sách.

### Bước 3 — Kết quả xuyên suốt

- Nhân viên triage, tạo/link Incident, Task, WorkOrder bằng domain services thật.
- Upload evidence thi công và QC; publish kết quả công khai theo Case.
- Projection status và timeline cư dân phản ánh tiến độ thực tế.
- Confirm/reopen có version/revision; staff nhận phản hồi kiểm tra lại.

**Đầu ra:** một sự cố được xử lý và cư dân xác nhận; một sự cố bị phản hồi chưa đạt
đi vào điều phối lại, không mất lịch sử.

### Bước 4 — Hoàn thiện P1

- Trao đổi theo hồ sơ, unread state/notification và thông tin tòa nhà có quản trị.
- Chatbot có knowledge/AI nếu cần; trace/timeout/fallback có cấu trúc.
- Realtime chỉ sau khi flow polling/authorization ổn định; không bắt buộc WebSocket ở P0.

## 4. Checklist nghiệm thu P0

| Nhóm | Tình huống | Kết quả phải có |
|---|---|---|
| End-to-end | Cư dân gửi trên browser A, nhân viên xem browser B | Cùng Case ID, dữ liệu server; không phụ thuộc localStorage/browser |
| Intake | Chat hỏi tiện ích, đóng draft hoặc chưa bấm gửi | Không tạo Case/Incident ngoài ý muốn |
| Validation | Thiếu mô tả/vị trí, field actor giả, quá 3 ảnh | Từ chối; không có bản ghi nghiệp vụ dở dang |
| Retry | Server commit rồi client mất mạng, gửi lại cùng key | Một Case duy nhất, cùng receipt |
| Retry | Cùng key khác payload | 409, không ghi đè hồ sơ cũ |
| Concurrency | Hai thiết bị confirm và reopen cùng version | Một command thắng; bên còn lại 409 |
| Version | Kết quả thay đổi sau khi cư dân mở trang | Không xác nhận nhầm resolution revision cũ |
| Permissions | Đổi ID thành Case/ảnh của người khác hoặc tenant khác | Không rò dữ liệu ở list/detail/search/ảnh/replay |
| Membership | Căn hộ không còn quyền trước submit | Server từ chối, không tin lựa chọn đã cache |
| Scope | Hai người cùng căn hộ, policy mặc định chỉ người gửi | Không tự thấy hồ sơ của nhau |
| Shared incident | Hai Case khác cư dân gắn cùng Incident | Xác nhận A không tự hoàn tất B, không lộ thông tin B |
| Multi-issue | Một Case có hai Incident, chỉ một đã QC PASS | Case không chuyển chờ xác nhận/hoàn tất sớm |
| QC | Thi công completed nhưng thiếu QC bắt buộc | Không phát hành quyền cư dân xác nhận |
| Rework | Cư dân phản đối, nhập lý do hợp lệ | Lưu phản hồi; trạng thái processing; staff thấy việc cần kiểm tra |
| Rework | Reopen một Case đã completed | 409 theo P0, không tự mở lại |
| Evidence | MIME giả, ảnh hỏng/quá lớn, file ID ngoài scope | Từ chối có mã lỗi; không tạo ready giả |
| Evidence | Upload thành công, tạo Case thất bại | File orphan được cleanup theo policy |
| Evidence | Ảnh đã bind, reload/URL hết hạn | Lấy URL mới và xem được, cleanup không xóa ảnh đang dùng |
| Failure | DB/object storage/outbox gặp lỗi | Không báo success giả; transaction/compensation đúng |
| Events | Consumer nhận cùng event hai lần | Không nhân đôi tác vụ/thông báo |
| Visibility | Event nội bộ có chi phí/ghi chú/cư dân khác | API resident chỉ trả projection đã lọc |
| Pagination | Nhiều trang request/event, có bản mới xen vào | Cursor ổn định, không rò scope; FE de-duplicate theo ID |
| Session | Logout/login người khác trên cùng máy | Xóa cache theo user; không hiện ảnh/hồ sơ/draft của người trước |
| FE error | Upload lỗi hoặc request timeout | Giữ nội dung đang soạn, có retry, không tạo mã giả |
| Mobile | 320/390/430 px và bàn phím đang mở | Không tràn ngang; gửi ảnh, xem kết quả, retry thao tác được |

Tests hiện có của frontend là demo/unit/browser checks, **chưa bao phủ** transaction,
auth đa tenant, concurrency thật, object storage hoặc flow hai app qua server.

## 5. Phối hợp với team nhân viên

1. Không dùng `app/.../use-operations-data.ts` làm backend hoặc import vào resident app.
   Tách rule cần dùng chung sang application services trong domain rồi mỗi FE gọi API.
2. Thống nhất field công khai cho cư dân và field nội bộ. Đặc biệt stage/label ở mock UI
   không mặc nhiên là enum canonical trong ERD.
3. Hiện phía nhân viên đổi một số data URL ảnh lớn thành URL storage tự ghép khi persist.
   Khi tích hợp phải thay bằng upload thật, không lấy đường dẫn giả làm bằng chứng đã lưu.
4. Hiện `residentConfirmIncident()` nằm trong mock phía nhân viên. Backend cần confirmation
   gắn actor cư dân và Case/report scope; không bê nguyên setter toàn Incident cho một cư dân.
5. Dùng fixture xuyên suốt: một Case nhiều vấn đề, hai Case chung một Incident,
   một WorkOrder QC FAIL/redo, một kết quả chờ cư dân và một membership hết hiệu lực.

## 6. Các quyết định cần chốt trước production

| Quyết định | Owner đề xuất | Mặc định của bản nháp |
|---|---|---|
| Visibility trong hộ gia đình | Product + domain + identity | Chỉ người gửi |
| Membership sau chuyển nhà | Domain + identity | Không mở thêm quyền; cần policy lịch sử rõ ràng |
| Đóng tự động khi cư dân im lặng | BQL + domain | Không tự đóng |
| Case bị từ chối/trùng/hủy | Product + domain + FE | Chưa hỗ trợ command/status riêng ở API cư dân P0 |
| Xác nhận nhiều report chung Incident | Domain | Ghi nhận riêng từng Case; domain quyết định đóng Incident |
| Retention ảnh/idempotency/audit | Vận hành + data owner | Orphan 24 giờ, receipt ít nhất 7 ngày là đề xuất, cần phê duyệt |
| Upload sync hay scan async | BE + vận hành | P0 chỉ trả ảnh ready; async cần bổ sung contract |
| Chọn session/cross-origin deployment | BE + DevOps | Reuse auth; ưu tiên same-origin proxy |
| Chat/knowledge provider | Platform + domain | P0 không phụ thuộc LLM |

## 7. Định nghĩa hoàn thành

P0 hoàn thành khi flow ở bước 2–3 chạy với API/database/storage thật trên hai phiên
đăng nhập độc lập, kiểm thử quyền/retry/concurrency đạt, migration chạy được ở môi trường
test, OpenAPI chuẩn khớp implementation, và FE không còn dùng mock success trên đường production.
Backend health trả 200 hoặc UI demo chạy được chưa đáp ứng tiêu chí này.
