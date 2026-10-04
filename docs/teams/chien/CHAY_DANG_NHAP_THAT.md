# Chạy hệ thống với đăng nhập thật (không dùng chế độ demo)

Ngày 03/10/2026. Áp dụng cho máy phát triển; các bước cũng là khuôn cho môi trường chung sau này.

Chế độ demo chọn vai bằng header và chỉ chạy trên máy phát triển. Chế độ đăng nhập thật dùng database riêng
(`vinhomes_connected`), tenant riêng, và mỗi người đăng nhập bằng email (hoặc số điện thoại) và mật khẩu của
chính mình. Backend ở chế độ này bỏ qua header demo.

## Dựng lần đầu

1. `python scripts/setup_password_database.py` (trong `services/vinhomes-api`): tạo database, tenant và một tài
   khoản quản trị. Mật khẩu quản trị nằm ở `.local-connected/initial-admin.txt`.
2. `PYTHONPATH=src python scripts/provision_connected.py`: nâng schema lên bản mới nhất, cấp quyền cho role của
   backend, rồi tạo tổ chức: khu Vinhomes Ocean Park 1 với 8 phân khu và 14 tòa, 20 căn tầng 12 của S1.01, đơn
   vị quản lý Sapphire (phụ trách cả phân khu Sapphire cho kỹ thuật và an ninh), phòng Ban quản lý có Supervisor,
   và ba tài khoản đầu tiên: Ban quản lý, kỹ thuật viên, cư dân căn 1201. Mật khẩu sinh ngẫu nhiên, ghi vào
   `.local-connected/accounts.txt`, không in ra màn hình. Chạy lại không tạo trùng và không đổi mật khẩu.
3. Nạp tri thức: `scripts/publish_learned.ps1 -Connected -User bql.sapphire@oceanpark.local -DataDir <thư mục
   Data-Vinhome>`, rồi ghi `KNOWLEDGE_TENANT_ID`, `KNOWLEDGE_BASE_ID` (lệnh in ra), `KNOWLEDGE_DATABASE_URL`,
   `RECEPTION_API_URL`, `KNOWLEDGE_PORT` vào `.local-connected/knowledge.env`.

Không file nào ở trên được đưa vào git (`.env.connected`, `.local-connected/`).

## Chạy

| Dịch vụ | Lệnh |
|---|---|
| Backend (8000) | `services/vinhomes-api/scripts/start_connected.ps1` |
| Tìm tri thức (8787) | `services/vinhomes-api/scripts/start_knowledge.ps1 -Connected` |
| Lễ tân (4202) | `agent-reception/scripts/start_runtime.ps1` |
| App cư dân (3011) | `bun run dev` với `VITE_ALLOW_DEMO_BACKEND=false` |
| Operations (3020) | `bun run dev:operations` với `VITE_ALLOW_DEMO_BACKEND=false` |

`start_connected.ps1` đọc cấu hình Lễ tân từ `.local-connected/reception.env` nếu có, không thì dùng chung
`.local-v3-faker/reception.env` với bản demo (máy phát triển chỉ chạy một dịch vụ Lễ tân). Backend demo và
backend đăng nhập thật cùng dùng cổng 8000 nên mỗi lúc chỉ chạy một trong hai.

## Đã kiểm ngày 03/10

- Qua API: không có phiên, sai mật khẩu hoặc header demo đều bị từ chối; mỗi tài khoản chỉ thấy dữ liệu của
  mình (kỹ thuật viên không đọc được hội thoại của cư dân, không thấy danh sách chờ duyệt của Ban quản lý).
- Trên trình duyệt, ba người đăng nhập bằng tài khoản thật: luồng sửa chữa 23 bước từ chat của cư dân tới lúc
  Ban quản lý duyệt đóng đạt cả 23 bước, không có lỗi HTTP.
- Chưa đăng nhập thì app cư dân tự chuyển sang trang đăng nhập (trước đó hiện trang chủ kèm dòng lỗi).

## Còn thiếu

- Thêm người: quản trị viên tạo tài khoản và gán vai trong Operations. Gắn cư dân vào căn hộ và tạo hồ sơ kỹ
  thuật viên (chuyên môn, ca làm) hiện chỉ có trong script, chưa có trên giao diện.
- Danh sách căn hộ thật: script mới tạo 20 căn mẫu của S1.01.
- Quên mật khẩu chưa nối (giao diện báo rõ là chưa có).
- Các phân khu ngoài Sapphire chưa có đơn vị quản lý nên cư dân ở đó chưa gửi được yêu cầu.
- Giới hạn số lần đăng nhập đang giữ trong bộ nhớ của một tiến trình; chạy nhiều tiến trình thì cần bộ đếm chung.
