# Rà soát toàn dự án — 05/10/2026

Nhánh `dev_teamChien_HuyDo` tại `f1ffcac`. Tài liệu này ghi những gì **đã chạy và đã thấy** ngày 05/10/2026 (11:50–12:30),
để lập kế hoạch; lúc đó chưa sửa dòng code nào. Việc đã làm sau đó ở mục 0. Phần đọc sâu luồng Lễ tân nằm ở
[RECEPTION_INTAKE_AUDIT_2026-10-05.md](RECEPTION_INTAKE_AUDIT_2026-10-05.md) (22 điểm lỗi, kèm `file:dòng`).

Cách làm: chạy các bộ test; đọc dữ liệu và log của stack Docker local đang chạy (`vinhomes_docker_complete`,
`vinhomes_docker_coordination`); đi qua mọi trang Operations bằng ba tài khoản thật (Playwright, chỉ đọc); gửi **một** phản
ánh thật qua ứng dụng cư dân với model thật để tái hiện lỗi được báo. Ảnh và kết quả thô ở thư mục không commit
`.codex-artifacts/audit-2026-10-05/`.

## 0. Tình trạng sau khi triển khai (05/10/2026, chiều)

Các mục từ 1 trở đi là hồ sơ lúc rà soát. Phần này ghi cái đã làm sau đó, trên cùng nhánh; trạng thái
"chưa commit" trong các ghi chép bên dưới là tại thời điểm kiểm tra ban đầu.

Kiểm tra lại trước khi đồng bộ nhánh ngày 05/10: backend 113 đạt, 11 bỏ qua; Lễ tân 363 đạt,
12 bỏ qua, 1 xfailed; Factory 47 đạt; cư dân 23 đạt; auth/config/guards và máy chủ giao diện 176 đạt;
tool host/báo cáo/an ninh/tri thức 1.251 đạt, 13 bỏ qua. Typecheck toàn workspace và build hai giao diện đạt.
Đã sửa phép so đường dẫn trong test máy chủ giao diện để chạy cả Windows và Linux. Đây là kết quả local;
trạng thái CI trên GitHub phải đối chiếu với từng commit được push.

Kiểm chứng Linux khi publish: job tích hợp nghiệp vụ trên GitHub đạt 117 test, 7 bỏ qua; các job
Lễ tân và Supervisor đạt. Bộ test giao diện phải chạy mỗi file trong một tiến trình vì mỗi file đóng
cửa sổ Happy DOM của nó, còn React/portal giữ module đã nạp. Chạy đúng cách này trong container Linux
sạch (Bun 1.3.14, cài theo lockfile, không dùng file `.env` local) đạt đủ 36 test của cả 8 file.

Phạm vi UI chủ dự án chốt khi hoàn tác: Điều phối giữ navigation chính và danh sách phiên ở hai vùng riêng.
Việc hoàn tác chỉ áp dụng lượt đổi bố cục Điều phối gần nhất; luồng Supervisor tự duyệt vẫn giữ nguyên.
Playwright xác nhận danh sách phiên, thu/mở navigation và màn hình 390 px không tràn ngang, không lỗi JavaScript.

### Đã làm và đã kiểm

| Việc | Kiểm bằng |
|---|---|
| A1–A9 của mục 4.3 (luồng Lễ tân): chi tiết từng điểm ở [mục 0 của tài liệu Lễ tân](RECEPTION_INTAKE_AUDIT_2026-10-05.md) | test đơn vị, test PostgreSQL, test đầu-cuối hai chế độ, chạy thật |
| Bản đóng gói mặc định `loop` (`compose.yml`, `deployment.env.example`, `agent-reception/.env.example`) | stack Docker chạy `loop` |
| Supervisor tự chạy lại phiên dừng vì model: sau 1 phút, rồi giãn dần, tối đa 2 giờ; khi một phiên còn lỗi thì các phiên khác chờ, không dồn dập gọi model | 4 test mới; trên stack thật 12 phiên cũ đã chạy lại |
| Supervisor nhận lại phiên bị bỏ dở giữa lúc lập phương án khi tiến trình dừng | test mới; trên stack thật 2 phiên |
| Vòng lặp chính của Supervisor không chết im lặng; lý do model lỗi (mã HTTP, mã lỗi của nhà cung cấp) được ghi log | đọc log trên stack |
| BQL mở địa chỉ của quản trị viên thì về trang Điều phối; `/operations/dispatch` không còn đưa về trang đăng nhập | Playwright, 2 vai trò × 5 địa chỉ |
| CI thêm ba việc: Lễ tân, Supervisor, và (trong job có sẵn) Factory cùng tool host/báo cáo/an ninh/tri thức | **mới chạy trên máy này, chưa chạy trên GitHub** |

