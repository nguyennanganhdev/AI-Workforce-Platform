# Báo cáo vòng 4: key/model, dọn lỗi, kế hoạch đối tác–sandbox, đóng gói Docker

14/10/2026 · Nhánh `feat/wf-remaining` · Người đọc: PM

## Tóm tắt

| # | Việc | Kết quả |
|---|---|---|
| 1 | Gắn key OpenAI, phân loại model | Xong: model nền `gpt-5.4-mini`, model cao `gpt-5.5`. **Chưa gọi model lần nào** |
| 2 | Kế hoạch cho ba phần còn thiếu của API đối tác | Xong (tài liệu), chờ anh/chị chốt D1–D3 |
| 3 | Sandbox nên làm thế nào | Xong (tài liệu): tự dựng bằng gói Docker, dùng gói Vinhome làm đối tác thật; chờ chốt D4–D5 |
| 4 | 2 test lỗi `mcp_rename_test.py` + lint Python file cũ | Xong |
| 5 | 21 cảnh báo lint frontend | Xong: 0 lỗi, 0 cảnh báo |
| 6 | File JS chính 767 kB | Xong: còn 240 kB |
| 7 | PR #76 / #78 | #76 đã vào `develop2`. **#78 lại vào `feat/wf-p0-p3`, không vào `develop2`** → mở PR mới (mục 7) |
| + | Lỗi hợp đồng tự phát hiện | Sửa: API đối tác đòi header `X-External-User-Id` mà hợp đồng không có |
| + | Đóng gói Docker và chạy | Xong: stack `awp-develop2` đang chạy, tài khoản và dữ liệu demo đã tạo sẵn |

Kế hoạch chi tiết mục 2–3: `KE_HOACH_DOI_TAC_VA_SANDBOX_2026-10-14.md`.

## 1. Key và model

- Key lấy từ `vinhome_Recident/agents/reception/.env` (OpenAI chính thức), ghi
  vào `platform_VP/agentscope/.env` (gitignored). Kiểm tra bằng `/models` (không
  tốn token): HTTP 200, 133 model.
- Phân loại:
  - **Model nền** `gpt-5.4-mini`: agent chuyên môn, tóm tắt context, ReMe.
  - **Model cao** `gpt-5.5`: Leader, copilot Studio, chấm kiểm thử, agent mức
    "mạnh", chấm eval.
  - **Không dùng** `gpt-5.6-luna/sol/terra`: chưa rõ hạng, và Luna từ chối gọi
    tool qua Chat Completions nếu không tắt reasoning (đã gặp ở Reception).
  - **Không dùng** các bản `-pro`: rất đắt.
- `bootstrap_demo.py` đã thêm credential OpenAI cho tài khoản quản lý demo.

## 4–5. Dọn lỗi có sẵn

- `tests/mcp_rename_test.py`: lỗi do test cũ. `MCPView` đã có thêm 4 trường
  (`tools`, `catalog_revision`, `last_synced_at`, `last_sync_error`) → cập nhật
  giá trị kỳ vọng: 3/3 pass.
- **Lint Python:** dự án dùng pre-commit (black/flake8/pylint), không dùng
  ruff. Hook `fix-encoding-pragma` của dự án còn **thêm** dòng
  `# -*- coding: utf-8 -*-` mà ruff đòi bỏ. Ruff báo 365 mục trên code
  workforce, chủ yếu là kiểu viết dự án không áp dụng. Đã sửa các lỗi thật: import thừa,
  import trùng/sai thứ tự, biến giải nén bỏ quên, nối chuỗi chưa bọc ngoặc. 4
  chỗ "biến vòng lặp trong closure" đã được xem từng chỗ: closure dùng ngay trong
  cùng vòng lặp nên không phải lỗi, giữ nguyên.
- Script `export_contracts.py` được chạy lại và sinh lại schema hợp đồng
  `workforce-v1.schema.json`, thêm các model team đã viết nhưng chưa xuất (ví
  dụ upload asset của khách). Đã commit riêng.
