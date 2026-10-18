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

Giai đoạn D:

- Port nguyên module/router personal chat và các component/hook UI mới của
  develop2. Các session cũ vẫn mở được qua lịch sử hoặc URL. Giữ reply-to,
  lựa chọn model sub-agent và chế độ chỉ đọc khi xem thành viên team của core.
- Chat riêng không có công cụ tạo team/mời agent hoặc công cụ workspace tùy ý.
  Nhóm riêng dùng TeamSay, dispatcher, shared context và cổng kết thúc của
  core. Hai bridge nhỏ chuyển review của nhóm sang handoff resolution và
  phát câu hỏi đã đăng ký; không thay TeamTurn hoặc Agent runtime.
- Báo cáo analysis được đánh dấu chưa xác minh và không trở thành evidence
  vận hành. Nhóm cần coordinator review; auto-review của team vận hành giữ
  nguyên. Không học hoặc nhắc ký ức vận hành trong chat riêng/nhóm riêng.
- Worker nhóm chưa chọn model dùng model của coordinator trong lượt đó.
  Gắn attribution agent/session/team cho ledger ở model chính và fallback.
- Console trao đổi với BQL về ticket đối tác qua session riêng; không ghi
  đè reply owner hoặc dùng lời của BQL để duyệt thay cư dân. Chỉ phòng đối
  tác dùng projection current-turn + durable packet; lịch sử gốc vẫn lưu.
  Các snapshot vh_ticket_get mới thay snapshot cũ trong packet, giữ nguyên
  raw events và trang lịch sử. Không bật fallback cắt lịch sử khi quá budget.
- Chỉ thêm field JSON, không có migration mới trong D.

Kiểm chứng D:

- 262 test trọng yếu team/context/leader/consent/toolkit/session: đạt. Thêm
  ba ca bridge (câu hỏi nhóm, ngắt/lỗi, cấm analysis ở team vận hành); cả hai
  module test liên quan: 30 ca đạt.
- Personal chat + challenge + session regression: 33 đạt, 1 skip trên
  Redis/SQLite. Ca runtime đồng thời bị skip ở SQLite đã chạy riêng trên
  PostgreSQL disposable: đạt, dùng Agent/middleware/dispatcher thật, chỉ
  thay provider bằng model xác định. Ca này kiểm tra peer exchange, review,
  synthesis, attribution và worker kế thừa model coordinator.
- Toàn bộ core: 2.996 ca; 23 failure/82 error/156 skip. So sánh tên từng lỗi
  với baseline trước C: không có failure/error mới; một failure cũ được sửa.
- Toàn bộ Workforce: 686 ca chạy, 13 skip, không có failure/error. Đường dẫn
  fixture đầy đủ loại được 13 lỗi import của baseline; schema artifact đã
  tái tạo ở C giải quyết hai failure baseline còn lại.
- 108 hàm pytest của C/D (gồm parametrization): 143 đạt, 6 skip. Dùng
  `--asyncio-mode=auto` cho async fixture của nguồn; lần chạy ban đầu thiếu
  cờ này gây 14 lỗi setup và đã được chạy lại đạt. Năm skip là chuẩn bị
  business sandbox cần monorepo đầy đủ (đã kiểm chứng riêng 5 ca ở C); một
  skip là runtime SQLite đã kiểm chứng riêng bằng PostgreSQL ở trên.
- Frontend: TypeScript và build đạt; Node 36 đạt/1 skip. Eslint toàn bộ 13
  file TypeScript thay đổi của D đạt. Route checker xác nhận 141 lời gọi UI
  so với 182 method/path backend.
- Sau khi mọi suite kết thúc, restart app: health 200, mọi component OK,
  container healthy. Smoke HTTP có xác thực trên stack thật (primary Redis,
  shared context PostgreSQL): auth/admin, tạo/sửa/đọc draft Studio, tạo nhóm,
  ghi/đọc context, room, AGENT_NOT_READY cho agent chưa publish, và cấm routing
  team trong chat riêng legacy đều đạt. Dùng credential placeholder trỏ
  loopback, không gọi model. Đã dọn tài khoản, credential và tài nguyên thử.

Lệnh kiểm tra backend (trong container `agentscope-dev-dong-app-1`, cwd `/app`):

```sh
PYTHONPATH=/tmp/testdeps:/app/src:/app/tests python -m unittest discover -s tests -p '*_test.py'
```

Workforce dùng unittest loader với mọi `tests/workforce/**/test_*.py`, thêm
`/app/tests/workforce/fixtures` vào PYTHONPATH để nạp `execution_fakes` và
`async_partners`; các ca pytest được chạy riêng. Các log kiểm chứng đặt tại
`/tmp/integration-D-*.log` trên host.

Các hàm pytest được chọn từ test tính năng C/D, chạy với
`python -m pytest -q --asyncio-mode=auto -p no:cacheprovider`; log
`/tmp/integration-CD-features-final.log`. Smoke stack:
`/tmp/integration-D-live-smoke.log`. Database PostgreSQL disposable đã xóa.

Giới hạn smoke hiện tại: unified partner đã được kiểm thử bằng HTTP/worker và
provider giả lập; stack thật đang để `WORKFORCE_PARTNER_API=false`. Chưa chạy
provider LLM thật hoặc gửi Discord; stack không có `DISCORD_BOT_TOKEN` trong
environment. Approval đăng ký đang bật. Không stage `.claude/`, không push.
