# Chạy local trên Windows không cần quyền admin

Môi trường đã được cài trong `.codex-artifacts/portable/runtime` trên máy này:
PostgreSQL 16.15, pgvector 0.8.6, Python 3.12 và thư viện API từ conda-forge.
Bun dùng bản có sẵn trong tài khoản Windows. Không tạo Windows service, không sửa
PATH hệ thống, không yêu cầu Docker. Tool và dữ liệu local được Git ignore.

## Bật và tắt

Mở PowerShell thông thường ở thư mục gốc dự án:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-local-portable.ps1
```

Tham số ExecutionPolicy chỉ áp dụng cho tiến trình này; không sửa policy máy.
Script khởi động nền, ghi log và PID trong `.codex-artifacts/portable/`.
Cổng đang có tiến trình lắng nghe được giữ nguyên; script không tự dừng tiến trình khác.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/stop-local-portable.ps1
```

Lệnh tắt giữ nguyên dữ liệu và dừng PostgreSQL bằng `pg_ctl` để đóng database đúng cách.
Sau khi khởi động lại Windows, chạy lại lệnh bật. Không di chuyển thư mục dự án
đang chứa runtime/database trong khi các service còn chạy.

## Địa chỉ và tài khoản

| Thành phần | Địa chỉ |
| --- | --- |
| Cư dân | http://127.0.0.1:3011 |
| BQL và admin | http://127.0.0.1:3020/operations/login |
| Nhân viên kỹ thuật | http://127.0.0.1:3023/operations/login |
| API Swagger | http://127.0.0.1:8000/docs |
| API readiness | http://127.0.0.1:8000/ready |
| Dịch vụ tài khoản/kết nối | http://127.0.0.1:3001/health |
| PostgreSQL | 127.0.0.1:5544 |

Dùng nhất quán `127.0.0.1` khi mở các app. Proxy gửi surface riêng để cookie
cư dân và nhân viên không thay thế phiên của nhau.

- Admin: `services/vinhomes-api/.local-connected/initial-admin.txt`.
- BQL, kỹ thuật, cư dân: `services/vinhomes-api/.local-connected/accounts.txt`.
- Cấu hình API: `services/vinhomes-api/.env.connected`.
- Cấu hình dịch vụ tài khoản: `.env` tại gốc repo.
- PostgreSQL admin local: `vinhomes_seed`; mật khẩu nằm trong
  `.codex-artifacts/portable/postgres-password.txt`.
- Database ứng dụng: `vinhomes_connected`. `vinhomes_v3` chỉ được tạo để kiểm tra
  migration/bootstrap, không phải database ứng dụng hiện đang dùng.

Các file trên chứa mật khẩu sinh ngẫu nhiên, được Git ignore. Không commit hoặc gửi
chúng trong chat công khai. Các tài khoản và căn hộ là dữ liệu thử trên máy này;
không phải bản backup dữ liệu của nhóm.

## Phạm vi đã chạy

Database thật, đăng nhập mật khẩu, API nghiệp vụ, frontend cư dân/BQL/nhân viên
và dịch vụ xác minh phiên tài khoản chạy local. Đã kiểm tra migration, pgvector,
readiness và đăng nhập/tải hồ sơ của bốn vai trò qua proxy frontend.
Đã kiểm tra một vòng tắt/bật và đăng nhập lại; cả `app` và `resident-app` build
Vite thành công. Build `app` còn cảnh báo chunk lớn và một số module Node được
externalize; chưa thay thế kiểm thử toàn bộ màn hình/nghiệp vụ trong trình duyệt.

Đây chưa phải toàn bộ stack AI của deployment Docker. Launcher chưa khởi động
Reception, Coordination, Knowledge, Factory, routines hoặc runtime OpenBot
Intelligence. AI thật cần API key/model và cấu hình agent đã publish của nhóm;
OAuth/connector ngoài cần credential riêng. API trả lỗi dịch vụ chưa cấu hình
khi gọi các phần đó, không tự chuyển thành AI giả. Cổng 3010 không được launcher này mở.
Dịch vụ tài khoản ở 3001 chạy entrypoint `business-connections.ts`, không phải
runtime OpenBot Intelligence đầy đủ; role database local chỉ có quyền đọc.

PostgreSQL portable dùng dòng 16 do gói pgvector Windows của conda-forge đi kèm
dòng này. Toàn bộ migration hiện tại đã áp dụng được. Deployment của nhóm dùng
PostgreSQL 17; không dùng cluster này để thay thế hoặc restore mù backup PG17.

## Công cụ và giới hạn mạng

Runtime này được cài bằng [micromamba](https://mamba.readthedocs.io/en/latest/installation/micromamba-installation.html),
dùng gói [pgvector của conda-forge](https://anaconda.org/conda-forge/pgvector).
Python và PostgreSQL nằm trong dự án, không có bước installer cấp máy.

Khi cần đồng bộ thư viện JavaScript, dùng Bun với trust store Windows:

```powershell
bun --use-system-ca install --frozen-lockfile
```

Một số gói tải vẫn có thể bị proxy công ty từ chối. Không tắt toàn bộ TLS.
Trong lần cài này, micromamba dùng `MAMBA_SSL_NO_REVOKE=true` cho riêng tiến trình
cài vì endpoint kiểm tra thu hồi không truy cập được; xác minh chứng chỉ vẫn bật.
Ổ `P:` tạm ánh xạ vào `.codex-artifacts` được dùng để rút ngắn đường dẫn cache;
launcher chạy ứng dụng không cần ổ ánh xạ này.

Các script bật/tắt dùng runtime đã cài trên máy này, chưa phải bộ cài tự động
cho một máy mới. Khi clone repo sang máy khác, cần cài lại runtime và bootstrap
database/config local; file binary, mật khẩu và dữ liệu không đi theo Git.
