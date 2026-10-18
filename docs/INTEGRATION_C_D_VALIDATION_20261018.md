Nhánh: `integration/core-phaihoang-ui-develop2`. Core bắt đầu ở `d2c33c5e`
(đã có A/B); nguồn port là `origin/develop2` tại `fe56707a`.

Giai đoạn C:

- Port Agent Spec, Studio, kiểm thử/publish/rollback, memory/learning và toàn bộ
  unified partner từ nguồn. Không bật eval trong Builder; Builder và API tool/KB
  cũ tiếp tục phục vụ agent có `published_version == 0`.
- Giữ TeamSay, TeamTurn, Agent runtime và SharedContextIsolationMiddleware của
  core. LeaderEvidence chỉ có callback mặc định `None`, gọi sau bước seal thành
  công. Learning đọc snapshot các branch đã hoàn tất của core; snapshot bị xóa
  khi có yêu cầu mới và không được đưa vào model packet.
- Ký ức được dựng lại theo từng lượt, có cổng provenance của nguồn, không nối
  vào lịch sử bền vững. Core vẫn tính toàn bộ prompt/tool/output reserve trước
  khi gọi model. Sửa lỗi baseline: tắt hai fallback cắt context khi middleware
  kiểm soát ngân sách của core đã được gắn.
- Port các phụ thuộc cần thiết của Studio: CAS SQL/Redis, workspace riêng cho
  bản publish, MCP consent và phân biệt quota cạn với rate limit.
- Giữ nguyên revision và nội dung migration 0016–0020. DB stack dong đã upgrade
  từ 0015 lên 0020. Một bản sao PostgreSQL của DB thật đã downgrade về 0015 rồi
  upgrade lại 0020 thành công và được dọn sau kiểm tra. Không downgrade DB thật.
  Backup: `/tmp/integration-cd-app.dump` trong container PostgreSQL (quyền 0600).

Kiểm chứng C:

- Baseline core: 2.953 unittest; 24 failure, 82 error, 156 skip. Baseline
  Workforce: 631 unittest; 2 failure, 13 error, 13 skip. Có dependency tùy chọn,
  công cụ sandbox không có trong image và import fixture cần PYTHONPATH riêng.
- 236 test team/context/leader/toolkit và hook learning: đạt. Một failure
  context truncation của baseline đã được sửa.
- Pytest tính năng C: 207 ca đạt; ca quota còn lại đã sửa và chạy lại cùng
  classifier/hook: 15 ca đạt, 31 subtest đạt. Các test chỉ dành cho eval Builder
  của develop2 được loại khỏi bản port theo phạm vi đã chốt.
- Sandbox preparation: 5 ca đạt với cây nguồn Platform + Domain đầy đủ.
  Observability/room/provider usage/ledger: 21 ca đạt.
- Full core: 2.992 ca đã chạy. Sáu snapshot mới do CAS/consent được cập nhật;
  cả các module đó và ca SSE khởi động server tạm thời lỗi đã chạy lại: 30 ca đạt.
  Không có lỗi logic mới so với baseline. Full Workforce: 699 ca, cùng đúng
  2 failure/13 error của baseline; đã tái tạo schema artifact và chạy lại cả
  hai ca schema: đạt. Các lỗi dependency/fixture có sẵn chưa được sửa.
- Frontend: TypeScript, eslint phần thay đổi, build đều đạt; Node: 36 đạt,
  1 skip. `frontend/scripts/check-api-routes.mjs` kiểm tra 135 lời gọi UI so
  với 175 method/path backend (gồm router onboarding unified).
- Đã restart app; `/health` trả 200, mọi component OK, container healthy.

Giai đoạn D: chưa triển khai tại commit C.

Giới hạn smoke hiện tại: unified partner đã được kiểm thử bằng HTTP/worker và
provider giả lập; stack thật đang để `WORKFORCE_PARTNER_API=false`. Chưa chạy
provider LLM thật hoặc gửi Discord; stack không có `DISCORD_BOT_TOKEN` trong
environment. Approval đăng ký đang bật. Không stage `.claude/`, không push.
