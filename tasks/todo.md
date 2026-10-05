# Việc cần làm — Lễ tân (chi tiết ở `tasks/plan.md`)

## Giai đoạn 0 — Nền để đo, dọn giao diện
- [x] T0.1 Danh sách hội thoại và thông báo dễ đọc (S) — commit b6db9a7
- [x] T0.2 Bộ đánh giá hội thoại tiếng Việt chạy tự động, có điểm gốc (M) — commit 33cdf61
- [x] T0.3 Dọn dữ liệu thử trong database demo (khôi phục bản sao lưu trước khi thử + nâng cấp lại)

## Giai đoạn 1 — Tri thức chạy thật
- [x] T1.1 Nạp Data-Vinhome, ánh xạ phạm vi ↔ tòa, cấp quyền cho Lễ tân (M) — 114 tài liệu; bộ 93 câu chưa đo được (đáp án lệch dữ liệu)
- [x] T1.2 Bật route tìm kiếm; Lễ tân trả lời có trích dẫn; test route cấp quyền (S)

### Điểm dừng 1 — duyệt bảng điểm gốc

## Giai đoạn 2 — Câu không có nguồn vào session của BQL
- [x] T2.1 Lễ tân mở yêu cầu hỏi đáp khi không có nguồn (M)
- [x] T2.2 Tin nhắn từ session về chat cư dân (M)
- [x] T2.3 Màn tin nhắn session trong Operations (M)

## Giai đoạn 3 — Agent do model dẫn dắt
- [x] T3.1 Model adapter gọi tool (S)
- [x] T3.2 Bộ tool cho agent (M) — luật trong tools.py; test đơn vị ở tests/agent
- [x] T3.3a Vòng agent + cổng policy (M)
- [x] T3.3b Bước kiểm tra đầu ra (M)
- [x] T3.4 So điểm với graph cũ bằng bộ đánh giá trên hai môi trường tạm (thay cho chạy ngầm): loop 94–100% / 96–100% / 4,75–4,88 so với graph 87% / 88% / 4,42

### Điểm dừng 2 — quyết định bật agent mới

## Giai đoạn 4 — Bộ nhớ dài hạn
- [x] T4.1 Bộ nhớ cư dân: 5 yêu cầu gần nhất của chính cư dân đưa vào ngữ cảnh agent (không cần kho mới; chỉ đọc dữ liệu của cư dân đó)
- [ ] T4.2 Hoãn: bộ nhớ hiện là lịch sử yêu cầu, cư dân đã xem được ở "Yêu cầu của tôi". Chỉ cần khi có bộ nhớ sở thích dạng tự do

## Giai đoạn 5 — Tự thẩm định, tự cải thiện
- [ ] T5.1 Thu tín hiệu ngầm (S) — hoãn: backend đã ghi sẵn xác nhận/từ chối, mở lại, retrieval_runs; chưa có dữ liệu thật để dùng
- [x] T5.2 Agent thẩm định tri thức, phân mức tự duyệt / chờ duyệt / loại (M)
- [ ] T5.3 Điểm tin cậy vào thứ hạng (M) — hoãn tới khi có tín hiệu thật
- [ ] T5.4 Ngân hàng ví dụ mẫu (S) — hoãn: ticket_triage_reviews chưa có dòng nào
- [x] T5.5 Nút duyệt một chạm trong Operations (S)

## Giai đoạn 6 — Tối ưu truy xuất (theo số đo)
- [x] T6.1 Viết lại câu hỏi theo ngữ cảnh — agent loop tự viết truy vấn đầy đủ khi gọi search_knowledge
- [x] T6.2 Không dấu, sai chính tả — agent loop viết lại truy vấn có dấu; nhóm no-accents đạt 80–100%
- [x] T6.3 Xếp hạng: đoạn khớp rõ nhất đứng đầu (leadClearMatch trong retrieve.ts)
- [ ] T6.4 Thực thể và cạnh (M) — hoãn: nhóm câu hỏi thông tin đã đạt 100%, chưa có số đo cho thấy cần
- [x] T6.5 Qdrant: không cần lúc này — 277 đoạn, tìm kiếm trung bình 486 ms (phần lớn là gọi embedding), chưa có index ANN và vẫn nhanh

