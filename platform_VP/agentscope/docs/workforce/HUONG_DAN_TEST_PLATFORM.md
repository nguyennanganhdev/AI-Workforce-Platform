# Hướng dẫn test platform sau P0–P3 và 11 vấn đề còn lại

Cập nhật 14/10/2026 · Nhánh `feat/wf-remaining` (xếp chồng trên `feat/wf-p0-p3`, PR vào `develop2`) · Người đọc: PM/tester

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
git checkout feat/wf-remaining     # hoặc develop2 sau khi hai PR được merge
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
| `KNOWLEDGE_VECTOR_URL` | để trống | URL Qdrant server nếu có (kèm `KNOWLEDGE_VECTOR_API_KEY`). Trống = Qdrant lưu trên đĩa trong volume `workspaces` |
| `KNOWLEDGE_VECTOR_PATH` | để trống | Thư mục lưu chỉ mục khi không dùng server; `:memory:` = kiểu cũ, mất khi khởi động lại |
| `WORKFORCE_PARTNER_API` | `false` | `true` để mở API đối tác `/workforce/v1` chạy bằng Leader console (mục 7.1). Cần `AUTH_ENABLED=true` và `AGENTSCOPE_SQL_URL` |

### 1.3 Chạy platform

**Cách A — Docker (khuyến nghị):**

```bash
docker compose --profile demo up -d --build           # app + web + MCP demo + Postgres/Redis/MinIO
python scripts/workforce/bootstrap_demo.py --env-file .env
```

- Project Docker: `awp-develop2` (đặt trong `.env`), không đụng các stack khác.
- Web: `http://localhost:5173` · API: `http://localhost:8000`.
- Container `app` tự chạy `alembic upgrade head`.
- `bootstrap_demo.py` **không gọi model**. Script tạo sẵn tài khoản quản lý
  khu vực, credential OpenAI (lấy key trong `.env`), MCP demo
  (`http://demo-mcp:8765/mcp`), key đối tác và tuyến `tower-a`. Mật khẩu và
  key nằm trong `.artifacts/demo-access/ACCESS.md` (không commit). Chạy lại
  script thì bước nào đã có sẽ được bỏ qua.
- Đổi cổng API thì sửa `WEB_API_BASE_URL` và build lại `web`.
- Dừng: `docker compose --profile demo down` (thêm `-v` nếu muốn xoá dữ liệu).

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

**Đã gắn (14/10):** key OpenAI lấy từ
`vinhome_Recident/agents/reception/.env` (endpoint OpenAI chính thức), ghi vào
`platform_VP/agentscope/.env` (file gitignored). Key liệt kê được 133 model
(chỉ gọi `/models`, không tốn token). Phân loại model:

| Vai | Model | Lý do |
|---|---|---|
| Model nền: agent chuyên môn, tóm tắt context, ReMe | `gpt-5.4-mini` | Rẻ, gọi tool tốt |
| Model cao: Leader lập kế hoạch/phản biện, copilot Studio, người chấm kiểm thử, agent đặt mức "mạnh", người chấm eval | `gpt-5.5` | Model mạnh nhất có model card trong fork |
| Không dùng | `gpt-5.6-luna/sol/terra` | Chưa rõ thứ hạng; Luna từ chối gọi tool qua Chat Completions nếu không tắt reasoning (đã gặp ở Reception) |
| Không dùng | `gpt-5.5-pro`, `gpt-5.4-pro` | Rất đắt, không cần cho demo |

Với Docker, `bootstrap_demo.py` tự thêm credential OpenAI cho tài khoản quản
lý. Nếu tự tạo tài khoản khác thì vào trang **Credential**, thêm credential
OpenAI với cùng key.

Muốn tự kiểm tra key (không in key ra màn hình):

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY"
```

**Đạt khi:** in `200`.

### 1.5 Server MCP demo (dữ liệu giả, có nhãn DEMO)

Mở terminal riêng, để chạy suốt buổi test:

```bash
cd platform_VP/agentscope
python scripts/workforce/demo_mcp_server.py --host 0.0.0.0 --port 8765
```

Trang **MCP** → thêm MCP qua URL:

- Docker với `--profile demo`: đã có service `demo-mcp`, `bootstrap_demo.py`
  tự thêm `http://demo-mcp:8765/mcp` (không cần mở terminal riêng)
- Docker, chạy MCP trên máy: `http://host.docker.internal:8765/mcp`
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

**Đạt khi:** câu trả lời dùng nội dung tài liệu.

**Chỉ mục còn sau khi khởi động lại (vấn đề 2):** `docker compose restart app`
(hoặc tắt/bật backend chạy tay), hỏi lại câu trên. **Đạt khi:** vẫn trả lời
đúng mà không phải tải lại tài liệu.

