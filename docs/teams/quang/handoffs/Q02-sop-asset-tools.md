# Báo cáo Q02 (đợt 2) — Tool tra SOP và đọc hồ sơ thiết bị

- **Người làm:** Phạm Thành Đạt (Team Quang).
- **Ngày:** 01/10/2026.
- **Task:** Q01 (danh mục tool) và Q02 (tool kỹ thuật), đợt 2.
- **Trạng thái:** xong 4 trong 14 tool. Tool vẫn chưa gọi được từ server đang chạy vì chưa được nối vào `createApp` (việc của Team Chiến).
- **Đợt trước:** [Q02-outage-schedule-tools.md](Q02-outage-schedule-tools.md). Các quyết định dùng chung (khuôn response, cách phân quyền, không có audit thì không trả dữ liệu, timeout, cửa nối vào server) đã giải thích ở đó và không nhắc lại.

## 1. Đã xây gì

| Tool | Trả lời câu hỏi | Nguồn dữ liệu | Đặc tả |
|---|---|---|---|
| `sop_kb.retrieve` | Quy trình đã duyệt cho loại sự cố này ở tòa này là gì, và nghiệm thu theo tiêu chí nào? | Bảng thật (`knowledge_documents`, `document_versions`, `document_scopes`, `document_acl`, `knowledge_bases`) | `tools.md` §3.1 |
| `asset.read` | Sự cố này liên quan thiết bị nào: model, vị trí, sở hữu, bảo hành, trạng thái? | Adapter POC (chưa có bảng) | `tools.md` §3.2 |

Kèm theo:
- **16 mã sự cố** của `general.md` §4 thành dữ liệu tham chiếu dùng chung: [reference/issue-codes.ts](../../../../server/src/technical-tools/reference/issue-codes.ts).
- **Tiêu chí nghiệm thu có cấu trúc**, để `technical.verify_resolution` sau này chấm bằng code.

## 2. Vì sao làm hai tool này tiếp

`sop_kb.retrieve` là bước 6 của luồng xử lý chung (`general.md` §6) và có trong cả 5 luồng POC — không có nó thì bot không có gì để đề xuất. Nó cũng dùng bảng đã tồn tại nên làm được trọn vẹn trên schema thật.

`asset.read` là điều kiện của ba tool tra cứu còn lại: `sensor.read` và `maintenance_history.read` đều tra theo `asset_id`. Làm nó trước cũng là lần đầu dựng adapter POC cho phần dữ liệu chưa có bảng, và cách làm đó sẽ dùng lại cho các tool sau.

## 3. Quyết định thiết kế và lý do

### 3.1. SOP: bốn điều kiện đồng thời, không có đường lùi

Một tài liệu chỉ được trả về khi **đủ cả bốn**: `status = published`, bộ tài liệu chứa nó còn `active`, phiên bản đang hiệu lực tại thời điểm hỏi, và đúng ngôn ngữ yêu cầu.

**Lý do:** `tools.md` §3.1 ghi rõ "không fallback sang version draft/archived/hết hạn". Bản nháp là việc ai đó đang làm dở, bản hết hiệu lực là hướng dẫn đã bị thay thế — kỹ thuật viên làm theo một trong hai thì đúng là sự cố mà tool này tồn tại để ngăn.

### 3.2. Không có quyền là từ chối, không phải mặc định cho phép

`document_acl` được đánh giá theo ba bậc: có dòng `deny` khớp thì từ chối; không có `deny` mà có `allow` thì cho phép; không có dòng nào khớp thì từ chối.

**Lý do:** từ điển dữ liệu của `document_acl` ghi "không có grant thì từ chối". Nếu thiếu cấu hình mà mặc định cho đọc, thì một tài liệu chưa ai cấp quyền sẽ đến tay mọi bot.

Vai trò của người gọi lấy từ danh tính đã xác thực, và nếu không có vai trò (ví dụ job chạy theo lịch, dùng service principal) thì không grant theo role nào khớp được — tức là từ chối, không phải mở.

