# Báo cáo Q02 (đợt 6) — Tool đề nghị cô lập nước/điện và rào chắn khu vực

- **Người làm:** Phạm Thành Đạt (Team Quang).
- **Ngày:** 01/10/2026.
- **Task:** Q01 (danh mục tool) và Q02 (tool kỹ thuật), đợt 6.
- **Trạng thái:** xong 12 trong 14 tool. Còn `apartment_entry.request` và `vendor_dispatch.request`. Tool vẫn chưa gọi được từ server đang chạy vì chưa được nối vào `createApp` (việc của Team Chiến).
- **Các đợt trước:** [đợt 1](Q02-outage-schedule-tools.md), [đợt 2](Q02-sop-asset-tools.md), [đợt 3](Q02-sensor-history-tools.md), [đợt 4](Q02-measurement-result-tools.md), [đợt 5](Q02-verify-append-tools.md).

## 1. Đã xây gì

| Tool | Làm gì | Lưu ở đâu | Đặc tả |
|---|---|---|---|
| `utility_isolation.request` | Đề nghị khóa nước / cắt điện trên các phạm vi đã nêu, trong một khung giờ | **Nước:** bảng thật, một transaction: `work_approvals` (`management_water_shutdown`, `pending`) + `service_interruptions` (`proposed`) + `interruption_scopes`. **Điện:** adapter phê duyệt POC | `tools.md` §6.1 |
| `area_restriction.request` | Đề nghị rào chắn một khu vực có nguy hiểm | Adapter phê duyệt POC | `tools.md` §6.2 |

Cả hai luôn trả **`PENDING_APPROVAL`**. Không van nào đóng, không cầu dao nào ngắt, không cửa nào khóa vì một lời gọi tool.

Kèm theo:

- **Adapter ghi DB đầu tiên** ([adapters/db/isolation-writer.ts](../../../../server/src/technical-tools/adapters/db/isolation-writer.ts)): ghi 3 bảng trong một transaction, tự sinh id nên không cần đọc lại.
- **Adapter đọc phạm vi** (`createDbScopeReadPort`): tòa nhà thuộc zone/site nào, và mỗi `scope_id` là vùng nào.
- **Adapter phê duyệt chung, POC** ([adapters/poc/approval-request-store.ts](../../../../server/src/technical-tools/adapters/poc/approval-request-store.ts)): chỉ có `create` và `listOpen`, **không có hàm duyệt**.
- `WorkOrderReadPort` có thêm `getTicket`.

## 2. Quyết định thiết kế và lý do

Câu hỏi xuyên suốt đợt này: *có cách nào để một đề nghị trở thành hành động mà không qua người phê duyệt không?* Mỗi quyết định dưới đây đóng một đường.

### 2.1. Ba lớp chặn tự phê duyệt

| Lớp | Cách chặn |
|---|---|
| Hợp đồng | Input `strict`: không có trường `status`, `approval_status`, `approved_by`, `execute_now`. Output chỉ nhận `approval_status: "PENDING_APPROVAL"` |
| Code | Adapter ghi luôn đặt `pending` / `proposed`; kho phê duyệt POC không có hàm duyệt |
| Database | Role của tool chỉ được **INSERT**, không được **UPDATE/DELETE** `work_approvals`, `service_interruptions`, `interruption_scopes`. Test chứng minh bằng `permission denied` |

Lớp database là lớp quan trọng nhất: kể cả khi agent bị prompt injection, hay một lỗi code nào đó cố đổi trạng thái, database vẫn từ chối.

Lý do viết "quản lý đã đồng ý qua điện thoại, cắt ngay" vẫn chỉ tạo đề nghị `pending` (ca L1-31).

### 2.2. Đề nghị không phải là sự thật

Interruption mới ghi ở trạng thái `proposed`. Các tool đọc (`technical.get_active_outage`, `utility_schedule.read`) từ đợt 1 đã không coi `proposed` là lịch cắt chính thức. Test bẫy L3: ngay sau khi tạo đề nghị khóa nước lúc 08:30–10:00, hỏi "lúc 08:59 có cắt nước không" → **không** thấy đề nghị đó. Nếu thấy, bot sẽ nói với cư dân rằng nước đã bị khóa trong khi nước vẫn chảy.

### 2.3. Phạm vi: chỉ vùng chứa chính tòa nhà