## Giai đoạn 7 — Vận hành thật
- [x] T7.1 Agent loop không giữ trạng thái (đọc hội thoại từ backend) nên chạy được nhiều bản; run treo quá 15 phút tự đóng. Chế độ graph vẫn dùng SQLite
- [x] T7.2 Token và độ trễ mỗi lượt ghi vào agent_runs và log; giới hạn 30 tin/phút mỗi cư dân
- [x] T7.3 Ma trận phân quyền + test từ chối — docs/teams/chien/RBAC_MATRIX_2026-10-03.md
- [ ] T7.4 Một phần: db:verify đã đạt (đếm bảng từ schema thay vì số cứng). Còn lại: migration 0001, 0002, 0007–0011 viết tay nên thiếu snapshot; cần đưa các bảng vh_* vào schema TS rồi sinh lại — việc của cả các team đã thêm migration
- [x] T7.5 Đã có sẵn: backend từ chối khởi động chế độ demo khi host không phải loopback
- [ ] T7.6 Nhập dữ liệu tổ chức thật qua Agent Factory (L, phụ thuộc Team Phái)

## Bổ sung ngày 03/10
- [x] Test đầu-cuối với model giả chạy cho cả `graph` và `loop` (8 test mỗi chế độ)
- [x] File chung của Masterise nạp vào phân khu duy nhất mà đơn vị đó vận hành
- [x] `publish_learned.ps1 -EveryMinutes` tự lặp, không còn bước chạy tay
- [x] Operations hiện đúng yêu cầu khẩn cấp (backend trả `critical`, giao diện từng so với `P0`)
- [x] Câu trả lời khẩn cấp kèm hướng dẫn an toàn do Ban quản lý duyệt (cháy, mùi gas, kẹt thang máy)
- [x] Database demo dựng lại sạch; bản chuẩn để khôi phục: `.local-v3-faker/backups/vinhomes_v3-clean-baseline-*.dump`

## Đợt tiếp theo — cả platform
Tiến độ từng team, các quyết định cần chốt và kế hoạch A (nền chung), B (Supervisor chạy thật), C (Vinhomes vận
hành thật): `docs/teams/chien/TIEN_DO_VA_KE_HOACH_2026-10-03.md`.

- [x] A1 Gộp PR #25 vào `develop` (03/10)
- [ ] A2 Team Phái đưa `agent-factory/` và `security-tools/` vào `develop` (hai PR)
- [ ] A3 Team Đông dọn 5 PR nội bộ
- [ ] A4 Sửa nền kiểm thử: 48 test `app`, 5 test Lễ tân, snapshot migration
- [ ] A5 Chốt 5 quyết định liên team
- [ ] B1 Một phần: Supervisor có binding, run và API riêng (`/internal/coordination/v1`); subagent chưa
- [x] B2 Supervisor thật nhận yêu cầu từ Lễ tân, lưu phiên bền, trả `accepted` (`agent-coordination/src/vinhomes`)
- [ ] B3 Supervisor lập phương án bằng model thật (model thật đã giao việc và nhận phân tích; phương án thuộc M3)
- [ ] B4 Phát hành phiên bản agent; nối lại Agent Factory
- [ ] B5 Cổng tool với 3 port và 2 tool đọc database thật
- [ ] B6 Sub-agent kỹ thuật dùng tool trong một yêu cầu thật
- [x] C1 Đăng nhập thật cho cư dân và nhân viên; luồng 23 bước đạt (`docs/teams/chien/CHAY_DANG_NHAP_THAT.md`)
- [ ] C2 Đóng gói và môi trường chung
- [ ] C3 Một phần: 3 hướng dẫn an toàn của Sapphire đã duyệt; danh sách từ khóa và các phân khu khác chưa
- [ ] C4 Job định kỳ nạp tri thức
- [ ] C5 Giám sát và xoay vòng token
- [ ] C6 Bổ sung dữ liệu, cập nhật bộ 93 câu

## Supervisor và session V2 (kế hoạch `KE_HOACH_SUPERVISOR_GROUPCHAT_SESSION_V2_2026-10-03.md`)
Chi tiết: `docs/teams/chien/SUPERVISOR_SESSION_V2_M0_M1_2026-10-03.md`.

- [x] M0 Baseline, kiểm kê, session và bảng contract
- [x] M1a Runtime nối backend thật cho `ticket_submitted → accepted`, có đối soát khi mất phản hồi
- [ ] M1b Kho PostgreSQL cho checkpoint, inbox, journal; test hai tiến trình
- [x] M2 Một specialist và model thật: admin duyệt là phát hành, agent được mời theo danh mục ticket, agent kỹ
  thuật trả lời trong phòng, Operations hiện phân tích (`docs/teams/chien/SUPERVISOR_SESSION_V2_M2_2026-10-04.md`)