### 3.3. Không đọc được thì trả `FORBIDDEN`, không có thì trả `NOT_FOUND`

Có quy trình hợp lệ nhưng người gọi không được đọc → `FORBIDDEN`. Không có quy trình nào hợp lệ → `NOT_FOUND`.

**Lý do:** `tools.md` §3.1 yêu cầu vậy, và hai trạng thái này là hai sự thật khác nhau: một nói "chưa có hướng dẫn", một nói "thiếu grant". Quản trị viên chỉ sửa được trường hợp thứ hai nếu câu trả lời phân biệt nó. Người gọi đã tự cung cấp mã sự cố và tòa nhà, nên `FORBIDDEN` ở đây không tiết lộ gì thêm.

Ngược lại, nếu tài liệu vừa không hợp lệ (nháp, hết hạn) vừa không được cấp quyền thì trả `NOT_FOUND` — không có grant nào để sửa, và không có gì cần gợi ý.

### 3.4. `applies_to_descendants` được tôn trọng

Tài liệu gắn ở cấp phân khu, khu hoặc tenant chỉ với tới tòa nhà khi cột này bật. Tài liệu gắn đúng tòa nhà thì luôn với tới.

**Lý do:** đây là cách dữ liệu phân biệt "hướng dẫn cho riêng tòa này" với "hướng dẫn cho cả khu". Bỏ qua nó thì quy trình kiểm tra trạm cấp nước tổng của khu sẽ được trả về như quy trình sửa vòi nước trong căn hộ.

### 3.5. Mã sự cố chọn tài liệu, câu hỏi chỉ xếp thứ tự

Tài liệu ứng viên do `issue_code` quyết định. Câu hỏi của người dùng chỉ dùng để xếp thứ tự, theo số từ khóa xuất hiện trong tiêu đề, trích đoạn và tiêu chí nghiệm thu. Tài liệu không khớp từ nào vẫn được trả về, xếp cuối.

**Lý do:** bot đã biết đúng loại sự cố. Bỏ đúng quy trình duyệt cho loại sự cố đó chỉ vì kỹ thuật viên diễn đạt khác đi sẽ khiến bot không còn hướng dẫn nào và không biết tại sao. Xếp hạng là quy tắc xác định, không phải mô hình liên quan, và không quyết định điều gì thuộc trách nhiệm con người.

Câu hỏi không còn từ nào để tìm (chỉ dấu câu, chỉ từ nối) → `NEEDS_INPUT`, và database không bị hỏi.

### 3.6. So chuỗi tiếng Việt bỏ dấu

Cả xếp hạng SOP và tìm thiết bị theo vị trí đều so sánh sau khi bỏ dấu và chuyển chữ thường.

**Lý do:** người ta gõ cả hai cách. "tieu chi nghiem thu" và "tiêu chí nghiệm thu" là cùng một câu hỏi; "A1-1205/phong khach" là cùng một căn phòng. So chuỗi thô thì câu trả lời phụ thuộc vào bàn phím của người gõ.

### 3.7. `asset.read` không bao giờ tự chọn

Đúng 1 kết quả → `OK`. 0 kết quả → `NOT_FOUND`. Từ 2 kết quả → `NEEDS_INPUT`, kèm **danh sách ứng viên** trong `data` và `missing_fields: ["asset_id"]`.

**Lý do:** `tools.md` §3.2 ghi "nhiều match mà không thể phân biệt trả NEEDS_INPUT cùng danh sách candidate tối thiểu, không tự chọn". Bot lấy nhầm thiết bị sẽ đi tiếp đọc lịch sử của thiết bị khác và đề xuất sửa máy khác. Danh sách đi kèm vì nếu chỉ nói "câu hỏi chưa rõ" thì bot phải tự đoán nên hỏi gì; có danh sách thì nó hỏi được cư dân hoặc kỹ thuật viên là máy nào.

