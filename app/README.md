# Chạy frontend nhân viên / OpenBot

Luồng FE mới: đăng nhập `/operations/login`, chọn tài khoản trong khu vực **trải nghiệm**. ADMIN-01 quản lý tài khoản; BQL-01 quản lý nhóm/ticket/báo cáo; KT-01 và AN-01 xử lý ticket đã được giao tại **Ticket & hiện trường**. Hướng dẫn nghiệp vụ và bàn giao backend: [Bốn luồng FE/UI](../resident-app/docs/05-workspace-fe-handoff.md).

Chạy các lệnh từ thư mục gốc repository:

```powershell
bun install --frozen-lockfile
bun run dev:operations
```

Giao diện nhân viên ở `http://localhost:3020`. Để chạy OpenBot ở cổng 3010,
dùng `bun run dev:openbot`. Tránh chạy hai Vite server của `app` cùng lúc khi
đang tái tạo cache; cả hai dùng chung thư mục `app/node_modules/.vite`.

## Runtime cho Vite

Chạy bằng Bun có sẵn, không cần cài Node.js hoặc quyền admin.
Các lệnh dev đi qua `scripts/vite.mjs`.

Trên Windows, Vite có thể báo `error while updating dependencies: undefined`
khi đổi tên `deps_temp_*` thành `deps` gặp khóa file tạm thời (`EPERM`).
Launcher cho phép thử lại thao tác này tối đa 60 giây, cách nhau 250 ms.
Chỉ áp dụng cho cache optimizer trong `app/node_modules/.vite` trên Windows;
không sửa package Vite, không thay đổi quyền truy cập hoặc thiết lập bảo mật.
Lỗi không liên quan đến khóa file được trả ngay; hết thời gian chờ vẫn báo lỗi gốc.

Lần đầu có thể mất thời gian để đóng gói dependencies. Khi thấy
`Waiting for Windows to release the dependency cache...`, chờ hoàn tất.
Nếu hết thời gian vẫn báo lỗi, dừng server trước khi thử lại, không chạy thêm
server khác vào cùng cache.

Tham khảo báo cáo tương tự (cũng xảy ra trên Node.js):
https://github.com/vitest-dev/vitest/issues/10890

Đã kiểm tra trên Bun 1.4.2: tạo cache mới thành công, tải `react.js` trả
JavaScript và Chrome render `/operations/my-tasks` không có Vite error overlay.
Các API như `/api/me` vẫn cần backend chạy riêng.