- [x] M2b Cổng tool cho agent chuyên môn: ba tool đọc của Team Quang, quyền theo lượt chạy của phiên
  (`docs/teams/chien/TOOL_GATEWAY_VA_KHAO_SAT_NHANH_2026-10-04.md`); tool ghi chưa mở
- [x] M2c BQL hỏi thêm agent trong phiên của ticket; màn nhóm BQL liệt kê các phiên của phòng
- [x] M2d Admin duyệt và thu hồi agent trên Operations; agent chuyên môn chạy `gpt-5.5`
- [x] M3a Supervisor đề xuất phương án (tác giả là agent), BQL duyệt hoặc từ chối trên Operations
  (`docs/teams/chien/SUPERVISOR_PHUONG_AN_M3A_2026-10-04.md`)
- [x] M3b Quyết định của BQL về tới Supervisor, cư dân duyệt qua Lễ tân, hỏi lại cư dân, hoàn tất, hủy
  (`docs/teams/chien/BQL_B1_B6_PROGRESS_2026-10-04.md`)
- [x] M4 Pause, resume, stop và màn quản lý session trên Operations: màn Điều phối, trang Agent, menu 4 mục
- [ ] M5 Nghiệm thu lỗi và triển khai giới hạn

## Kết nối ngoài cho agent của BQL (MCP theo URL; làm ngày 04/10/2026, đêm)

Chủ dự án chốt: làm **MCP theo URL** trước, agent dùng **khóa dùng chung** của nhóm BQL (phiên do Supervisor chạy không
có người đứng sau, nên chỉ kiểu này dùng được trong phiên). Kết nối theo tài khoản từng người (OAuth) cần thống nhất
đăng nhập với OpenBot, để sau.

Cách làm: kết nối là một dòng trong danh mục tool sẵn có (`mcp_servers`, provenance `custom`, kèm nhóm được dùng) và
một khóa đã mã hóa (`credentials`, kind `mcp`), không thêm bảng. Tool host Bun (`server/src/technical-api`) giữ khóa mã
hóa và là nơi duy nhất gọi ra máy chủ MCP, bằng mã MCP của OpenBot (`server/src/plugins/mcp.ts`). API nghiệp vụ kiểm
quyền và ghi audit.

- [x] K1 Lưu kết nối của một nhóm: địa chỉ https, khóa mã hóa khi lưu, không API nào trả lại khóa. Test: BQL gọi API
      quản trị bị 403; danh sách không chứa khóa.
- [x] K2 Tool host liệt kê và gọi tool (`/internal/technical/v1/connections`). Khác kế hoạch ban đầu: **không tin** nhãn
      "chỉ đọc" do máy chủ MCP tự khai (đúng quy tắc sẵn có của OpenBot); quản trị viên chọn từng công cụ được phép.
      Công cụ máy chủ tự đánh dấu phá hủy thì không chọn được.
- [x] K3 Cổng tool chuyển lời gọi sau khi kiểm lượt chạy, bản agent đã ghim, quyền, nhóm của kết nối, khóa còn hiệu
      lực; ghi audit. Test: OK, lỗi do tool, tool host lỗi, khóa bị thu hồi, công cụ phá hủy, gỡ công cụ đang được agent
      đã phát hành dùng (bị từ chối, nêu tên agent).
- [x] K4 Màn "Kết nối ngoài" của quản trị viên: thêm kết nối, mở ra là hỏi máy chủ danh sách công cụ, chọn công cụ
      được phép, xóa. Không có nút bật/tắt riêng: bỏ chọn công cụ là tắt; bảng hiện có không có cột trạng thái.
- [x] K5 Hộp cấu hình agent hiện công cụ của kết nối, gom theo tên kết nối, chỉ với nhóm được dùng.
- [ ] K6 Nghiệm thu bằng máy chủ MCP thử (`server/scripts/mcp_test_server.ts`). Đã chạy trên trình duyệt: quản trị viên
      thêm kết nối và cho phép công cụ (6/6 bước); BQL cấp công cụ cho agent mới và lưu (3/3 bước); tool host gọi máy
      chủ MCP thật bằng khóa đã mã hóa. **Chưa chạy:** đánh giá, phát hành và câu trả lời của agent trong phòng nhóm, vì
      khóa model mới bị `api.openai.com` trả 401 `invalid_api_key` (và `OPENAI_BASE_URL` trong `agent-reception/.env`
      đang trống).
