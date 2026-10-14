# Báo cáo vòng 5: nối Vinhome thật vào develop2, chạy trên VPS

14/10/2026 · Nhánh `feat/wf-partner-case` (PR #80, CI xanh) · Người đọc: PM

## Tóm tắt

- develop2 đã hiểu bộ khai báo của Vinhome (`vinhomes-declaration.json`) mà
  **không cần sửa gì bên Vinhome**. Có:
  - leader riêng cho route (agent Agent Studio, nói bằng `CaseSay`);
  - tool `vh_*` với `client_reference` do platform tự điền;
  - sự kiện provider (có ký HMAC, tin mẫu, hạng sự kiện, đánh thức leader);
  - duyệt của đối tác;
  - onboarding một lệnh.
- Platform đang chạy **trên cùng VPS** với Vinhome, đã nối:
  - route `local-management` ở trạng thái **active**;
  - cầu nối Vinhome **bật** (`http://awp-platform:8000`);
  - hai khoá đều được chấp nhận.
- Đã chạy thử đầu-cuối với ChatService thật, model **giả** và MCP **giả**:
  phiếu → tra cứu → giao việc → tin cho cư dân → sự kiện → mời xác nhận →
  đóng. Lần chạy này lộ ra một lỗi (leader thấy cả tool nhóm), đã sửa.
- **Chưa gọi model thật lần nào.** Phần test với cư dân thật là của anh/chị.

## Sandbox là gì trong trường hợp này

Vinhome đã chạy thật trên VPS. "Sandbox" chỉ là **môi trường thử của platform**
mà Vinhome nối vào bằng khoá riêng (`--environment sandbox`), trước khi coi là
production. Nó đã được dựng: platform `awp-platform` trên VPS, client
`Vinhomes (sandbox)`.

## VPS: có ảnh hưởng gì tới Vinhome không

| Hạng mục | Tình trạng |
|---|---|
| Tài nguyên | RAM còn trống khoảng 2,2/3,8 GB (platform dùng khoảng 600 MB); đĩa còn 23 GB |
| Cổng | Platform chỉ mở trên `127.0.0.1` (8000, 5173, 5442, 6390, 9200/9201), không trùng cổng Vinhome (80/443/8011/8080/5560) |
| Dữ liệu | Platform có Postgres/MinIO/Redis riêng (project `awp-platform`); không đọc DB của Vinhome |
| Những gì đã đổi bên Vinhome | (1) `deployment.env`: thêm `MCP_ALLOWED_HOSTS=api:8000` và thay 5 dòng `VINHOMES_API_PLATFORM_*` (bản cũ: `deployment.env.bak-awp-20261014`); (2) khởi động lại `api`, `platform-sync` đúng tag đang chạy; (3) đóng 2 liên kết thử cũ (12/10, `mock-an`) của platform cũ, vì chúng làm cầu nối đọc lỗi 404 mỗi giây |
| Hành vi | Từ lúc bật cầu nối, phiếu Lễ tân bàn giao sẽ do leader của platform xử lý bằng model thật (`gpt-5.4-mini`, key OpenAI) |

**Rủi ro thật: có hai phiên cùng triển khai.** Từ khoảng 14:00, một phiên làm
việc khác (cùng tài khoản git) đã:

- thêm 2 commit vào nhánh này: `33310ad7` cấp token MCP riêng cho từng
  workflow, `d4d0af55` đóng gói tokenizer cho VPS không có mạng ra ngoài;
- chạy lại platform trên VPS bằng image `agentscope-local:platform-owned-d4d0af55`;
- triển khai Vinhome bằng image `platform-owned-c8dbc981`.

Hai phiên không xung đột git (phiên kia làm tiếp trên commit của tôi). Nhưng
nếu cả hai cùng đẩy image lên VPS thì bản sau sẽ đè bản trước. Từ thời điểm
này **tôi không triển khai lên VPS nữa** cho tới khi anh/chị chỉ định một phiên
phụ trách VPS.

## Đã làm (commit trên `feat/wf-partner-case`)

| Commit | Nội dung |
|---|---|
| `233f95da` | Mã lỗi close đúng hợp đồng: `REVISION_CONFLICT`, `WORKFLOW_NOT_READY_TO_CLOSE`, `APPROVAL_PENDING`, `WORKFLOW_CLOSED`. Payload `approval.required` có `arguments_hash`, `expected_revision` |
| `0cb52353` | Runtime đối tác: `CaseSay`/`CaseFinalize`, bộ kiểm câu, tool khai báo, operation, sự kiện provider, duyệt, onboarding, migration `0017` |
| `dc34ef76` | `compose.partner-network.yaml` và runbook VPS |
| `66327d6e` | Onboarding kiểm MCP **trước** khi cấp khoá (khoá chỉ hiện một lần) |
| `036e3c87` | Leader đối tác chỉ thấy `CaseSay`, `CaseFinalize` và tool khai báo; thêm bộ kiểm thử offline `scripts/workforce/offline_partner_e2e` |
| `33310ad7`, `d4d0af55` | Của phiên kia (xem trên) |

Test tự động:

- integrations/orchestration/e2e/console/foundation: 391 passed;
- bộ collaboration của CI: 214 passed;
- test mới cho đối tác (luồng Vinhome, duyệt, bộ kiểm câu, bộ lọc tool,
  onboarding với BusinessService thật) đều pass;
- CI PR #80 pass.

## Anh/chị test thế nào

1. **Phía cư dân (Vinhome thật):** vào `https://vinhome-platform.duckdns.org`
   bằng một tài khoản cư dân thử (danh sách ở
   `vinhome_Recident/deploy/test-accounts-20261013/`), nhắn một yêu cầu sửa
   chữa đủ thông tin.
   **Đạt khi:**
   - Lễ tân tạo phiếu;
   - vài giây sau trong hộp chat có lời của trợ lý điều phối: chào, nói đã gửi
     việc cho nhân viên và đang chờ người nhận;
   - nhân viên đúng chuyên môn thấy lời mời việc trong app nhân viên.
2. **Phía nhân viên:**
   - Nhận việc → cư dân nhận tin mẫu "Nhân viên … đã nhận yêu cầu…, dự kiến
     đến lúc …", không qua model.
   - Đang đến, đã đến, bắt đầu, xong → các tin mẫu tương ứng.
   - Gửi kết quả nghiệm thu → leader được đánh thức, mời cư dân xác nhận.
   - Cư dân bấm xác nhận → workflow đóng.
3. **Phía platform:** mở đường hầm rồi vào `http://localhost:5173`.
   - Lệnh đường hầm:
     `ssh -i ~/.ssh/vinhomes_vps_103_238_235_156 -N -L 5173:127.0.0.1:5173 -L 8000:127.0.0.1:8000 root@103.238.235.156`
   - Tài khoản nằm trong `/opt/awp-platform/app/ACCESS.md` trên VPS.
   - Quản lý agent có agent `DieuPhoiVinhomes` (v1, không cho mời).
   - **Kết nối đối tác** có tuyến `local-management` active.
4. **Khi có trục trặc:**
   - Log cầu nối: `docker logs vinhomes-domain-platform-sync-1`.
   - Log platform: `docker logs awp-platform-app-1`.
   - Trạng thái: `python -m vinhomes_api.platform status` trong `platform-sync`.

## Còn lại

| # | Việc | Ghi chú |
|---|---|---|
| 1 | **Chỉ định một phiên phụ trách VPS** | Tránh hai phiên đẩy image đè nhau |
| 2 | Test với cư dân thật (model thật) | Việc của anh/chị |
| 3 | Merge PR #80 | CI xanh |
| 4 | `/partner/approvals/{id}/chat` | Vinhome không dùng; làm khi có đối tác cần |
| 5 | Snapshot trả `pending_approvals`, Vinhome đọc `approvals` | Chỉ dùng khi cursor hết hạn; nên thống nhất tên trong hợp đồng |
| 6 | Giao diện platform chỉ vào được qua đường hầm SSH | Muốn mở công khai thì cần thêm tên miền và TLS |
