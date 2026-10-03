# Kế hoạch: Lễ tân tự nhiên, có tri thức, tự học, sẵn sàng vận hành thật

Ngày lập: 03/10/2026. Người lập: Team Chiến. Trạng thái: chờ duyệt, chưa viết code.

## Tổng quan

Lễ tân hiện tạo ticket tốt nhưng trả lời cứng, không có tri thức, không nhớ cư dân và không tự cải thiện.
Kế hoạch này đưa Lễ tân tới mức: model tự dẫn dắt hội thoại và tự chọn tool; mọi thông tin về tòa nhà lấy
từ dữ liệu có trích dẫn; câu không trả lời được đi vào session của BQL cho Supervisor xử lý; tri thức và bộ
nhớ tự lớn lên từ kết quả thật, chỉ cần người duyệt ở nhóm nội dung rủi ro cao.

## Hiện trạng đã kiểm chứng (03/10/2026)

| Hạng mục | Thực tế |
|---|---|
| Tài liệu tri thức | **Có.** Repo công khai `github.com/leduc1707/Data-Vinhome`: 140 file Markdown về Ocean Park (đô thị, Vinhomes Sapphire/Pavilion/Zenpark, Masterise, thấp tầng): nội quy, phí, tiện ích, danh bạ, quy định theo tòa. Bộ đánh giá 93 câu hỏi đã nằm trong `server/tests/knowledge/eval/ocean-park.v1.json`. Chưa nạp vào database nào. |
| Dữ liệu kỹ thuật | Nhánh `dev_TeamQuang_ddhung04` (chưa merge): 16 đoạn tham khảo phân loại sự cố, ghi rõ chỉ dùng nội bộ, không trả lời cư dân. Dành cho Technical agent. |
| Nhánh Hoàng, Đông | Không có tài liệu tri thức. Đông có một bộ dữ liệu đánh giá điều phối. |
| Cách tìm kiếm hiện có | Team Quang: cắt Markdown theo tiêu đề, embedding OpenAI, pgvector + từ khóa rồi trộn hạng, lọc quyền trước khi tìm. |
| Qdrant | Chỉ có một bản ghi quyết định kiến trúc trên `main` (PostgreSQL giữ dữ liệu gốc, Qdrant giữ vector cho memory). **Không có dòng code nào.** |
| GraphRAG | Chưa có ở nhánh nào. |
| Lễ tân | Graph cố định 18 node; model chỉ phân loại và trích xuất; 21 câu trả lời viết sẵn (đã thêm bước viết lại lời). |
| Câu hỏi không có nguồn | Dừng ở "chưa đủ nguồn". Session chỉ được tạo cùng ticket; ticket chỉ có hai loại `incident` và `service_request`; đường Supervisor → Lễ tân → cư dân chưa nối. |
| Bộ nhớ | Bảng có sẵn (`memory_namespaces`, `memory_candidates`, `memory_publications`, `run_memory_access`), chưa dùng. |
| Tín hiệu phản hồi | Bảng có sẵn (`ticket_reviews`, `ticket_triage_reviews`, `knowledge_reviews`, `retrieval_runs`, `retrieval_hits`), đều 0 dòng. |
| Danh sách hội thoại | Tiêu đề là tên mặc định; dòng phụ hiện UUID của ticket. |

## Điểm gốc (03/10/2026, graph cố định, `gpt-5.4-mini`, chấm bằng `gpt-5.4`, 52 kịch bản, hai lần chạy)

| Chỉ số | Lần 1 | Lần 2 |
|---|---|---|
| Đạt kiểm tra cứng | 85% | 88% |
| Đạt phát biểu của kịch bản | 88% | 87% |
| Độ tự nhiên (1–5) | 4,19 | 4,37 |
| Có bịa thông tin | 0% | 4% |
| Độ trễ trung vị / p95 | 5,9 s / 7,6 s | 6,1 s / 7,9 s |