- [ ] Còn thiếu: đổi khóa của một kết nối (hiện phải xóa rồi thêm lại); công tắc tắt khẩn cấp một kết nối đang được
      agent dùng (hiện phải thu hồi agent trước); chạy trong container với một máy chủ MCP thật trên internet.

## Phát hành agent không qua quản trị viên (chủ dự án chốt 04/10/2026, đêm)

- [x] BQL tự phát hành agent sau khi đánh giá trên máy chủ đạt cả 6 ca; không còn bước quản trị viên duyệt trên giao
      diện. Quản trị viên cấu hình nền tảng (tài khoản, kết nối ngoài) và vẫn thu hồi được agent ở trang Agent.
- [ ] Chạy lại vòng tạo → đánh giá → phát hành trên giao diện khi khóa model dùng được.

## Lưu ảnh và tệp trên MinIO/S3 (làm ngày 05/10/2026)

Bảng đã có sẵn và được dùng nguyên: `storage_locations` (provider, bucket), `file_objects` (`object_key`), `files`,
`ticket_files`. Không thêm bảng hay cột.

- [x] M1 Một lớp lưu trữ chung (`vinhomes_api/storage.py`): 5 module đọc/ghi ảnh dùng chung, lưu đĩa vẫn chạy như cũ.
- [x] M2 Provider `s3` cho MinIO/S3 (thư viện `minio`); bật bằng `VINHOMES_API_S3_ENDPOINT`, khóa lấy từ biến môi trường.
- [x] M3 Compose có dịch vụ `minio`, bucket riêng tư, job `storage` tạo bucket và ghi nhận nơi lưu.
- [x] M4 Ảnh vẫn đi qua API (kiểm quyền như cũ, hai frontend không đổi).
- [x] M5 Chuyển ảnh cũ: job `storage` chép file sang bucket rồi đổi bản ghi nơi lưu. Cơ sở dữ liệu không cho đổi nơi lưu
      của từng ảnh, nên cái được đổi là bản ghi `storage_locations`. Đã kiểm với MinIO thật (test) và trong container
      (6 ảnh cũ chuyển sang bucket, tải lại được; tải ảnh mới lên và tải về đúng nội dung).
- [ ] Upload thẳng từ trình duyệt lên MinIO bằng phiên upload (`file_uploads`) theo tài liệu luồng mục tiêu.
- [ ] Lời gọi MinIO còn chạy đồng bộ trong vài route (chặn vòng lặp trong lúc gọi); chuyển sang thread khi có tải thật.
- [ ] `scripts/cleanup_resident_photos.py` (dọn ảnh cư dân hết hạn) mới chạy với lưu đĩa.
- [ ] Container `minio` chưa có kiểm tra sức khỏe; chưa có khóa riêng chỉ có quyền trên bucket; chưa bật versioning.
- [ ] Giao diện kỹ thuật viên còn hiện ảnh dạng tên file.

## Model theo vai trò, nhiều nhà cung cấp (làm ngày 05/10/2026)

Theo `docs/teams/chien/MULTI_MODEL_REPO_AUDIT_2026-10-04.md`, bốn vấn đề cần sửa trước khi dùng nhiều nhà cung cấp:

- [x] Tách khóa và địa chỉ của embedding khỏi chat (`KNOWLEDGE_EMBEDDING_API_KEY`, `_BASE_URL`).
- [x] Mỗi vai trò có nhà cung cấp, khóa, địa chỉ riêng: Lễ tân (`RECEPTION_MODEL_*`), Supervisor (`COORDINATION_MODEL_*`),
      agent chuyên môn (`COORDINATION_OPENBOT_MODEL_*`). Khóa OpenAI không bao giờ gửi sang nhà cung cấp khác.
- [x] Gemini, DeepSeek, Groq đi qua giao thức tương thích OpenAI; Supervisor đổi tham số giới hạn token theo nhà cung cấp
      và cho khai tên model nhà cung cấp trả về.
- [x] Launcher, compose và file mẫu cùng dùng một bộ tên biến; màn "Model" của quản trị viên hiện model từng vai trò.
- [ ] **Chưa chạy với khóa thật** của Google, DeepSeek, Groq, Anthropic: phần đã kiểm là mỗi vai trò gửi đúng khóa, đúng
      địa chỉ, đúng tham số (test) và stack container khởi động, báo đúng nhà cung cấp. Cần khóa để chạy hội thoại thật.
