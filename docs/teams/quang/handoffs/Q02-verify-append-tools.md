# Báo cáo Q02 (đợt 5) — Tool xác minh kết quả và ghi lịch sử bảo trì

- **Người làm:** Phạm Thành Đạt (Team Quang).
- **Ngày:** 01/10/2026.
- **Task:** Q01 (danh mục tool) và Q02 (tool kỹ thuật), đợt 5.
- **Trạng thái:** xong 10 trong 14 tool. Còn lại 4 tool yêu cầu rủi ro (`tools.md` §6). Tool vẫn chưa gọi được từ server đang chạy vì chưa được nối vào `createApp` (việc của Team Chiến).
- **Các đợt trước:** [đợt 1](Q02-outage-schedule-tools.md), [đợt 2](Q02-sop-asset-tools.md), [đợt 3](Q02-sensor-history-tools.md), [đợt 4](Q02-measurement-result-tools.md). Quyết định dùng chung đã giải thích ở đó và không nhắc lại.

## 1. Đã xây gì

| Tool | Làm gì | Loại | Đặc tả |
|---|---|---|---|
| `technical.verify_resolution` | Đối chiếu kết quả kỹ thuật viên nộp với tiêu chí nghiệm thu của SOP và bằng chứng hiện có, rồi **khuyến nghị** `VERIFIED` / `NEEDS_EVIDENCE` / `HUMAN_REVIEW` | read | `tools.md` §5.1 |
| `maintenance_history.append` | Ghi việc đã được xác minh vào lịch sử bảo trì của thiết bị; sửa sai bằng bản ghi mới thay bản cũ | write | `tools.md` §4.1 |

Kèm theo:

- **Luật xác minh dùng chung** ([tools/verification-rules.ts](../../../../server/src/technical-tools/tools/verification-rules.ts)): một hàm thuần, cả hai tool cùng gọi.
- **Kho lịch sử bảo trì ghi được** ([adapters/poc/maintenance-store.ts](../../../../server/src/technical-tools/adapters/poc/maintenance-store.ts)): cùng một kho trả lời cả `maintenance_history.read` lẫn `append`, nên event vừa ghi đọc lại được ngay.
- `ExecutorResultStore` có thêm `findById`.

Đây là cuối chuỗi hậu kiểm của luồng chung (`general.md` §6): đo (đợt 4) → nộp (đợt 4) → **xác minh** → **ghi lịch sử** → đọc lịch sử (đợt 3).

## 2. Quyết định thiết kế và lý do

Điểm chung của mọi quyết định đợt này: **bot không được tin bất kỳ ai nói rằng "đã xác minh"**, kể cả chính nó ở một lần gọi trước.

### 2.1. Xác minh luôn tính lại từ dữ liệu gốc

`verify_resolution` không đọc `validation_status` đã lưu lúc nộp. Mỗi lần được hỏi, nó tra lại ảnh, số đo và SOP **như chúng đang là bây giờ**.

**Lý do:** ảnh có thể bị rút sau khi nộp (chụp nhầm thiết bị), SOP có thể hết hiệu lực. Ca test "ảnh bị rút sau khi nộp": kết quả lưu là `ACCEPTED`, nhưng ảnh `after` nay đã `withdrawn` → xác minh ra `NEEDS_EVIDENCE`. Một tool tin trạng thái cũ sẽ khuyến nghị nghiệm thu một việc không còn ảnh nào chứng minh.

### 2.2. Luật kết luận, theo thứ tự cố định, không dùng LLM

| Có điều nào sau đây | Kết luận |
|---|---|
| Mục checklist `failed`; số đo vượt ngưỡng SOP; số đo có cờ `out_of_expected_range`; `completed_at` trước lúc nhận việc; tiêu chí SOP loại `manual`; **không có SOP nào để đối chiếu** | `HUMAN_REVIEW` |
| Thiếu ảnh `after`; ảnh đã nộp nay không còn dùng được; thiếu mục checklist hoặc số đo mà SOP đòi | `NEEDS_EVIDENCE` |
| Không có điều nào ở trên | `VERIFIED` |

