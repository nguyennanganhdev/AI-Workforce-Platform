# Đặc tả thu thập dữ liệu thật và kiểm tra sẵn sàng

## 1. Nguồn cần xin theo ưu tiên

| Ưu tiên | Nguồn/đơn vị | Xin gì | Điều kiện sử dụng |
| --- | --- | --- | --- |
| P0 | BQL Vinhomes của địa bàn POC | SOP kỹ thuật và an toàn hiện hành, bảng phân cấp sự cố, SLA, kênh báo đúng tòa, quyền phê duyệt, sơ đồ phạm vi kỹ thuật | Văn bản/version, người ban hành, ngày hiệu lực, tòa/phân khu áp dụng; Domain Owner duyệt |
| P0 | Hệ thống ticket/work order hoặc bản export ẩn danh | Ít nhất một chuỗi ticket→assessment→assignment→kết quả cho mỗi năm POC | Giữ khóa liên kết, timeline và version; loại PII trước chia sẻ |
| P0 | Kỹ thuật viên/đội bảo trì | Checklist thực tế, nguyên nhân xác nhận, số đo, vật tư, ảnh trước/sau, điều kiện nghiệm thu | Người ghi và người xác minh rõ; không dùng lời agent làm measurement |
| P1 | Asset/CMMS | Tài sản, model, vị trí, warranty, lịch sử sửa/bảo trì, manual thiết bị | Asset gắn đúng building và quyền truy cập |
| P1 | BMS/IoT và gián đoạn dịch vụ | Danh mục sensor, metric/unit, timestamp/quality, outage và phạm vi | Có giới hạn freshness; nguồn chưa đáng tin không chứng minh an toàn |
| P1 | Quản lý tri thức | SOP version, publication/review, ACL và scope, tài liệu đã thu hồi | Chỉ published/effective/allowed được retrieval |
| P1 | Bộ phận tài chính/điều phối (nếu làm giá) | Chi phí thực tế của work order đã hoàn thành, basis/currency, revision, trường hợp miễn phí/bảo hành/outlier | Chỉ observation verified; không nhập dữ liệu hóa đơn của người khác vào RAG cư dân |
| P2 | Phản hồi cư dân và nhân viên | Kết quả self-help, dừng/từ chối, tái phát, nhận xét sai lệch | Có consent và quyền; không tự học trực tiếp từ chat chưa duyệt |

Nếu chỉ thu được tài liệu công khai như `DV-01`, có thể xây test và RAG nội bộ có kiểm duyệt; không có căn cứ xuất bản SOP, SLA, self-help hoặc giá cho cư dân.

## 2. Mẫu metadata bắt buộc cho mỗi fact/tài liệu

```json
{
  "source_id": "opaque-id",
  "source_kind": "bql_document | manufacturer_manual | technician_record | public_reference | synthetic_fixture",
  "publisher": "Tên đơn vị ban hành",
  "source_uri_or_file_id": "URL hoặc file ID được phép đọc",
  "document_code": "Mã văn bản nếu có",
  "version": "Phiên bản nguồn",
  "issued_at": null,
  "effective_from": null,
  "effective_to": null,
  "retrieved_at": "2026-10-01T00:00:00Z",
  "content_sha256": "SHA-256 của bytes gốc",
  "tenant_id": null,
  "domain_id": null,
  "workspace_id": null,
  "building_ids": [],
  "access_class": "public | staff | restricted",
  "review_status": "unverified | reviewed | published | revoked",
  "reviewed_by": null,
  "claim_paths": ["trang/điều/mục/ảnh chứa fact"]
}
```

`null` nghĩa là chưa biết, không mặc định phạm vi toàn tenant. Với dữ liệu có PII, lưu file bytes ở storage có quyền và chỉ xuất bản metadata/đoạn đã khử định danh. Mỗi fact quan trọng (SLA, liên hệ, bước thao tác, mốc an toàn) cần provenance riêng, không chỉ một link cho cả tài liệu.

## 3. Schema thu thập tối thiểu theo lifecycle