Hỏng ở cả hai lần: tin nhắn mơ hồ bị tạo yêu cầu ngay (5/6 kịch bản); "nấu cơm bị cháy khét" bị xếp khẩn cấp;
yêu cầu xin danh sách cư dân bị tạo thành ticket; câu hỏi ngoài phạm vi không được định hướng lại.
Hỏng thất thường: báo cháy không dấu rơi vào "cần xem xét" và không tạo yêu cầu (1/2 lần) — lỗi an toàn,
cần điều tra trước Giai đoạn 3; từ "ticket" lọt vào câu hỏi lại (1/2 lần).

## Quyết định kiến trúc

1. **Câu không trả lời được đi vào session của BQL, không có kênh riêng.** Lễ tân mở một yêu cầu hỏi đáp
   (ticket loại `service_request`, danh mục "Hỏi đáp"; không đổi schema), backend mở session trong group chat của
   BQL, Supervisor nhận. Khi Supervisor của Team Đông chưa chạy, BQL trả lời ngay trong session đó; cùng một
   đường đưa câu trả lời về chat của cư dân. Khi Supervisor chạy, không phải đổi gì ở phía Lễ tân.

2. **Model dẫn dắt hội thoại, code giữ quyền quyết định nghiệp vụ.** Thay phần "phân loại rồi đi nhánh" bằng
   một vòng agent gọi tool. Những thứ vẫn là code, model không vượt được: danh tính và ủy quyền, policy khẩn
   cấp, một hội thoại một yêu cầu đang mở, thứ tự nháp → bàn giao, idempotency, nguồn gốc dữ kiện. Trước khi
   gửi, một bước kiểm tra chặn câu trả lời khẳng định điều backend chưa xác nhận hoặc nêu phí/quy định mà
   không có trích dẫn.

3. **Xây agent mới song song, bật bằng cờ.** Graph của Team Hoàng giữ nguyên và vẫn là mặc định cho tới khi
   agent mới thắng trên bộ đánh giá. Không xóa code của Team Hoàng.

4. **Giữ pgvector, chưa dùng Qdrant.** 140 tài liệu là vài nghìn đoạn; pgvector đủ tới hàng triệu vector và cho
   phép lọc quyền, RLS và tìm kiếm trong cùng một câu truy vấn, đúng với thiết kế "lọc quyền trước" của Team
   Quang. Qdrant thêm một kho thứ hai phải đồng bộ và kiểm quyền lại. Chỉ chuyển khi số đo cho thấy cần
   (trên khoảng 1 triệu vector hoặc độ trễ tìm kiếm vượt 300 ms); đường chuyển đã có trong bản ghi quyết định.

5. **"Graph" cho RAG làm bằng quan hệ trong PostgreSQL, không dựng GraphRAG đầy đủ.** Dữ liệu vốn có cấu trúc
   cây (đô thị → phân khu → tòa → căn) và database đã có đồ thị thực thể (tòa, căn, tài sản, ticket, danh mục).
   Thêm bảng thực thể và cạnh cho tri thức (tiện ích, loại phí, thiết bị, đầu mối liên hệ), mở rộng kết quả
   tìm kiếm sang các đoạn láng giềng. Tóm tắt cộng đồng kiểu GraphRAG của Microsoft là quá mức với 140 tài
   liệu; chỉ xét lại khi kho vượt vài nghìn tài liệu.

6. **Tự học là vòng phản hồi có chấm điểm, không phải huấn luyện lại model.** Ba đầu ra: điểm tin cậy của từng
   đoạn tri thức (ảnh hưởng thứ hạng), ngân hàng ví dụ mẫu chọn theo độ giống, và bộ đánh giá chặn mọi thay
   đổi prompt/model làm tệ đi.

7. **Tự động theo mức rủi ro, người chỉ bấm duyệt ở mức cao.**

   | Mức | Nội dung | Cách vào kho |
   |---|---|---|
   | A | Bộ nhớ riêng của một cư dân, rút từ ticket đã đóng và đã xác nhận | Tự động hoàn toàn |
   | B | Hỏi đáp chung từ câu trả lời của BQL, kinh nghiệm xử lý sự cố | Agent thẩm định chấm; đạt thì tự xuất bản với nhãn "chưa xác minh", tự hết hạn; được dùng lại nhiều lần mà không bị phản hồi xấu thì tự nâng hạng |
   | C | Phí, giá, quy định, hướng dẫn an toàn | Agent soạn sẵn, BQL bấm một nút duyệt ngay trong session |

   Mức C không tự động: một con số phí sai hay một hướng dẫn an toàn sai gây hại thật.

