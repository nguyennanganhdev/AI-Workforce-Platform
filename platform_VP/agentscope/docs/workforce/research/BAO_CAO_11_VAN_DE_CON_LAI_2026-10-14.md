# Báo cáo xử lý 11 vấn đề còn lại

14/10/2026 · Nhánh `feat/wf-remaining` (xếp chồng trên `feat/wf-p0-p3` / PR #76) ·
Người đọc: PM

## Tóm tắt

- **10/11 vấn đề đã làm xong** và có test tự động; **vấn đề 11 (sandbox đối
  tác) đã chuẩn bị sẵn**, chờ được cấp sandbox — không đánh dấu đạt.
- **Chưa test với model thật.** Theo yêu cầu, chỉ chạy test tự động và build.
  Ngoài ra key hiện có trong máy đều bị 401 nên cũng chưa chạy thật được.
- Việc tiếp theo của anh/chị: điền key hợp lệ (mục 1), rồi test theo
  `docs/workforce/HUONG_DAN_TEST_PLATFORM.md` — mục 7 dành riêng cho vòng này.

## 1. Kiểm tra key và model

| Hạng mục | Kết quả |
|---|---|
| `.env` của worktree `develop2` | **Chưa có** → đã tạo (gitignored, không commit). Secret AUTH/PARTNER sinh ngẫu nhiên; cổng tránh các stack đang chạy: Postgres 5442, Redis 6390, MinIO 9200/9201 |
| Model | `MODEL_PROVIDER=openai`, `WORKFORCE_MODEL_NAME=gpt-5.4-mini`, `WORKFORCE_LEADER_MODEL_NAME=gpt-5.5`. **Tên model chưa xác nhận được** với gateway vì không có key chạy được |
| API key | `OPENAI_API_KEY` để **trống**. Hai key tìm thấy ở checkout chính (gateway OpenAI-compatible và DashScope) đều trả **401** |
| `.env` checkout chính | `MODEL_NAME` khai báo hai lần với giá trị khác nhau — nên dọn |
| Credential trong app | Workforce lấy model từ credential lưu trong app (trang Credential), không chỉ `.env` → phải thêm credential sau khi có key |
| Docker | Stack agentscope chưa chạy; ảnh `minio/minio` chưa có trong máy (lần đầu `compose up` phải tải) |

**Kết luận:** chưa sẵn sàng test thật. Cần một key hợp lệ; cách kiểm key và tên
model ở mục 1.4 của hướng dẫn test.

## 2. Kết quả từng vấn đề

Quyết định của anh/chị trong vòng này: vấn đề 1 và 3 **hợp nhất qua Agent
Studio**; vấn đề 11 **chuẩn bị sẵn, chờ cấp**.

| # | Vấn đề | Đã làm | Commit |
|---|---|---|---|
| 1 | API đối tác `/workforce/v1` chưa chạy Leader thật | Bật `WORKFORCE_PARTNER_API=true`: workflow đối tác chạy bằng **Leader console** của quản lý khu vực (`ChatService` + middleware hiện có). Mỗi ticket một session Leader, `workflow_reply` nối tiếp cùng session, trạng thái tiếp theo suy từ câu trả lời (hỏi lại → `awaiting_user`, xong → `awaiting_confirmation`). Thêm luồng onboarding 3 bên: admin xác minh quản lý, quản lý cấp tuyến, đối tác xác nhận; người dùng cuối lấy từ `external_user_id` của query/body như hợp đồng (sửa ở vòng 4) | `78a18e5c` |
| 2 | Kho kiến thức mất chỉ mục khi khởi động lại | Qdrant lưu trên đĩa (volume `workspaces`) mặc định; dùng Qdrant server nếu đặt `KNOWLEDGE_VECTOR_URL`; `:memory:` chỉ khi đặt rõ | `7b33cf7e` |
| 3 | Hai đường quản lý agent song song | Agent Studio là nguồn duy nhất: ticket (console lẫn đối tác) dùng agent Studio; khi được mời, session của agent **ghim phiên bản đã phát hành** lúc đó — phát hành bản mới không đổi ticket đang chạy. Quản lý cấp tuyến đối tác ngay trong Quản lý agent → **Kết nối đối tác** | `aed3fc06`, `9b22c8a5` |
| 4 | Xác nhận tool ghi dựa vào từ khoá tên | Cổng quyền đọc `requires_consent` của spec agent và `readOnlyHint=false` của MCP; tool bị buộc hỏi khách trước khi chạy, kể cả tên không có từ khoá ghi | `f21c09e7` |
| 5 | Leader chờ bằng vòng hỏi 0,5 s | Shared Context phát tín hiệu qua message bus mỗi lần đổi; Leader thức dậy theo tín hiệu, hỏi lại an toàn mỗi 5 s; không có bus thì giữ cách cũ | `fd84238f` |
| 6 | Số tính ra (giá × đêm) bị cổng bằng chứng chặn | Nhận thêm tích của số tiền có bằng chứng với số lượng có bằng chứng (và tích đó cộng giá gốc) | `fdb61d15` |
| 7 | Tóm tắt Shared Context dùng model đắt | Khi Leader dùng model mạnh, tóm tắt context dùng model mặc định (rẻ) | `00cb46f3` |
| 8 | Endpoint bật/tắt phát hành cũ bỏ qua phiên bản | Chỉ cho bật lại agent đã có phiên bản; chưa có → 409, hướng sang Quản lý agent | `2ccd4935` |
| 9 | Agent từ Builder chat cũ không có kịch bản kiểm thử | Builder sinh kèm 3 kịch bản; tab Kiểm thử có nút "Nhờ copilot viết kịch bản" cho agent cũ | `6971a2fc` |
| 10 | Bundle frontend > 500 kB | Mọi trang tải theo route (`lazy`); file JS chính còn ~767 kB vì thư viện dùng chung — xem mục 4 | `ee4c621d` |
| 11 | Sandbox đối tác `NOT_VERIFIED` | Script `scripts/workforce/partner_sandbox_check.py` đóng vai đối tác chạy toàn hợp đồng và ghi bằng chứng chờ người duyệt; checklist `docs/workforce/SANDBOX_DOI_TAC_CHECKLIST.md`. **Vẫn `NOT_VERIFIED`** | `61771628` |

Tổng: 12 commit, 37 file, +2.310 / −48 dòng.

## 3. Test tự động đã chạy

| Bộ | Kết quả |
|---|---|
| `tests/workforce` (toàn bộ) | 728 test, **không có test lỗi**; một số test bị skip vì máy local không có PostgreSQL riêng/Playwright (CI có) |
| Bộ collaboration trong CI (`workforce-phase-d.yml`, gồm test mới: consent, kho kiến thức, Leader wait, ledger) | **211 passed**, 11 subtests passed (15 file) |
| Test mới của vòng: chế độ hợp nhất (Leader hỏi → khách trả lời → đóng; header sai bị từ chối; script sandbox chạy hết hợp đồng trên app thật trong process), onboarding 3 bên trên schema đã migrate, ghim phiên bản, toggle cũ, sinh kịch bản, price × qty, tóm tắt bằng model rẻ, tín hiệu context | pass |
| Frontend: `tsc`, `lint`, `build` | `tsc` sạch; lint 0 lỗi (21 cảnh báo cũ); build OK |

Model, MCP và dữ liệu trong các test là bản giả lập; SQL, HTTP, job worker và
workflow là code thật.

## 4. Vấn đề còn lại / giới hạn

| # | Vấn đề | Mức | Đề xuất |
|---|---|---|---|
| 1 | Chưa có key model hợp lệ → chưa test thật được, tên model `gpt-5.4-mini`/`gpt-5.5` chưa xác nhận | Cao | Cấp key, chạy mục 1.4 rồi mục 3–7 của hướng dẫn |
| 2 | Chế độ hợp nhất chưa gắn: API duyệt của đối tác, sự kiện provider job, theo dõi thao tác ngoài (`waiting_external_event`) | Trung bình | Thao tác có tác động hiện đi qua xác nhận trong chat; làm tiếp khi đối tác cần duyệt từ phía họ |
| 3 | Sandbox đối tác chưa có | Theo D7 | Cấp URL + key sandbox, chạy checklist |
| 4 | `tests/mcp_rename_test.py` có 2 test lỗi **sẵn từ trước** (lỗi cả trên nhánh gốc), không thuộc CI | Thấp | Sửa riêng |
| 5 | Ruff báo lỗi ở vài file cũ (`check_phase_d_environment.py`, `export_contracts.py`, `test_phase_c_c7.py`); frontend còn 21 cảnh báo lint cũ | Thấp | Dọn riêng |
| 6 | File JS chính ~767 kB (thư viện dùng chung) | Thấp | Tách vendor (`manualChunks`) nếu thấy tải chậm |
| 7 | PR #76 (P0–P3) chưa merge; PR vòng này xếp chồng lên nó | — | Review/merge #76 trước |

## 5. Anh/chị test thế nào

1. Điền key, thêm credential, kiểm tên model — hướng dẫn mục 1.4.
2. Chạy lại các mục 2–6 (đã có từ P0–P3) để chắc không hỏng.
3. Mục 7 cho vòng này: 7.1 API đối tác (cần `WORKFORCE_PARTNER_API=true`),
   7.2 ghim phiên bản, 7.3 xác nhận tool, 7.4–7.7 các sửa nhỏ, 7.8 script sandbox
   chạy local.