`NEEDS_INPUT` không được đánh dấu là lỗi (`isError: false`), vì đó là câu trả lời bot hành động được, khác với một lần gọi thất bại.

### 3.8. Adapter POC không tự chứa dữ liệu

`createInMemoryAssetReadPort()` và `createInMemorySopProfilePort()` nhận dữ liệu từ bên ngoài, mặc định là rỗng. Bộ dữ liệu mẫu nằm trong test.

**Lý do:** kế hoạch 5 team cấm đưa mock vào đường chạy thật. Nếu module mang theo hồ sơ thiết bị bịa, một deployment sẽ trả lời câu hỏi về điều hòa của cư dân bằng dữ liệu tưởng tượng, và bot sẽ đề xuất sửa nó. Không có dữ liệu thì tool trả `NOT_FOUND` — điều đó đúng, và người dựng deployment xử lý được.

### 3.9. Tiêu chí nghiệm thu là dữ liệu có cấu trúc

Mỗi tiêu chí có `text` để hiển thị và `check` để máy chấm: `checklist`, `evidence`, `measurement` hoặc `manual`.

**Lý do:** `sop_kb.retrieve` chỉ trả `text`, đúng như output schema của `tools.md`. Nhưng `technical.verify_resolution` sau này phải kết luận `VERIFIED` / `NEEDS_EVIDENCE` / `HUMAN_REVIEW`; nếu tiêu chí chỉ là một câu văn thì quyết định đó rơi vào tay model đọc văn xuôi, mà `general.md` §3.1 cấm agent tự tạo số đo hay bằng chứng. `manual` là câu trả lời trung thực cho tiêu chí chỉ người mới quyết được, và luôn dẫn tới `HUMAN_REVIEW`.

### 3.10. Danh tính cần thêm hai trường

`ResolvedIdentity` giờ có thêm `user_id` và `role_code` (tùy chọn).

**Lý do:** `document_acl` cấp quyền theo role, theo người, hoặc theo workspace. Không có hai trường này thì không đánh giá được ACL. Để tùy chọn vì job chạy theo lịch không có người đứng sau; khi thiếu thì không grant nào khớp, tức là từ chối.

Đây là thay đổi hợp đồng với `ContextResolver` của Chiến — đã ghi vào [Q02-sop-asset.md](../requests/Q02-sop-asset.md) mục 1.

## 4. Dữ liệu mẫu

### 16 tài liệu (`fixtures/sop.ts`)

Mỗi tài liệu tồn tại để chứng minh một điều. Đọc tại thời điểm 30/09/2026 09:00 UTC.

| Mã | Điều cần chứng minh |
|---|---|
| S1 | luồng thuận: published, đang hiệu lực, đúng tòa, đúng role |
| S2 | tài liệu cấp phân khu với tới mọi tòa trong phân khu |
| S3 | tài liệu cấp khu với tới tòa nhà; một tài liệu phục vụ hai mã sự cố |
| S4 | hai tài liệu cùng một mã sự cố, nên câu hỏi quyết định thứ tự |
| S5 | phiên bản đã hết hiệu lực không còn là hướng dẫn |
| S6 | bản nháp không bao giờ được trả về |
| S7 | dòng `deny` thắng dòng `allow` của role khác |
| S8 | tài liệu không có dòng ACL nào bị từ chối, không mặc định cho đọc |
| S9 | tài liệu đã lưu trữ không còn là hướng dẫn |
| S10 | hướng dẫn của phân khu này không với sang phân khu khác |
| S11 | tài liệu cấp khu không áp dụng xuống cấp dưới thì không tới tòa nào |
| S12 | tài liệu ngôn ngữ khác không dùng cho yêu cầu tiếng Việt |
| S13 | tài liệu published trong bộ đã ngừng dùng không còn là hướng dẫn |
| S14 | tài liệu chưa kích hoạt phiên bản nào được báo là không có, không phải kết quả rỗng |
| S15 | tài liệu cấp tenant với tới mọi tòa của tenant |
| S16 | thư viện của tenant khác vô hình |

