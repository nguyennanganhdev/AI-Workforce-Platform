# Hướng dẫn test platform sau P0–P3

Cập nhật 14/10/2026 · Nhánh `feat/wf-p0-p3` (PR vào `develop2`) · Người đọc: PM/tester

Tài liệu này để **người** chạy thử platform với model thật. Mọi test tự động
(unit/integration, build frontend) đã chạy và pass; phần dưới đây là những gì
chỉ kiểm được khi có model, MCP và giao diện thật.

Mỗi bước có **"Đạt khi"** để ghi kết quả. Ghi lại ticket/agent bị lỗi kèm ảnh
chụp hoặc `session_id` để tra metric.

---

## 1. Chuẩn bị

### 1.1 Lấy code

```bash
git fetch origin
git checkout feat/wf-p0-p3        # hoặc develop2 sau khi PR được merge
cd platform_VP/agentscope
```

### 1.2 Biến môi trường mới (`platform_VP/agentscope/.env`)

Giữ các biến đang dùng (AUTH_*, PARTNER_*, OPENAI_*...). Thêm:

| Biến | Gợi ý | Ý nghĩa |
|---|---|---|
| `WORKFORCE_MODEL_NAME` | `gpt-5.4-mini` | Model mặc định của Leader/agent (model rẻ) |
| `WORKFORCE_LEADER_MODEL_NAME` | `gpt-5.5` (hoặc model mạnh mà gateway có) | Model mạnh cho Leader lập kế hoạch/phản biện, copilot, người chấm kiểm thử, agent đặt mức "mạnh". Phải cùng credential. Để trống = mọi vai dùng model mặc định |
| `WORKFORCE_PROMPT_CACHE_KEY` | `false` lúc đầu | Bật `true` ở bước 7 để thử; nếu gateway báo lỗi "unknown parameter" thì để `false` |
| `WORKFORCE_LEADER_WAIT_SECONDS` | `240` | Thời gian tối đa một lượt Leader chờ các agent (kể cả việc phụ thuộc) |
| `WORKFORCE_LEARNING` | `true` | Học sau ticket (bộ nhớ + tự cải tiến luật). `false` để tắt |

### 1.3 Chạy platform

**Cách A — Docker (khuyến nghị):**

```bash
docker compose up -d --build
```

Container `app` tự chạy `alembic upgrade head` — database lên tới
`0016_agent_memories` (bảng bộ nhớ agent mới).

**Cách B — chạy tay:**

```bash
python -m alembic -c src/agentscope/app/storage/_sql/_alembic/alembic.ini upgrade head
python examples/agent_service/main.py                # backend :8000
cd examples/web_ui && pnpm install && pnpm dev       # frontend :5173
```

**Đạt khi:** mở được web UI, đăng nhập được; thanh bên trái có thêm biểu tượng
**"Quản lý agent"** (hình hai người).

### 1.4 Model credential

Trang **Credential** → thêm credential OpenAI-compatible (API key + base URL
gateway). Kiểm tra model `WORKFORCE_MODEL_NAME` và `WORKFORCE_LEADER_MODEL_NAME`
đều có trong danh sách model của credential.

### 1.5 Server MCP demo (dữ liệu giả, có nhãn DEMO)

Mở terminal riêng, để chạy suốt buổi test:

```bash
cd platform_VP/agentscope
python scripts/workforce/demo_mcp_server.py --host 0.0.0.0 --port 8765
```

Trang **MCP** → thêm MCP qua URL:

- Docker: `http://host.docker.internal:8765/mcp`
- Chạy tay: `http://127.0.0.1:8765/mcp`

**Đạt khi:** MCP hiện đủ 10 tool: `search_hotels`, `get_hotel_detail`,
`search_cars`, `calculate_trip_cost`, `book_hotel`, `lookup_incident_type`,
`check_technician_availability`, `get_service_fee`, `get_cleaning_schedule`,
`create_work_order`.

---

## 2. Vấn đề 4 + 3 — Trang Quản lý agent và Builder copilot

### 2.1 Tạo 4 agent từ mẫu ngành

Quản lý agent → **Tạo agent** → tab **Từ mẫu ngành**, lần lượt tạo:

| Mẫu | Gắn tool (tab Công cụ) |
|---|---|
| Tìm khách sạn / xe | `search_hotels`, `get_hotel_detail`, `search_cars` |
| Tính chi phí chuyến đi | `calculate_trip_cost` |
| Kỹ thuật toà nhà | `lookup_incident_type`, `check_technician_availability`, `get_service_fee`, `create_work_order` |
| Vệ sinh khu vực chung | `get_cleaning_schedule` |

Với mỗi agent: **Lưu nháp** → **Chạy kiểm thử** → xem kết quả ở tab Kiểm thử →
**Phát hành**.

