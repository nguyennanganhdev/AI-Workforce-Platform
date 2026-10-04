# Nghiệm thu local — 05/10/2026

Người dùng chốt Docker local trước; bật CI và merge PR #31 khi checks đạt; dùng Playwright headless; để phiên khác hoàn thiện MCP.

| Task | Đã làm/kiểm hiện tại | Chưa đạt |
|---|---|---|
| 1. Model/UI/MCP | UI mới dùng tài khoản thật: admin tạo đơn vị, chung đăng nhập, cư dân tạo ticket có ảnh MinIO. Gọi API model thật để kiểm khóa. | Reception key: 401 `invalid_api_key`; Factory key: 429 `credit_balance_exhausted`. Chưa tìm khóa Gemini/DeepSeek/Claude. Chưa nghiệm thu hội thoại/plan/MCP trên image mới; không dùng mock/bằng chứng cũ thay thế. |
| 2. Docker/restore/monitor/CI | Các dịch vụ/container healthy. Restore độc lập: 194 bảng nghiệp vụ, 6 bảng checkpoint, 8 object; số dòng/checksum khớp. Monitor unavailable sau 3 lần và recovered khi lên lại. CI đã bật. | Domain/chứng chỉ thật hoãn theo người dùng. Webhook chưa có đích để nghiệm thu. CI/merge cập nhật bên dưới. |
| 3. Admin tạo đơn vị | UI tên/mã/tòa/dịch vụ, transaction tạo coverage/workspace/phòng BQL/Supervisor/membership admin/preset báo cáo. RBAC/tenant/input/overlap/rollback đạt; Playwright POST 201. | Admin cấp thêm tài khoản BQL ở trang Tài khoản. |
| 4. Preset báo cáo | Instructions chính thức đóng gói trong API image; tự có nháp khi tạo đơn vị. Job idempotent cài vào phòng BQL mặc định, giữ nguyên agent đã chỉnh sửa/phát hành/thu hồi; chỉ publish khi sáu ca runtime đạt. | Model lỗi nên job giữ nháp; tự phát hành chưa nghiệm thu, cần chạy lại khi có khóa/quota. |
| 5. Một đăng nhập | OpenBot xác minh `vinhomes_session` qua nghiệp vụ mỗi request, cùng `users.id`, quyền canonical; role riêng giới hạn bảng. `/api/me`, trang tài khoản và sign-out dùng chung phiên Operations. Có link Kết nối cá nhân. | OAuth thật cần client/consent. MCP trong phòng BQL vẫn thuộc phiên MCP; caller cá nhân chưa nghiệm thu. Account host dùng plugin store theo user; runtime OpenBot tổng quát cần Intelligence riêng. Agent nghiệp vụ chạy qua Coordination/agent-bot. |
| 6. Upload trực tiếp | Browser metadata 201 → MinIO POST 204 → complete 200 → ticket 201, không POST ảnh qua API. Signed policy 5 phút/exact size/MIME/key; xác minh hash/image/quyền rồi copy sang key ready khác. Replay/cross-user/non-image kiểm với MinIO thật. Mobile không tràn ngang. | Bucket cần lifecycle cho staging nếu vận hành lâu dài. API tiếp tục xác minh/đọc ảnh sau upload. |

## Kiểm tra

- API: **84 passed, 7 skipped**, PostgreSQL runtime `NOSUPERUSER NOBYPASSRLS` và MinIO thật. Bài bỏ qua là opt-in/service khác, không chứng minh provider.
- Linux TypeScript: **175 passed** (auth bridge/config/guards/proxy); resident **17 passed**. Typecheck app/server/worker/resident-app đạt.
- Docker images build đạt; upgrade migration/quyền bốn role đạt, đăng ký 14 tool kỹ thuật.
- Auth validation bỏ phản chiếu password/input. Một phản hồi chẩn đoán đã chứa mật khẩu admin local: đã đổi ở hai DB, cập nhật file ignored và thu hồi phiên.

[JSON đã loại credential/hội thoại](evidence/completion-2026-10-05/acceptance.json).
Ảnh/trace giữ local ở `.codex-artifacts/completion-ui.json`, `completion-direct-ui.json`, `completion-admin-unit.png`,
`completion-openbot-accounts.png`, `completion-resident-upload*.png`, `completion-backup-restore.log`, `completion-monitor-events.log`.

## Bản chạy và vận hành

Operations <http://localhost:3022/operations/login>; cư dân <http://localhost:3013/#/login>;
API <http://localhost:8020/ready>; monitor <http://localhost:9099/health>, <http://localhost:9099/metrics>.
Credentials ở `services/vinhomes-api/.local-connected/initial-admin.txt` và `accounts.txt`, không trong Git.
Docker dùng `vinhomes_docker_complete`/`vinhomes_docker_coordination`; native của phiên MCP vẫn dùng DB cũ.
Restore verification tạo DB/bucket mới, không thay DB nguồn. Khi khôi phục thành môi trường chạy, phải cấp role/key và
cập nhật storage bằng upgrade/storage; bài verification ở đây đối chiếu dữ liệu và checksum.

```powershell
./deploy/vinhomes/run-local.ps1
./deploy/vinhomes/backup-verify.ps1
# Sau khi cập nhật khóa model trong deploy/vinhomes/deployment.env:
docker compose --env-file deploy/vinhomes/deployment.env -f deploy/vinhomes/compose.yml up -d
docker compose --env-file deploy/vinhomes/deployment.env -f deploy/vinhomes/compose.yml --profile upgrade run --rm report-bootstrap
```

`run-local.ps1` cần PostgreSQL/role/tổ chức đầu tiên provision như README. Model job trả lỗi khi thiếu quota/khóa, giữ draft.
Các dịch vụ vẫn chạy để kiểm nghiệp vụ. Không gọi bản này production-ready.

## Nhánh/phát hành

[Snapshot 38 remote](BRANCH_AUDIT_2026-10-05.md). Current `dev_teamChien_HuyDo`; head PR #31 `dev_TeamChien`, base `develop`.
Trước commit hoàn thiện đã chứa đủ `origin/develop`, 62 commit riêng; local develop cũ được giữ.
CI/merge #31: đang kiểm tra để phát hành, sẽ cập nhật sau checks GitHub.
Zizmor phát hiện ba pin Rust action cũ không còn trong lịch sử repo upstream; đã chuyển tới SHA trong `master`,
giữ input `toolchain: stable` theo [hướng dẫn chính thức](https://github.com/dtolnay/rust-toolchain#choice-of-full-length-commit-sha).
