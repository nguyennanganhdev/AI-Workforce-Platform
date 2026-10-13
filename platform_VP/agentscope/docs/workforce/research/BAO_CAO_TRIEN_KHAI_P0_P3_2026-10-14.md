# Báo cáo triển khai P0–P3: xử lý 4 vấn đề của platform Workforce

Ngày 14/10/2026 · Nhánh `feat/wf-p0-p3` (từ `develop2@f495ec00`) · Người đọc: PM và trưởng các lane

Kế hoạch gốc: [BAO_CAO_4_VAN_DE_VA_KE_HOACH_2026-10-13.md](BAO_CAO_4_VAN_DE_VA_KE_HOACH_2026-10-13.md).
Hướng dẫn test: [../HUONG_DAN_TEST_PLATFORM.md](../HUONG_DAN_TEST_PLATFORM.md).

---

## 0. Tóm tắt

| Vấn đề | Đã làm | Kết quả đo được (không cần model) |
|---|---|---|
| 1. Agent phối hợp kém | Giao thức chuyển từ prompt sang runtime: `TeamSay` gọn theo vai, runtime tự điền người nhận/câu hỏi đang chờ/bằng chứng; **sổ giao việc** có `done_when` và `depends_on`, runtime tự khởi động việc phụ thuộc; Leader **phản biện** (accept/challenge/stop); Leader chờ lại sau mỗi lần giao việc mới; prompt trung lập domain; model mạnh cho Leader | Phần cố định mỗi lần gọi: Leader **3.616 → 1.190 token (−67%)**, worker **2.826 → ~840 token (−70%)** (tokenizer o200k) |
| 2. Token, memory, context, cập nhật tri thức | Đo token thật của provider + token được cache theo từng agent; gói context chung dời ra cuối prompt để cache được; `prompt_cache_key` tuỳ chọn; **bộ nhớ dài hạn** có nguồn, tự duyệt, thay thế chứ không xoá; kho kiến thức gắn theo agent; **tự cải tiến luật** sau ticket tốt, chỉ phát hành khi kiểm thử vẫn đạt | Có endpoint số đo cho từng ticket; bảng `agent_memories` (migration 0016) |
| 3. Builder cứng | **Agent Spec** có cấu trúc; Builder copilot biến mỗi câu thành bản vá đúng chỗ + tối đa 3 câu hỏi; tạo agent từ mô tả/mẫu ngành; **kiểm thử bằng model thật trước khi phát hành** (tool đọc chạy thật, tool ghi chỉ mô phỏng); Builder chat cũ được phép hỏi lại thay vì đoán | Phát hành bị chặn nếu < 3 kịch bản hoặc < 80% đạt trên đúng bản nháp |
| 4. Thiếu trang quản lý agent | Trang **Quản lý agent**: danh sách + chi tiết dạng form 9 tab + copilot bên cạnh; phiên bản, so sánh, rollback, ngừng phát hành, prompt tự viết, bộ nhớ | Frontend typecheck, lint, build pass |

**Chưa kiểm bằng model thật** — theo yêu cầu "không tự test". Toàn bộ bằng
chứng dưới đây là test tự động với model giả lập. Hướng dẫn chạy thật: mục 1–6
của file hướng dẫn test.

---

## 1. Nhánh và các commit

`feat/wf-p0-p3`, 11 commit trên `develop2@f495ec00`:

| Commit | Nội dung |
|---|---|
| `4689a927` | P0: sửa CI gate (đòi Alembic head cũ nên mọi job bị bỏ qua); đồng bộ artifact schema Phase A |
| `8768bda9` | P0: ghi token provider + token cache theo agent; endpoint số đo ticket; đồng bộ artifact lifecycle Phase C |
| `d663bee7` | P0: server MCP demo 2 lĩnh vực; script đánh giá phối hợp bằng model thật |
| `a507ad50` | P0: CI chạy thêm test phối hợp/console/eval (trước đây không chạy) |
| `3d5f20fc` | P1: tiền tố prompt ổn định để cache; model theo vai |
| `20182fbb` | P1: sổ giao việc, `TeamSay` gọn, phản biện, prompt trung lập, sửa bộ kiểm bằng chứng |
| `19a0fa15` | P2: Agent Spec, phiên bản, copilot, kiểm thử trước phát hành |
| `cee9f1f6` | P2: giao diện Quản lý agent |
| `c22a36f6` | P3: bộ nhớ dài hạn, kiến thức theo spec, tự cải tiến luật |
| `f95ee966` | Biến môi trường mới; test bộ nhớ trên Redis |
| (cuối) | Tài liệu, compose |

