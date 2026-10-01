# Kết nối Resident – Operations – PostgreSQL, 01/10/2026

## Nhánh và nguồn merge

- Nhánh làm việc: `frontend/ft-resident`, nền frontend `2b9230d`.
- Đã fetch và merge `origin/dev_TeamChien-beHuy` tại `1980b30` vào frontend bằng merge commit `d24beef`.
- Backup trước merge: `backup/resident-before-behuy-20261001`.
- Xung đột `.gitignore`, `server/src/app.ts`, `server/src/index.ts` đã xử lý. Giữ API summary Hono cũ `/api/vinhomes/tickets`; router Hono bổ sung đặt tại `/api/vinhomes/v3`.
- Backend được tích hợp vào hai frontend là FastAPI V3 trong `services/vinhomes-api`, dùng schema PostgreSQL canonical của `server/drizzle`. Không dùng database legacy Alembic `vh_incident` làm nguồn ticket.
- Không sửa worktree riêng đang checkout nhánh backend. Chưa push các thay đổi lên remote.

## Hiện trạng trước tích hợp

Frontend có giao diện và reducer cho chat nhiều phòng, phản ánh, theo dõi, xác nhận/làm lại, auth, tài khoản và nhóm BQL, công việc điện/nước/an ninh, báo cáo mẫu. Dữ liệu nghiệp vụ nằm trong localStorage; thao tác thành công ở UI chưa tạo bản ghi backend.

Nhánh backend đã có API V3 cho ticket, conversation, routing, work order, assignment, approval, evidence, QC, redo, thông báo, cùng các module nước/an ninh/knowledge/rooms/reports và trang demo. Sự tồn tại của endpoint không chứng minh tất cả chức năng đã được nghiệm thu qua frontend.

## Phần đã nối với database

| Luồng | Thực hiện |
|---|---|
| Profile | Đọc user, căn hộ đã xác minh, danh mục dịch vụ từ database |
| Hội thoại | Tạo/đọc phòng riêng theo user, gửi tin với client message ID, đọc theo sequence, lưu read cursor |
| Gửi phản ánh | Chọn căn hộ/danh mục, mô tả/vị trí/contact, review trước gửi, tạo một ticket/phòng |
| Ảnh cư dân | Kiểm tra loại và decode ảnh, tối đa 10 MiB/ảnh, tối đa 3 ảnh trong command; private file read và ownership |
| Retry | Tạo ticket, upload ảnh và quyết định cư dân dùng key ổn định trong lần mở app; receipt ticket nằm trong event append-only |
| BQL | Đọc ticket cùng ID với cư dân, tiếp nhận, tạo phiếu, chọn nhân viên và phân công |
| Nhân viên | Chỉ đọc ticket đã có phân công; nhận việc kèm ETA, di chuyển, đến hiện trường, gửi phương án, thi công, upload bằng chứng |
| Đồng ý sửa chữa | Cư dân nhận phương án; backend chặn bắt đầu xử lý khi chưa có đồng ý |
| QC | Người có quyền quản lý nghiệm thu độc lập; không phát hành kết quả khi còn phiếu chưa hoàn thành hoặc QC chưa đạt |
| Kết quả | Cư dân xác nhận hoặc nêu lý do làm lại; kiểm version và ownership, chỉ một quyết định đồng thời thành công |
| Làm lại | Quay lại tiếp nhận; giữ nguyên phiếu, bằng chứng và QC cũ |
| Đồng bộ | Poll API mỗi 5 giây và sau thao tác; không chia sẻ localStorage giữa hai app |

Màn kết nối thật được tách khỏi màn preview để không đưa reducer hoặc quyền giả lập vào đường ghi database. Màn preview cũ vẫn mở qua nút trải nghiệm. Màn kết nối chưa thay toàn bộ chức năng và bố cục phong phú của preview.

## Các lỗi backend đã sửa

