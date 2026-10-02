# Technical A2 HTTP API và PostgreSQL V3

## Yêu cầu

Thực hiện `my-docs/rag/endpoint_call_technical_tool.md`: 15 endpoint gọi 14 tool Technical A2 đã có của Team Quang; dữ liệu lưu PostgreSQL, API trả thông tin để agent tiếp tục xử lý.

## Thay đổi

- Lấy module và bộ test Team Quang từ `origin/dev_TeamQuang` commit `6094b53`; không viết lại tool hoặc agent/LLM.
- Thêm `server/src/technical-api/{routes,runtime,database}.ts`, gắn `/api/technical/v1` vào Hono; dùng token callback và run assertion đã ký, grants agent giao với scope người yêu cầu.
- Thêm migration 0009, RLS, trigger append-only, receipt idempotency và audit cùng transaction dữ liệu. Runtime chặn role có UPDATE/DELETE, superuser và BYPASSRLS.
- Thêm script cấp role, seed faker và kiểm tra HTTP/PostgreSQL. Cấu hình local giữ trong thư mục gitignored. Bổ sung hai tên biến vào `.env.example`.
- Cập nhật chính tài liệu yêu cầu với checklist hoàn thành, cấu hình, luồng và kết quả kiểm tra.

## Xác minh

- Migration áp dụng thành công vào PostgreSQL Docker demo port 5544; role và seed đã tạo.
- TypeScript kiểm tra thành công sau khi hoàn thiện router, runtime, adapter và script kiểm tra.
- 882 test Team Quang pass trên PGlite và 882 pass trên PostgreSQL thật. Sửa fixture để nạp toàn bộ migration V3 thay vì chỉ baseline.
- 5 test HTTP boundary pass: xác thực catalogue, query mapping, field lạ/trùng, JSON/path override và giới hạn body.
- Thử đủ 15 route với Hono `app.request` và PostgreSQL thật; luồng ghi số đo → gửi kết quả → verification → append lịch sử thành công; các đề nghị tạo pending. Retry trả đúng response gốc, không tạo trùng; đổi payload trả 409, chèn tenant trả 400, thiếu auth trả 403. Work order không bị đổi trạng thái.
- Sửa JSONB binding qua `::text::jsonb` để driver Bun không mã hóa JSON hai lần; dùng UUID hợp lệ trong fixture SOP/căn hộ.

## Rủi ro / việc còn lại

- Hono mặc định cổng 3001; FastAPI cổng 8000 không được thay đổi trong task này.
- Để phục vụ agent thật, bật hai biến TECHNICAL_API, khởi động lại Hono và cấp token/grants cho ID agent thật. Script thử dùng token tạm và không kiểm tra UI cấp token hoặc AI runtime.
- Người dùng đã yêu cầu push lên `dev_TeamChien-beHuy`. Phạm vi commit là API Technical A2, module Team Quang cần thiết, migration, seed, test và tài liệu; các thay đổi FE và tích hợp FE/BE tồn tại trước task được giữ ngoài commit.
