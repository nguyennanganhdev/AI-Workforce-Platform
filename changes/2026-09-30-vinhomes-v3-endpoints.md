# Bổ sung API endpoint V3 cho FE và client agent

## Trạng thái mới nhất: demo dùng PostgreSQL V3 + dữ liệu faker

- Chủ dự án yêu cầu dữ liệu giả nằm trong database, API dùng schema thật. `main.py` không còn chọn ứng dụng RAM khi bật demo; dùng cùng các router V3. `demo_api.py`/test RAM cũ chỉ là lịch sử, không phải entry point đang chạy.
- Thêm Docker Compose riêng với `pgvector/pgvector:pg17`, port loopback 5544 và volume bền vững. `setup_demo_database.ps1` dùng migrator gốc của server, seed và cấu hình runtime role không superuser/BYPASSRLS. Credential sinh ngẫu nhiên, chỉ lưu trong `.local-v3-faker/` bị Git bỏ qua.
- Seed bảng V3 với nhân vật cư dân/BQL/kỹ thuật/an ninh/admin, membership và scope, 20 căn hộ, chuyên môn/ca trực, coverage, 21 ticket mẫu, 20 hóa đơn issued + invoice_lines, room, agent và storage. Dữ liệu tổng hợp SQL, không thêm dependency Faker. Seed chạy lại không reset trạng thái ticket.
- Chọn actor fixture trên loopback bằng header khi bật demo, sau đó vẫn kiểm tra quyền/scope trong DB. Tắt demo giữ xác thực Hono/dev user hiện có. `/demo/fixtures` đọc UUID thực tế từ database.
- Sửa BQL phân công thay vì chỉ admin; khóa hàng staff để kiểm tra capacity/ca trực/chuyên môn và offer timeout. Sửa availability bỏ assignment hết hạn/việc đã hoàn tất. Thêm `/dispatch-queue` đọc work order queued trong phạm vi.
- Khi hoàn tất: yêu cầu bằng chứng active và nước đã khôi phục, tạo customer_completion và ticket resolved. Cư dân duyệt chuyển closed; từ chối đưa việc về in_progress. Message/mention phản hồi demo được ghi vào PostgreSQL, mention done, không gọi LLM.
- Sửa upload ảnh local theo tenant_prefix trong storage_locations để đáp ứng trigger object_version_scope; download kiểm tra đường dẫn nằm trong root. Grant UPDATE một cột staff_profiles phục vụ SELECT FOR UPDATE, cùng các bảng ghi bổ sung.
- Gateway Hono demo kiểm tra dataMode=faker-database; hướng dẫn mới `HUONG_DAN_DEMO_DATABASE_V3.md`; các hướng dẫn RAM được đánh dấu lịch sử.

### Bằng chứng thực hiện

- Docker PostgreSQL healthy; migrator báo migrations-applied ok; seed/grant thành công.
- `/health` trả schema v3 + faker-database; `/ready` ready. OpenAPI hiện có 68 path.
- Gọi API trực tiếp trên database faker: chat/message → ticket → routing ACK → work order → BQL phân công → nhân viên nhận → en_route/arrived/in_progress → đề xuất nước → BQL duyệt → notify/start/restore → upload ảnh → evidence → completed → cư dân duyệt. Ticket `9d0211eb-cffc-4c60-94f7-f3224e1aefcf` kết thúc closed; assignment và approval nằm trong DB.
- Báo cáo issued-revenue qua gateway Hono trả 20 hóa đơn, 4.100.000 VND từ invoice_lines. Mention demo-report lưu status done. Đã có một lần upload bị trigger tenant_prefix từ chối; sửa code rồi upload/gắn evidence thành công. Có một lần dispatch thiếu quyền lock staff; bổ sung grant rồi phân công/nhận thành công.
- Compileall thành công; git diff --check thành công (cảnh báo LF/CRLF). Không thêm hoặc chạy suite test mới trong lần chuyển nguồn dữ liệu này; bằng chứng là thao tác API trên database cục bộ.

