# Báo cáo Q02 — Hai tool gián đoạn điện nước của Technical Agent A2

- **Người làm:** Phạm Thành Đạt (Team Quang).
- **Ngày:** 30/09/2026.
- **Task:** Q01 (danh mục tool) và Q02 (tool kỹ thuật), phần đầu.
- **Trạng thái:** xong 2 trong 14 tool. Tool chưa gọi được từ server đang chạy vì chưa được nối vào `createApp` (việc của Team Chiến).

## 1. Đã xây gì

| Tool | Trả lời câu hỏi | Đặc tả |
|---|---|---|
| `technical.get_active_outage` | Đúng lúc sự cố xảy ra, tòa nhà có đang bị cắt điện/nước không? | `tools.md` §3.5 |
| `utility_schedule.read` | Trong một khoảng thời gian, tòa nhà có lịch cắt điện/nước nào? | `tools.md` §3.6 |

Cả hai chỉ đọc, dùng chung ba bảng đã có trong schema: `service_interruptions`, `interruption_scopes`, `access_scopes`.

Kèm theo là phần nền mà 12 tool còn lại sẽ dùng lại: khuôn response, host kiểm tra quyền, cửa nối vào server, danh mục tool, cách seed dữ liệu và chạy test trên schema thật.

## 2. Vì sao làm hai tool này trước

- Cả hai đọc bảng **đã tồn tại**, nên làm được trọn từ dữ liệu đến test trên database thật mà không phải chờ team khác thêm bảng.
- Cả hai chỉ đọc, nên chưa cần cơ chế chống ghi trùng (`idempotency_key`). Phần nền dựng được gọn trước khi gặp bài toán khó hơn.
- Chúng xuất hiện sớm trong luồng xử lý: bước "kiểm tra outage" là bắt buộc ở luồng cầu dao nhảy và nước thải trào ngược (`general.md` §10).

## 3. Cấu trúc code

```
server/src/technical-tools/
  contracts/      hình dạng dữ liệu vào/ra (Zod)
  domain/         kiểu một đợt cắt
  ports/          interface nguồn dữ liệu, danh tính, đồng hồ, audit
  adapters/db/    truy vấn Drizzle trên bảng thật
  tools/          hai tool + luật lọc + phần dùng chung
  tool.ts         kiểu TechnicalTool và defineTool
  host.ts         chuỗi kiểm tra chung cho mọi tool
  entry.ts        createTechnicalToolCaller
  catalog.ts      danh mục tool (Q01)
  index.ts        các export cho phần còn lại của server
```

Một lời gọi đi qua các bước sau:

1. `entry.ts` nhận tên tool và tham số từ route `/api/agent-tools/call`.
2. `host.ts` xác định người gọi, kiểm tra capability, validate input, kiểm tra tòa nhà có trong quyền.
3. Tool gọi adapter để lấy các đợt cắt phủ tòa nhà.
4. `interruption-rules.ts` lọc theo trạng thái và thời gian.
5. `host.ts` kiểm tra output, ghi audit, bọc vào khuôn response.

## 4. Các quyết định thiết kế và lý do

### 4.1. Quyền không lấy từ input của bot

`tenant_id`, role và danh sách tòa được phép đến từ danh tính đã xác thực (`ContextResolver`), không từ tham số bot gửi. Schema input dùng chế độ strict, nên bot gửi thêm `tenant_id` sẽ bị từ chối `INVALID_INPUT` chứ không bị bỏ qua.

**Lý do:** `tools.md` §1.1 yêu cầu. Nếu tool tin `tenant_id` trong input thì một prompt injection là đủ để đọc dữ liệu tenant khác.

### 4.2. Mọi lời từ chối giống hệt nhau

Tòa nhà ngoài quyền, tòa nhà của tenant khác và tòa nhà không tồn tại đều trả `FORBIDDEN` với cùng một câu. Lý do cụ thể chỉ ghi vào audit.

**Lý do:** nếu ba trường hợp trả khác nhau, chính câu từ chối cho người gọi biết tòa nào có tồn tại.

### 4.3. Không bao giờ báo đợt cắt `proposed` hay `cancelled`