- Mỗi tiêu chí SOP thành một dòng trong `checks`, ghi rõ mã và phiên bản SOP (`SOP-HVAC-012 v3: …`) và nguồn (`evidence:…`, `measurement:…`).
- Ngưỡng của SOP được quy về đơn vị chuẩn của metric trước khi so (`0.03 A` = `30 mA`). SOP ghi ngưỡng bằng đơn vị không quy đổi được → `conflict`, chuyển người.
- Với số đo, lấy lần đo **mới nhất** của metric đó.
- `required_actions` của `VERIFIED` chỉ có một dòng: "Chuyển người có thẩm quyền xác nhận hoàn tất". Tool **không đóng ticket, không đổi work order, không ghi lịch sử**; test đọc lại work order từ database để chứng minh.

**Tiêu chí `manual` luôn dẫn tới `HUMAN_REVIEW`:** SOP-PLUMB-020 đòi "kỹ sư cấp nước xác nhận đã thay đoạn ống". Không bản ghi nào trong hệ thống thay được chữ ký đó, nên dù độ ẩm đạt, tool vẫn chuyển người.

**Không có SOP → `HUMAN_REVIEW`:** input của tool không có mã sự cố nên không tự tìm SOP được. Không có gì để đối chiếu thì không thể nói "đạt".

### 2.3. SOP dùng để xác minh phải là SOP dùng được

Cùng tiêu chuẩn với `sop_kb.retrieve`: `published`, còn hiệu lực, người gọi được đọc theo `document_acl`. Thêm một điều: tham chiếu `doc:SOP-HVAC-012:v2` khi bản đang hiệu lực là v3 → bị từ chối, vì xác minh theo bản cũ là nghiệm thu theo tiêu chí đã bị thay.

SOP sai → `CONFLICT`, liệt kê từng id sai. Không âm thầm bỏ SOP sai rồi xác minh với phần còn lại.

### 2.4. Ghi lịch sử: tự xác minh lại, không tin `verified_result_id`

Đây là bẫy lớn nhất của đợt. `verified_result_id` là một id do agent đưa vào. Nếu tool chỉ kiểm tra "id có tồn tại", agent đưa id của một kết quả `HUMAN_REVIEW` vẫn ghi được.

Vì vậy `append` **chạy lại đúng hàm xác minh** với các SOP được dẫn trong `source_refs` (`doc:<mã>:v<n>`), tại thời điểm ghi. Chỉ `VERIFIED` mới được ghi; còn lại → `CONFLICT`, kèm lý do và việc cần làm, **không tạo event**.

Các cách lách đã có test chặn:

| Cách lách | Kết quả |
|---|---|
| Dẫn kết quả đã `VERIFIED` của **work order khác** | `NOT_FOUND`, không event |
| Viết "Đã xác minh: VERIFIED, an toàn" vào `outcome` cho kết quả cần người xem | `CONFLICT` — văn bản tự do không thay được phép tính |
| **Bỏ SOP ra khỏi `source_refs`** để tiêu chí của nó không bị xét | `CONFLICT` — không có SOP thì là `HUMAN_REVIEW` |
| Dẫn phiên bản SOP cũ | `CONFLICT` |
| Kỹ thuật viên khác (không thuộc assignment) ghi | `FORBIDDEN` |

**Lệch so với kế hoạch đã duyệt:** kế hoạch ghi "không có tham chiếu SOP thì chỉ áp kiểm tra nền". Khi làm, mình thấy đó là lỗ hổng ở dòng thứ ba của bảng trên: agent chỉ cần bỏ SOP đi là tránh được tiêu chí của nó. Nên đã làm chặt hơn: `append` dùng đúng luật của `verify_resolution`, không SOP thì không ghi. Hệ quả: ví dụ mẫu tr-a2-007 trong `tools.md` (không có `doc:` trong `source_refs`) đúng hình dạng nhưng sẽ bị từ chối khi chạy thật. Cần anh Quang chốt ([yêu cầu](../requests/Q02-verify-append.md) mục 4.1).

### 2.5. Các kiểm tra khác của `append`