---

## 2. P0 — Đo và gỡ chặn

| Việc | Chi tiết | File |
|---|---|---|
| CI đỏ | Gate đòi head `0012` (và bước restore so với `0012`) nên fail ngay bước đầu sau khi có `0013–0015`. Nay chỉ kiểm "đúng một head" và so restore với head tính được | `.github/workflows/workforce-phase-d.yml`, `scripts/workforce/check_phase_d_environment.py` |
| Test lệch artifact | 2 test so schema artifact với code bị lệch vì các trường Shared Context mới (Phase A và lifecycle Phase C). Sinh lại artifact (chỉ thêm trường) | `docs/workforce/handoffs/*/schemas.json` |
| CI không chạy test phối hợp | Các test phối hợp/Shared Context nằm ở `tests/` gốc, không có trong gate; thay đổi ngoài `app/workforce/` không kích hoạt CI. Đã thêm 2 bước bắt buộc (`console.xml`, `collaboration.xml`) và mở rộng đường dẫn kích hoạt | workflow |
| Đo token thật | Mỗi lần gọi model trong team cộng `usage` của provider (input, **cached input**, output) theo agent vào `SharedContextMetrics.provider_usage` | `_shared_context.py`, `middleware/_shared_context_middleware.py` |
| Endpoint số đo | `GET /workforce/console/tickets/{session_id}/metrics`: tổng + theo agent (tỉ lệ cache), nhánh phối hợp (trao đổi, bị chặn bằng chứng, trạng thái), sổ giao việc, số sự kiện | `_router/_workforce_insights.py` |
| Dữ liệu demo | MCP server hư cấu (nhãn DEMO): du lịch (khách sạn, xe, tính chi phí, đặt phòng) và dịch vụ cư dân (phân loại sự cố, lịch thợ, phí, lịch vệ sinh, lệnh sửa). Tool đọc/ghi được đánh dấu `readOnlyHint` | `scripts/workforce/demo_mcp_server.py` |
| Đánh giá bằng model thật | 7 kịch bản, chấm tất định (số tiền dạng VN, tên bắt buộc/cấm bịa, hỏi lại, không bị dừng giữa chừng) + LLM judge tuỳ chọn; đọc số đo token/cache; xuất `REPORT.md`, so sánh 2 lần chạy | `scripts/workforce/eval/` |

---

## 3. P1 — Vấn đề 1: phối hợp giữa agent

### 3.1 Nguyên nhân đã xử lý

| Nguyên nhân (báo cáo 13/10) | Cách xử lý |
|---|---|
| `TeamSay` 14 tham số, 9 loại tin | Model chỉ thấy: Leader `kind` = handoff / review / ask_customer (+ `to`, `content`, `done_when`, `decision`); worker `kind` = result / error / question / answer / need_customer_info (+ `to` chỉ khi hỏi đồng đội). Tham số cũ vẫn nhận (tương thích phát lại sau crash) |
| Model phải tự điền id | Runtime tự điền: kết quả/lỗi → reply owner; câu trả lời → đúng người đã hỏi + id câu hỏi; key câu hỏi khách → băm nội dung; **accept** → tự gắn id bằng chứng (báo cáo + chuỗi trích dẫn + kết quả tool) |
| Không có tiêu chí xong, không phản biện | `AgentInvite` nhận `done_when`, `depends_on`; Leader `review` → `challenge` (giao lại đúng phần thiếu, tối đa theo `COLLABORATION_MAX_VERIFICATIONS`), `accept`, `stop` |
| Agent phụ thuộc phải đi hỏi đồng đội | **Sổ giao việc** (`SharedTaskState.assignments`): việc có `depends_on` được ghi `queued`, không giao; khi các việc phụ thuộc báo cáo (hoặc lỗi) runtime tự giao, kèm ghi chú phần còn thiếu nếu đồng đội lỗi |
| Leader trả "Nhóm chưa hoàn tất" sau 60 giây | Một ngân sách chờ cho cả lượt (`WORKFORCE_LEADER_WAIT_SECONDS`, mặc định 240s) và **chờ lại sau mỗi lần giao việc mới/phản biện** (trước đây chỉ chờ ở vòng đầu, việc giai đoạn 2 luôn bị coi là chưa xong) |
| Prompt dài, lẫn luật du lịch | Prompt Leader/worker viết lại, trung lập domain; luật du lịch/dịch vụ cư dân chuyển sang `docs/workforce/domain_packs/` và mẫu agent. Bỏ cổng từ khoá "tính chi phí" chỉ đúng cho du lịch |
| Model rẻ cho việc điều phối | `WORKFORCE_LEADER_MODEL_NAME` cho Leader; agent đặt mức "mạnh" trong spec cũng dùng model này |
| Bộ kiểm bằng chứng từ chối nhầm | Con số trong câu làm dính hai cụm chữ thành "tên riêng" giả (`DEMO Song Han 1200000 VND` → tên "demo song han vnd"). Nay con số cắt tên |