### 11 thiết bị (`fixtures/assets.ts`)

Phòng tắm căn A1-1205 có **ba** thiết bị, trong đó **hai** cùng loại bồn cầu. Đó là ca mà tool buộc phải từ chối tự chọn: chỉ vị trí → 3 kết quả; thêm `asset_type=toilet` → vẫn 2; thêm `asset_type=water_heater` → đúng 1.

Ngoài ra: thiết bị khu vực chung của tòa, thiết bị đã `retired`, thiết bị ở tòa ngoài quyền, và thiết bị của tenant khác.

### 22 ca theo mức độ

Nằm trong `sop-asset.flow.test.ts`, đặt tên L3-5…L3-10, L2-5…L2-10, L1-4…L1-10, mỗi ca gồm tình huống cư dân báo, lời gọi tool và kết quả phải ra.

## 5. Kiểm thử

**284 test trong `server/tests/technical-tools/`, tất cả đều qua** (đợt trước 125, đợt này thêm 159).

| File | Số test | Kiểm tra |
|---|---|---|
| `catalog.test.ts` | 27 | Danh mục 4 tool và 16 mã sự cố; viết theo dữ liệu nên thêm tool không phải sửa assertion |
| `sop-asset.contract.test.ts` | 25 | Hai ví dụ mẫu của `tools.md` qua được schema; input sai bị từ chối |
| `sop-asset.rules.test.ts` | 40 | ACL ba bậc, hiệu lực phiên bản, điều kiện là hướng dẫn, thứ tự xếp hạng, so chuỗi tiếng Việt |
| `sop-asset.db.test.ts` | 22 | Phạm vi tòa/phân khu/khu/tenant, `applies_to_descendants`, RLS, role chỉ đọc |
| `sop-asset.flow.test.ts` | 47 | 22 ca theo mức độ + ca quyền + ca ACL + provenance + audit, gọi qua `createTechnicalToolCaller` |

Đã chạy trên hai môi trường:

- **PGlite** (mặc định), nạp nguyên baseline 148 bảng — 12 giây.
- **PostgreSQL 17.11** thật qua `TEST_DATABASE_URL` — 42 giây, cùng 284 test.

Test đã bắt được một lỗi trong kỳ vọng ban đầu của mình: mình quên rằng S12 (bản tiếng Anh) vẫn phải được adapter trả về, vì lọc ngôn ngữ là việc của tầng luật chứ không phải của truy vấn.

Đã thử cố ý phá bốn quy tắc để xác nhận test bắt được:

| Phá gì | Số test đỏ |
|---|---|
| Không có dòng ACL nào cũng cho đọc | 7 |
| Bản nháp cũng tính là hướng dẫn | 5 |
| Adapter bỏ qua `applies_to_descendants` | 5 |
| Adapter thiết bị tự lấy kết quả đầu tiên | 4 |

```
bun test server/tests/technical-tools
bun run --filter server typecheck
bunx biome lint server/src/technical-tools server/tests/technical-tools
```

Cả ba lệnh đều sạch.

## 6. Còn lại

- **10 tool chưa có code:** `sensor.read`, `maintenance_history.read`, 3 tool ghi nhận, 1 tool xác minh, 4 tool yêu cầu rủi ro.
- **Host chưa có idempotency**, cần bổ sung trước khi làm tool ghi.
- **Nguồn SOP profile và hồ sơ thiết bị** hiện là POC. Xem [Q02-sop-asset.md](../requests/Q02-sop-asset.md).
- **Ba việc chặn bot dùng tool** (nối vào server, `ContextResolver` thật, nơi ghi audit) vẫn như đợt trước.

## 7. Phạm vi thay đổi

Chỉ tạo và sửa file trong vùng của Team Quang: `server/src/technical-tools/**`, `server/tests/technical-tools/**`, `docs/teams/quang/**`. Không sửa schema, migration, `app.ts`, `index.ts`, `package.json` hay lockfile.