- [ ] Claude: mới qua lớp tương thích của Anthropic (bỏ qua yêu cầu trả JSON), chỉ để thử. Cần adapter Messages riêng.
- [ ] Agent chuyên môn (agent-bot) và Factory chưa được kiểm tham số riêng với nhà cung cấp khác OpenAI.
- [ ] Eval của Lễ tân còn dùng chung model với Lễ tân làm giám khảo; cần giám khảo cố định khi so sánh model.
- [ ] Embedding Google/Voyage/BGE: chưa làm (cần model space riêng, nhập lại tri thức, chỉnh lại ngưỡng).
- [ ] Màn "Model" chỉ xem; chưa có nút gọi thử model và chưa đổi model từ giao diện.

## Giao diện quản trị viên (làm ngày 05/10/2026)

- [x] Menu riêng: Tài khoản, Đơn vị quản lý, Kết nối ngoài, Model, Nhật ký.
- [x] Tài khoản làm lại: tìm kiếm, lọc vai trò, tạo, đổi vai trò và đơn vị, duyệt, khóa.
- [x] Đơn vị quản lý (chỉ xem), Model (chỉ xem), Nhật ký (lọc theo loại, xem sự kiện cũ hơn).
- [ ] Tạo đơn vị quản lý, nhóm BQL và giao tòa nhà từ giao diện (hiện bằng script `provision_connected.py`).
- [ ] Đặt lại mật khẩu cho tài khoản; xóa tài khoản.
- [ ] Nhật ký chưa tìm theo người hoặc theo khoảng thời gian, chưa xuất file.

## Agent báo cáo trong phòng nhóm (rà ngày 05/10/2026)

- [x] 4 tool báo cáo đã đóng gói (job `catalogue`); agent đang phát hành ở local và trả lời khi được nhắc trong phòng.
- [ ] Agent là dữ liệu của phòng, chưa có lệnh tự tạo khi cài đặt: bản triển khai mới phải tạo qua trang Agent
      (cấu hình ở `docs/teams/hoang/agent/`). `publish_agent.ps1` mới đọc được tool kỹ thuật.
- [ ] Agent báo cáo không khai danh mục nên Supervisor không mời vào phiên; chủ dự án chưa nói có cần hay không.

## Giao diện nhân viên kỹ thuật và phần BQL còn sót (làm ngày 05/10/2026, đợt 2)

- [x] Mục "Công việc đã hoàn thành" đưa nhân viên về trang đăng nhập (đã sửa).
- [x] Một mục menu "Việc của tôi" với hai thẻ Đang mở / Lịch sử, có biểu tượng.
- [x] Ảnh hiện thành hình, theo thứ tự phản ánh → trước → sau; bỏ mã `VH-…`, "phiên bản", mã phiếu; ô ghi chú chỉ hiện
      khi còn thao tác được.
- [x] Chuông, số trên menu và tiêu đề tab báo việc mới được mời nhận.
- [x] BQL: bỏ khối "Phiên điều phối" cũ ở trang chi tiết (thay bằng liên kết sang phiên), bỏ mã `VH-…` ở danh sách.
- [ ] Trang chi tiết công việc vẫn là bố cục cũ (thẻ `ws-card`), chưa theo kiểu màn Điều phối; chưa thử lại trọn luồng
      nhận việc → gửi kết quả sau khi sửa giao diện, vì tạo yêu cầu mới cần model.
- [ ] Hộp đánh giá agent bắt nhập tay 6 tình huống.

## Chuẩn bị triển khai thật (làm ngày 05/10/2026, đợt 2)

- [x] HTTPS: dịch vụ `proxy` (Caddy, profile `tls`) trước hai giao diện; cookie phiên có cờ Secure khi `SECURE_COOKIES=1`.
      Đã kiểm trong container với chứng chỉ nội bộ: đăng nhập, 13 bước kiểm đều đạt qua https.
