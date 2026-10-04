# Dữ liệu cần bàn giao từ team Quang

Ba tool đọc kỹ thuật đã nối với Supervisor. Tool trả rỗng khi chưa có dữ liệu đủ điều kiện hoặc dữ liệu nằm ngoài quyền. Tool ghi/tạo yêu cầu là contract khác, không mở bằng cách seed SOP.

## SOP kỹ thuật

Team Quang cung cấp file SOP gốc và một manifest JSON/CSV cho từng phiên bản, với:

- Mã tài liệu (`code`), tiêu đề, ngôn ngữ `vi`, số phiên bản, ngày hiệu lực từ/đến, hash nội dung, người phê duyệt và nguồn tài liệu.
- Mã tình huống (`issueCodes`) khớp danh mục `server/src/technical-tools/reference/issue-codes.ts`, trích đoạn hướng dẫn (`excerpt`).
- Tiêu chí nghiệm thu (`acceptanceCriteria`): id, nội dung và cách kiểm (`checklist`, ảnh trước/sau, phép đo kèm đơn vị/ngưỡng, hoặc `manual`). Ngưỡng do chủ SOP xác nhận, không tự đặt.
- Phạm vi áp dụng theo tenant/site/zone/building; nếu áp dụng xuống tòa con thì khai báo rõ. ACL cấp đọc cho workspace BQL; agent trong phiên dùng quyền workspace, không có role của người dùng.

Các bảng cần nạp đồng bộ: `knowledge_bases` active; `knowledge_documents` published + `active_version_id`; `document_versions` có hiệu lực; `document_scopes`, `document_acl`; `vh_technical_sop_profiles` khớp chính xác mã và phiên bản. Chỉ gửi PDF hoặc chỉ ghi profile là chưa đủ để `sop_kb.retrieve` trả tài liệu.

Để nghiệm thu bước đầu, yêu cầu SOP cho các tình huống có trong bộ đánh giá hiện hành: nước yếu/mất nước/rò nước và sự cố điện tương ứng mã issue đã thống nhất. Team Quang xác nhận danh mục và số tài liệu thực có; không tạo hướng dẫn nghiệp vụ giả để lấp dữ liệu.

## Gián đoạn và lịch cắt dịch vụ

Manifest gồm id/mã, tenant, dịch vụ (`utility` theo enum trong `domain/interruption.ts`), phạm vi site/zone/building, trạng thái chính thức, thời gian dự kiến bắt đầu/kết thúc, thời gian thực tế bắt đầu/kết thúc và nguồn cập nhật.

Nạp `service_interruptions` và `interruption_scopes` trỏ tới `access_scopes` hiện có. `active` có `actual_start` mới là gián đoạn đang diễn ra; lịch được duyệt/thông báo không được báo như đang mất dịch vụ. Múi giờ phải rõ, dùng ISO timestamp có offset. Dữ liệu lịch sử hoặc test phải được đánh dấu trong bộ bàn giao, không đưa lên môi trường thật như sự cố thật.

## Danh mục và dữ liệu phụ trợ

- Mapping mã tòa/khu/căn hộ của Quang sang UUID nghiệp vụ; coverage BQL phải khớp cùng phạm vi.
- Nếu triển khai các tool thiết bị/lịch sử: danh mục thiết bị, vị trí, loại và mã thiết bị, lịch sử bảo trì, phép đo có thời điểm và đơn vị, bằng chứng/nguồn. Đối chiếu contract `server/src/technical-api/database.ts` trước khi nạp.
- Nếu dùng RAG tìm kiếm nội dung ngoài SOP: file/chunks, namespace và ACL, embedding model đúng dimension của kho, trạng thái publish; kiểm chứng ingestion/retrieval riêng. Ba tool đọc hiện tại không chứng minh RAG đã có dữ liệu.

## Bằng chứng bàn giao

Gửi manifest + file nguồn + script import có thể chạy lại + mapping ID + kết quả truy vấn/tool. Bộ kiểm chứng cần có SOP hợp lệ, hết hiệu lực, không đủ ACL; gián đoạn đang diễn ra, lịch tương lai, đã khôi phục; cùng một truy vấn trong và ngoài phạm vi BQL. Kết quả phải đúng và mỗi call có audit. Không yêu cầu team Quang gửi credential hoặc khóa model trong tài liệu.

Tin nhắn có thể gửi team Quang:

> Nhờ team bàn giao bộ SOP đã duyệt và dữ liệu gián đoạn/lịch cắt dịch vụ theo manifest tại tài liệu này. Ưu tiên các ca nước/điện trong bộ đánh giá agent kỹ thuật. Cần file nguồn, phiên bản/hiệu lực, issue code, tiêu chí nghiệm thu, scope/ACL workspace BQL, mapping UUID và script import chạy lại được. Bàn giao kèm kết quả tool cho ca có dữ liệu, không có dữ liệu và ngoài quyền. Gateway đọc đã mở; hiện cần dữ liệu nghiệp vụ đủ điều kiện để nghiệm thu.
