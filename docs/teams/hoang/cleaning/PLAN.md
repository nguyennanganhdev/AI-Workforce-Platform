# Plan triển khai tool vệ sinh

Ngày 06/10/2026, nhánh `dev_TeamHoang_PhanDung`. Đã triển khai theo phạm vi đã chỉnh: nghiệp vụ giống kỹ thuật, đổi đội phụ trách sang vệ sinh, không sửa phần hiện hữu.

## Phạm vi

Chỉ thêm tool, contract/export, adapter, test và tài liệu trong ba thư mục vệ sinh. Không sửa source/test kỹ thuật, backend V3, database/migration, UI, agent/prompt/release hoặc gateway/runtime. Không tạo result store, audit/receipt hoặc transaction infrastructure riêng.

## Thiết kế và thực hiện

1. Đối chiếu toàn bộ 14 tool của `technical-tools/catalog.ts`, tạo mapping đối ứng rõ ràng. Đã hoàn thành.
2. Gọi trực tiếp implementation/schema của tool gốc qua adapter scope vệ sinh. Giữ nghiệp vụ, capability, effect, timeout, idempotency và approval. SOP đổi mã đối tượng sang CLEAN. Đã hoàn thành.
3. Bọc năm API nghiệp vụ V3 đã có để tìm đội vệ sinh, đọc/tạo việc, phân công và cập nhật tiến độ. Giữ quyền, version, ca/capacity và state machine backend. Đã hoàn thành.
4. Bỏ mọi điều kiện riêng từng tự thêm: gate VERIFIED khi completed, contract result có expected_version/observations/notes, store riêng và chống trùng mô tả ngoài luật backend. Đã hoàn thành.
5. Kiểm thử mapping/delegation cho từng tool, chức năng nghiệp vụ, scope vệ sinh, phân công và cập nhật trạng thái; kiểm typecheck/hồi quy và xác nhận diff phần hiện hữu rỗng. Đã hoàn thành.

## Cấu trúc

`server/src/cleaning-tools/` ngang hàng với `server/src/technical-tools/`, gồm catalogue, host/entry, contracts, ports và adapters. `tools/technical-counterparts.ts` bọc cả 14 tool gốc; `tools/operations.ts` bọc API điều phối nội bộ. Không đặt implementation mới vào module kỹ thuật.

Tests ở `server/tests/cleaning-tools/`. Mapping/contract ở [TOOLS.md](TOOLS.md), bàn giao/kết quả kiểm tra ở [IMPLEMENTATION.md](IMPLEMENTATION.md).

## Tiêu chí và ranh giới

Đủ 14 capability kỹ thuật có đối ứng chạy cùng implementation, không chỉ nêu trong tài liệu. Điều phối nhắm đúng đội vệ sinh; backend giữ quyền/policy/trạng thái hiện có. Không sửa file hiện hữu hoặc thêm bảng/migration. Module có 19 entry do năm API điều phối vốn nằm ngoài catalogue kỹ thuật.

Deployment vẫn cung cấp context/grants, work/evidence/result/SOP/mapping và backend bridge; không lấy việc xuất hiện agent mới trong groupchat làm tiêu chí của đợt tool. Chưa commit/push.