- [x] MinIO: API dùng khóa riêng chỉ có quyền trên bucket (job `storage` tạo), có kiểm tra sức khỏe.
- [x] Sao lưu: hướng dẫn trong `deploy/vinhomes/README.md`; đã thử lệnh nén volume ảnh.
- [ ] Chưa chạy với tên miền thật và chứng chỉ Let's Encrypt; chưa có lịch sao lưu tự động, chưa thử khôi phục trọn vẹn.
- [ ] Chưa có giới hạn tài nguyên, thu thập log tập trung, cảnh báo; chưa thử khởi động lại cả máy chủ.
- [ ] CI vẫn tắt; PR #31 chưa gộp.

## Việc chưa làm vì cần chủ dự án quyết

- [ ] Admin tạo đơn vị quản lý từ giao diện: phải quyết hai đơn vị có được phụ trách chung một tòa không, và chấp nhận
      cấp cho API quyền ghi vào khoảng mười bảng cấu trúc (đơn vị, phạm vi, nhóm, phòng, Supervisor).
- [ ] Agent báo cáo có vào phiên của Supervisor hay chỉ trả lời trong phòng nhóm.
- [ ] Dùng dữ liệu của Team Quang vào đâu (loại sự cố, ca đánh giá, tri thức tham khảo nội bộ).

## Tính năng OpenBot đưa vào cho BQL (làm ngày 05/10/2026, đợt 3)

Theo `docs/teams/chien/OPENBOT_FEATURES_FOR_BQL_2026-10-05.md`. Phần Vinhomes không chạy server OpenBot, nên chỉ dùng
các module tách chạy riêng được.

### Lịch chạy agent (Routines)

- [x] Dịch vụ `routines` (`server/src/room-routines`) dùng nguyên kho lịch, bộ quét và hàng đợi của OpenBot. Role
      database riêng: tool host của Team Quang từ chối chạy khi role của nó được sửa hoặc xóa dữ liệu.
- [x] API quyết ai được đặt lịch (quản lý của phòng, là thành viên; agent đã phát hành) và thực hiện lượt chạy: đăng
      chỉ dẫn vào phòng nhóm dưới tên người đặt lịch, nhắc agent. Kết quả của câu hỏi đóng lượt chạy.
- [x] Trang Agent có thẻ "Lịch chạy": hằng ngày, Thứ Hai đến Thứ Sáu, hằng tuần; giờ Việt Nam; bật, tắt, xóa; kết quả
      lượt gần nhất bằng chữ. Câu hỏi theo lịch được ghi "Theo lịch" trong phòng nhóm.
- [x] Đã thử trên trình duyệt với stack local: đặt lịch, đến hạn, tin vào phòng, Supervisor nhận, tắt, xóa.
- [x] Sửa lịch đã đặt (chỉ dẫn, ngày, giờ; agent giữ nguyên): nút "Sửa" trong thẻ Lịch chạy.
- [ ] Chưa có trần số lịch theo đơn vị (trần 20 lịch là theo người).
- [ ] Chạy ở chế độ demo (không có Supervisor) thì lượt chạy không được đóng, 10 phút sau ghi "bỏ qua".

### Kho tri thức cho agent của BQL

- [x] Tool đọc `knowledge.search` sau cổng tool: phiên bản đã phát hành phải được cấp tool, tòa nhà phải trong phạm
      vi của đơn vị, mỗi lần gọi có nhật ký.
- [x] Dịch vụ tìm kiếm vẫn hỏi lại API ai đang tìm. Với agent chuyên môn, API cấp một mã theo lượt chạy và trả lời
      bằng quyền của lượt chạy đó: vai trò quản lý, phạm vi tòa nhà, kèm phạm vi của chính đơn vị.
- [x] Lượt chạy trong phiên Supervisor không có người hỏi: dịch vụ tìm kiếm chấp nhận và ghi nhật ký không có người.
- [ ] Chưa chạy trọn vẹn với embedding thật (khóa model bị từ chối). Ngưỡng tương đồng 0,35 đặt theo câu hỏi của cư
      dân, chưa đo với câu hỏi của BQL.
- [ ] Chưa có tài liệu nào phát hành riêng cho đơn vị quản lý; trường `knowledge_namespace_ids` vẫn không dùng.

### Ảnh và tệp trong phòng nhóm

- [x] Đính kèm ảnh (PNG, JPEG, GIF, WebP, tới 8 MB) và tệp văn bản (txt, md, csv, json, tới 1 MB), tối đa 8 tệp một
      tin: giới hạn của OpenBot (`shared/attachments.ts`). API kiểm nội dung khớp loại đã khai.