Chạy thật trên stack Docker (`gpt-6-luna`), 13:40:

| Cư dân gửi | Kết quả |
|---|---|
| (bấm "Bắt đầu trò chuyện") | mở cuộc trò chuyện, không gửi tin nào, không tạo yêu cầu |
| "Nhà tắm của tôi bị rò nước" + ảnh | "Bạn thấy nước rò ở đâu trong nhà tắm: vòi, ống, bồn cầu, tường hay trần? Nếu chưa xác định được, bạn cứ nói chưa rõ nhé." Chưa có yêu cầu |
| "Rò ở chân vòi lavabo, chảy nhỏ giọt" | yêu cầu được tạo: tiêu đề "Nhà tắm của tôi bị rò nước", mô tả là hai câu trên nguyên văn, 1 ảnh, dữ kiện `area=Nhà tắm`, `item=chân vòi lavabo`. Supervisor đề xuất phương án, đang chờ BQL duyệt |
| "Máy nước nóng… không có mùi khét…" | yêu cầu thường, không còn bị xếp khẩn cấp |
| (chỉ gửi ảnh) | "Mình chưa xem được ảnh. Bạn đang gặp sự cố hay cần hỗ trợ việc gì vậy?" Không tạo yêu cầu, không để lại bản nháp |

Ảnh màn hình và kịch bản kiểm: `.codex-artifacts/audit-2026-10-05/after-fix/`.

Kết quả test sau khi sửa:

| Bộ test | Trước | Sau |
|---|---|---|
| Backend | 82 đạt, 11 bỏ qua | 99 đạt, 11 bỏ qua |
| Lễ tân | 343 đạt, 1 hỏng, 9 bỏ qua | 362 đạt, 12 bỏ qua, 1 đánh dấu hỏng có lý do |
| Lễ tân đầu-cuối, backend thật, `loop` và `graph` | không chạy | 9/9 mỗi chế độ |
| Supervisor | 452 đạt | 456 đạt |
| Ứng dụng cư dân | 17 đạt | 22 đạt |

Test Lễ tân còn đánh dấu hỏng: `test_existing_graph_can_reach_http_with_new_backend_port`. Module `src/tools` của Team
Hoàng từ chối đúng yêu cầu mà graph gửi và chưa được nối vào runtime; chưa sửa.

### Điều tôi ghi sai ở lượt rà soát

- "65 test Operations hỏng": phần lớn do tôi chạy `bun test` trong thư mục `app/`. File nạp trước của bộ test
  (`bunfig.toml` ở gốc repo) chỉ có hiệu lực khi chạy từ gốc; chạy từ gốc thì còn 41 test hỏng, trong đó
  `agent-factory-ui` chỉ hỏng 1 chứ không phải 11. Phần còn lại đã xử lý, xem bảng "Test giao diện Operations" dưới.
- "Agent Báo cáo có hai bản cùng `published`": đúng thiết kế. Phiên đang chạy giữ bản nó đã ghim; nơi mời agent chỉ
  lấy bản mới nhất.

### Test giao diện Operations (làm thêm cùng ngày)

Chạy `bun --no-env-file test app/tests` từ gốc repo: trước 913 đạt, 41 hỏng, 1 lỗi nạp file; sau **952 đạt, 7 hỏng**.