1. Commit transaction phải hoàn tất trước HTTP success: các dependency database V3 dùng `scope="function"` (FastAPI >=0.142). Trước đó lỗi constraint khi commit có thể xảy ra sau response 201.
2. File giữ nguyên security scope của conversation; liên kết vào `ticket_files`, không đổi scope bất biến.
3. Event không UPDATE để thêm receipt; ghi receipt/idempotency ngay khi INSERT.
4. Hoàn thành thi công không đồng nghĩa đạt QC. Chỉ phát hành yêu cầu xác nhận khi các phiếu cần xử lý đều hoàn thành và QC PASS.
5. Không cho BQL dùng chuyển trạng thái trực tiếp để đóng thay cư dân.
6. Phiếu completed/cancelled giải phóng assignment. Migration `0003_release_finished_assignments.sql` sửa các assignment cũ còn chiếm tải.
7. Retry quyết định trả cùng payload; version cũ và key trùng khác nội dung bị từ chối.
8. Thu hẹp quyền đọc của staff theo assignment; lỗi máy chủ auth không bị chuyển thành đăng nhập thành công hoặc demo.
9. Chặn mutation từ browser origin ngoài cấu hình.

## Cấu trúc app

Theo xác nhận của người dùng: chỉ xóa resident cũ, giữ Operations/BQL. Rà soát `app/src` không còn module hay route resident độc lập để xóa. `components/technician/resident-handover.tsx` là màn bàn giao của nhân viên, được giữ lại. `resident-app` tiếp tục là workspace riêng; không import code của `app`.

## Kiểm chứng

- PostgreSQL 17 + pgvector local, port 5544; migration canonical và seed fixture đã chạy thành công.
- Role API local là `NOSUPERUSER NOBYPASSRLS`.
- Hai bài integration HTTP chạy trên database thật: vòng xác nhận hoàn tất và vòng yêu cầu làm lại. Bao gồm ownership ảnh/ticket, căn hộ không hợp lệ, upload hỏng, retry khác nội dung, thiếu bằng chứng, staff không được QC, version cũ và hai quyết định đồng thời.
- Bộ Python hiện có và integration đã qua: 5 bài tại thời điểm chạy vòng nghiệp vụ cuối; kiểm tra origin bổ sung có lệnh bên dưới.
- 65 bài frontend hiện có đã qua; đây là kiểm tra reducer/preview, không thay thế integration database.
- Typecheck resident/app/server đã qua; build resident và app đã qua. App build còn cảnh báo bundle lớn/browser externalization từ dependency hiện có.
- `server db:verify`: 148 bảng, 1048 statements và 18 kiểm tra PostgreSQL cô lập đã qua.
- HTTP frontend 3011, frontend Operations 3020 và backend `/ready` trả 200.
- Chưa kiểm chứng trực quan bằng browser: công cụ browser phiên này không có browser khả dụng. HTTP/build không được coi là visual QA.

## Chưa thể gọi là hoàn chỉnh production

- Form đăng nhập/đăng ký bằng số điện thoại và reset/OTP vẫn chưa có nhà cung cấp. Backend có thể kiểm session platform qua `VINHOMES_API_AUTH_URL`, nhưng phiên đăng nhập thật chưa được nghiệm thu ở môi trường này.
- Local đang bật `VINHOMES_API_DEMO_MODE=1`: identity là tài khoản fixture, **dữ liệu nghiệp vụ thật trên PostgreSQL nhưng không phải xác thực production**.
- Chưa tích hợp hết UI quản trị tài khoản, nhóm/agent BQL, báo cáo, nước lớn, an ninh khẩn, vệ sinh, contractor, billing và knowledge. Các màn preview tương ứng vẫn là mẫu.
- Chat có persistence thật; chưa có AI provider production. Phản hồi tự động local do backend demo tạo.
- Staff file storage vẫn chỉ dành cho development; cần object storage production, scan, retention và cleanup orphan. Resident ảnh dùng private filesystem local, chưa có vận hành backup/cleanup tự động.
- Polling chưa phải push realtime. Notification delivery ngoài app chưa được nghiệm thu.
- Danh sách connected Operations hiện tối đa 100 ticket; approvals resident tối đa 100. Cần pagination UX trước dữ liệu lớn.
- Idempotency key FE hiện nằm trong bộ nhớ lần mở app; cần lưu journal theo user để retry chắc chắn qua reload giữa lúc gửi.
- Chưa có test browser hai phiên đăng nhập thật, test đa tenant đầy đủ hoặc nghiệm thu staging.

## Chạy lại

Xem [hướng dẫn kết nối](../resident-app/docs/07-connected-runtime.md). Không chạy seed demo lên database đang có dữ liệu thật.