- [x] Lưu bằng `message_files` và nơi lưu chung (MinIO/S3 hoặc đĩa khi chạy local); chỉ thành viên phòng đọc được.
- [x] Agent được nhắc nhận nội dung tệp văn bản (tối đa 20.000 ký tự mỗi lượt) và tên ảnh.
- [x] Đính kèm được trong câu hỏi của phiên điều phối (tệp tải lên phòng của phiên; trong phiên phải có chữ kèm theo).
- [x] Job `file-cleanup` xóa tệp tải lên quá một ngày mà không gắn vào tin nào; chạy bằng role và khóa của API.
- [x] Agent xem được ảnh trong phòng nhóm và câu hỏi theo lịch: ảnh đi kèm tin nhắn dưới dạng hình, tối đa 10 MB mỗi
      lượt; tắt bằng `SPECIALIST_SEES_IMAGES=0`. Đã kiểm bằng một tiến trình Bot thật nối với nhà cung cấp giả.
- [ ] Trong phiên điều phối chuyên viên mới được báo tên ảnh: chờ Team Đông trả lời
      `docs/teams/dong/requests/2026-10-05-anh-trong-phien-dieu-phoi.md`.
- [x] Bản tạm (`staging/`) của ảnh tải thẳng lên MinIO: xóa ngay khi ảnh được nhận; job `file-cleanup` dọn phần còn
      lại sau một giờ và ghi phiên tải lên hết hạn là `expired`.
- [ ] Tệp phòng nhóm đi qua API, chưa dùng đường tải thẳng lên MinIO.

### Hai việc nhỏ

- [x] Tool host kiểm tham số trước khi gọi máy chủ MCP ngoài; tham số chứa thông tin xác thực bị giữ lại, nhật ký ghi
      `ARGUMENTS_WITHHELD`.
- [x] Job `audit-retention` dọn nhật ký cũ hơn `AUDIT_RETENTION_DAYS`. Phải khai tenant trên kết nối: đã thử, không
      khai thì xóa 0 dòng.
- [x] Xuất nhật ký ra tệp CSV theo khoảng ngày (giờ Việt Nam), tối đa 50.000 sự kiện một tệp; mỗi lần xuất được ghi
      lại.
- [x] Hướng dẫn hẹn giờ cho hai job dọn dẹp (crontab, Task Scheduler) trong `deploy/vinhomes/README.md`. Các dòng hẹn
      giờ là mẫu, chưa chạy thử trên máy chủ thật.
- [x] Thẻ Đánh giá có ô "Hỏi thử bản nháp": hỏi một câu, đọc câu trả lời và công cụ agent định gọi, rồi dùng câu hỏi
      đó làm ca đánh giá. Vẫn cần đủ 6 ca và nội dung bắt buộc của từng ca để phát hành.
- [x] Trang quản trị MinIO có cổng cố định 9001 (trước đó là cổng ngẫu nhiên không mở ra máy chủ).

### Chưa làm, xếp theo thứ tự đề xuất của tài liệu nghiên cứu

- [ ] Tìm web bằng Tavily: cần chủ dự án quyết có cho agent đọc web không.
- [ ] Skills, rồi model theo từng agent: chỉ đáng làm khi BQL có nhiều agent.
- [ ] SSO và kết nối theo tài khoản từng người: phụ thuộc việc thống nhất đăng nhập với OpenBot.

## Chờ khóa model dùng được

Khóa trong `agent-reception/.env` bị `api.openai.com` trả 401 `invalid_api_key` (kiểm lại ngày 05/10, 01:17).

- [ ] Đánh giá và phát hành "Agent Sổ tay" (bản nháp đang có ở local), hỏi agent trong phòng nhóm bằng công cụ của kết
      nối MCP (K6).
- [ ] Chạy lại luồng trọn vẹn trên giao diện mới và các bước cần model trong container.
- [ ] Chạy thử một nhà cung cấp thứ hai (Gemini hoặc DeepSeek) bằng khóa thật.
- [ ] Lịch chạy: một lượt mà agent trả lời được (đã thấy lượt chạy tới Supervisor và đóng "lỗi" vì model không trả lời).
- [ ] Agent tra cứu kho tri thức bằng `knowledge.search` với embedding thật, và đánh giá, phát hành một agent có tool này.
- [ ] Agent đọc tệp văn bản và xem ảnh đính kèm trong phòng nhóm rồi trả lời (đã kiểm tới nhà cung cấp giả).
- [ ] Hỏi thử một bản nháp bằng model thật.