Một đề nghị cho tòa A1 chỉ được nhắm tới **tòa A1, zone của nó, hoặc site của nó**. Bị từ chối (`CONFLICT`): tòa bên cạnh (A2), zone khác, tòa của tenant khác, **cả tenant** (đó là một tổ chức, không phải một nơi có van để khóa), scope không tồn tại.

**Người duyệt = phạm vi rộng nhất** trong đề nghị. Đề nghị cắt cả zone S1 thì người duyệt phải có thẩm quyền trên cả zone, không phải chỉ quản lý tòa A1 nơi phát sinh sự cố.

### 2.4. Không tạo đề nghị trùng

Đã có đề nghị cùng loại (nước/điện), cùng work order, chưa `cancelled`/`restored`, và trùng khung giờ → `CONFLICT`, nêu id đề nghị cũ. Rào chắn: đã có đề nghị đang chờ cho cùng sự cố, cùng khu vực (so sau khi bỏ hoa thường, dấu, khoảng trắng, dấu câu) → `CONFLICT`.

**Lý do:** người duyệt nhìn thấy một đề nghị cho mỗi vấn đề, không phải một đề nghị cho mỗi lượt agent trả lời. Gửi lại do mất mạng thì dùng cùng `idempotency_key` và nhận lại đúng đề nghị cũ.

### 2.5. Nhánh điện không vào `work_approvals`

Database chưa có `kind` phê duyệt cho cắt điện, mà `service_interruptions.approval_id` **bắt buộc** trỏ tới một dòng `work_approvals`. Mượn `customer_repair` thì đề nghị cắt điện cả nhánh sẽ được gửi tới **cư dân** để duyệt. Vì vậy cả approval lẫn interruption `proposed` của điện nằm trong adapter POC, đúng như `tools.md` §6.1 và §8 mục 13 cho phép. Có test xác nhận số dòng `work_approvals` không đổi sau đề nghị cắt điện.

### 2.6. Ghi nguyên tử

Ba bảng ghi trong một transaction. Hai test DB làm lệnh ghi thứ 2 và thứ 3 thất bại (interruption trùng id, scope không tồn tại) và xác nhận **không còn approval nào sót lại**. Một approval mồ côi là một đề nghị khóa nước đang chờ duyệt mà không ai thấy được nó ảnh hưởng tới đâu.

### 2.7. Điều kiện khác

| Kiểm tra | Sai thì |
|---|---|
| `planned_end` sau `planned_start` (so theo thời gian, không theo chữ) | `INVALID_INPUT` |
| `planned_end` đã qua | `INVALID_INPUT` |
| Work order trong tòa | `NOT_FOUND` như nhau dù ở tòa khác hay không tồn tại |
| `incident_id` là ticket của work order | `CONFLICT` |
| Người đề nghị cắt là kỹ thuật viên đang nhận work order, hoặc `management` | `FORBIDDEN` |
| Ảnh đã đăng ký, còn hiệu lực, cùng ticket (ảnh đang tải bị từ chối) | `CONFLICT` |
| Rào chắn: `requested_until` ở tương lai, tối đa 7 ngày | `INVALID_INPUT` |
| Rào chắn: ticket trong tòa; work order (nếu có) thuộc ticket | `NOT_FOUND` / `CONFLICT` |

Ai có capability `area_restriction:request` và quyền với tòa đều đề nghị rào chắn được, không cần thuộc work order: ai thấy nguy hiểm cũng phải báo được.

## 3. Dữ liệu mẫu

Không seed thêm. Dùng lại 5 work order, ảnh, cây phạm vi (site Ocean Park → zone S1 → A1, A2; zone S2 → B1; tòa X1 của tenant khác) và 10 interruption mẫu.

**DB riêng cho test ghi:** PGlite trước đây dùng chung một instance cho mọi file test. Vì đợt này ghi thật, `technicalToolsTestDatabase({ isolated: true })` tạo một instance riêng cho file test ghi, để không làm lệch số đếm mà các test đọc cũ kiểm tra (ví dụ "tenant thấy đúng 9 interruption"). Trên PostgreSQL mỗi file vốn đã có database riêng.

### Ca theo mức độ bẫy (`request.flow.test.ts`)