## Danh sách công việc

### Giai đoạn 0 — Nền để đo và dọn giao diện (không phụ thuộc ai)

**T0.1 Danh sách hội thoại và thông báo dễ đọc** (S)
- Tiêu đề tự đặt từ tin nhắn đầu của cư dân hoặc tiêu đề ticket; dòng phụ là mã yêu cầu + trạng thái, hoặc
  trích tin nhắn cuối; có thời gian tương đối; ẩn hội thoại rỗng.
- Chấp nhận: không còn UUID hay "Hội thoại mới" trên màn hình khi hội thoại đã có tin nhắn.
- Kiểm chứng: ảnh chụp trình duyệt hai màn; `bun test` của `resident-app`.
- File: `v3_resident.py`, `ConversationList.tsx`, `use-connected-resident.ts`, `App.tsx`.

**T0.2 Bộ đánh giá hội thoại tiếng Việt chạy tự động** (M)
- Khoảng 60 kịch bản nhiều lượt (báo sự cố, mơ hồ, hỏi thông tin, khẩn cấp, bổ sung, hủy, không dấu, chen
  ngang, cố ý đánh lừa). Chấm bằng kiểm tra cứng (có ticket không, mức ưu tiên, có trích dẫn không) và một
  model chấm độ tự nhiên, độ đúng.
- Chấp nhận: một lệnh in ra bảng điểm; chạy lại hai lần lệch không quá 3 điểm.
- Kiểm chứng: chạy trên graph hiện tại để có điểm gốc.
- File: `agent-reception/tests/eval/`.

**T0.3 Dọn dữ liệu thử** (XS) — cần bạn đồng ý vì là xóa dữ liệu.

### Giai đoạn 1 — Tri thức chạy thật

**T1.1 Nạp Data-Vinhome và gắn với tòa nhà trong database** (M)
- Ánh xạ thư mục dữ liệu ↔ phạm vi truy cập của tòa; tạo kho tri thức; cấp quyền đọc cho Lễ tân.
- Chấp nhận: cư dân ở tòa S1.01 chỉ tìm thấy tài liệu đô thị, Sapphire 1 và tòa mình.
- Kiểm chứng: bộ 93 câu của Team Quang đạt bằng hoặc hơn số Team Quang đã công bố.
- Phụ thuộc: Team Quang xác nhận ánh xạ phạm vi.

**T1.2 Bật route tìm kiếm trên server, Lễ tân trả lời có trích dẫn** (S)
- Chấp nhận: "số an ninh chung cư" trả về 0858 001 080 kèm nguồn; câu ngoài phạm vi báo không có nguồn.
- Kiểm chứng: test cho route cấp quyền tri thức (hiện chưa có); chat thử trên trình duyệt.

### Điểm dừng 1: Lễ tân trả lời được câu hỏi tòa nhà có trích dẫn; có điểm gốc của cả hai bộ đánh giá. Duyệt trước khi đi tiếp.

### Giai đoạn 2 — Câu không có nguồn đi vào session của BQL

**T2.1 Lễ tân mở yêu cầu hỏi đáp khi không có nguồn** (M)
- Chấp nhận: cư dân hỏi câu không có nguồn → Lễ tân nói sẽ hỏi BQL → BQL thấy một yêu cầu "Hỏi đáp" kèm session.

**T2.2 Tin nhắn từ session về tới chat cư dân** (M)
- BQL (hoặc Supervisor) trả lời trong session; cư dân thấy câu trả lời trong đúng hội thoại.
- Chấp nhận: test đầu-cuối qua HTTP; kiểm trên trình duyệt hai phía.
- Phụ thuộc: hợp đồng message V2 của Team Đông (đã có loại `information_requested`, `completed`).