Chỉ bốn trạng thái được trả: `approved`, `notified`, `active`, `restored`.

**Lý do:** `proposed` là đề nghị chưa ai duyệt. Ở ca Level 1 (nước ngập gần tủ điện), bot vừa gửi đề nghị khóa nước; nếu tool báo đề nghị đó là "đang cắt", bot có thể nói với cư dân rằng nước đã khóa trong khi nước vẫn chảy.

### 4.4. Không đoán giờ khôi phục

`published_eta` là `planned_end` đã công bố, giữ nguyên kể cả khi giờ đó đã qua. Đợt cắt `active` quá giờ dự kiến mà chưa khôi phục vẫn được báo là đang cắt.

**Lý do:** `tools.md` §3.5 ghi "không tự suy đoán ETA". Một giờ khôi phục do tool tự tính là phỏng đoán được trình bày như sự thật.

### 4.5. Tách luật lọc khỏi câu truy vấn

Adapter database chỉ lấy các đợt cắt đúng tenant, đúng loại, có phạm vi phủ tòa nhà. Việc đợt nào được trả do các hàm thuần trong `interruption-rules.ts` quyết định.

**Lý do:** luật thời gian là phần dễ sai nhất (biên khung giờ, đợt quá hạn). Tách ra thì test được 40 ca mà không cần database, và adapter thứ hai sau này không thể hiểu "đang cắt" khác adapter đầu.

### 4.6. Tool lấy dữ liệu qua port

Tool gọi interface `InterruptionReadPort`, không gọi SQL trực tiếp.

**Lý do:** kế hoạch 5 team quy định tool nghiệp vụ nên đi qua service của backend. Khi Chiến có service, chỉ cần viết adapter mới, không sửa tool. Cũng nhờ vậy cùng một code chạy được trên PGlite và PostgreSQL thật.

### 4.7. Truy vấn chạy trong transaction chỉ đọc có đặt tenant

Mỗi lời gọi mở một transaction chỉ đọc và đặt `app.tenant_id` trước khi truy vấn, theo cách `withDatabaseScope` đang làm.

**Lý do:** để RLS của schema có hiệu lực. Cách ly tenant khi đó không phụ thuộc vào việc câu truy vấn có nhớ điều kiện `tenant_id` hay không.

### 4.8. Bỏ qua dòng dữ liệu tự mâu thuẫn

Dòng có `planned_end` sớm hơn hoặc bằng `planned_start` bị loại.

**Lý do:** schema không có CHECK cho quy tắc này. Một dòng như vậy sẽ "giao" với mọi khoảng thời gian nếu so sánh ngây thơ, và xuất hiện trong lịch của bất kỳ ngày nào.

### 4.9. Không có audit thì không trả dữ liệu

Mọi lời gọi đều ghi audit, kể cả lời bị từ chối. Nếu ghi audit thất bại, tool trả `INTERNAL_ERROR` và không trả kết quả.

**Lý do:** `general.md` A2-FR-014 yêu cầu mọi lần gọi tool có `trace_id`, `agent_version` và thời điểm. Gateway hiện có của server cũng theo nguyên tắc không có hành động nào thiếu dòng audit.

### 4.10. Có timeout

Mỗi tool có thời hạn 5 giây. Quá hạn hoặc nguồn dữ liệu lỗi thì trả `INTERNAL_ERROR` với `retryable: true`, thông báo chung chung, không lộ chi tiết SQL hay chuỗi kết nối.

**Lý do:** ở ca Level 1, bot không được treo chờ một tra cứu; luồng phải đi tiếp để tạo yêu cầu khẩn.

### 4.11. Nối vào server qua cửa đã có

`createTechnicalToolCaller` trả về đúng kiểu `DeploymentToolCaller` đã có ở `server/src/app.ts`. Với tên tool không thuộc module này, hàm trả `null` để route xử lý như cũ.

**Lý do:** không phải thêm route mới hay sửa `app.ts`. Token agent và run assertion đã được route xác minh trước khi tới tool.

### 4.12. Thêm `INVALID_INPUT` vào danh sách trạng thái

