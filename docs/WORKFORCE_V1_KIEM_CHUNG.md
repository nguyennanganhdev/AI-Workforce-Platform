# Workforce v1: bằng chứng triển khai và giới hạn nghiệm thu

Ngày 10/10/2026, worktree `E:\AI-Workforce-Platform-dev_platform`, branch `dev_platform`. Lõi mới là `platform_VP/core/awp`; vendor AgentScope không bị sửa. Merge source đã có trước đợt này; không thay worktree `E:\AI-Workforce-Platform` hay cấu hình dịch vụ Vinhomes đang chạy.

## Phạm vi đã triển khai

Reception thuộc Vinhomes, ghi command vào outbox trong transaction cư dân. Backend gửi Workforce API với binding cư dân/BQL/ticket/generation/channel; route chọn supervisor. Supervisor tổ chức chuyên viên đã công bố bằng AgentScope TeamCreate/AgentCreate; customer không chọn đội khi tạo workflow.

Profile có vai trò, mission, instructions, team/tool allowlist, model/tier, knowledge và memory. Workflow pin profile/model/giá/route/integration/tài liệu. Session execution có epoch riêng theo lease generation; worker cũ không thể lấy quyền của lượt mới. Case file giữ dữ kiện, bằng chứng, câu hỏi, tranh luận và báo cáo chung; memory riêng theo workflow/profile không tự trở thành evidence.

PostgreSQL giữ command/job/lease/checkpoint/operation intent/event/consent. Redis là message bus; không giữ nguồn trạng thái duy nhất. Model phải được khai báo giá; reserve trước provider call. Mặc định route $0.50/100.000 token mỗi workflow, trần tháng $100/tenant UTC; có thể cấu hình. Đó là giới hạn kiểm soát, không phải số đo chi phí thực tế. SDK retry/fallback bị tắt trong luồng Workforce để tránh attempt không được reserve. Mất usage giữ nguyên reservation.

MCP Vinhomes cung cấp đọc ticket/nhân lực, đề xuất phương án, tạo work order và chào assignment qua lệnh nghiệp vụ hiện có. Service actor cần RBAC và grant BQL/tool. Write mặc định cần structured consent; category tự giao mặc định rỗng. Unknown sau mất phản hồi được đối soát bằng bằng chứng; không gọi lại thao tác. Kết quả đối soát terminal có thể đưa supervisor tiếp tục đúng một lần.

MinIO private quản lý ảnh; finalize xác minh bytes/SHA/MIME/pixel trước attach. Model vision nhận derivative bỏ EXIF; proxy đọc kiểm quyền. Provider progress được đồng bộ bằng outbox, inbox, HMAC, version và dedupe; không gọi LLM cho mỗi progress. Resident UI hiển thị consent và dừng theo dõi riêng; dừng workflow không hủy công việc hoặc đóng ticket.

Console có cookie HttpOnly, CSRF, admin/operator/viewer, profile version, routes, credentials, MCP, knowledge, workflow/cost và đối soát/audit. Mật khẩu/khóa local ở file ignored, không nằm trong JavaScript hay Git.

## Kiểm chứng

| Kiểm tra | Bằng chứng và phạm vi |
|---|---|
| Core | `python -m pytest -q` với `AWP_TEST_INFRA=1`: 53 passed trong 134,91 giây; gồm regression baseline và Workforce. Sau mở rộng đoạn thi công/QC, test kết nối chạy riêng đạt trong 13,19 giây |
| Tải orchestration | `test_twenty_native_agent_teams_execute_concurrently`: 20 workflow và 60 session AgentScope, PostgreSQL/Redis thật, model giả; có question/answer/report và chặn số không có evidence |
| Process | `test_cross_process_queue_drains_once`: hai consumer Redis process nhận 200 item không trùng; `test_two_processes_initialize_fresh_postgres_schema`: hai process khởi tạo cùng DB mới |
| Recovery/quyền | Lease hết hạn, owner/generation cũ bị chặn spend/finalize; session cũ không nhận execution mới; revoke cư trú chặn read/spend; budget tháng; command replay/conflict |
| Side effect | Mất response sau MCP write chỉ dispatch một lần, chuyển unknown; đối soát có evidence tạo một supervisor continuation, không redispatch |
| Domain kết nối | `test_reception_handoff_mcp_consent_staff_progress_and_tracking_close`: restricted PostgreSQL role, migrations domain, Reception thật, HTTP ASGI, MCP SDK, MinIO thật, structured consent, work order/offer, nhân viên accept/en_route/arrived, đề xuất sửa chữa và cư dân duyệt, in_progress, evidence trước/sau, complete, QC độc lập, cư dân xác nhận đóng ticket qua API; provider progress và late event không mở lại workflow đã dừng |
| Ảnh | File Vinhomes ready/scan clean → transfer upload MinIO → finalize → workflow attach; kiểm SHA/scope/immutability; bucket private |
| Resident UI | 3 test `resident-workforce-ui.test.tsx`; consent đúng operation, chống gửi lại, hết hạn, dừng tracking cần bước xác nhận riêng. Chạy file DOM riêng process |
| Frontend | `npm run build -w @vinhomes/resident-web`: TypeScript và Vite đạt |
| Container | API/worker build bằng dependencies hash-pinned, chạy riêng cùng PostgreSQL/Redis/MinIO; health HTTP và 9 endpoint dữ liệu console đạt; source trong image và console được đối chiếu với source cuối |
| Provider SDK | Khởi tạo không gọi mạng thành công cho OpenAI, OpenAI-compatible, Anthropic, DashScope, DeepSeek, Gemini, Moonshot, MiniMax, Volcengine, xAI, Ollama trong image |
| Static | Ruff đạt trên module Workforce, scripts/tests mới và adapter domain mới; `git diff --check` đạt. Không tuyên bố lint toàn repository sạch |
| CI | Thêm job `workforce-core` vào workflow hiện có: test không yêu cầu infra, lint và kiểm OpenAPI khớp source. Chưa push nên chưa có kết quả GitHub Actions |