---

## 6. Token và cache

1. Với `WORKFORCE_PROMPT_CACHE_KEY=false`, chạy kịch bản 3.1, ghi `cache_hit_ratio`.
2. Đặt `true`, khởi động lại backend, chạy lại 3.1 trong ticket mới, so sánh.

**Đạt khi:** tỉ lệ cache ≥ lần 1 và không có lỗi gọi model. Nếu gateway lỗi
"unknown parameter prompt_cache_key" → đặt lại `false`.

Tham khảo: phần cố định của mỗi lần gọi đã giảm (đếm bằng tokenizer o200k):
prompt Leader + tool phối hợp **3.616 → ~1.190 token**, worker **2.826 → ~840 token**.

---

## 7. Mười một vấn đề còn lại (vòng 3)

Số trong ngoặc là số thứ tự trong danh sách vấn đề còn lại của báo cáo P0–P3.

### 7.1 API đối tác chạy bằng Leader console (vấn đề 1 và 3)

Ticket của đối tác giờ do **chính Leader console** của quản lý khu vực trả lời,
với các agent đã phát hành trong Quản lý agent. Đặt `WORKFORCE_PARTNER_API=true`,
khởi động lại backend. `SECRET` = `PARTNER_API_PROVISIONING_SECRET` trong `.env`,
`BASE` = `http://127.0.0.1:8000`.

1. **Quản lý khu vực:** đăng ký tài khoản quản lý (chọn domain/khu). Việc đăng
   ký tạo membership *chờ xác minh*. Ghi lại `user_id` (devtools → `/auth/me`)
   và `domain_id` (`GET /directory/domains`).
2. **Admin xác minh quản lý:**
   ```bash
   curl -X POST $BASE/workforce/v1/admin/memberships/verify \
     -H "X-Provisioning-Secret: $SECRET" -H "Content-Type: application/json" \
     -d '{"manager_account_id":"<user_id>"}'
   ```
   **Đạt khi:** trả `"status":"verified"`; secret sai → 403.
3. **Admin cấp key đối tác:**
   ```bash
   curl -X POST $BASE/integrations/api-keys \
     -H "X-Provisioning-Secret: $SECRET" -H "Content-Type: application/json" \
     -d '{"domain_id":"<domain_id>","name":"Đối tác thử"}'
   ```
   Ghi `client_id` và `api_key` (`KEY`, chỉ hiện một lần).
4. **Quản lý cấp tuyến:** đăng nhập tài khoản quản lý → Quản lý agent →
   **Kết nối đối tác** → nhập `client_id` và mã toà (vd `tower-a`) → Cấp.
   **Đạt khi:** tuyến hiện *chờ đối tác xác nhận*, có mã tuyến và `v1`.
5. **Đối tác xác nhận:**
   ```bash
   curl -X POST $BASE/workforce/v1/partner/routes/<route_id>/confirm \
     -H "X-API-Key: $KEY" -H "Content-Type: application/json" -d '{"expected_revision":1}'
   ```
   **Đạt khi:** trả `"status":"active"`; trong dialog tuyến chuyển *đang hoạt động*.
6. **Đối tác gửi ticket:** dùng script ở 7.8 (trỏ `--base-url` về máy local),
   hoặc gửi tay `POST /workforce/v1/partner/requests` với header `X-API-Key`
   (hoặc `Authorization: ApiKey <key>`); người dùng cuối là `external_user_id`
   trong body (POST) hoặc query (GET), đúng như hợp đồng đối tác.

**Đạt khi:** request về `completed`; câu trả lời đến từ Leader của quản lý
(cùng luật/giọng như trên console); nếu Leader hỏi lại thì `workflow_state` =
`awaiting_user`, gửi `workflow_reply` thì tiếp tục **cùng một** session; tới
`awaiting_confirmation` thì `close` được. Đọc kết quả với `external_user_id`
khác người gửi → 403/404.

Giới hạn: chưa có API duyệt của đối tác, sự kiện provider job và theo dõi thao
tác ngoài (`waiting_external_event`); tool có tác động đi qua xác nhận trong chat.

### 7.2 Ticket giữ phiên bản agent khi được mời (vấn đề 3)

1. Agent *Kỹ thuật toà nhà* đang **v1**. Mở ticket 3.5, đợi Leader mời agent.
2. Trong lúc ticket còn mở: thêm luật "Luôn kết thúc bằng câu: Chúc anh/chị một
   ngày tốt lành." → kiểm thử → phát hành **v2**.
3. Nhắn tiếp trong ticket cũ; rồi mở ticket mới hỏi lại.

**Đạt khi:** ticket cũ vẫn trả lời theo v1 (không có câu mới); ticket mới theo v2.

