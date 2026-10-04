# Tiến độ các team và kế hoạch triển khai tiếp

> Phần trạng thái là snapshot lịch sử 03/10; đọc [báo cáo 04/10](REPO_RESEARCH_2026-10-04/README.md) để biết thay đổi sau đó. Giữ tài liệu này cho backlog/tiêu chí A–C. Bản rà Đông 01/10 và báo cáo 7 tool cũ đã bỏ khỏi cây tài liệu; nguồn lịch sử vẫn ở Git/backup.

Ngày 03/10/2026. Người viết: phía Team Chiến (backend, frontend, điều phối platform). Nguồn: trạng thái các nhánh
và PR trên GitHub lúc 12:50 ngày 03/10, tài liệu trong `docs/teams/*`, và các lần chạy kiểm thử nêu ở từng mục.
Chỗ nào chỉ dựa trên tài liệu của team khác mà chưa tự chạy lại thì ghi rõ.

## Kết luận

- **Vinhomes chạy được trọn luồng trên máy phát triển, chưa sẵn sàng vận hành thật.** Cư dân chat với Lễ tân, hỏi
  tri thức, báo sự cố, báo khẩn cấp; Ban quản lý và kỹ thuật viên xử lý tới khi đóng yêu cầu. Còn thiếu: đăng nhập
  thật, đóng gói triển khai, và Supervisor thật (hiện Ban quản lý bấm tay từng bước).
- **Ba team đang chờ cùng một thứ: lớp nền agent ở backend.** `server/src/platform` và `server/src/runtime` vẫn
  trống. Team Đông chờ Authority và nơi phát hành phiên bản agent, Team Quang chờ cổng tool, Team Phái chờ backend
  nối lại Agent Factory. Đây là việc của Team Chiến và là đường găng của cả platform.