**Đạt khi:**
- Agent mới ở trạng thái *Bản nháp*; nút **Phát hành** bị khoá và ghi rõ lý do
  ("Hãy chạy kiểm thử…").
- Kiểm thử hiện từng kịch bản: câu trả lời, tool đã gọi (tool ghi như
  `create_work_order` hiện **"(mô phỏng)"**, không tạo lệnh thật), lý do của người
  chấm AI.
- Đạt ≥ 80% (≥ 3 kịch bản) thì phát hành được → trạng thái *Đang phát hành*, **v1**.
- Nếu < 80%: không phát hành được. Ghi lại kịch bản trượt và lý do người chấm.

### 2.2 Tạo agent bằng mô tả (Builder không còn "cứng")

Tạo agent → **Mô tả bằng lời**, nhập ví dụ:

> Agent tiếp nhận phản ánh tiếng ồn của cư dân. Luôn xin lỗi và ghi nhận trước,
> hỏi số căn hộ và khung giờ bị ồn, không hứa xử lý trong thời gian cụ thể,
> nếu có đánh nhau hoặc nguy hiểm thì báo bảo vệ ngay.

**Đạt khi:** form được điền: tên, mô tả, mục tiêu, giọng điệu; mỗi ý thành
**luật** riêng ("không hứa thời gian" là luật bắt buộc); "đánh nhau → báo bảo vệ"
nằm ở **Khi nào chuyển người**; có 3–5 kịch bản kiểm thử. Copilot có thể hỏi tối
đa 3 câu nếu thiếu thông tin quan trọng.

### 2.3 Sửa agent bằng copilot (khung bên phải)

Trên agent *Kỹ thuật toà nhà* đã phát hành, gõ lần lượt:

1. "Thêm luật: không báo giá khi chưa có ảnh hiện trường."
2. "Giọng thân thiện hơn, xưng em và gọi anh/chị."
3. "Viết thêm 2 kịch bản kiểm thử cho trường hợp mất điện."
4. "Cho agent quyền thanh toán online." (tool không tồn tại)

**Đạt khi:**
- Mỗi yêu cầu chỉ đổi đúng chỗ: (1) thêm 1 luật, (2) đổi giọng điệu, (3) thêm 2
  kịch bản; phần khác giữ nguyên. Copilot liệt kê thay đổi dạng *Thêm/Sửa/Bỏ*.
- (4) không thêm tool, nói rõ tool không có trong kho.
- Sau khi sửa, nút Phát hành khoá lại vì bản nháp đổi → phải chạy kiểm thử lại.

### 2.4 Phiên bản, rollback, sửa prompt trực tiếp

- Chạy kiểm thử → phát hành → **v2**. Tab **Phiên bản**: có v1, v2, tác giả,
  ghi chú. Bấm **Quay về** v1 → tạo **v3** có nội dung v1.
- Tab **Prompt**: xem "Prompt chạy thật" (cuối có *WORKFORCE RUNTIME POLICY*).
  Bật **Tự viết prompt**, sửa một câu, lưu nháp, kiểm thử, phát hành.
- **Ngừng phát hành** → agent không còn được Leader mời; phát hành lại được.

**Đạt khi:** mọi thao tác trên hoạt động; prompt chạy thật thay đổi đúng như
form/tự viết.

### 2.5 Trang Builder (chat) cũ

Trang Agent Builder vẫn còn. Gõ yêu cầu mơ hồ: "Tạo cho tôi một agent".
**Đạt khi:** Builder hỏi lại một câu (agent làm gì, cho ai) thay vì tự đoán ra
agent.

---

## 3. Vấn đề 1 — Agent phối hợp trong session của Leader

Trang **Leader** → **Tạo ticket thử nghiệm** cho mỗi kịch bản (một ticket một kịch bản).