| Loại record | Trường không thể thiếu | Kiểm tra chính |
| --- | --- | --- |
| Incident/ticket | `ticket_id`, source, tenant/domain/building đã xác minh, request kind, thời điểm nhận, mô tả, scope ảnh hưởng | Một người có nhiều căn không được tự chọn căn; không dùng tên tòa trong text làm quyền |
| Assessment | ticket/generation, issue code, facts có kiểu và provenance, unknown fields, người/run đề xuất, policy/binding/version | Append-only; mỗi fact có nguồn; emergency signal không chờ ảnh |
| Decision/SLA | applied decision, severity/priority, emergency, policy/binding/rule/engine version, review, cycle/deadline | Chỉ backend áp dụng; hạ mức cần người duyệt; SLA tính từ thời điểm nhận |
| Asset | asset ID, building, type/model, location, ownership, warranty, status, updated_at | Nhiều match trả NEEDS_INPUT; model quyết định manual |
| Sensor/measurement | metric, value, unit, observed/measured_at, received_at, quality, thiết bị và người đo | Không ghi số do model suy ra; stale/bad không xác nhận an toàn |
| Work order/assignment | order ID, ticket ID, scope, status/version, executor, thời gian, skill/capacity, approval | Agent chỉ đề xuất; assignment phải có quyền và đúng scope |
| Evidence | evidence/file/object ID, ticket/work order, loại trước/sau, captured_at, source, hash, scan/readiness, ACL | Không dùng file chưa verified clean hoặc sai ticket |
| Executor result | assignment, checklist, diagnosis, repair notes, parts, measurement/evidence IDs, started/completed | Kỹ thuật viên xác thực, không sửa bản đã xác nhận; thiếu evidence không completed giả |
| Maintenance event | asset, verified result, outcome, occurred_at, source refs | Chỉ append sau kết quả được xác nhận; revision thay cho overwrite |
| Procedure | source work order, tác giả nhân viên, structured steps, preconditions/contraindications/stop conditions, audience, review/publication/version | Draft không hướng dẫn cư dân; revoke có hiệu lực ngay |
| Actual cost | work order, repair scope, currency, labor/material/other/tax/discount/total, cost basis, status/version | Một work order độc lập một mẫu; miễn phí/bảo hành/outlier tách; chỉ verified dùng thống kê |

## 4. Yêu cầu lấy mẫu để test

Để **đóng tiêu chí dữ liệu mẫu** của A2, thu ít nhất một ví dụ đã được kỹ thuật viên xác minh cho mỗi 16 issue code, và cho năm POC cần một chuỗi end-to-end có ticket, work order, checklist, evidence và outcome. Đây là ngưỡng fixture tối thiểu của dự án, không phải cỡ mẫu thống kê cho tự động hóa hoặc giá. Nên bổ sung một ca missing facts, một ca emergency, một ca scope sai, một ca SOP hết hiệu lực và một ca evidence thiếu cho từng luồng.

Giá tham khảo có ngưỡng mẫu độc lập/freshness do policy và Domain Owner chốt; không suy ra ngưỡng từ fixture. Chưa có verified actual cost thì tool estimate phải trả `insufficient_data`, không dựng khoảng giá mặc định. Tương tự, một procedure từ work order chỉ là candidate cho đến khi người có quyền review/publish.

## 5. Quy tắc làm sạch và đối soát

1. Loại/ẩn tên, số điện thoại, số căn, biển số, khuôn mặt và nội dung nhạy cảm trước khi đưa vào bộ test hoặc RAG chung. Giữ khóa ánh xạ trong môi trường có quyền nếu cần đối soát.
2. Chuẩn hóa `issue_code`, `equipment_class`, `diagnosis_code`, `repair_scope_code`, đơn vị đo và UTC timestamp bằng taxonomy version; giữ nguyên câu mô tả gốc ở vùng giới hạn quyền.
3. Kiểm tra `tenant/building/ticket/work_order/assignment` bằng FK và service scope. Dữ liệu ngoài scope không được vào retrieval index.
4. Tách `reported_at`, `observed_at`, `captured_at`, `measured_at`, `received_at`; không dùng thời gian thiết bị làm thứ tự giao dịch.
5. Gộp retry bằng idempotency key và payload hash; correction là revision có `supersedes_*`, không chỉnh bản đã xác nhận.
6. Liên kết mọi trích dẫn tới document version/chunk và mọi estimate tới reference/sample set; thu hồi nguồn phải invalidation kết quả phụ thuộc.
7. Đặt nhãn `synthetic` hoặc `external_reference` cho dữ liệu mẫu từ nơi khác; không lưu nó như bản ghi Vinhomes thật.

## 6. Điểm chưa có sau lượt thu thập công khai

- Quy trình nội bộ Vinhomes theo đúng tòa và phiên bản, ngưỡng SLA, người duyệt các hành động rủi ro.
- Dataset ticket/work order/evidence/sensor/asset có cấu trúc và được phép sử dụng.
- Bản ghi chi phí sửa chữa thực tế đã xác minh và bộ procedure self-help được publish.
- Quyền/license để sao chép toàn văn tài liệu bên thứ ba vào corpus; hiện thư mục chỉ giữ diễn giải ngắn và link nguồn.

Các mục này phải được BQL/Domain Owner cung cấp hoặc phê duyệt. Không suy ra từ repo công khai, website bán hàng hoặc tình huống giả lập.