**T2.3 Màn tin nhắn session trong Operations** (M)
- BQL đọc và trả lời trong session, thấy cả thông tin cư dân tự bổ sung.

### Giai đoạn 3 — Agent do model dẫn dắt

**T3.1 Model adapter gọi tool** (S) — thêm tool calling gốc; giữ chế độ JSON cũ.

**T3.2 Bộ tool cho agent** (M)
- `search_knowledge`, `recall_memory`, `my_requests`, `request_status`, `start_request` (gói cả chuỗi nháp →
  xác minh → đánh giá → định tuyến → bàn giao thành một lệnh, vẫn chạy bằng code hiện có), `add_information`,
  `cancel_request`, `ask_management`.
- Chấp nhận: mỗi tool có test từ chối khi vi phạm bất biến (ví dụ mở yêu cầu thứ hai trong cùng hội thoại).

**T3.3 Vòng agent + cổng policy + bước kiểm tra đầu ra** (L, tách hai phần khi làm)
- Chấp nhận: khẩn cấp vẫn do policy quyết định trước khi model chạy; câu trả lời nêu phí mà không có trích
  dẫn bị chặn và viết lại; tối đa 6 bước tool mỗi lượt.

**T3.4 Chạy song song và so sánh** (S)
- Agent mới chạy ngầm trên cùng tin nhắn, không gửi cho cư dân; so điểm với graph cũ.
- Chấp nhận để bật: điểm tự nhiên cao hơn rõ rệt, điểm an toàn không thấp hơn, không tạo sai ticket.

### Điểm dừng 2: quyết định bật agent mới làm mặc định dựa trên bảng điểm.

### Giai đoạn 4 — Bộ nhớ dài hạn

**T4.1 Bộ nhớ cư dân từ ticket đã đóng** (M)
- Tự động khi ticket đóng và cư dân xác nhận: thiết bị, sự cố lặp lại, khung giờ tiện tiếp thợ.
- Chấp nhận: cư dân báo lại sự cố cũ, Lễ tân nhắc được lần trước; cư dân khác không đọc được (test RLS).

**T4.2 Quyền xem và xóa bộ nhớ của chính mình** (S) — cư dân xem và xóa được; đây là dữ liệu cá nhân.

### Giai đoạn 5 — Tự thẩm định và tự cải thiện

**T5.1 Thu tín hiệu ngầm** (S)
- Không cần ai nhập: cư dân xác nhận hay từ chối kết quả, mở lại, hỏi lại ngay sau câu trả lời, BQL sửa danh
  mục/mức ưu tiên, đoạn tri thức nào được trích dẫn.

**T5.2 Agent thẩm định tri thức** (M)
- Chấm từng ứng viên: có nguồn xác minh không, có khái quát được không, có mâu thuẫn tài liệu hiện có không,
  có dữ liệu cá nhân không. Phân vào mức A/B/C.
- Chấp nhận: trên 40 ứng viên dựng sẵn, không ứng viên chứa phí hay dữ liệu cá nhân nào lọt vào mức tự xuất bản.

**T5.3 Điểm tin cậy ảnh hưởng thứ hạng; tự nâng và hạ hạng** (M)

**T5.4 Ngân hàng ví dụ mẫu từ các lần BQL sửa phân loại** (S)

**T5.5 Nút duyệt một chạm cho mức C trong session** (S)

### Giai đoạn 6 — Tối ưu truy xuất (chỉ làm cái nào bộ đánh giá cho thấy có lợi)

**T6.1 Viết lại câu hỏi theo ngữ cảnh hội thoại** (S) — hiện tìm bằng nguyên văn tin nhắn cuối.
**T6.2 Tìm tiếng Việt không dấu và sai chính tả** (S)
**T6.3 Xếp hạng lại kết quả** (S)
**T6.4 Thực thể và cạnh cho tri thức, mở rộng sang đoạn láng giềng** (M)
**T6.5 Đo và quyết định Qdrant** (XS) — theo ngưỡng ở quyết định 4.