| # | Khách nhắn | Đạt khi |
|---|---|---|
| 3.1 | "Mình đi Đà Nẵng 2 người, ở 2 đêm, cần xe đón từ sân bay Đà Nẵng về trung tâm. Tổng ngân sách 5 triệu và muốn giữ lại 1 triệu dự phòng. Gợi ý giúp mình phương án phù hợp." | Leader mời agent tìm khách sạn/xe và agent tính chi phí; agent tính chi phí **chỉ bắt đầu sau khi** agent tìm kiếm báo kết quả (không hỏi đi hỏi lại). Trả lời có DEMO Sông Hàn Riverside (2.650.000 VND gồm xe) hoặc DEMO Mỹ Khê Beach Stay (1.750.000), trần chi tiêu 4.000.000; không coi DEMO Ngũ Hành Sơn Resort là phù hợp; không bịa khách sạn ngoài dữ liệu. Không xuất hiện câu "Nhóm chưa hoàn tất yêu cầu…" |
| 3.2 | "Mình muốn đi Nha Trang, tư vấn khách sạn và xe giúp mình nhé." rồi "2 người, ở 3 đêm, xe đón từ sân bay Cam Ranh." | Lượt 1 hỏi **một** câu gộp. Lượt 2 đề xuất DEMO Trần Phú Ocean 3.150.000 VND và xe 420.000 VND, không hỏi thêm sở thích |
| 3.3 | "Tìm giúp mình khách sạn ở Đà Lạt cho 4 người, 2 đêm." | Nói rõ không còn phòng phù hợp; không bịa khách sạn khác |
| 3.4 | Như 3.1, rồi "Đổi lại giúp mình: nhóm thành 4 người và cần xe 7 chỗ, ngân sách và dự phòng giữ nguyên." | Tính lại: Mỹ Khê 2 phòng × 2 đêm 3.000.000 + xe 7 chỗ 380.000 = 3.380.000 phù hợp; không giữ kết quả cũ |
| 3.5 | "Căn hộ S1-1205 bị vỡ ống nước dưới bồn rửa, nước đang tràn ra sàn. Ngày 2026-10-20 khi nào có thợ đến được và phí sửa thế nào?" | Hướng dẫn khoá van tổng trước; khung giờ thợ DEMO (09:00, 13:30, 16:00 hoặc 10:30); phí 0 đồng kiểm tra, 150.000 VND/giờ; **không** tự tạo lệnh sửa |
| 3.6 | "Hành lang tầng 12 toà S1 có nước đọng và rác chưa dọn, đồng thời căn S1-1208 nhà mình bị mất điện từ sáng." | Hai agent (vệ sinh, kỹ thuật) cùng làm; trả lời gộp: lịch vệ sinh S1 + hướng dẫn ngắt cầu dao |
| 3.7 | "Đặt luôn DEMO Mỹ Khê Beach Stay cho mình." (sau 3.1) | Runtime hỏi xác nhận trong chat trước khi gọi `book_hotel`; chỉ đặt sau khi gõ "xác nhận" |

### 3.8 Xem số đo của một ticket

Lấy `session_id` của ticket (cột trái trang Leader hiện 10 ký tự đầu; bản đầy
đủ có trong URL/devtools), gọi:

```
GET /workforce/console/tickets/{session_id}/metrics
```

(trình duyệt đang đăng nhập: mở devtools → Network → copy header Authorization;
hoặc dùng script ở mục 4). **Xem:**

| Trường | Ý nghĩa | Kỳ vọng |
|---|---|---|
| `total.input_tokens`, `output_tokens` | Token thật của provider | So sánh giữa các lần chạy |
| `total.cache_hit_ratio` | Tỉ lệ token đầu vào được cache | > 0 từ lần gọi thứ 2 trong cùng ticket (nếu gateway hỗ trợ cache) |
| `by_agent[]` | Token, cache theo từng agent | Leader dùng model mạnh, agent dùng model mini |
| `branches[]` | Mỗi agent: số trao đổi, số lần bị chặn bằng chứng, trạng thái | Không có nhánh `stopped`; `evidence_rejections` thấp |
| `assignments[]` | Sổ giao việc: mục tiêu, `done_when`, `depends_on`, trạng thái | Kết thúc ở `verified`/`accepted` |

Nếu `calls_with_usage` = 0: gateway không trả `usage` → không đo được token/cache;
báo lại để đổi cấu hình gateway.

---

## 4. Đo tự động bằng model thật (P0)

Script chạy 7 kịch bản ở mục 3 qua API thật, chấm tự động và xuất báo cáo:

```bash
cd platform_VP/agentscope
python scripts/workforce/eval/run_collab_eval.py \
  --base-url http://127.0.0.1:8000 \
  --tenant default --identity <email> --password '<mật khẩu>' \
  --judge
```

- `--judge` dùng thêm model chấm: đặt `EVAL_JUDGE_MODEL=<model mạnh>` (và
  `EVAL_JUDGE_API_KEY`/`EVAL_JUDGE_BASE_URL` nếu khác `OPENAI_API_KEY`/`OPENAI_BASE_URL`).
- Chạy một phần: `--only travel-full-brief resident-pipe-burst`.
- Kết quả: `.artifacts/collab-eval/<thời điểm>/REPORT.md` (bảng đạt/không đạt,
  token, % cache, số trao đổi, lần bị chặn) và `results.json`.
- So hai lần chạy (ví dụ trước/sau bật cache):
  `python scripts/workforce/eval/run_collab_eval.py --compare A/results.json B/results.json`

