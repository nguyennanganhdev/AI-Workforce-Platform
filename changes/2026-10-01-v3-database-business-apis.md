# API nghiệp vụ mới dùng PostgreSQL V3

- Ngày: 2026-10-01
- Yêu cầu: hoàn thiện endpoint theo kế hoạch demo và bản cập nhật `my-docs/nghiep_vu_moi.md`; dữ liệu giả phải được seed/ghi vào database thật. Chỉ viết HTTP API, không viết tool, runtime hoặc API gọi RAG.

## Thay đổi

- Bổ sung camera/contact, cảnh báo ACK/chuyển cấp, phê duyệt điều động/hủy bảo vệ, account membership, agent trong room và đề xuất memory.
- Bổ sung phương án HITL BQL → cư dân; cư dân đồng ý mới tạo các work order. Ticket mới yêu cầu phương án được duyệt trước khi dispatch; fixture cũ giữ contract cũ.
- Một hội thoại có nhiều ticket; ticket có idempotency key. Ảnh được lưu/kiểm tra checksum trước khi có ticket, gắn vào message rồi liên kết ticket.
- Bổ sung dữ liệu thiết bị/sensor/measurement, quyền thao tác, xác minh kết quả, lịch sử bảo trì, hóa đơn/thanh toán demo, báo cáo và job xuất DOCX.
- Bổ sung bản ghi đánh giá và quyết định admin cho agent, phiên bản cấu hình, Task Board, Mailbox và context room. Không thực thi AgentScope/LLM.

## File/module chính

- `server/drizzle/0003_vinhomes_security.sql`, `0004_vinhomes_business_flows.sql`: bảng có FK, RLS và ràng buộc trạng thái; bỏ unique một ticket/chat.
- `services/vinhomes-api/src/vinhomes_api/v3_*.py`: router, quyền, validation và transaction.
- `services/vinhomes-api/scripts/seed_v3_remaining.sql`, `upgrade_demo_database.ps1`: seed bổ sung và nâng cấp database khi chạy launcher.
- `scripts/generate-db-schema.py`: giữ export security và không tái tạo unique channel của ticket.

## Quyết định & giả định

- Giữ PostgreSQL Docker cổng 5544, FastAPI cổng 8000; không reset volume. Runtime role không là superuser và không bypass RLS.
- FastAPI dùng danh tính/quyền người yêu cầu từ Hono. Demo loopback dùng các actor seed; không có dịch vụ auth thứ hai.
- BQL phụ trách phê duyệt các hành động nghiệp vụ. p1–p4 ánh xạ từ P0–P3 theo quyết định đã chốt.
- Registry/version và trạng thái nghiệp vụ do backend lưu. Team hoàn thành không tự đổi trạng thái ticket.
- Upload hiện dùng storage local demo; thanh toán là bản ghi giả, không gọi nhà cung cấp.

## Xác minh

- Đã áp dụng migration 0003/0004/0005 và seed bổ sung bằng script upgrade, thành công.
- Đã gọi API PostgreSQL: camera/account reads; alert create/retry/ACK/escalate; guard dispatch approval/accept/cancel rejection; room agent create/add; memory proposal/admin approve; account lifecycle.
- Đã chạy thủ công: hai ticket trên một chat, tạo ticket chống trùng; plan BQL/resident approve; progress; upload/complete/checksum/message/image attachment; agent evaluation record/admin decision; report reads và tạo export.
- Ruff format/check F cho 12 module mới: thành công ở lần chạy đã ghi nhận. Chưa chạy test suite, chưa thêm test.
- Invoice create đã sửa `staff_profiles.status` thành `active`; create/issue/payment/retry thành công: 50.000 issued, 25.000 collected, 25.000 outstanding.
- Luồng draft/commit/plan BQL+resident/assignment accept/en_route/arrived/in_progress/before+after/executor result/customer completion/feedback/maintenance append chạy thành công; retry maintenance trả cùng ID.
- Configuration/evaluation synthetic/admin approval tạo immutable version; team/task/mailbox/state chạy đến completed. Đây là persistence API, không chạy runtime.
- Link ảnh trả 68 bytes PNG; dùng link dưới danh tính khác nhận 403. DOCX tải được, mở ZIP có word/document.xml. Sai role admin 403, room ngoài quyền 404, task version cũ 409.
- Restart FastAPI rồi đọc lại ticket closed và team completed thành công. Ruff F cho V3, Python AST, migration JSON, node --check và git diff --check đạt. Ruff toàn service có 10 unused imports ở module cũ ngoài V3, chưa sửa ngoài phạm vi.
- Migration 0005 sửa trigger đang đếm accepted assignments của work đã hoàn thành; đồng bộ baseline invariants. Không sửa migration đã áp dụng.
- API trạng thái kiểm tra plan, công việc bắt buộc, customer acceptance và QC. Ticket mới cần ảnh trước khi hoàn thành. Truy vấn QC được chạy dưới runtime RLS: fixture fail trả true, công việc hoàn thành không có fail trả false; chưa chạy nhánh redo pass đầy đủ.

## Rủi ro / việc còn lại

- Luồng chính đã xác minh; chưa kiểm chứng mọi tổ hợp đa công việc, cư dân từ chối/redo, đồng thời, cancel guard được duyệt hoặc lỗi storage giữa transaction.
- Workspace có thay đổi song song ngoài task: resident-app, resident_contract/resident_cases, dependency và file 0005_resident_contract.sql. Giữ nguyên; file đó chưa thuộc journal của task này, không tuyên bố đã áp dụng hoặc tích hợp.
- Chưa kiểm tra trực quan UI, chưa tích hợp runtime/provider/S3; đánh giá agent trong demo là fixture, không là kết quả LLM judge.
- Generator dictionary chưa chạy lại: thao tác đọc `design/v2.json` bị treo trong môi trường hiện tại. Migration/runtime schema đã được áp dụng trực tiếp.