### Việc còn lại

- Các route chỉ có ở RAM trước đó chưa tự trở thành router V3: camera/contact ngoài, chuỗi cảnh báo/ACK, phê duyệt điều động/hủy, account FastAPI, tạo agent trong room, đề xuất memory. Schema work_approvals hiện chưa cho kind điều động/hủy. Không thêm bảng ngoài contract trong lần đổi nguồn dữ liệu này.
- Chưa nối/xác minh các màn hình FE; gateway hiện là demo chọn actor, chưa phải ủy quyền phiên người dùng thật. Hóa đơn đang là fixture seed, chưa tự phát hành cho mọi công việc mới. Các mục bên dưới là lịch sử trước lần chuyển sang database.

- Ngày: 2026-09-30
- Yêu cầu: Triển khai API endpoint theo backlog trong `my-docs/DANH_SACH_TOOL_API_CAN_XAY_DUNG.md`, tuân thủ `Agent-rules/`. Cùng cổng 8000 phục vụ FE và client agent; không viết mã agent tool.

## Thay đổi

- Thêm xác thực tenant member cho tài nguyên của cư dân; giữ xác thực operations hiện có cho các route BQL/nhân viên.
- Bổ sung chat, tin nhắn, ticket của cư dân, thông báo, phê duyệt sửa chữa, group room và trạng thái mention.
- Chat cư dân có thể tạo đúng một ticket cho căn hộ đã xác minh; route đến BQL theo coverage, thông báo BQL; BQL ACK sẽ ghi event và báo lại cư dân.
- Bổ sung tra nhân viên còn năng lực, tìm kiếm knowledge theo ACL/scope, báo cáo tần suất sự cố và giá trị hóa đơn đã phát hành (JSON/DOCX), admin duyệt memory.
- Bổ sung yêu cầu ngừng nước, phê duyệt BQL, thông báo cư dân bị ảnh hưởng, ghi nhận ngừng và cấp nước lại.
- Khóa quyền phê duyệt nước cho BQL phụ trách; cư dân quyết định các approval `customer_repair`/`customer_completion` được giao cho mình.
- API sự cố an ninh nhận mức nghiệp vụ P0–P3 và ánh xạ sang cột `p1`–`p4`, vẫn giữ input cũ.

## File/module chính

- `services/vinhomes-api/src/vinhomes_api/v3_auth.py` — tenant member dependency.
- `services/vinhomes-api/src/vinhomes_api/v3_resident.py` — chat, ticket, thông báo, approval cư dân.
- `services/vinhomes-api/src/vinhomes_api/v3_rooms.py` — room messages và mention.
- `services/vinhomes-api/src/vinhomes_api/v3_operations.py` — availability và quyền phê duyệt.
- `services/vinhomes-api/src/vinhomes_api/v3_specialized.py` — ánh xạ mức an ninh.
- `services/vinhomes-api/src/vinhomes_api/v3_knowledge.py` — tra tri thức theo ACL.
- `services/vinhomes-api/src/vinhomes_api/v3_reports.py` — JSON và DOCX report trực tiếp.
- `services/vinhomes-api/src/vinhomes_api/v3_memory.py` — admin review memory.
- `services/vinhomes-api/src/vinhomes_api/v3_water.py` — gián đoạn cấp nước.
- `services/vinhomes-api/src/vinhomes_api/main.py` — nạp router mới.
- `services/vinhomes-api/README.md` — cập nhật quyền và endpoint cổng 8000.
- `my-docs/DANH_SACH_TOOL_API_CAN_XAY_DUNG.md` — cập nhật phạm vi và tiến độ.

## Quyết định & giả định