**Muốn có số "trước cải tiến"**: chạy cùng script trên nhánh `develop2` cũ
(trước merge PR) — script chỉ cần endpoint metrics, nên trên bản cũ phần token
sẽ trống nhưng phần đạt/không đạt vẫn so được.

**Đạt khi:** ≥ 6/7 kịch bản đạt; không kịch bản nào có "Nhóm chưa hoàn tất".

---

## 5. Vấn đề 2 — Bộ nhớ dài hạn, tự cải tiến, kiến thức

### 5.1 Bộ nhớ sau ticket thành công

1. Chạy ticket 3.5 (vỡ ống nước) tới khi Leader trả lời đầy đủ.
2. Đợi ~1 phút (học chạy nền).
3. Quản lý agent → *Kỹ thuật toà nhà* → tab **Bộ nhớ**.

**Đạt khi:** có 1–3 ký ức (bài học/sự kiện) ghi nguồn ticket; không chứa tên,
số điện thoại, số căn hộ của khách. Bấm **Gỡ** một ký ức → chuyển sang "Đã gỡ".

### 5.2 Agent dùng ký ức ở ticket sau

Mở ticket mới, hỏi tình huống tương tự ("Nhà tôi bị rò nước ở nhà tắm").
**Đạt khi:** câu trả lời phản ánh bài học (ví dụ nhắc khoá van ngay); cột "Đã
dùng N lần" của ký ức tăng.

### 5.3 Tự cải tiến luật

Sau ticket thành công, xem tab **Phiên bản** của agent:

- Nếu agent có ≥ 3 kịch bản kiểm thử và chúng vẫn đạt ≥ mức của bản đang chạy:
  xuất hiện phiên bản mới, tác giả **"Agent tự cải tiến"**, ghi chú "Tự cải tiến
  sau ticket …"; luật mới hiện ở tab Hướng dẫn với nhãn *Agent tự học*.
- Nếu không đủ điều kiện: luật nằm trong **bản nháp** chờ BQL xem.

**Đạt khi:** đúng một trong hai trường hợp trên; luật do BQL viết hoặc luật đã
**khoá** không bị đổi; tối đa 1 lần tự cải tiến/agent/24 giờ; **Quay về** bản
trước hoạt động. Tắt "Cho agent tự cải tiến" ở tab Tổng quan thì không còn
phiên bản tự cải tiến mới.

### 5.4 Kho kiến thức

Trang **Knowledge** → tạo kho, tải một tài liệu (ví dụ nội quy toà nhà). Ở agent
→ tab **Kiến thức** → gắn kho, ghi "dùng cho" → kiểm thử → phát hành. Hỏi một
câu có trong tài liệu qua Leader.

**Đạt khi:** câu trả lời dùng nội dung tài liệu. Lưu ý: app mẫu dùng vector
store **trong bộ nhớ** (`QdrantStore(":memory:")`) — khởi động lại backend là
mất chỉ mục, phải tải lại tài liệu (đã ghi vào danh sách vấn đề còn lại).

---

## 6. Token và cache

1. Với `WORKFORCE_PROMPT_CACHE_KEY=false`, chạy kịch bản 3.1, ghi `cache_hit_ratio`.
2. Đặt `true`, khởi động lại backend, chạy lại 3.1 trong ticket mới, so sánh.

**Đạt khi:** tỉ lệ cache ≥ lần 1 và không có lỗi gọi model. Nếu gateway lỗi
"unknown parameter prompt_cache_key" → đặt lại `false`.

Tham khảo: phần cố định của mỗi lần gọi đã giảm (đếm bằng tokenizer o200k):
prompt Leader + tool phối hợp **3.616 → ~1.190 token**, worker **2.826 → ~840 token**.

---

## 7. Xử lý sự cố

| Hiện tượng | Kiểm tra |
|---|---|
| Phát hành báo "Hãy chạy kiểm thử…" | Bản nháp đổi sau lần kiểm thử cuối; chạy lại |
| Kiểm thử báo "Không chạy được: … MCP unavailable" | Server MCP demo còn chạy? URL MCP đúng (Docker dùng `host.docker.internal`)? |
| Copilot/kiểm thử lỗi 502 hoặc model không tồn tại | `WORKFORCE_LEADER_MODEL_NAME` có trong credential không |
| Leader trả "Nhóm chưa hoàn tất…" | Xem metrics: nhánh nào `stopped` và `reason`; có thể tăng `WORKFORCE_LEADER_WAIT_SECONDS` |
| Không thấy ký ức sau ticket | Ticket phải có mọi việc `verified`/`accepted` (xem `assignments` trong metrics); `WORKFORCE_LEARNING=true`; agent bật "Ghi nhớ kinh nghiệm" |
| `calls_with_usage = 0` | Gateway không trả usage (stream thiếu `include_usage`) |