Test infra dùng PostgreSQL port 5589 và Redis DB 15 riêng; API/worker sandbox dùng Redis DB 0. Không dùng chung wakeup queue giữa test database và ứng dụng. Database domain test có tên riêng và được thu hồi sau test; không migrate database Vinhomes đang phục vụ.

## Chưa nghiệm thu

- **Model thật:** sandbox chưa có provider/model được lựa chọn và cấu hình. Các model giả chứng minh orchestration và contract; không chứng minh khả năng tự lập kế hoạch, chất lượng hội thoại, vision, factual accuracy hay giá thực trả. Cần eval bằng model thật với transcript/evidence/usage, đặt ngưỡng chất lượng và chi phí trước khi bật cho cư dân.
- **Nghiệp vụ mở rộng:** luồng kỹ thuật không yêu cầu kế hoạch ban đầu đã chạy qua toàn bộ API nhân viên → báo giá/phê duyệt cư dân → evidence → QC độc lập → xác nhận đóng ticket. Chưa nghiệm thu mọi category, emergency, luồng kế hoạch cần BQL duyệt, redo/reject/cancel hoặc thao tác UI thực tế.
- **Browser/mobile:** frontend build và DOM tests đạt; browser automation không khả dụng trong môi trường phiên này. Chưa có bằng chứng thao tác trực quan trên browser/mobile.
- **Sự cố vận hành:** lease/generation, uncertain write, startup hai process và bus hai process đã được kiểm thử; chưa diễn tập đầy đủ kill/restart worker đang gọi model thật, mất mạng hạ tầng, backup/restore và soak test dài hạn.
- **SDK vendor:** load test còn cảnh báo `ChatService.run was never awaited` trong nhánh spawn-race/retry của wakeup dispatcher AgentScope. Test vẫn đạt; vendor giữ nguyên. Theo dõi/tái hiện riêng trước khi nghiệm thu vận hành dài hạn. Có thêm cảnh báo deprecation SDK/MinIO và serializer MemoryConfig baseline.
- **RAG/memory:** knowledge hiện là tài liệu text đã duyệt với lexical retrieval, không phải semantic/vector RAG. Memory giới hạn theo workflow/profile; không phải trí nhớ dài hạn xuyên workflow được tự hợp nhất.
- **Tự giao/hủy:** chưa có category/điều kiện tự giao được người dùng xác nhận nên không bật. Chưa expose MCP hủy công việc; yêu cầu hủy cần quy trình domain riêng, không ánh xạ sang close tracking.
- **Retention ảnh:** staging bỏ dở có lifecycle một ngày trên bucket mới; ảnh đã attach giữ lại. Chính sách lưu/xóa ảnh nghiệp vụ và dữ liệu cư dân cần được chốt khi onboarding.

## Chạy lại và onboarding

Trong `platform_VP/core`: `uv sync --frozen`, `uv run python scripts/init_local.py`, `docker compose up -d --build`. Local console ở `http://127.0.0.1:8089/console`; tài khoản ở `.local/accounts.txt` ignored. Điền khóa model trong `.env`, catalog/giá trong `models.yaml`, tái tạo API/worker. Không cần gửi khóa trong chat.

Test core không có infra tự skip các bài PostgreSQL/Redis/MinIO. Để chạy đủ, bật `AWP_TEST_INFRA=1`; domain test cần cài editable `vinhomes-api[workforce]` và cấu hình riêng `RESIDENT_TEST_ADMIN_URL`, `RESIDENT_TEST_RUNTIME_URL` theo fixture domain `test_resident_contract.py` được import bởi `test_vinhomes_workforce.py`, trỏ sandbox với runtime không BYPASSRLS. Không trỏ test vào database đang phục vụ.

Onboarding thật theo `WORKFORCE_VINHOMES_ONBOARDING.md`: migration/roles, service actor/grants, provider schema/transitions, MCP endpoint/secrets, route revision confirm, resident membership, profiles/model/giá và asset origin. Domain feature flag vẫn tắt mặc định cho đến khi nghiệm thu.
