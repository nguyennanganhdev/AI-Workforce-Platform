# Checklist sandbox đối tác

Trạng thái: **chuẩn bị sẵn, chưa chạy**. Chưa có sandbox/UAT đối tác nào được
cấp, nên chưa có bằng chứng thật. CI chỉ được ghi sandbox là pass khi biến
`WORKFORCE_SANDBOX_EVIDENCE` trỏ tới bằng chứng do **người** đã duyệt
(xem `handoffs/phan-hoang-dung/PHASE_D_D5.md`). Script không bao giờ tự đánh
dấu "verified".

## 1. Cần được cấp trước

| Hạng mục | Ai cấp | Ghi chú |
|---|---|---|
| URL platform sandbox (HTTPS) | Team platform | Bật `WORKFORCE_PARTNER_API=true`, có PostgreSQL + worker |
| Model key hợp lệ trên sandbox | Team platform | Chạy thật sẽ tốn token |
| Partner API key | Admin, qua `POST /integrations/api-keys` (header `X-Provisioning-Secret`, body `domain_id`, `name`) | Chỉ hiện một lần; không commit |
| Quản lý khu vực đã xác minh | Admin, `POST /workforce/v1/admin/memberships/verify` | |
| Route đã cấp và đối tác đã xác nhận | BQL trong "Quản lý agent → Kết nối đối tác", đối tác gọi `POST /workforce/v1/partner/routes/{route_id}/confirm` | Ghi lại `external_management_ref` |
| Một `external_user_id` thử nghiệm | Đối tác | Không dùng dữ liệu cư dân thật |

## 2. Chạy

```bash
cd platform_VP/agentscope
export PARTNER_SANDBOX_BASE_URL=https://<sandbox>
export PARTNER_SANDBOX_API_KEY=<partner key>      # không in, không commit
export PARTNER_SANDBOX_MANAGEMENT_REF=<external_management_ref>
export PARTNER_SANDBOX_USER=resident-sandbox-1
.venv/Scripts/python.exe scripts/workforce/partner_sandbox_check.py
```

Script đóng vai đối tác qua hợp đồng `/workforce/v1` và ghi lại từng bước:

| Bước | Đạt khi |
|---|---|
| `start_workflow` | HTTP 200/202 |
| `read_result` | Request về `completed` trong `--timeout` (mặc định 300 s) |
| `idempotent_retry` | Gửi lại cùng `external_request_id` trả đúng `request_id` cũ |
| `event_history` | HTTP 200 |
| `sse_replay` | Stream SSE có sự kiện; nối lại bằng `Last-Event-ID` chỉ trả các sự kiện sau đó |
| `workflow_reply` / `read_reply_result` | Chỉ chạy nếu Leader hỏi lại (`awaiting_user`) |
| `close_workflow` | Chỉ chạy nếu workflow tới `awaiting_confirmation` |

Kết quả nằm ở `.artifacts/partner-sandbox/<thời gian>/evidence.json` và
`EVIDENCE.md`; dòng cuối in ra là ứng viên cho `WORKFORCE_SANDBOX_EVIDENCE`
kèm "pending human review".

## 3. Người duyệt kiểm tra

- [ ] Mọi bước trong `EVIDENCE.md` đều ✅; bước nào ❌ thì ghi lý do.
- [ ] Câu trả lời của Leader đúng nghiệp vụ, không bịa số liệu, đúng khu vực.
- [ ] Không có secret hay dữ liệu cá nhân thật trong `evidence.json`.
- [ ] Trên console, phiên Leader của ticket dùng đúng phiên bản agent đã phát hành.
- [ ] Điền "Reviewed by / Date / Decision" trong `EVIDENCE.md`, lưu file vào
      nơi lưu trữ của dự án.
- [ ] Chỉ khi Decision = VERIFIED: đặt biến repo `WORKFORCE_SANDBOX_EVIDENCE`
      = dòng ứng viên + đường dẫn nơi lưu bằng chứng.

## Giới hạn đã biết của chế độ hợp nhất

Partner approval API, sự kiện provider job và theo dõi thao tác ngoài
(`waiting_external_event`) chưa được gắn ở chế độ này; các thao tác có tác
động của tool đi qua cơ chế đồng ý (consent) của chat. Sandbox chỉ kiểm được
những gì hợp đồng ở trên mô tả.