### 3.2 Cách hoạt động (ví dụ du lịch)

```text
Khách: "Đà Nẵng 2 người, 2 đêm, xe sân bay, ngân sách 5tr giữ 1tr"
Leader → AgentInvite: Tìm khách sạn/xe (done_when: ≥2 lựa chọn có giá)
                      Tính chi phí (depends_on: Tìm khách sạn/xe; done_when: tổng + trần + dư/thiếu)
Runtime: giao ngay việc tìm; việc tính chi phí ở trạng thái queued
Tìm khách sạn/xe → TeamSay(kind="result") → runtime ghi reported, tự giao việc tính chi phí
Tính chi phí → TeamSay(kind="result") → runtime xác minh bằng kết quả tool → verified
Leader (model mạnh) đọc sổ giao việc + kết quả → accept hoặc challenge → trả lời khách
```

### 3.3 Thay đổi team cần biết

- Worker không cần (và không nên) truyền `to` khi báo kết quả. Test cũ "worker
  gửi không có `to` là broadcast bị từ chối" đổi thành "kết quả không có `to`
  được định tuyến về reply owner".
- Chữ trong system prompt đổi: `BOUNDED COLLABORATION` → `COLLABORATION LIMITS`.
- Gói Shared Context không còn nằm trong system message mà là message cuối
  (`name="shared_context"`). Test kiểm vị trí gói đã cập nhật.

---

## 4. P2 — Vấn đề 3 và 4: Agent Spec, Builder copilot, trang quản lý

### 4.1 Agent Spec (`app/_agent_spec.py`)

Một tài liệu có cấu trúc cho mỗi agent: tên, mô tả (Leader đọc để mời), đối
tượng, ngôn ngữ, giọng điệu, mục tiêu, trong/ngoài phạm vi, **luật** (bắt buộc/nên,
nguồn: BQL/Builder/agent/mẫu, **khoá**), chuyển người, tool (dùng khi nào, cần
xác nhận, chỉ đọc), kho kiến thức, đồng đội, ví dụ, **kịch bản kiểm thử**, mức
model, bật/tắt bộ nhớ và tự cải tiến, **prompt tự viết** (thay phần sinh từ form).
Prompt chạy thật được dựng từ spec; bài học agent tự học đứng ở mục riêng cuối
prompt. Agent cũ được bọc spec tự động khi mở lần đầu, **prompt chạy thật giữ
nguyên từng ký tự**.

### 4.2 Agent Studio API (`/workforce/console/studio`)

| Endpoint | Việc |
|---|---|
| `GET /agents`, `GET /agents/{id}` | Danh sách; chi tiết (spec đang chạy, bản nháp, khác biệt, prompt chạy thật, phiên bản, kiểm thử gần nhất, lý do chưa phát hành được) |
| `POST /agents` | Tạo từ mẫu ngành / nhân bản / trống |
| `POST /agents/compose` | Tạo bản nháp từ mô tả bằng lời (copilot) |
| `PUT/DELETE /agents/{id}/draft` | Lưu / huỷ bản nháp (form) |
| `POST /agents/{id}/copilot` | Một câu → bản vá tối thiểu + ≤3 câu hỏi; tool lạ bị từ chối |
| `POST /agents/{id}/tests/run` | Chạy kịch bản với model thật; gắn kết quả vào **hash** của bản nháp |
| `POST /agents/{id}/publish` | Cần ≥3 kịch bản và ≥80% đạt trên đúng bản nháp; tạo phiên bản bất biến; áp tool/kiến thức vào phiên chính |
| `POST /agents/{id}/rollback` | Phát hành lại nội dung phiên bản cũ thành phiên bản mới |
| `POST /agents/{id}/withdraw` | Ngừng phát hành |
| `GET /templates`, `GET /tools`, `POST /preview` | Mẫu ngành, kho tool, xem trước prompt |
| `GET /agents/{id}/memories`, `POST …/retire` | Bộ nhớ của agent |