### 7.3 Xác nhận tool theo spec (vấn đề 4)

Agent *Kỹ thuật toà nhà* → tab Công cụ → bật **"Cần khách xác nhận trước khi
chạy"** cho `get_service_fee` (tool chỉ đọc) → kiểm thử → phát hành. Hỏi phí sửa
ống nước qua Leader.

**Đạt khi:** chat hỏi xác nhận trước khi gọi `get_service_fee`; tắt lại thì
không hỏi. `book_hotel`/`create_work_order` (MCP khai báo `readOnlyHint=false`)
luôn hỏi xác nhận.

### 7.4 Leader đợi theo tín hiệu (vấn đề 5)

Chạy 3.1 và 3.6. **Đạt khi:** Leader trả lời ngay sau khi agent cuối cùng báo
cáo xong, kết quả như mục 3 (không có "Nhóm chưa hoàn tất…").

### 7.5 Số tính ra không bị chặn (vấn đề 6)

Chạy 3.4 (4 người, 2 phòng × 2 đêm). **Đạt khi:** câu trả lời có 3.000.000 và
3.380.000; metrics của agent tính chi phí có `evidence_rejections` = 0.

### 7.6 Tóm tắt Shared Context dùng model rẻ (vấn đề 7)

Đặt `WORKFORCE_LEADER_MODEL_NAME` khác `WORKFORCE_MODEL_NAME`. Chạy một ticket
dài (3.1, rồi 3.4, rồi hỏi thêm 3–4 câu). **Đạt khi:** không lỗi; nếu gateway có
log theo model, các lượt tóm tắt context gọi model mặc định (mini), không gọi
model mạnh.

### 7.7 Các vấn đề nhỏ (8, 9, 10)

- **(8)** Agent chưa có phiên bản: bật phát hành ở trang agent cũ → lỗi 409
  "Agent chưa có phiên bản đã kiểm thử. Hãy phát hành ở trang Quản lý agent."
  Agent đã có phiên bản thì tắt/bật lại được.
- **(9)** Builder chat cũ tạo agent mới → agent có sẵn **3 kịch bản kiểm thử**.
  Agent cũ thiếu kịch bản: tab Kiểm thử có nút **Nhờ copilot viết kịch bản**.
- **(10)** devtools → Network: mỗi trang chỉ tải file JS của nó khi bấm vào;
  lần mở đầu nhẹ hơn.

### 7.8 Sandbox đối tác (vấn đề 11)

Chưa có sandbox thật nên chưa thể đánh dấu đạt. Đã chuẩn bị script và
checklist: `docs/workforce/SANDBOX_DOI_TAC_CHECKLIST.md`. Có thể chạy thử với
platform local sau khi làm 7.1:

```bash
python scripts/workforce/partner_sandbox_check.py --base-url http://127.0.0.1:8000 \
  --api-key "$KEY" --management-ref tower-a --external-user-id resident-sandbox-1
```

**Đạt khi:** `.artifacts/partner-sandbox/<thời gian>/EVIDENCE.md` có các bước ✅;
dòng cuối ghi "pending human review". Kết quả local **không** dùng làm bằng
chứng sandbox.

---

## 8. Xử lý sự cố

| Hiện tượng | Kiểm tra |
|---|---|
| Phát hành báo "Hãy chạy kiểm thử…" | Bản nháp đổi sau lần kiểm thử cuối; chạy lại |
| Kiểm thử báo "Không chạy được: … MCP unavailable" | Server MCP demo còn chạy? URL MCP đúng (Docker dùng `host.docker.internal`)? |
| Copilot/kiểm thử lỗi 502 hoặc model không tồn tại | `WORKFORCE_LEADER_MODEL_NAME` có trong credential không |
| Leader trả "Nhóm chưa hoàn tất…" | Xem metrics: nhánh nào `stopped` và `reason`; có thể tăng `WORKFORCE_LEADER_WAIT_SECONDS` |
| Không thấy ký ức sau ticket | Ticket phải có mọi việc `verified`/`accepted` (xem `assignments` trong metrics); `WORKFORCE_LEARNING=true`; agent bật "Ghi nhớ kinh nghiệm" |
| `calls_with_usage = 0` | Gateway không trả usage (stream thiếu `include_usage`) |
| Backend không khởi động, báo `WORKFORCE_PARTNER_API=true requires…` | Cần `AUTH_ENABLED=true` và `AGENTSCOPE_SQL_URL` |
| Ticket đối tác bị 403/404 | Membership đã `verified`? Tuyến đã `active`? `external_management_ref` trùng mã toà của tuyến? |
| Request đối tác đứng ở `accepted`/`running` | Xem log backend: key model sai, hoặc quản lý chưa có agent nào đã phát hành |
