# N2 — nghiệm thu cặp image trên staging cách ly

Bản đã kiểm: app/web `vin-n2-platform-rc:9876d94e`, `vin-n2-web-rc:9876d94e`, Domain bên dưới. Staging đang lưu ở `P/.artifacts/n2-s16-staging-r4`; hai CMD scenario 2 PASS/0 SKIP, saved Leader reply UI PASS, restore 4/4 kho. Chi tiết và giới hạn: [S16 handoff](../N2_HANDOFF_SLICES_20261018.md), [manifest](evidence/n2-s16-20261018.json). Không ghi đè thư mục này khi chạy lại; dùng output mới hoặc cleanup-only để dọn.

Thứ tự đã chốt: staging trước, VPS sau. Runner không đọc deployment.env, không dùng model thật và không thay stack đang phục vụ. `VIN_PLATFORM_ENABLED=true`, `VINHOMES_CUSTOMER_PLATFORM_ENABLED=true`, M2/chatbot cohort cutover=false. DB fixture nâng đến 0024, tách khỏi DB ứng dụng.

## Build từ commit sạch

Từ `platform_VP/agentscope`, lấy SHA đã commit rồi build bằng Dockerfile production:

```powershell
$rcSha = git rev-parse HEAD
$rcTag = git rev-parse --short HEAD
docker build --label "org.opencontainers.image.revision=$rcSha" -t "vin-n2-platform-rc:$rcTag" -f Dockerfile .
# Từ examples/web_ui:
docker build --label "org.opencontainers.image.revision=$rcSha" --build-arg VITE_API_BASE_URL=/api --build-arg VITE_VIN_EXPERIENCE_ENABLED=true -t "vin-n2-web-rc:$rcTag" -f frontend/Dockerfile .
```

Domain đã giao: `vinhomes-domain-api:vin-n1-6ef348ce-rc-20261018`. Runner đối chiếu revision label, pip check, non-root và hash Python/SQL của Domain; đối chiếu toàn bộ file Python Platform/main.py và hash bundle trích từ web image. Hai API chạy CMD production, không mount source ứng dụng. Guard mạng test là mount riêng; nginx chỉ đổi port/upstream loopback, giữ rules proxy/cookie/SSE/cache/SPA. Staff web dùng dist N1 có sẵn.

## Chạy / dọn riêng fixture

Từ `platform_VP/agentscope`, thay `<tag>` bằng tag vừa build; output phải mới:

```powershell
.venv/Scripts/python.exe scripts/workforce/check_vin_rc.py --app-image vin-n2-platform-rc:<tag> --web-image vin-n2-web-rc:<tag> --domain-image vinhomes-domain-api:vin-n1-6ef348ce-rc-20261018 --staff-dist E:/AI-Workforce-Platform/vinhome_Recident/apps/staff-web/dist --output .artifacts/n2-staging-<tag> --restore --keep-running
# Dọn đúng fixture theo state + ownership label, không dọn stack khác:
.venv/Scripts/python.exe scripts/workforce/check_vin_rc.py --output .artifacts/n2-staging-<tag> --cleanup-only
```

Loopback dành riêng: Platform/web 18104; staff 18105; Domain 18101; PostgreSQL 15459; fake model 18103; Redis 18106. Runner kiểm tra port trước tạo fixture. Không mở ra Internet. Nếu PASS và có `--keep-running`, để staging chạy cho chủ dự án xem; FAIL tự dọn. Dữ liệu/cookie/token fixture nằm trong `.artifacts` ignored, không đưa vào Git. Không dùng tài khoản thực trên stack này.

Hai scenario RC: (1) đăng nhập/consent/link → Leader SDK gọi CustomerService context/create → staff UI + API xử lý/ảnh/QC → cư dân bấm duyệt repair/completion → replay receipt/canonical closure/zero BQL; (2) admin N2-08 đọc/sửa quota rồi xác minh persistence bằng session mới. Script yêu cầu đúng ba scripted calls cho Leader, không gọi repair model sau receipt thành công. Restore chạy riêng bốn kho synthetic; app đã restore không được khởi động, không phải cutover production.

Bảy journey bổ sung ở [runbook browser/runtime](N2_BROWSER_RUNTIME_RUNBOOK_20261018.md) kiểm C07 plan approve/reject với hai revision riêng, C09 126 run qua sáu trang, Builder/eval/publish/checkpoint, lịch/Discord/outbox và admin CAS/library. Phải báo riêng kết quả source integration và RC; không suy tất cả scenario source đã chạy trên CMD image. Fixture dispatcher qua Domain API không chứng minh agent tự phân công staff. Model thật, chất lượng nghiệp vụ, ảnh đầu vào/vision và chữ ký UAT vẫn là các gate riêng.

Evidence máy: `rc-summary.json`, `domain-package`, hash assets, ảnh browser, summary N1, `restore/deep-restore.json`. Chỉ đưa metadata đã bỏ bí mật vào handoff. Trước VPS cần chốt đúng stack/URL, backup, migration/config, rollback và người ký UAT; không tự bật M2 từ kết quả health/fixture.