Kiểm thử trước phát hành (`_service/_agent_eval.py`): mỗi kịch bản là một tin
nhắn khách; tool có `readOnlyHint` được gọi thật, mọi tool khác trả "SIMULATED,
NOT executed"; chấm bằng điều kiện bắt buộc/cấm + model chấm. Server MCP nay lưu
cờ `read_only` khi khám phá tool.

### 4.3 Giao diện (`/workforce/agents`)

- Danh sách: trạng thái, phiên bản, kết quả kiểm thử, số tool, số luật (+ luật tự học).
- Tạo: **Mô tả bằng lời** (có thể dựa trên mẫu), **Từ mẫu ngành** (du lịch: tìm
  kiếm, tính chi phí; dịch vụ cư dân: kỹ thuật, vệ sinh), **Nhân bản**, trống.
- Chi tiết: 9 tab (Tổng quan, Hướng dẫn, Công cụ, Kiến thức, Phối hợp, Kiểm
  thử, Prompt, Phiên bản, Bộ nhớ) + **copilot** bên phải sửa cùng bản nháp;
  thanh hành động Lưu nháp / Chạy kiểm thử / Phát hành (+ ghi chú) / Huỷ thay
  đổi / Ngừng phát hành.

### 4.4 Builder chat cũ

Bước phác thảo được phép trả **một câu hỏi** thay vì bắt buộc đề xuất agent; bỏ
ví dụ khách sạn/xe khỏi prompt Builder. Khuyến nghị dùng "Mô tả bằng lời" ở
trang Quản lý agent thay cho trang chat cũ.

---

## 5. P3 — Vấn đề 2: bộ nhớ, kiến thức, tự cải tiến

| Thành phần | Chi tiết |
|---|---|
| Lưu trữ | `AgentMemoryRecord` trong storage bền của Shared Context: bảng `agent_memories` (migration `0016`), Redis hash cho triển khai chỉ dùng Redis |
| Truy hồi | So khớp từ khoá bỏ dấu kiểu BM25 trong ngân sách ký tự; gắn vào system prompt của agent dưới nhãn "kinh nghiệm, ưu tiên thấp hơn kết quả tool". Không cần endpoint embedding |
| Ghi nhớ | Sau khi Leader trả lời **có bằng chứng** và mọi việc trong sổ là `verified`/`accepted`, chạy nền: model rút ≤3 điều cho mỗi agent, **mỗi điều phải trích id sự kiện có thật** (không có → bỏ); hợp nhất add/update(thay thế)/no-op; agent tự duyệt (theo quyết định của anh) |
| Tự cải tiến | ≤1 luật mới/ticket, nhãn *Agent tự học*. Tự phát hành phiên bản mới (tác giả "agent") **chỉ khi** agent có ≥3 kịch bản và tỉ lệ đạt không thấp hơn bản đang chạy; không thì để nháp. Không đụng luật của BQL hay luật khoá, không đè bản nháp BQL đang sửa, tối đa 1 lần/agent/24h, rollback được |
| Kiến thức | Kho kiến thức khai trong spec được dùng cả trong phiên team (trước đây phiên được mời không mang cấu hình kiến thức) |
| Tắt/bật | `WORKFORCE_LEARNING`, và từng agent: "Ghi nhớ kinh nghiệm", "Cho agent tự cải tiến" |

---

## 6. Kiểm thử tự động đã chạy

Môi trường: Python 3.11 venv riêng của worktree, cài theo CI (`.[dev,service,storage-postgres,auth]`); Node 24 + pnpm theo lockfile.

| Bộ | Kết quả |
|---|---|
| `tests/workforce/foundation` | 35 pass |
| `tests/workforce/registry` | 31 pass, 1 skip (PostgreSQL) |
| `tests/workforce/builder` | 91 pass, 12 skip (browser) |
| `tests/workforce/lifecycle` | 75 pass, 4 skip (trước đây 1 fail: artifact lệch, đã sửa) |
| `tests/workforce/orchestration` | 269 pass |
| `tests/workforce/execution` | 116 pass, 1 skip |
| `tests/workforce/integrations` | 16 pass |
| `tests/workforce/e2e` | 25 pass, 4 skip |
| `tests/workforce/console` + `eval` | 30 + 5 pass |
| Phối hợp, Shared Context, team tools, bộ nhớ, storage SQL (`tests/*.py` liên quan) | 239 pass |
| Migration SQLite từ đầu tới `0016_agent_memories` | thành công |
| Frontend: `tsc -b`, `eslint` (file mới/sửa), `vite build` | pass (cảnh báo chunk > 500 kB có sẵn) |