| Mức | Ca |
|---|---|
| **Level 3** | L3-20 khóa nước 1 giờ → `PENDING_APPROVAL`, DB có approval `pending` + interruption `proposed`; L3-21 rào hành lang sàn ướt; L3-22 gửi lại sau mất mạng chỉ 1 dòng; bẫy: đề nghị không hiện là đang cắt nước |
| **Level 2** | L2-24 trùng giờ cùng work order → nêu đề nghị cũ; giờ kế tiếp không trùng thì được; L2-25 khung giờ đã qua; L2-26 cắt cả zone → người duyệt cấp zone; L2-27 ảnh đã rút + ảnh ticket khác; L2-28 rào trùng khu vực (viết khác kiểu); tầng khác là khu vực khác; L2-29 quá 7 ngày |
| **Level 1** | L1-29 cầu dao tóe lửa → cắt điện qua adapter, không vào `work_approvals`; đề nghị điện trùng giờ; L1-30 input tự nhận đã duyệt (4 biến thể); L1-31 lý do "quản lý đã đồng ý"; L1-33 phạm vi sai (5 biến thể); L1-34 ảnh đang tải; L1-36 hai lời gọi cùng khóa cùng lúc; L1-37 kỹ thuật viên không thuộc work order; L1-38 rào chắn tòa ngoài quyền / ticket lạ / work order của sự cố khác / ảnh của sự cố khác |

L1-32 (role thử UPDATE) và L1-35 (ghi lỗi giữa chừng) nằm ở test DB.

## 4. Kiểm thử

**748 test trong `server/tests/technical-tools/`, tất cả đều qua** (đợt trước 651, đợt này thêm 97).

| File | Số test | Kiểm tra |
|---|---|---|
| `request.rules.test.ts` | 18 | Phạm vi chứa tòa; phạm vi rộng nhất; trùng khung giờ; so khu vực; giới hạn 7 ngày |
| `request.contract.test.ts` | 21 | Hai ví dụ mẫu; trường bắt buộc; không trường nào nhận "đã duyệt"; output chỉ `PENDING_APPROVAL` |
| `approval-request-store.test.ts` | 4 | Kho POC: lọc theo tenant/loại/sự cố; không có hàm duyệt |
| `isolation-writer.db.test.ts` | 17 | Ghi 3 bảng đúng giá trị; nguyên tử (2 ca); RLS; role không UPDATE/DELETE được |
| `request.flow.test.ts` | 35 | Toàn bộ ca ở mục 3 qua `createTechnicalToolCaller` |

Cập nhật: `catalog.test.ts` (12 tool), harness, `host.test.ts`, `idempotency.test.ts`, `support/database.ts` (quyền INSERT, DB riêng).

Đã chạy trên hai môi trường:

- **PGlite**: 36 giây.
- **PostgreSQL 17** thật qua `TEST_DATABASE_URL`: 117 giây, cùng 748 test.

Đã thử cố ý phá năm quy tắc:

| Phá gì | Số test đỏ |
|---|---|
| Ghi interruption `approved` thay vì `proposed` | 6 |
| Bỏ kiểm tra phạm vi thuộc tòa | 5 |
| Ghi approval trong transaction riêng | 2 |
| Bỏ kiểm tra trùng khung giờ | 2 |
| Nhánh điện ghi vào `work_approvals` | 2 |

Lần đầu phá "approval transaction riêng" chỉ có 1 test đỏ; đã thêm ca interruption trùng id.

```
bun test server/tests/technical-tools
bun run --filter server typecheck
bunx biome check server/src/technical-tools server/tests/technical-tools
```

Cả ba lệnh đều sạch.

## 5. Giới hạn đã biết

- **Hai đề nghị trùng giờ, khác khóa, gửi đúng cùng lúc** có thể cùng lọt qua kiểm tra trùng (kiểm tra rồi mới ghi). Cùng khóa thì host đã chặn. Muốn chặn hẳn cần ràng buộc trong database (xem yêu cầu).
- **Khóa chống trùng và đề nghị nước không cùng transaction** (khóa ở bộ nhớ, đề nghị ở DB) — như đã nêu ở đợt 4.
- **Chưa ghi `work_approval_evidence`**: bảng này cần `sha256` của file, nằm ở `file_objects` mà role không được đọc. Ảnh hiện nằm trong `request_detail`.

## 6. Còn lại

- 2 tool: `apartment_entry.request`, `vendor_dispatch.request`.
- Yêu cầu tích hợp: [Q02-isolation-restriction.md](../requests/Q02-isolation-restriction.md).

## 7. Phạm vi thay đổi

Chỉ tạo và sửa file trong vùng của Team Quang: `server/src/technical-tools/**`, `server/tests/technical-tools/**`, `docs/teams/quang/**`. Không sửa schema, migration, `app.ts`, `index.ts`, `package.json` hay lockfile.