- Giữ DB `p1`–`p4`, ánh xạ P0→p1, P1→p2, P2→p3, P3→p4 theo quyết định chủ dự án.
- BQL phụ trách duyệt khóa nước và các đề xuất điều động/hủy theo quyết định chủ dự án; đề xuất điều động/hủy chưa có endpoint và schema tương ứng.
- Doanh thu là giá trị dòng hóa đơn trạng thái `issued`, không phải tiền đã thu; category kỹ thuật được chọn qua `categoryId`.
- Client agent dự kiến đi qua Hono với quyền người yêu cầu. Gateway ủy quyền từ Hono sang FastAPI chưa có trong thay đổi này; không tin actor ID do client tự gửi.

## Xác minh

- `python -m compileall -q` trên các module sửa/thêm: thành công.
- Sinh OpenAPI từ `vinhomes_api.main.app`: thành công, có 66 path sau khi bổ sung chat→ticket và routing ACK.
- `git diff --check`: thành công trên các file Git đang theo dõi lúc kiểm tra. Sau đó checkout chung chuyển sang `dev_TeamChien-beHuy` và một commit WIP đã theo dõi phần lớn `services/`; các thay đổi của task vẫn còn trong working tree.
- `docker ps` không kết nối được Docker Desktop Linux Engine vì daemon chưa chạy.
- Chưa chạy test hoặc gọi endpoint với PostgreSQL/Docker; chưa xác minh SQL với database thật.

## Rủi ro / việc còn lại

- Chưa có API đầy đủ cho camera metadata, cảnh báo khẩn cấp/ACK, điều động/hủy và phát thông báo tự động cho mọi loại event. Chủ dự án xác nhận camera và contact khẩn cấp nằm ở hệ thống ngoài; đang chờ địa chỉ/contract.
- Mention mới được ghi `queued`; chưa có worker chạy agent. DOCX tạo trực tiếp, chưa dùng `report_requests` và không có job nền.
- Gateway Hono→FastAPI cho agent chưa được nối; agent nền không có cookie trình duyệt để tự gọi các endpoint bảo vệ ở cổng 8000.
## Bổ sung theo yêu cầu demo mock

- Chủ dự án cho phép dữ liệu mock để chạy đầy đủ luồng. Thêm `demo_api.py`, bật bằng `VINHOMES_API_DEMO_MODE=1`, không cần PostgreSQL. Không thay đổi bảng/database V3.
- Có trạng thái ticket, queue/assignment, phê duyệt nước và điều động/hủy bảo vệ, cảnh báo/ACK, bằng chứng metadata, nghiệm thu/sửa lại, thông báo, room/mention, báo cáo hóa đơn mock issued + DOCX, quản trị account và memory.
- Gateway riêng `server/scripts/vinhomes-demo.ts` trên loopback 3001 chuyển tiếp tới FastAPI mock 8000, không gọi DB hoặc server Hono chính. Chọn vai trò qua header demo; không mô phỏng thành xác thực phiên thật. Không viết agent tool.
- Script `scripts/start_demo.ps1`; tài liệu `HUONG_DAN_DEMO_MOCK.md`; cập nhật danh sách endpoint và hướng dẫn Swagger.
- Kiểm tra `python -m pytest services/vinhomes-api/tests/test_demo_api.py -q`: **3 passed** (luồng nước + hóa đơn/DOCX, an ninh + phê duyệt/ACK, sai quyền + nhân viên bận + idempotency + khóa account). Có cảnh báo deprecation từ Starlette TestClient/httpx.
- Chạy FastAPI thật trên 8000 và gateway Hono trên 3001; gọi health qua cả hai, resolve BQL qua Hono thành công. `git diff --check` thành công.
- Mock reset khi restart; phản hồi agent là mẫu đồng bộ, không gọi LLM. Bằng chứng chỉ là metadata/tham chiếu demo, không upload ảnh thật. Contract mock dùng ID dễ đọc; chưa xác minh tích hợp FE hiện tại hoặc SQL/database V3. Các phần chờ hệ thống ngoài ghi trước đó chỉ còn áp dụng cho chế độ dữ liệu thật.