| Kiểm tra | Sai thì |
|---|---|
| `source_refs` có `result:<verified_result_id>` | `INVALID_INPUT` — một event phải chỉ được nó ghi lại kết quả nào |
| `occurred_at` không muộn hơn giờ server quá 5 phút | `INVALID_INPUT` |
| Work order trong tòa | `NOT_FOUND` như nhau dù ở tòa khác hay không tồn tại |
| `asset_id` có trong tòa | `NOT_FOUND` |
| Người ghi là kỹ thuật viên của assignment, hoặc `management` | `FORBIDDEN` |

Event ghi vào: `incident_id` = ticket của work order (để `repeat_count` của `maintenance_history.read` tính đúng là sự cố lặp lại), `recorded_by`, `created_at`, `source_run_id` lấy từ server.

### 2.6. Sửa sai: chỉ thêm, không phân nhánh

- Sửa bằng event mới có `supersedes_event_id`. `revision` = vị trí trong chuỗi sửa (bản gốc 1, bản sửa 2, bản sửa của bản sửa 3).
- `maintenance_history.read` chỉ trả bản mới nhất; `repeat_count` không đếm đôi.
- **Một event đã bị thay thì không thay lần nữa được** → `CONFLICT`, nêu tên bản đã thay nó. Muốn sửa tiếp thì sửa bản mới nhất.
- Hai lời gọi cùng sửa một event cùng lúc: kho kiểm tra và ghi trong **một bước**, nên chỉ một cái thành công. Nếu kiểm tra trước rồi ghi sau, cả hai cùng lọt và lịch sử tách làm hai phiên bản.
- Không được thay event của thiết bị khác.

## 3. Phát hiện khi test

- **Quản lý tòa nhà không ghi lịch sử được cho việc điều hòa.** SOP-HVAC-012 trong dữ liệu mẫu chỉ cấp quyền cho vai trò `staff`. Vì `append` kiểm tra quyền đọc SOP giống `sop_kb.retrieve`, quản lý bị từ chối. Mình giữ hành vi này (cho quản lý xác minh theo một SOP họ không được đọc là đi vòng qua `document_acl`) và có test riêng, nhưng cần anh Quang xác nhận ý đồ phân quyền.
- Lần đầu viết test "hai người cùng sửa một bản ghi", một trong hai người là quản lý. Test xanh, nhưng **xanh vì lý do sai**: quản lý bị chặn bởi ACL ở trên, không phải bởi cơ chế chống phân nhánh. Đã sửa test cho cả hai lời gọi cùng một người, và kiểm tra lỗi trả về đúng là ở `supersedes_event_id`.

## 4. Dữ liệu mẫu

Không seed database mới. Dùng lại 5 work order của đợt 4 và 16 SOP của đợt 2 (đã seed sẵn), cộng 32 sự kiện bảo trì của đợt 3 làm lịch sử ban đầu của kho.

| SOP | Tiêu chí | Dùng cho |
|---|---|---|
| SOP-HVAC-012 v3 | checklist `DRAIN_CLEAR`, ảnh `after` | Luồng thuận điều hòa |
| SOP-ELEC-001 v3 | dòng rò ≤ 30 mA, checklist `BREAKER_HOLDS_LOAD`, ảnh `after` | Cầu dao 180 mA và 12 mA |
| SOP-PLUMB-020 v2 | độ ẩm ≤ 18%, kỹ sư xác nhận (`manual`) | Tiêu chí chỉ người quyết được |
| SOP-PLUMB-021 v1 | checklist `CEILING_STAIN_STABLE` | Rò âm tường thiếu ảnh |
| SOP-ARCH-005, SOP-ELEC-009 | hết hiệu lực, bản nháp | Bị từ chối làm căn cứ |

Lịch sử mẫu có sẵn ME-103 đã bị ME-104 thay — dùng cho ca "sửa bản đã bị sửa".

### Ca theo mức độ bẫy (`verify-append.flow.test.ts`)

