# Rà soát lại các bảng, sơ đồ và mô tả dự án

Ngày 04/10/2026, checkout `dev_teamChien_HuyDo`, HEAD quan sát `afa1af8`. Kiểm tra đọc PostgreSQL local và source; không tạo/sửa bảng hay chạy migration. Chỉ sửa tài liệu/sơ đồ do bản đồ trước tạo.

## Kết quả kiểm cấu trúc

- PostgreSQL `vinhomes_v3`: **193 bảng public, 682 FK**. Tập tên bảng và toàn bộ định nghĩa FK trùng catalog trong DATABASE_MAP; không chỉ so tổng số.
- Danh mục ALL_TABLES có đủ 193 mục; từ điển RAG có đủ 57 bảng đã chọn, không có tên bảng tưởng tượng trong tập này.
- Các cạnh FK nét liền trong bảy sơ đồ RAG khớp FK thật, bao gồm khóa ghép. Cạnh nét đứt là bước ứng dụng, không được đọc là constraint.
- 279 chunks/279 embeddings và các row count RAG là **snapshot backup 03/10**, không thay bằng số live hôm nay. 57 bảng là một phần của 193, không cộng thêm.

## Các điểm phải sửa cách hiểu

| Điểm | Cách mô tả trước dễ gây hiểu sai | Đối chiếu và sửa |
|---|---|---|
| Phạm vi RAG | “19 lõi + 38 liên quan” dễ đọc thành 57 bảng riêng cho RAG | 14 RAG/tài liệu/quyền/review + 5 memory/runtime-memory + 38 bảng nền/liên quan được báo cáo chọn. Đây là kiểm kê rộng, không là yêu cầu triển khai đủ 57 bảng cho retrieval |
| Phân team | Chia trang theo team dễ đọc thành ownership từng bảng hoặc mỗi team có DB riêng | Backend/schema dùng chung, tenant/kho/scope/ACL tách quyền. Trang team mô tả vai trò sử dụng/tích hợp; không quy tác giả hoặc DB ownership từ tên trang |
| Report trong Reception | `report_sources` nằm chung bảng liệt kê Reception | Report dataset/provenance, không là bảng nguồn passage/citation và không có FK tới document/version/chunk. Đã tách mục Report khỏi bảng Reception |
| Hai Reception | Sơ đồ/chỉ số trước áp toàn bộ `knowledge.py` cho Reception | Chỉ nhánh graph dùng `answer/used`, retry 502 một lần. Loop dùng `Toolbox._search_knowledge` + `loop.py` với `reply/sources`; cùng API/topK/timeout nhưng khác flow |
| Học Q&A | Luồng tổng thể ghi người có quyền duyệt mọi candidate | `v3_learning.decide`: personal/not generalizable→rejected; low risk→approved tự động; fee/rule/safety→pending BQL. Approved vẫn cần export/publish để vào RAG |
| Memory schema | Có bảng memory/context dễ đọc thành runtime đã ghi đầy đủ | Chưa thấy writer cho context_snapshots/runtime_memory_bindings/run_memory_access trong module runtime/RAG/Vinhomes đã rà. FK tồn tại không chứng minh runtime tích hợp |
| Storage | PostgreSQL runtime trong checklist dễ đọc như quyết định đã chốt | Khuyến nghị của hướng dẫn, chưa triển khai/chưa chốt với các team. Cần semantics persistence; chọn storage theo môi trường. Không tạo thêm bảng runtime từ việc viết tài liệu |
| Tiến độ M2 | Bản đầu còn nói code chưa commit/chưa có live evidence | Code sau đó đã commit. Báo cáo M2 ghi live-model/E2E và browser 24/24; chưa rerun lần này. Vẫn analysis_ready + NoTools + UnboundBackendActions/UnboundEvents |

## Nguồn chính cần giữ riêng

1. **Yêu cầu sản phẩm:** [Yêu cầu Vinhomes](../../../VINHOMES_BUSINESS_REQUIREMENTS.md), kế hoạch chung/team. Payment/accounting, nhiều vấn đề trong một tin và cấu hình riêng mỗi BQL không tự thành feature đã xong vì DB có bảng.
2. **Schema thực tế:** [Catalog live](../DATABASE_MAP_2026-10-04/schema-live.json), migrations và kiểm PostgreSQL. Schema có cả nền OpenBot, nghiệp vụ và extensions.
3. **Code hiện tại:** Reception graph/loop, v3_learning, Vinhomes Coordination ports/runtime, Hono optional hosts. Quyền nghiệp vụ vẫn do backend.
4. **Bằng chứng chạy được:** [M2](../SUPERVISOR_SESSION_V2_M2_2026-10-04.md) và artifact/test đúng commit. Không chép nhãn “chưa có” ở proposal Phái cũ hoặc “DONE” local thành trạng thái toàn hệ thống.
5. **Đề xuất còn mở:** PostgreSQL runtime, ownership/versioned groupchat và các mốc integration. Giữ nhãn đề xuất tới khi team chốt và implementation/test chứng minh.

Lần rà soát này chưa chạy lại paid-model/browser/E2E, chưa kiểm mọi branch/staging và chưa chứng minh đầy đủ ý định sản phẩm của owner từ một sơ đồ database. Nếu owner chỉ ra điểm nghiệp vụ khác, đối chiếu yêu cầu trước khi đổi schema.