Skip là test cần PostgreSQL DSN hoặc trình duyệt; CI cung cấp cả hai.

Test mới viết: sổ giao việc + phụ thuộc + phản biện + tự điền người nhận
(`workforce_task_ledger_test.py`), đo token/cache (`workforce_provider_usage_test.py`,
`console/test_ticket_metrics.py`), chọn model theo vai, Agent Spec
(`console/test_agent_spec.py`), luồng Studio tạo → kiểm thử → phát hành → copilot
→ v2 → rollback (`console/test_agent_studio_api.py`), bộ nhớ SQL/Redis + vòng học
(`workforce_agent_memory_test.py`), công cụ đánh giá (`eval/test_collab_eval_tools.py`).

---

## 7. Giới hạn của bản này

1. **Chưa chạy với model/MCP thật** (theo yêu cầu). Chất lượng thực tế của
   copilot, người chấm, trích bài học phụ thuộc model — đo bằng mục 2–5 của
   hướng dẫn test và script đánh giá.
2. Cờ "cần khách xác nhận" trong spec là chỉ dẫn cho model; việc **bắt buộc**
   xác nhận ở runtime vẫn do heuristic của MCP (`destructiveHint`, tên tool chứa
   book/order/pay…). Tool ghi có tên vô hại và không khai `destructiveHint` có thể
   chạy không hỏi.
3. Truy hồi bộ nhớ theo từ khoá; câu hỏi diễn đạt rất khác có thể không khớp.
4. Phiên bản trong Studio là của agent trên console; module `lifecycle/releases`
   của API đối tác (`/workforce/v1`) vẫn tách riêng.
5. Ticket đang chạy dùng cấu hình agent tại thời điểm mỗi lượt (không ghim phiên bản theo ticket như luồng đối tác).

---

## 8. Vấn đề còn lại của dự án (đề xuất đưa vào kế hoạch)

| # | Vấn đề | Mức | Đề xuất |
|---|---|---|---|
| 1 | API đối tác `/workforce/v1` chưa có bản cài đặt `LeaderTurnRunner` → luồng đối tác chưa chạy Leader thật | Cao | Viết runner dùng chính `ChatService` + middleware hiện tại; E2E với model thật |
| 2 | Vector store của kho kiến thức trong app mẫu là `QdrantStore(":memory:")` → khởi động lại mất chỉ mục | Cao | Dùng Qdrant chạy riêng hoặc pgvector có sẵn trong compose |
| 3 | Hai đường quản lý agent song song: console/Studio (agent của người dùng) và `workforce/builder` + `lifecycle` (manifest đối tác) | Cao | Chốt một nguồn: cho Studio phát hành ra `releases`, hoặc ngược lại |
| 4 | Xác nhận tool ghi dựa vào từ khoá tên tool | Trung bình | Cổng quyền đọc `requires_consent` của spec và `readOnlyHint=False` |
| 5 | Leader chờ kết quả bằng vòng hỏi 0,5s trong lượt chạy (tối đa 240s) | Trung bình | Chuyển sang đánh thức theo sự kiện khi có báo cáo |
| 6 | Bộ kiểm bằng chứng dựa regex: số tính ra (giá × đêm) không có trong kết quả tool sẽ bị chặn | Trung bình | Dùng tool tính toán; mở rộng nhận diện phép nhân đơn giản |
| 7 | Tóm tắt Shared Context dùng cùng model với agent gọi (Leader dùng model mạnh thì tóm tắt cũng đắt); `ModelRouterMiddleware` có sẵn chưa dùng | Thấp | Cho tóm tắt dùng model rẻ |
| 8 | Endpoint bật/tắt phát hành cũ (`/workforce/console/agents/{id}/lifecycle`) bỏ qua phiên bản | Thấp | Ẩn khỏi UI cũ hoặc chuyển qua Studio |
| 9 | Agent tạo bằng Builder chat cũ không có kịch bản kiểm thử → luật tự học chỉ nằm ở bản nháp | Thấp | Copilot "viết 3 kịch bản" cho các agent cũ |
| 10 | Bundle frontend > 500 kB | Thấp | Tách trang theo `import()` |
| 11 | Sandbox đối tác vẫn `NOT_VERIFIED` (từ Phase D) | Theo kế hoạch D7 | Cần endpoint/credential sandbox |