- **Frontend:**
  - 4 cảnh báo thiếu dependency của hook: sửa mà không đổi thời điểm chạy.
  - 17 cảnh báo fast-refresh: chuyển helper, context và hook sang file `.ts`
    riêng (6 file mới).
  - `tsc`, `lint` (0/0) và `build` đều qua.

## 6. Kích thước frontend

Tách thư viện dùng chung bằng `codeSplitting` của Vite 8: `react` 285 kB,
`ui` 180 kB, `data` 80 kB; file chính còn **240 kB** (trước 767 kB). Các chunk
lớn còn lại là ngôn ngữ highlight code và markdown, chỉ tải khi cần.

## 7. Trạng thái merge

- #76 → `develop2` (04:07:06).
- #78 có base là `feat/wf-p0-p3`, nên được merge vào nhánh đó (04:07:24), sau
  khi #76 đã vào. Vì vậy **`develop2` chưa có 11 vấn đề và mọi việc vòng
  này**.
- Đã mở PR mới `feat/wf-remaining` → `develop2` (chứa nội dung #78 và các
  commit vòng 4). Cần merge PR này thì `develop2` mới là bản demo đầy đủ.

## Lỗi tự phát hiện: header không có trong hợp đồng

Ở vòng trước, chế độ hợp nhất bắt buộc header `X-External-User-Id`. Hợp đồng
quy định `external_user_id` nằm trong query (GET) hoặc body (POST). Một đối tác
làm đúng hợp đồng, như cầu nối Vinhome, sẽ bị từ chối. Đã sửa theo hợp đồng và
cập nhật test, script sandbox và hướng dẫn.

## Đóng gói Docker và chạy

- `docker compose --profile demo up -d --build` dựng 7 service: app, web
  (nginx), demo-mcp, Postgres, Redis, MinIO, minio-init. Project `awp-develop2`,
  tách khỏi các stack khác.
- Ba trục trặc của môi trường đã xử lý:
  - Image `minio/minio` không còn kéo được → dùng
    `cgr.dev/chainguard/minio` (hai stack khác trong máy cũng dùng).
  - Trên máy này, cổng mở ở `0.0.0.0` bị một bộ chuyển tiếp Windows nhân bản
    sang `[::1]` và treo, làm `localhost` không vào được → mặc định chỉ mở trên
    `127.0.0.1` (biến `BIND_HOST`).
  - MCP demo từ chối Host `demo-mcp` (chống DNS-rebinding) → tắt kiểm tra này
    khi server không chạy ở loopback.
- `bootstrap_demo.py` (không gọi model) đã tạo: tài khoản quản lý khu vực,
  credential OpenAI, MCP demo (10 tool), key đối tác, tuyến `tower-a`
  (active). Mật khẩu và key nằm ở `platform_VP/agentscope/.artifacts/demo-access/ACCESS.md`.

## Test tự động

| Bộ | Kết quả |
|---|---|
| `tests/workforce` (toàn bộ) | **706 passed**, 22 skipped (PostgreSQL riêng/Playwright, CI có), 313 subtests, 0 lỗi |
| Bộ collaboration của CI + `mcp_rename_test.py` | **214 passed**, 0 lỗi |
| Frontend | `tsc` sạch, `lint` 0 lỗi/0 cảnh báo, `build` OK |
| Docker | 7 service lên, app healthy, web/API/CORS kiểm qua `localhost`, bootstrap chạy 2 lần (lần 2 bỏ qua bước đã có) |

Không có test nào gọi model thật.

## Việc tiếp theo

1. Merge PR mới vào `develop2`.
2. Anh/chị test theo `HUONG_DAN_TEST_PLATFORM.md` (stack đang chạy, mở
   `http://localhost:5173`).
3. Chốt D1–D5 trong kế hoạch đối tác–sandbox để tôi làm phần A rồi B.