- **Các nhánh chưa về một nền chung.** `dev_TeamChien` đi trước `develop` 77 commit (PR #25 đang mở);
  `devTeamPhai` đi trước 27 commit nhưng tụt sau 79 commit và chưa có PR vào `develop`; `main` tụt sau `develop`
  90 commit.

## Tiến độ từng team

| Team | Phần việc | Đã vào `develop` | Chạy được | Đang chặn |
|---|---|---|---|---|
| Chiến | Backend nghiệp vụ, app cư dân, Operations, tích hợp Lễ tân | Chưa: PR #25 (CI `core` đạt, ba job `app` đang chờ) | Trọn luồng trên database demo | Xem mục Vinhomes |
| Hoàng | Lễ tân (graph LangGraph), nền Report agent | Có, PR #21 ngày 01/10. Không có commit mới từ 01/10 | Graph chạy trong dịch vụ Lễ tân; 346 test đạt, 5 test hỏng có từ trước (`tests/tools/test_adversarial.py`) | Lệch schema V1/V2 với Team Đông (theo bản rà của Team Đông 01/10, chưa kiểm lại) |
| Quang | Tri thức (RAG), 14 tool kỹ thuật | Có, PR #18 ngày 01/10. Không có commit mới từ 01/10 | Tri thức: đã nạp 115 tài liệu, Lễ tân đang dùng. Tool: 882 test đạt với nguồn giả lập | Cổng `/internal/tools/*` chưa được gắn vào server; 7 port backend chưa có |
| Đông | Supervisor và phòng họp agent (`agent-coordination`) | Có, PR #27 ngày 02/10 | Dịch vụ khởi động ở cổng 4300; `/ready` trả 503 vì thiếu ràng buộc backend | Chưa có Authority, nơi phát hành phiên bản agent, kho lưu production; 5 PR nội bộ còn mở (#9, #10 từ 30/09) |
| Phái | Agent Factory, bộ tool an ninh (Security MCP) | **Chưa.** Chỉ có trên `devTeamPhai` | Agent Factory chạy độc lập ở cổng 4010 (theo tài liệu của họ: 44 kiểm tra đạt) | Backend chưa nối; 6 câu hỏi mở Q1–Q6 trong `agent-factory/docs/coordination-integration-spec.md` chờ Team Chiến và Team Đông |

Ghi chú:

- Team Đông tự rà ngày 01/10 (`docs/teams/dong/review_team_dong.md`): 0/8 nhiệm vụ D01–D08 đủ bằng chứng nghiệm
  thu, chưa chạy đầu-cuối với model thật. Sau đó PR #26 (02/10) thêm dịch vụ chạy bền, khóa phiên bản AgentScope
  2.0.9 và Dockerfile. README hiện ghi "production assembly remains blocked" vì backend chưa có hợp đồng tương ứng.
- Team Phái làm hai mảng: `agent-factory/` (32 file, tự chạy được, đã gỡ phần nối backend theo yêu cầu) và
  `server/src/security-tools/` (45 file: bảo vệ, camera, sự cố, bằng chứng, điều động, với nguồn giả lập).
- Team Quang ghi rõ 14 tool mới ở mức module và POC, chưa phải production
  (`docs/teams/quang/requests/technical-tools-progress-report.md`).

## Vinhomes: đã có gì, còn thiếu gì

Đã kiểm trên trình duyệt thật ngày 03/10, model thật, cả app cư dân và Operations:

- Luồng sửa chữa 19 bước từ chat của cư dân tới lúc Ban quản lý duyệt đóng: đạt 19/19.
- Hỏi tri thức có ghi nguồn, hỏi tiếp không dấu, báo khẩn cấp, câu hỏi chuyển Ban quản lý rồi trả lời quay lại,
  duyệt tri thức học được: đạt 12/12.
- Kiểm thử tự động: backend 58 đạt; đầu-cuối với model giả 8/8 ở cả hai chế độ agent; tri thức 75 đạt.

Mới trong ngày 03/10: Operations hiện đúng yêu cầu khẩn cấp; câu trả lời khẩn cấp kèm hướng dẫn an toàn do Ban
quản lý duyệt; database demo dựng lại sạch và có bản sao lưu chuẩn để khôi phục.

Còn thiếu trước khi vận hành thật:

| Việc | Hiện trạng |
|---|---|
| Đăng nhập thật | Demo chọn vai bằng header, chỉ chạy trên máy phát triển. Database đăng nhập bằng mật khẩu (`vinhomes_connected`) chưa có dữ liệu tòa nhà |
| Supervisor | Trang yêu cầu hiện "Phiên điều phối" nhưng chưa có agent nào điều phối |
| Đóng gói triển khai | Backend nghiệp vụ, dịch vụ Lễ tân và dịch vụ tìm tri thức chỉ chạy bằng script trên máy; chưa có container hay môi trường chung |
| Nạp tri thức định kỳ | Đang là script PowerShell tự lặp; kho dữ liệu nằm ở thư mục tạm của máy phát triển |
| Nội dung cần Ban quản lý duyệt | Danh sách từ khóa khẩn cấp; 3 hướng dẫn an toàn của Sapphire đang chờ duyệt; các phân khu khác chưa có đơn vị quản lý trong database |
| Kiểm thử nền | `app`: 48/993 test hỏng có từ trước; Lễ tân: 5 test hỏng; test nhật ký migration hỏng vì thiếu snapshot |
| Vận hành | Token dịch vụ dùng chung chưa xoay vòng; mới có log, chưa có giám sát và cảnh báo |

## Mọi team đang chờ backend những gì

| Team chờ | Cần từ backend (Team Chiến) | Tài liệu nêu yêu cầu |
|---|---|---|
| Đông | Authority cho lượt chạy của nhóm agent; nơi phát hành và đọc phiên bản agent; kho lưu production cho phòng và Supervisor; gắn route `/v2/reception`, `/v2/events` | `agent-coordination/README.md` |
| Quang | Cổng `/internal/tools/*`; `BuildingAccessPort`, `TenantReadSessionPort`, `CoveringScopesPort`; nguồn dữ liệu thật cho tài sản, cảm biến, lịch sử bảo trì | `docs/teams/quang/requests/technical-tools-backend-ports.md` |
| Phái | Nối lại Agent Factory (`/api/agent-factory/*`), lưu agent idempotent, kiểm tra sẵn sàng; nguồn cho `defaultToolRefs` | `agent-factory/docs/backend-integration-spec.md` (nhánh `devTeamPhai`) |
| Hoàng | Không chờ backend; cần thống nhất schema V2 với Team Đông | `docs/teams/dong/review_team_dong.md`, mục 5 |

## Quyết định cần chốt

| # | Câu hỏi | Người quyết | Chặn việc nào |
|---|---|---|---|
| 1 | Agent do Factory tạo chạy trong phòng bằng cách nào: dựng trong tiến trình AgentScope (không dùng được tool), hay gọi từ xa tới runtime của platform (giữ nguyên tool và quyền) | Đông cùng Chiến | B2, B4 |
| 2 | Backend lưu phiên bản agent ở đâu và phát cho Coordination qua API nào | Chiến | B4 |
| 3 | Kết quả đánh giá và duyệt của quản trị cho một agent lưu ở đâu, ai chạy đánh giá | Chiến cùng Đông | B4 |
| 4 | Lễ tân dùng agent mới (`loop`) làm mặc định, hay giữ graph | Chiến cùng Hoàng | A4 |
| 5 | Ai bên Ban quản lý duyệt danh sách từ khóa khẩn cấp và hướng dẫn an toàn | Chiến | C3 |

Câu 1–3 là Q1–Q3 trong tài liệu của Team Phái. Đề xuất cho câu 1: bắt đầu bằng cách dựng trong tiến trình cho agent
không dùng tool (chỉ còn thiếu một provider), song song làm cổng tool; agent có tool đi đường gọi từ xa.
Đề xuất cho câu 4: đổi sang `loop` (điểm đánh giá 100% / 98% so với 87% / 88%, và đã có cùng bộ test đầu-cuối).

## Kế hoạch

Mục tiêu của đợt tới: **một yêu cầu sửa chữa do Supervisor thật điều phối, dùng ít nhất một tool kỹ thuật thật,
trên nền `develop` chung.** Mỗi việc là một lát cắt chạy được và có cách kiểm. Cỡ: S (1–2 file), M (3–5 file),
L (nhiều thành phần).

### A. Về một nền chung

| Việc | Ai | Cỡ | Xong khi |
|---|---|---|---|
| A1. Gộp PR #25 vào `develop` | Chiến | S | CI đạt, `develop` có dịch vụ Lễ tân và luồng sửa chữa |
| A2. Team Phái gộp `develop` vào nhánh mình rồi mở hai PR: `agent-factory/` và `server/src/security-tools/` | Phái | M | Hai PR vào `develop`, không đụng phần nối backend |
| A3. Team Đông gộp hoặc đóng 5 PR nội bộ (#9, #10, #22, #24, #28) | Đông | S | Không còn PR mở quá 2 ngày |
| A4. Sửa nền kiểm thử: 48 test `app`, 5 test Lễ tân, snapshot migration | Chiến, Hoàng | M | Ba bộ test xanh trên `develop` |
| A5. Chốt 5 quyết định ở mục trên trong một buổi | Chiến chủ trì | S | Có biên bản và JSON Schema dùng chung cho TypeScript và Python |

Điểm dừng A: `develop` chứa mã của cả năm team và CI xanh.

### B. Supervisor chạy thật (đường găng)

| Việc | Ai | Cỡ | Phụ thuộc | Xong khi |
|---|---|---|---|---|
| B1. Backend cấp ủy quyền cho nhóm agent (danh tính dịch vụ theo workspace) và endpoint Authority | Chiến | M | A5 | Test từ chối: sai workspace, sai phiên, phiên đã đóng đều bị chặn |
| B2. Coordination chạy với ràng buộc thật ở môi trường phát triển | Đông, Chiến | M | B1 | `/ready` trả 200; Lễ tân bàn giao yêu cầu sang `/v2/reception` và nhận xác nhận |
| B3. Supervisor lập phương án bằng model thật và ghi vào phòng của Ban quản lý | Đông, Hoàng | M | B2 | Một yêu cầu đi từ chat cư dân tới phương án hiện trong Operations, Ban quản lý bấm duyệt |
| B4. Backend lưu và phát hành phiên bản agent; Agent Factory nối lại; một agent không tool vào phòng | Chiến, Phái, Đông | L | A2, A5 | Tình huống T1 trong tài liệu của Team Phái đạt |
| B5. Cổng tool với 3 port và 2 tool đọc database thật (mất điện nước, lịch tiện ích) | Chiến, Quang | M | A5 | Agent có quyền gọi được, agent không có quyền bị từ chối; test trên PostgreSQL thật |
| B6. Sub-agent kỹ thuật dùng tool ở B5 trong một yêu cầu thật | Đông, Quang | M | B3, B5 | Phương án của Supervisor trích kết quả tool |

Điểm dừng B: chạy lại luồng 19 bước, trong đó các bước lập phương án và phân công do Supervisor làm.

### C. Vinhomes vận hành thật

| Việc | Ai | Cỡ | Xong khi |
|---|---|---|---|
| C1. Đăng nhập thật cho cư dân và nhân viên; database đăng nhập có dữ liệu Ocean Park | Chiến | M | Luồng 19 bước chạy không cần chế độ demo |
| C2. Đóng gói backend nghiệp vụ, Lễ tân, tìm tri thức; một môi trường chung cho các team | Chiến | L | Người khác bật được cả hệ thống bằng một lệnh |
| C3. Ban quản lý duyệt từ khóa khẩn cấp và hướng dẫn an toàn; thêm đơn vị quản lý cho các phân khu còn lại | Chiến, Ban quản lý | S | Báo mùi gas ở mọi phân khu có hướng dẫn đã duyệt |
| C4. Job định kỳ nạp tri thức thay script; kho dữ liệu ở vị trí cố định | Chiến, Quang | S | Câu trả lời được duyệt tự vào kho trong 10 phút, không ai chạy tay |
| C5. Giám sát: số lượt, độ trễ, chi phí model, lỗi; xoay vòng token dịch vụ | Chiến | M | Có bảng theo dõi và cảnh báo khi Lễ tân không trả lời |
| C6. Dữ liệu: bổ sung tài liệu còn thiếu, cập nhật bộ 93 câu hỏi đánh giá | Quang, nhóm dữ liệu | M | Bộ 93 câu chấm được và có điểm gốc |

### Thứ tự

A1–A5 làm trước và làm song song. B1 là việc mở khóa nhiều nhất nên Team Chiến bắt đầu ngay sau A5. B5 không phụ
thuộc B1–B3 nên làm song song. C1–C3 không phụ thuộc B, có thể xen kẽ. C2 nên xong trước điểm dừng B để các team
kiểm trên cùng một môi trường.

## Rủi ro

| Rủi ro | Mức | Cách giảm |
|---|---|---|
| Team Chiến là điểm nghẽn của cả ba team | Cao | Chốt hợp đồng (A5) trước, để các team làm tiếp với bản giả lập đúng hợp đồng trong lúc chờ |
| `devTeamPhai` tụt sau `develop` 79 commit | Cao | A2 làm ngay, tách hai PR nhỏ |
| Schema V1/V2 lệch giữa Lễ tân và Supervisor | Trung bình | Test hợp đồng hai chiều trong B2 |
| Nội dung an toàn sai tới cư dân | Cao nếu xảy ra | Chỉ gửi nguyên văn câu Ban quản lý đã duyệt; chưa duyệt thì không gửi (đã có test) |
| Ba bộ test đang đỏ che lỗi mới | Trung bình | A4 |