**Lý do:** `tools.md` §1.3 không liệt kê giá trị này trong enum `status`, nhưng §3.6 và §7 lại yêu cầu trả nó khi input sai. Cần anh Quang chốt (xem `requests/Q02-interruptions.md` mục 6).

## 5. Dữ liệu mẫu

Nằm ở `server/tests/technical-tools/fixtures/`. Mốc thời gian cố định là 30/09/2026 09:00 UTC.

- **Thế giới mẫu:** 2 tenant; tòa A1 và A2 (bot được cấp quyền), B1 (không được cấp), X1 (tenant khác).
- **10 đợt cắt (I1–I10):** mỗi đợt tồn tại để chứng minh một điều, ví dụ I1 là đợt đang cắt đã quá giờ dự kiến, I3 là đề nghị chưa duyệt, I6 phủ theo phân khu, I10 là dòng dữ liệu lỗi.
- **10 ca theo mức độ:** 4 ca Level 3, 4 ca Level 2, 2 ca Level 1. Mỗi ca gồm lời cư dân báo, lời gọi tool và kết quả phải ra.

## 6. Kiểm thử

125 test trong `server/tests/technical-tools/`, tất cả đều qua.

| File | Số test | Kiểm tra |
|---|---|---|
| `outage-schedule.contract.test.ts` | 23 | Hai ví dụ mẫu của `tools.md` qua được schema; input sai bị từ chối; tên tool khớp với cách route đổi tên |
| `outage-schedule.rules.test.ts` | 40 | Luật lọc: từng trạng thái × trước / trong / sau khung giờ; dòng dữ liệu lỗi |
| `outage-schedule.db.test.ts` | 20 | Adapter trên schema thật: phạm vi tòa / phân khu / khu; RLS; role chỉ đọc |
| `outage-schedule.flow.test.ts` | 42 | Gọi qua `createTechnicalToolCaller`: 10 ca theo mức độ, ca quyền, ca input sai, ca nguồn dữ liệu lỗi, audit |

Đã chạy trên hai môi trường:

- **PGlite** (mặc định): PostgreSQL chạy trong tiến trình, nạp nguyên baseline `0000_grey_blockbuster.sql` với đủ 148 bảng, trigger và RLS. Không cần cài gì thêm.
- **PostgreSQL 17.11** (khi đặt `TEST_DATABASE_URL`): tự tạo database tạm, migrate bằng migrator của Drizzle, đọc qua `createDatabase` của server, chạy xong thì xóa.

Truy vấn trong test chạy bằng role không phải superuser và chỉ có quyền `SELECT` trên bốn bảng, nên RLS có hiệu lực thật.

Đã thử cố ý làm hỏng ba chỗ để xác nhận test bắt được lỗi: coi `proposed` là chính thức (2 test đỏ), bỏ bước đặt tenant (29 test đỏ), bỏ kiểm tra tòa nhà (5 test đỏ).

```
bun test server/tests/technical-tools
bun run --filter server typecheck
bunx biome lint server/src/technical-tools server/tests/technical-tools
```

Cả ba lệnh đều sạch. Chưa chạy phần còn lại của bộ test toàn repo vì nó cần `.env` và database test riêng.

## 7. Chưa làm và còn phụ thuộc

- **12 tool còn lại** chưa có code: 4 tool tra cứu, 3 tool ghi nhận, 1 tool xác minh, 4 tool yêu cầu rủi ro.
- **Host chưa có idempotency**, cần bổ sung khi làm tool ghi.
- **Chưa nối vào server:** cần Chiến thêm caller vào `server/src/index.ts`.
- **`ContextResolver` thật** (task C06): trong test đây là chỗ giả lập duy nhất.
- **Nơi ghi audit thật:** `auditEventTypes` chưa có loại sự kiện cho tool kỹ thuật.
- **Khoảng trống schema** liên quan đến hai tool: xem `requests/Q02-interruptions.md` mục 5.

## 8. Phạm vi thay đổi

Chỉ tạo file mới trong vùng của Team Quang: `server/src/technical-tools/**`, `server/tests/technical-tools/**`, `docs/teams/quang/**`. Không sửa schema, migration, `app.ts`, `index.ts`, `package.json` hay lockfile.