### Giai đoạn 7 — Vận hành thật, bỏ chế độ demo

**T7.1 Lưu phiên Lễ tân trên PostgreSQL** (M) — chạy được nhiều bản; dọn run treo.
**T7.2 Theo dõi chi phí, độ trễ, giới hạn tần suất theo cư dân** (S)
**T7.3 Ma trận phân quyền và test từ chối cho từng vai trò** (M) — xem mục RBAC.
**T7.4 Một đường migration duy nhất** (M) — `db:verify` đang lệch 148/154 bảng; database thật từng bị áp sai thứ tự.
**T7.5 Tắt đường đăng nhập demo trong bản chạy thật** (S)
**T7.6 Nhập dữ liệu tổ chức thật** (L, phụ thuộc Team Phái) — tòa, căn, cư dân, danh mục, phòng và Supervisor của từng BQL qua Agent Factory.

## Phân quyền từ các bên tới platform (RBAC)

| Lớp | Hiện có | Còn thiếu |
|---|---|---|
| Danh tính | Tài khoản platform; đăng nhập bằng mật khẩu hoặc phiên platform | Chế độ demo dùng header vẫn tồn tại song song |
| Vai trò người | `management`, `staff`, `customer` gắn với phạm vi (tenant, khu, phân khu, tòa, đơn vị quản lý); quản trị platform | Chưa có ma trận viết ra và test từ chối đầy đủ |
| Cư dân | Thành viên tenant + căn hộ đã xác minh; chỉ thấy hội thoại và yêu cầu của mình (RLS) | — |
| Lễ tân | Token ngắn hạn gắn với một lượt chat của một cư dân | Giới hạn tần suất |
| Supervisor và subagent | Bảng cho danh tính dịch vụ theo workspace đã có | Chưa có cơ chế ủy quyền cho nhóm agent; phụ thuộc Team Đông |
| Tri thức | Quyền đọc theo agent và theo phạm vi tài liệu; lọc quyền trước khi tìm | Chưa có dữ liệu quyền nào; route cấp quyền chưa có test |
| Bộ nhớ | Bảng không gian nhớ và nhật ký truy cập | Chưa dùng |
| Agent Factory | Tạo đặc tả agent | Chưa gắn quyền khi tạo agent, phòng, Supervisor cho BQL thật |

## Rủi ro

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| Model tự dẫn dắt nói sai phí, quy định, hoặc hứa hẹn | Cao | Bước kiểm tra đầu ra bắt buộc trích dẫn; chạy song song trước khi bật; bộ đánh giá chặn |
| Tri thức tự xuất bản sai lan sang nhiều cư dân | Cao | Mức B gắn nhãn chưa xác minh và tự hết hạn; mức C luôn có người duyệt |
| Bộ nhớ cư dân lộ sang người khác | Cao | RLS theo cư dân; test từ chối; cư dân tự xem và xóa |
| Dữ liệu Data-Vinhome không khớp tòa nhà trong database | Trung bình | T1.1 làm ánh xạ trước, có test phạm vi |
| Chi phí model tăng (vòng agent gọi nhiều lượt) | Trung bình | Giới hạn 6 bước; theo dõi chi phí mỗi lượt; model nhỏ cho bước phụ |
| Sửa trên vùng của Team Hoàng gây xung đột | Trung bình | Agent mới là module riêng, bật bằng cờ |
| Supervisor của Team Đông chưa chạy | Trung bình | Giai đoạn 2 chạy được với BQL trả lời tay trên cùng đường |

## Câu hỏi cần bạn trả lời

1. Dùng repo Data-Vinhome làm kho tri thức chính thức được không? Ai chịu trách nhiệm nội dung? Có nạp cả phần Masterise không?
2. Đồng ý giữ một nút duyệt của BQL cho phí, quy định và hướng dẫn an toàn (mức C) không?
3. Agent mới đặt trong `agent-reception/` cạnh graph của Team Hoàng; ai là chủ về sau, Team Hoàng hay Team Chiến?
4. Cho phép xóa dữ liệu thử trong database demo (T0.3) không?