| Nhóm | Nguyên nhân | Đã làm |
|---|---|---|
| 10 test ở `connected-operations-ui` và bốn file `operations-*`: đạt khi chạy riêng, hỏng khi chạy chung | React DOM quyết định một lần, lúc được nạp, có nghe sự kiện `input` hay không. File test chạy trước nạp nó khi chưa có DOM, nên từ đó `fireEvent.change` trên ô nhập không tới React nữa | Các test này gõ vào ô nhập như người dùng (`app/tests/type-into.ts`), đúng cách các test gốc đang làm. Select và ô chọn tệp giữ nguyên |
| `agent-factory-ui` C05 (và C06 theo sau) | Test gõ bảy biểu mẫu, quá 5 giây mặc định trên máy này | Cho test đó 30 giây |
| 23 test của `serve.test.ts` | Thư mục chạy tiến trình con lấy bằng biểu thức chỉ nhận dấu `/`, trên Windows trỏ nhầm vào `tests/` | Nhận cả hai loại dấu |
| 5 test còn lại của `serve.test.ts` | So đường dẫn bằng dấu `/` trong khi Windows trả `\`; sản phẩm trả đúng file | Chưa sửa: chỉ là cách viết phép so, trên Linux đạt |
| 2 test của `build-cache.test.ts` | Tiến trình con thoát mã 1; chưa tìm nguyên nhân | Chưa sửa |

Thử nạp React DOM trong file nạp trước (để sửa tận gốc cho mọi file) làm 212 test khác hỏng, nên đã bỏ cách đó.

### Supervisor duyệt thay Ban quản lý (chủ dự án chốt chiều 05/10)

Ban quản lý không còn duyệt từng phương án, không phân công và không nghiệm thu; chỉ bấm "Duyệt đóng phiên" ở cuối.

- Supervisor tự duyệt phương án nó đề xuất (`services/vinhomes-api/src/vinhomes_api/supervised_flow.py`); nhật ký ghi
  người quyết định là Supervisor. Cư dân vẫn là người đồng ý phương án.
- Cư dân đồng ý xong, phiếu việc được mời tới kỹ thuật viên đang rảnh nhất của đơn vị, đúng chuyên môn và đang trong ca
  (hạn nhận 24 giờ). Không có ai phù hợp thì phiếu nằm chờ và Ban quản lý phân công tay như trước.
- Kỹ thuật viên báo xong thì kết quả tới thẳng cư dân để xác nhận, không qua bước nghiệm thu của Ban quản lý.
- `VINHOMES_API_SUPERVISOR_APPROVES_PLANS=0` (compose: `SUPERVISOR_APPROVES_PLANS`) trả cả ba bước về cho Ban quản lý.
- Lễ tân: khi tin của cư dân đã được chuyển làm câu trả lời cho Supervisor, câu đáp là câu cố định "Mình đã chuyển câu
  trả lời của bạn tới Ban quản lý", không còn để model viết (trước đó model có thể đáp "chưa ghi nhận được").

Chạy thật 16:17–16:19 trên stack Docker, một yêu cầu mới: Lễ tân hỏi lại → cư dân nói không biết → tạo yêu cầu →
Supervisor hỏi cư dân → cư dân trả lời trong chat → phương án được Supervisor duyệt → cư dân đồng ý → phiếu việc tự
mời kỹ thuật viên → làm việc, ảnh trước/sau → cư dân xác nhận → Ban quản lý đóng phiên. Trình duyệt của Ban quản lý
chỉ gửi đúng một lệnh ghi: đóng phiên. Bằng chứng: `.codex-artifacts/audit-2026-10-05/full-flow-supervised/`.

Còn lại: kỹ thuật viên vẫn gửi "phương án sửa" tại chỗ và cư dân bấm đồng ý lần hai trước khi thi công (giao diện kỹ
thuật viên chưa đổi); trạng thái phía Supervisor vẫn là `execution_ready` sau khi phiên đóng.

### Chưa làm

| Việc | Vì sao |
|---|---|
| Xóa khoảng 10.000 dòng backend thế hệ cũ | cần bạn xác nhận riêng |
| SLA, triage, loại sự cố cho yêu cầu; thêm danh mục dịch vụ ngoài Kỹ thuật và An ninh | là tính năng mới, cần quyết định nghiệp vụ |
| Dữ liệu SOP cho agent kỹ thuật (công cụ vẫn trả 0 kết quả) | chờ quyết định về dữ liệu Team Quang |
| Agent đang phát hành giữ công cụ đã bị bỏ khỏi danh mục | chưa làm bước kiểm khi đổi danh mục |
| Model xem ảnh ở Lễ tân; màn BQL hiện ảnh trong hội thoại | chưa làm |
| Supervisor xử lý song song; báo cư dân khi phiên dừng; hiện tin bị giữ lại cho BQL | chưa làm |
| Hai mục Công việc, Báo cáo của BQL theo giao diện mới; gỡ các trang cũ còn mở được | chưa làm |
| Tiêu chí hỏi lại riêng cho từng loại sự cố | đợt này dùng một tiêu chí chung: hiện tượng + vật hoặc điểm cụ thể |
| Danh sách từ khóa khẩn cấp | cần người có thẩm quyền duyệt; danh sách hiện hành ở `v3_reception_runtime.py` (`EMERGENCY_KINDS`, `BENIGN_TERMS`) |

Khung chat của ứng dụng cư dân đã có test tự động: quy tắc được tách thành hàm thuần
(`resident-app/src/services/chat-turn.ts`) và kiểm ở `resident-app/tests/chat-turn.test.ts` (5 test; cả bộ 22 đạt).
Phần vẽ giao diện vẫn kiểm bằng trình duyệt.

Dữ liệu thử để lại trên stack local: ba cuộc trò chuyện và hai yêu cầu của lượt kiểm 13:40, một yêu cầu "Sự cố chưa
rõ" của lượt tái hiện 12:01. 12 phiên cũ đã được chạy lại bằng model thật. Trạng thái 20 phiên lúc 14:10: 7 chờ
cư dân trả lời, 7 chờ BQL duyệt, 4 dừng vì backend từ chối (dữ liệu thử đã đổi), 1 dừng vì hết quyền, 1 có kết quả
chưa rõ.

## 1. Kết luận

1. **Luồng nhận yêu cầu từ Lễ tân hỏng ngay trên đường chính, và đã tái hiện được.** Cư dân bấm "Bắt đầu trò chuyện",
   rồi gửi "Nhà tắm của tôi bị rò nước" kèm ảnh: hệ thống tạo một yêu cầu rỗng tên "Sự cố chưa rõ", **từ chối** câu phản
   ánh thật ("bấm Chat mới để báo riêng"), ảnh không vào yêu cầu, và cư dân nhận ba câu hỏi từ ba nơi khác nhau.
2. Nguyên nhân lớn nhất **không nằm trong bản kế hoạch sửa Lễ tân đã có**: ứng dụng cư dân chạy cùng lúc trợ lý
   Lễ tân và một biểu mẫu từng bước của riêng nó, và tự gửi câu "Báo sự cố" thay cư dân.
3. Bản kế hoạch đó chẩn đoán đúng phần còn lại (8/11 điểm đúng, 3 điểm đúng một phần), nhưng thiếu một điều: chế độ
   `graph` — mặc định của bản đóng gói — **không bao giờ hỏi lại** được.
4. Sau khi bàn giao, Supervisor và agent chuyên môn chạy được, nhưng agent kỹ thuật chưa có dữ liệu: công cụ tra SOP
   trả kết quả 0 trên 27 lần gọi. 12 phiên đang đứng vì model từng hết hạn mức và không tự chạy lại.
5. Giao diện: không trang nào lỗi HTTP hay lỗi JavaScript với cả ba vai trò. Phần còn dở là hai trong bốn mục của BQL
   vẫn là giao diện cũ, và mười trang cũ vẫn mở được bằng địa chỉ.
6. Backend chạy đúng với test của nó (82 đạt), nhưng khoảng một phần ba mã trong gói là thế hệ cũ không còn được nạp,
   và CI không chạy test của Lễ tân, Supervisor, Factory.

## 2. Ba nhánh

| Nhánh | Commit | So với `origin/develop` |
|---|---|---|
| `dev_teamChien_HuyDo` (đang dùng) | `f1ffcac` 05/10 11:22 | hơn 13 commit, không thiếu commit nào |
| `origin/dev_TeamChien` | `f1ffcac` | trùng nhánh trên |
| `origin/develop` | `5fcb882` 05/10 03:53 | — |

Nhánh local `dev_TeamChien` (chậm 40 commit) và `develop` (chậm 259 commit) là bản cũ trên máy, chưa kéo về. 13 commit
mới (ảnh trong phòng nhóm, lịch agent, xuất nhật ký, Lễ tân dùng `gpt-6-luna`) chưa có PR vào `develop`. Cây làm việc
còn `docker-compose.yml` bị đổi định dạng (không đổi nội dung) và hai tài liệu chưa commit.

## 3. Kết quả test

| Bộ test | Kết quả | CI có chạy |
|---|---|---|
| Backend `services/vinhomes-api` (PostgreSQL tạm) | 82 đạt, 11 bỏ qua | có |
| Lễ tân `agent-reception` | 343 đạt, **1 hỏng**, 9 bỏ qua | **không** |
| Supervisor `agent-coordination` | 452 đạt | **không** |
| Agent Factory | 44 đạt | **không** |
| Tool host, báo cáo, an ninh, tri thức (`server/tests/...`) | 1.251 đạt, 13 bỏ qua | **không** (CI chỉ chạy 3 file khác) |
| Ứng dụng cư dân | 17 đạt | có |
| Ứng dụng Operations (`app/tests`) | 872 đạt, **65 hỏng** | chỉ 1 file |

- Test Lễ tân hỏng: `tests/tools/test_adversarial.py::test_existing_graph_can_reach_http_with_new_backend_port` — graph
  dừng ở `waiting_operation`, không gọi backend. Cả thư mục `agent-reception/src/tools/` (khoảng 1.150 dòng) không được
  runtime nạp.
- 9 test đầu-cuối của Lễ tân bị bỏ qua vì cần dịch vụ thật: không có test tự động nào đi hết đường cư dân → Lễ tân →
  Supervisor.
- 65 test hỏng của Operations: 28 ở `serve.test.ts` (trên Windows báo không tìm thấy `serve.ts`; tài liệu nghiệm thu ghi
  bộ này đạt trên Linux), 11 ở `agent-factory-ui.test.tsx`, 11 ở sáu file `operations-*` và `connected-operations-ui`,
  15 ở bốn file không thuộc phần Vinhomes. Chưa xem nguyên nhân từng cái.
- 11 test backend bỏ qua gồm 4 test đăng nhập mật khẩu và 4 test MinIO (cần bật riêng).

## 4. Luồng Lễ tân → yêu cầu: điều thực sự xảy ra

### 4.1. Tái hiện ngày 05/10 lúc 12:01 (stack Docker, `loop`, `gpt-6-luna`)

| Giờ | Ai | Nội dung |
|---|---|---|
| 12:01:15 | Ứng dụng, thay cư dân | "Báo sự cố" (tự gửi khi bấm "Bắt đầu trò chuyện") |
| 12:01:18 | Lễ tân | tạo yêu cầu "Sự cố chưa rõ", mô tả "Cư dân báo: “Báo sự cố”, chưa nêu loại sự cố hoặc vị trí", bàn giao Supervisor |
| 12:01:20 | Lễ tân | "Sự cố gì đang xảy ra và ở vị trí nào trong căn hộ vậy?" |
| 12:01:21 | Cư dân | "Nhà tắm của tôi bị rò nước" + 1 ảnh |
| 12:01:25 | Lễ tân | "Mình chưa ghi nhận được sự cố rò nước nhà tắm ở cuộc trò chuyện này. Bạn vui lòng bấm “Chat mới” để báo riêng nhé." |
| 12:01:25 | Supervisor | "Bạn vui lòng cho biết sự cố cụ thể là gì và xảy ra ở vị trí nào? Có nguy hiểm tức thời…" |
| cùng lúc | Biểu mẫu của ứng dụng | "Sự cố xảy ra ở đâu? Nhập tầng, căn hộ hoặc vị trí cụ thể." |

Sau lượt này yêu cầu vẫn tên "Sự cố chưa rõ", 0 ảnh, phiên Supervisor chờ thông tin. Câu trả lời và ảnh của cư dân chỉ
nằm trong khung chat. Ảnh màn hình: `.codex-artifacts/audit-2026-10-05/resident-leak-repro.png`.

Lần này model không bịa chi tiết. Một lần chạy không chứng minh nó không bịa; phần đọc code cho thấy không có gì chặn
(mô tả do model viết đi thẳng vào yêu cầu).

### 4.2. Các ca thật khác trong cơ sở dữ liệu của stack

| Lúc | Cư dân gửi | Kết quả |
|---|---|---|
| 05/10 10:58 | (bấm nút) "Báo sự cố", rồi "tôi chưa có sự cố" | yêu cầu "Sự cố chưa xác định" vẫn mở, Supervisor vẫn hỏi cư dân |
| 05/10 11:02 | "Hiện tại nhà tôi đang bị rò nước trong phòng tắm" | bàn giao ngay, không hỏi vị trí rò; phương án đang chờ BQL duyệt. Cư dân gõ tiếp "Căn hộ 1201" thì Lễ tân đáp "chưa ghi nhận được… vì cuộc trò chuyện đang có yêu cầu khác mở" |
| 05/10 11:31 | "xem cho tôi nước bị ngắt tại phòng" + ảnh | bàn giao ngay; 50 giây sau Supervisor mới hỏi mất nước toàn căn hay một khu vực |
| 05/10 10:51 | "Xin chào", "hi" | hai lần "Xin lỗi, tôi chưa xử lý được tin nhắn này"; log không có dòng nào về lỗi |
| 05/10 10:59 | "hi", rồi "Căn hộ 1201" | biểu mẫu tạo yêu cầu tên "hi", mô tả "hi"; không tới Supervisor |
| 05/10 11:07 | báo vòi bếp rò | mô tả yêu cầu có câu "Bạn từng báo việc tương tự vào ngày 2026-10-05" (lời Lễ tân nói với cư dân) |
| 04/10 17:38 | "Máy nước nóng… không nóng… **không có mùi khét**" | xếp khẩn cấp; cư dân nhận "Anh chị đi thang bộ, cúi thấp nếu có khói, rồi ra điểm tập kết" kèm mã `VH-…` |

### 4.3. Nguyên nhân, theo thứ tự ảnh hưởng

| # | Vấn đề | Bằng chứng |
|---|---|---|
| A1 | Ứng dụng cư dân chạy song song Lễ tân và biểu mẫu từng bước của nó; nút "Bắt đầu trò chuyện" gửi câu "Báo sự cố" cho Lễ tân như lời cư dân | `resident-app/src/services/use-connected-resident.ts:311-358`, `:365-397`; `Assistant.tsx:125` |
| A2 | Một cuộc trò chuyện chỉ có một yêu cầu, và `loop` không có công cụ bổ sung thông tin hay ảnh vào yêu cầu đang mở. Yêu cầu rỗng tạo từ "Báo sự cố" khóa luôn cuộc trò chuyện | `agent-reception/src/agent/tools.py:143-145`; `prompt.py:19-22` |
| A3 | Không có cổng nội dung trước khi bàn giao: `loop` chỉ kiểm chữ không rỗng, danh mục, mức ưu tiên, căn hộ; `facts` luôn rỗng. `graph` thì backend trả `staff_required` cho mọi "sự cố" và `missing_information: []`, nên không bao giờ hỏi lại | `tools.py:141-157`, `:119-120`; `v3_reception_runtime.py:78-86`; `graph/assessment.py:116-117` |
| A4 | Câu cư dân trả lời Supervisor trong khung chat không tới Supervisor; ô trả lời nằm ở trang chi tiết yêu cầu | `resident-app/src/app/App.tsx:530-531`; không có công cụ tương ứng trong `tools.py` |
| A5 | Khẩn cấp dò theo cụm từ, không xét phủ định ("không có mùi khét" → cháy). Ở `loop`, cờ khẩn cấp bật trước khi tạo được yêu cầu | `v3_reception_runtime.py:36-43`, `:67-74`; `tools.py:169` |
| A6 | Model không nhận ảnh; tin chỉ có ảnh được ứng dụng gắn câu "Đính kèm ảnh phản ánh" | `agent-reception/src/runtime/model.py:88-99`; `use-connected-resident.ts:316` |
| A7 | Lượt lỗi bị nuốt, không ghi log: không biết vì sao 10:51 hỏng | `agent-reception/src/runtime/service.py:261-262`, `:274-275` |
| A8 | Prompt bảo model ghi "cư dân từng báo việc tương tự" vào mô tả yêu cầu | `agent/prompt.py:23-24` |
| A9 | Bản đóng gói mặc định `graph`; bản đã thử và đang chạy là `loop`. Ai cài theo file mẫu sẽ chạy chế độ chưa ai thử trên stack | `deploy/vinhomes/compose.yml:95`, `deployment.env.example:57` |

## 5. Từng agent

| Agent | Đang có | Chưa giải quyết |
|---|---|---|
| Lễ tân | hai chế độ, tra tri thức có trích nguồn, tạo yêu cầu, khẩn cấp, chuyển câu hỏi cho BQL | mục 4 |
| Supervisor | mở phiên, mời chuyên viên theo danh mục, hỏi cư dân, đề xuất phương án, hai lần duyệt, dừng/chạy tiếp | 12 phiên dừng `model_unavailable` không tự chạy lại khi model hoạt động, 7 mục hộp thư `blocked`; backend vẫn ghi phiên là `running` hoặc `waiting`; cư dân không được báo. Xử lý tuần tự từng tin cho mọi yêu cầu. 20/38 mục ngân sách token ở trạng thái không rõ mức dùng |
| Kỹ thuật | bản phát hành giữ 3/14 công cụ (đều là đọc) | `sop_kb.retrieve`: 23 lần `NOT_FOUND`, 4 lần `INTERNAL_ERROR`, 0 lần có kết quả; tra lịch cắt dịch vụ trả 0 dòng. Phân tích hiện là hiểu biết chung của model. 11 công cụ còn lại (4 yêu cầu, 3 ghi) chưa mở |
| Báo cáo | 4 công cụ, trả lời trong phòng nhóm | không được mời vào phiên (không khai danh mục); hai bản cùng ở trạng thái `published`; một agent thử đang phát hành giữ công cụ `reporting.get_incident_frequency_summary` đã bị bỏ khỏi danh mục |
| An ninh | một agent thử, 2 công cụ đọc | chưa có agent chính thức; danh mục mới đăng ký 2 công cụ đọc, phần sự cố, điều động, khẩn cấp trong `server/src/security-tools` chưa đăng ký |
| Factory | dịch vụ chạy; 2 lần soạn agent được ghi nhật ký | trang Model không hiện model của Factory; 11 test giao diện Factory hỏng; chưa chạy lại vòng tạo → đánh giá → phát hành sau khi đổi model |

Dữ liệu yêu cầu: cả 24 yêu cầu không có hạn phản hồi, chính sách SLA, loại sự cố, nhóm phụ trách; `triage_status` là
`pending` kể cả yêu cầu đã đóng; hai bảng `ticket_assessments` và `ticket_triage_decisions` không có dòng nào. Chỉ có
hai danh mục dịch vụ (Kỹ thuật, An ninh): vệ sinh, phí, khiếu nại chưa có đường đi.

## 6. Giao diện theo vai trò

Đã mở 22 địa chỉ `/operations/*` với từng tài khoản: không có phản hồi 4xx/5xx, không lỗi JavaScript, không tràn ngang.

| Vai trò | Menu | Nhận xét |
|---|---|---|
| Nhân viên kỹ thuật | Việc của tôi | gọn; mọi địa chỉ khác bị đưa về đây, trừ `/completed-tasks` và `/work-orders` (trang cũ vẫn mở được). Ô tìm kiếm ghi "mã ticket, nhân viên" |
| BQL | Điều phối, Công việc, Agent, Báo cáo | Điều phối và Agent theo kiểu mới. **Công việc và Báo cáo còn giao diện cũ.** Danh sách "Cần bạn xử lý" có 13 mục, 9 mục là phiên dừng vì model, phải bấm từng cái. Danh sách công việc có yêu cầu rác ("hi", "Sự cố chưa xác định") |
| Quản trị viên | thêm Tài khoản, Đơn vị quản lý, Kết nối ngoài, Model, Nhật ký | Model chỉ xem, chưa gọi thử, chưa đổi được từ giao diện |

- BQL gõ địa chỉ của quản trị viên (`/audit`, `/models`, `/units`, `/connections`) thì thấy trang Công việc dưới tiêu đề
  "Nhật ký"… Không lộ dữ liệu quản trị, nhưng tiêu đề sai.
- Năm trang (`approvals`, `contractor`, `evidence`, `sanitation`, `security`) hiện "Chức năng chưa được nối đầy đủ";
  `incidents`, `triage`, `qc`, `work-orders`, `my-tasks` là trang cũ vẫn mở được.
- `/operations/dispatch` đưa người đã đăng nhập về trang đăng nhập (route còn dùng tài khoản xem thử:
  `app/src/routes/_authed/operations/dispatch.tsx:6-7`).

Chưa bấm thử các thao tác ghi (tạo agent, duyệt phương án, nhận việc) trong lượt này.

## 7. Cấu hình agent, nền tảng, model

- Model đặt theo vai trò bằng biến môi trường (Lễ tân, Supervisor, agent chuyên môn, Factory, embedding). Không có model
  theo từng agent: 14 phiên bản agent đều để trống `model_profile_id`.
- Chỉ OpenAI đã chạy với khóa thật. `gpt-6-luna` không dùng được cho agent chuyên môn.
- BQL tự tạo và phát hành agent sau 6 ca đánh giá; sáu ca phải nhập tay.
- Thay đổi danh mục công cụ không kiểm lại các agent đang phát hành (xem agent giữ công cụ đã bỏ ở mục 5).
- Kết nối ngoài (MCP theo URL): có một kết nối thử; vòng đánh giá và phát hành với công cụ ngoài chưa chạy trên stack
  Docker.

## 8. Backend

- Ứng dụng nạp 47 router, hầu hết từ các file phẳng `v3_*.py` viết SQL trực tiếp (khoảng 17.300 dòng). File lớn nhất:
  `v3_reception_operations.py` 1.279 dòng cho 2 route.
- Khoảng 10.000 dòng không được `main.py` nạp: các gói `actions`, `approvals`, `events`, `evidence`, `incidents`, `qc`,
  `resolution`, `tasks`, `work_orders`, `commands`, `outbox`, `rules`, `db` và `demo_api.py` (55 route). Chúng chỉ nhập
  lẫn nhau; commit cuối là `c63e90a` ngày 30/09. `test_demo_api.py` vẫn test phần này.
- Dịch vụ gần như không ghi log nghiệp vụ: Supervisor 3 dòng, OpenBot 1 dòng sau gần một giờ chạy; 3 lượt chạy
  `failed` không có `error_code`; 24 lượt chạy vẫn `running`, cũ nhất từ 04/10.

## 9. Việc cần chủ dự án chốt trước khi lập kế hoạch

1. Khung chat cư dân do **Lễ tân dẫn** hay do **biểu mẫu từng bước** dẫn. Đề xuất: Lễ tân dẫn; biểu mẫu chỉ hiện khi
   Lễ tân không trả lời được; bỏ việc tự gửi "Báo sự cố".
2. Chế độ chính thức của Lễ tân. Đề xuất: `loop` kèm cổng nội dung, và đổi mặc định của bản đóng gói cho khớp.
3. Ai hỏi làm rõ: Lễ tân trước khi bàn giao (đề xuất, đúng bản kế hoạch đã có) hay Supervisor sau khi bàn giao (như
   hiện nay: mỗi yêu cầu thiếu thông tin vẫn mở một phiên Supervisor).
4. Ai duyệt danh sách từ khóa khẩn cấp, và có chấp nhận dùng model để xét phủ định hay không.
5. Bỏ phần backend thế hệ cũ hay giữ.
6. CI chạy thêm bộ nào (đề xuất: Lễ tân, Supervisor, Factory, tool host — tổng dưới 2 phút).

## 10. Thứ tự đề xuất

1. **Chặn hỏng đường chính**: A1, A2, A7, A9, rồi A5. Mỗi mục có test với model giả kiểm payload gửi backend.
2. **Bản kế hoạch sửa Lễ tân đã có**, bổ sung A1, A2, A4 và phần `graph` không hỏi lại; A3, A6, A8 nằm trong đó.
3. **Supervisor không bỏ lửng**: tự chạy lại phiên dừng vì model, báo cư dân khi phiên dừng, đồng bộ trạng thái phiên.
4. **Dữ liệu cho agent kỹ thuật** (cần quyết định về dữ liệu Team Quang), dọn agent giữ công cụ đã bỏ.
5. **CI và test đầu-cuối** cho đường cư dân → Lễ tân → Supervisor; sửa test đang hỏng.
6. Giao diện cũ của BQL, các trang cũ còn mở được, dọn backend thế hệ cũ, SLA và triage.

## 11. Chưa kiểm trong lượt này

- Luồng sau khi BQL duyệt phương án (cư dân đồng ý, kỹ thuật viên làm, nghiệm thu) trên bản hiện tại.
- Chế độ `graph` với model thật; nhà cung cấp model thứ hai; kết nối MCP trong container.
- Các thao tác ghi trên giao diện; ứng dụng cư dân ngoài khung chat.
- Việc model bịa chi tiết: mới chạy một lần, lần đó không bịa.
- Lượt tái hiện để lại một yêu cầu thử "Sự cố chưa rõ" (05/10 12:01) và một phiên Supervisor đang chờ thông tin trên
  stack local.