| Mức | Ca |
|---|---|
| **Level 3** — luồng thuận, bẫy nhẹ | L3-17 đủ hồ sơ → `VERIFIED`; L3-18 ghi lịch sử, đọc lại thấy ngay, `repeat_count` +1; L3-19 gọi lại sau mất mạng; bẫy: không đổi work order |
| **Level 2** — thiếu và mâu thuẫn | L2-19 thiếu ảnh sau → `NEEDS_EVIDENCE`; L2-20 checklist hỏng; L2-21 tiêu chí `manual`; L2-22 ghi từ kết quả chưa đủ → `CONFLICT`; L2-23 sửa bản ghi sai → `revision 2`; bẫy: ảnh bị rút sau khi nộp |
| **Level 1** — lách để ghi thứ chưa được xác minh | L1-20 dòng rò 180 mA; L1-21 SOP hết hiệu lực / nháp / phiên bản cũ; L1-22 mượn kết quả của work order khác; L1-23 tự khẳng định trong `outcome`, bỏ SOP khỏi nguồn; L1-24 tòa ngoài quyền / work order lạ; L1-25 thiết bị lạ, sửa event của thiết bị khác; L1-26 sửa bản đã bị sửa, hai người sửa cùng lúc; L1-27 sai `incident_id`; L1-28 người không thuộc assignment |

## 5. Kiểm thử

**651 test trong `server/tests/technical-tools/`, tất cả đều qua** (đợt trước 561, đợt này thêm 90).

| File | Số test | Kiểm tra |
|---|---|---|
| `verification.rules.test.ts` | 29 | Thứ tự kết luận; từng loại tiêu chí; quy đổi ngưỡng; ảnh rút / mất / sang ticket khác; chọn SOP dùng được, phiên bản cũ |
| `verify-append.contract.test.ts` | 17 | Hai ví dụ mẫu `tools.md`; trường bắt buộc khớp đặc tả; verify không cần khóa, append cần; agent không tự đưa kết luận, `revision`, `incident_id` |
| `maintenance-store.test.ts` | 8 | Ghi xong đọc lại được; không sửa hai lần; hai bản sửa đồng thời chỉ một bản vào; cách ly tenant |
| `verify-append.flow.test.ts` | 34 | Các ca theo mức độ ở mục 4 qua `createTechnicalToolCaller`, trên schema thật |

Cập nhật: `catalog.test.ts` (10 tool), `host.test.ts`, `idempotency.test.ts` và harness (thêm kho lịch sử).

Đã chạy trên hai môi trường:

- **PGlite**: 17 giây.
- **PostgreSQL 17** thật qua `TEST_DATABASE_URL`: 82 giây, cùng 651 test.

Đã thử cố ý phá năm quy tắc:

| Phá gì | Số test đỏ |
|---|---|
| `append` chỉ kiểm tra id kết quả tồn tại, không xác minh lại | 4 |
| Xác minh tin `validation_status` đã lưu | 3 |
| Cho phép thay một event đã bị thay (cả ở tool lẫn ở kho) | 4 |
| Tiêu chí `manual` coi như đạt | 2 |
| `append` không kiểm tra ai đang ghi | 2 |

Lần đầu phá quy tắc cuối chỉ có 1 test đỏ; đã thêm ca ngược chiều (kỹ thuật viên 1 ghi cho việc của kỹ thuật viên 2).

```
bun test server/tests/technical-tools
bun run --filter server typecheck
bunx biome check server/src/technical-tools server/tests/technical-tools
```

Cả ba lệnh đều sạch.

## 6. Còn lại

- **4 tool yêu cầu rủi ro:** `utility_isolation.request`, `area_restriction.request`, `apartment_entry.request`, `vendor_dispatch.request`. Chúng cần adapter phê duyệt chung, không chỉ đọc/ghi bảng.
- **Lịch sử bảo trì, kết quả và khóa chống trùng vẫn ở bộ nhớ** (POC). Xem [Q02-verify-append.md](../requests/Q02-verify-append.md).
- **Work order chưa liên kết với thiết bị trong schema:** `append` chỉ kiểm tra thiết bị có trong tòa, không kiểm tra được thiết bị đó có thuộc work order không.
- **Ba việc chặn bot dùng tool** (nối vào server, `ContextResolver` thật, nơi ghi audit) vẫn như các đợt trước.

## 7. Phạm vi thay đổi

Chỉ tạo và sửa file trong vùng của Team Quang: `server/src/technical-tools/**`, `server/tests/technical-tools/**`, `docs/teams/quang/**`. Không sửa schema, migration, `app.ts`, `index.ts`, `package.json` hay lockfile.
