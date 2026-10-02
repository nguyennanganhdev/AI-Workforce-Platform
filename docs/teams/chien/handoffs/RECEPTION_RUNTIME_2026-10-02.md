# Ghép Reception vào chat cư dân — bàn giao 02/10/2026

Gửi: Team Hoàng (chủ `agent-reception/`), Team Đông, Team Quang, Team 5.
Trạng thái: chạy được đầu-cuối trên PostgreSQL thật, với model stub trong test tự động và với LLM thật
(`gpt-5.4-mini`) khi chạy tay ngày 03/10/2026. Chưa có bộ eval tiếng Việt tự động cho LLM thật.

## Vì sao có thay đổi trong `agent-reception/`

Graph (`src/graph`) và bộ tool có kiểu (`src/tools`) chưa có phần ghép thành service, và hợp đồng của graph
khác backend ở ba điểm: xác thực (service bearer so với cookie cư dân), vỏ kết quả (`kind/value` so với kết quả
phẳng), và mô hình ticket (graph tạo ticket ngay ở bước draft; backend chỉ tạo ticket lúc handoff).
Theo quyết định của Chiến: **hợp đồng backend là chuẩn, lớp chuyển đổi nằm ở phía Reception.**

Phần thêm mới nằm trọn trong `agent-reception/src/runtime/` và `agent-reception/tests/runtime/`; không sửa
`src/graph`, `src/tools`, `src/prompts`. Bộ test sẵn có của team vẫn 332 đạt / 5 lỗi như trước.

## Luồng

```text
Cư dân nhắn (resident-app) → POST /resident/chats/{id}/messages (backend, commit)
  → backend mở một run cho tin nhắn đó và ký token ủy quyền (10 phút)
  → backend gọi POST {RECEPTION_URL}/v1/turns  (Bearer service token, body kèm delegation)
  → runtime chạy một lượt graph theo thread = channel, mọi lời gọi dưới đây dùng Bearer <token ủy quyền>
      policy:    POST /internal/reception/policy/evaluate        (backend quyết định)
      operation: POST /internal/reception/v1/execute
      tri thức:  POST {KNOWLEDGE_URL}/internal/knowledge/search   (khi được cấu hình)
  → runtime ghi câu trả lời: POST /internal/reception/chats/{id}/replies
  → backend đóng run (token hết hiệu lực ngay)
  → resident-app đọc hội thoại từ backend như cũ
```

Runtime không chạy được thì backend tự ghi một câu trả lời hướng cư dân dùng biểu mẫu.

## Ánh xạ operation (`runtime/backend.py`)

| Graph gọi | Backend thực hiện | Ghi chú |
|---|---|---|
| `create_ticket_draft` | `create_ticket_draft` (draft rỗng) | Graph nhận `ticket_id` = id draft, mã `DRAFT-…`, version `0` |
| `get_verified_resident_context` | `get_verified_resident_context` + `update_ticket_incident` (căn hộ) | Nhiều căn hộ thì hỏi lại; thiếu tên/số điện thoại xác minh thì báo cư dân |
| `update_ticket_incident` | `update_ticket_incident` | Model đề xuất danh mục dịch vụ từ catalog backend; đề xuất sai thì chuyển người xem xét |
| `submit_ticket_assessment` | `submit_ticket_assessment` | Mức ưu tiên là đề xuất của model; khẩn cấp do policy backend quyết định |
| `resolve_management_destination` | cùng tên | Có BQL phụ trách là đủ; chưa có Supervisor vẫn đi tiếp |
| `handoff_ticket` | `handoff_ticket` với `plan_required=false` | Backend tạo ticket; có Supervisor thì tạo team + message V2 |
| `register_supervisor_wait` | cùng tên khi có team | |
| `get_ticket_status` | cùng tên | `closed`/`cancelled` mới là hoàn tất |
| `append_ticket_information`, `request_ticket_cancellation` | message V2 khi ticket có team | Không có team: thông tin nằm trong chat; hủy chuyển người xem xét |
| `escalate_emergency` | cùng tên khi đã có ticket | Chưa có ticket: đánh dấu để ticket tạo ra ở mức critical |
| `process_self_help` | không gọi (backend trả 501) | Trả `unavailable`, graph mời hỗ trợ trực tiếp |
| `respond_supervisor_interaction`, `get_supervisor_event` | chưa hỗ trợ | Chờ Supervisor runtime |

## Thay đổi phía backend (`services/vinhomes-api`)

- `reception_delegation.py`: `start_run` mở run cho một tin nhắn, `finish_run` đóng run, `DelegatedScope` xác
  thực token và đọc lại quyền từ database ở mỗi lời gọi (xem mục Ủy quyền).
- `reception_runtime_api.py`: `/internal/reception/v1/execute`, `/v1/reconcile`, `/v1/knowledge-authorization`.
  Bọc các operation sẵn có; từ chối context, channel hay ticket nằm ngoài cuộc trò chuyện của run.
- `v3_reception_runtime.py`: catalog danh mục, policy, ghi câu trả lời, gọi runtime sau khi commit.
- `server/drizzle/0011_reception_runtime_backend.sql`: đăng ký runtime `reception-langgraph`.
  `scripts/grant_v3_api_role.sql`: quyền ghi `runtime_identities`, `runtime_session_bindings`, `agent_runs`.
- `v3_reception_operations.py`: `handoff_ticket` nhận `plan_required` (mặc định `true`); BQL chưa có
  Supervisor thì vẫn tạo ticket, `team` và `handoff` là `null`.
- `v3_reception.py`: context cư dân thêm `building_code`, `domain_name`.

## Ủy quyền

Service token (`VINHOMES_API_RECEPTION_SERVICE_TOKEN` = `RECEPTION_SERVICE_TOKEN`) chỉ chứng minh lời gọi
`/v1/turns` đến từ backend. Nó **không** thao tác thay cư dân được: các route `/internal/reception/*` chỉ nhận
token ủy quyền.

Với mỗi tin nhắn cư dân, backend (trong transaction mang danh cư dân đó):

1. Lấy hoặc tạo `execution_principals` (kind `user`) và `runtime_identities` của cư dân trên runtime
   `reception-langgraph`.
2. Lấy hoặc tạo một `runtime_session_bindings` kiểu `personal` cho cặp (cuộc trò chuyện, agent Lễ tân). Một cuộc
   trò chuyện giữ một binding qua mọi lượt; graph dùng id này làm `bindingId`.
3. Tạo một `agent_runs` trạng thái `running`, khóa idempotency `reception-turn:<message id>`.
4. Ký token HMAC bằng `RECEPTION_DELEGATION_KEY` (chỉ backend giữ), hạn 10 phút, chứa run, binding, principal,
   phiên bản quyền. Ghi audit `reception.delegation_issued`.

Mỗi lời gọi của runtime, backend kiểm chữ ký và hạn, rồi đọc lại từ database: run còn `running`, binding và
identity còn `active`, cư dân còn hoạt động, còn là thành viên tenant và còn sở hữu cuộc trò chuyện, agent Lễ tân
còn `active`, runtime còn `enabled`. Sai một điều kiện là 403. Kết thúc lượt, backend chuyển run sang
`succeeded`/`failed`, nên token chết cùng lượt chat.

Runtime giữ token trong bộ nhớ theo cuộc trò chuyện đang xử lý, không ghi vào checkpoint hay log.

Tắt toàn bộ Reception ngay lập tức: `update runtime_backends set enabled=false where code='reception-langgraph'`.

## Giới hạn cần biết

1. Policy khẩn cấp là danh sách từ khóa có dấu. Tin nhắn không dấu sẽ không tự kích hoạt khẩn cấp; graph hỏi lại.
2. Báo khẩn cấp trước khi có ticket chỉ là cờ nội bộ; BQL nhận thông báo khi ticket được tạo.
3. Trạng thái hội thoại lưu SQLite cục bộ: một replica. Nhiều replica cần checkpointer PostgreSQL.
4. Tìm tri thức: runtime gửi token ủy quyền tới `search_knowledge` v1; server hỏi lại backend ở
   `/internal/reception/v1/knowledge-authorization`. Đường này mới kiểm với stub đúng schema: chưa có dữ liệu
   tri thức, chưa có `agent_knowledge_grants` cho agent Lễ tân, chưa có key embedding. Server mount route khi
   `KNOWLEDGE_ENABLED=1` (`server/src/knowledge/runtime.ts`).
5. Ticket do Reception tạo đi luồng trực tiếp (BQL tạo phiếu, không có bước duyệt kế hoạch).
6. Backend chết giữa lượt thì run nằm lại ở `running`; token vẫn hết hạn sau 10 phút. Chưa có job dọn run treo.
7. Phiên bản agent Lễ tân (`agent_versions`) được tạo tự động ở lần đầu, nội dung chỉ là bản ghi định danh;
   khi Agent Factory quản lý phiên bản thật thì binding mới sẽ dùng phiên bản mới nhất.

## Chạy với LLM thật (03/10/2026)

Chạy tay qua API cư dân trên database demo, model `gpt-5.4-mini`, mỗi lượt 3–6 giây. Các kịch bản đã đúng:
báo sự cố → ticket + session; hỏi tiến độ; bổ sung thông tin; yêu cầu hủy; hỏi thông tin (chưa có nguồn);
báo cháy → ticket critical; chào hỏi rồi báo sự cố; tin nhắn không dấu; hỏi thông tin rồi báo sự cố.

Để đến được đó phải sửa bốn chỗ mà model stub không lộ ra. Ba chỗ nằm trong `src/graph` và `src/prompts`
của Team Hoàng, cần các bạn rà lại:

1. `workflow.py` `_collect_incident_details`: lượt báo sự cố đầu tiên được model gắn nhãn `new_incident` và
   graph từ chối như thể đã có sự cố khác. Nay chỉ từ chối khi đã có sự cố được ghi.
2. `workflow_validation.py` `parse_turn`: model nhắc lại dữ kiện của lượt trước và cả lượt bị
   `MODEL_CANNOT_VERIFY_FACTS`. Nay bỏ qua dữ kiện trích từ tin nhắn cũ có thật trong hội thoại; nguồn không
   tồn tại và `staff_verified` vẫn bị chặn (test `test_injection_cannot_supply_authority` giữ nguyên).
3. `workflow.py` sau `get_ticket_status`/`request_ticket_cancellation`: câu hỏi tiến độ nằm lại trong
   `pending_incident_messages` làm lượt kế tiếp bị đọc thành hỏi tiến độ. Nay xóa danh sách đó.
   `prompts/workflow.py`: thêm ba dòng nói rõ `intent` chỉ xét tin nhắn hiện tại.
4. `runtime/backend.py`: model hay bỏ `title`; lớp chuyển đổi lấy câu đầu của mô tả làm tiêu đề.

Lời trả lời: trong graph, model chỉ phân loại và trích xuất (JSON); mọi câu cư dân đọc là câu cố định trong
code. `runtime/voice.py` thêm một lượt model viết lại câu đó cho tự nhiên theo tin nhắn của cư dân, không được
thêm dữ kiện hay cam kết; lỗi hoặc mất câu hỏi thì dùng lại câu gốc. Câu trả lời có trích dẫn và lượt khẩn
cấp không qua bước này.

Còn tồn tại:

- `gpt-4o-mini` vẫn đọc sai lượt bổ sung thông tin thành sự cố mới; không dùng model này.
- Mô tả mơ hồ ("nhà tôi có vấn đề về nước") vẫn tạo ticket ngay, không hỏi lại chi tiết.
- Thông tin cư dân tự bổ sung khi Supervisor không hỏi bị backend V2 từ chối (409). Lớp chuyển đổi coi là
  chưa chuyển: tin nhắn nằm trong cuộc trò chuyện của ticket, cư dân nhận câu "đã lưu, đang chờ chuyển".
  Cần một message type cho thông tin tự nguyện, hoặc BQL đọc được hội thoại của ticket.
- Báo cháy chỉ nhận câu "đã tiếp nhận" kèm mã; chưa có hướng dẫn an toàn vì chưa có tri thức được duyệt.
- Policy khẩn cấp bỏ qua vài cách nói thường ngày của "cháy" ("cháy bóng", "cháy cầu chì"). Danh sách này và
  danh sách từ khóa khẩn cấp cần BQL duyệt.

## Tri thức chạy thật (03/10/2026)

Kho `github.com/leduc1707/Data-Vinhome` (140 file, 114 tài liệu sau khi gộp) đã nạp vào database demo.

- Nạp: `server/src/knowledge/publish.ts <thư-mục> --site ocean-park-1 --user <người xuất bản>`. Khác `cli.ts` (bản
  dev tự tạo phạm vi), lệnh này gắn tài liệu vào phạm vi thật: `00-do-thi` → site, `<đơn vị>/<phân khu>` → zone có
  cùng mã, thư mục tòa → building có cùng mã. Thư mục không có phạm vi tương ứng thì báo ra và không xuất bản.
- Demo: `seed_v3_ocean_park.sql` đổi site demo thành Vinhomes Ocean Park 1, thêm 8 phân khu và 14 tòa; cư dân
  demo ở S1.01 (Sapphire).
- Tìm kiếm: `server/src/knowledge/serve.ts` (cổng 8787) phục vụ `POST /internal/knowledge/search` với phân quyền
  thật, không cần chạy cả platform server. Mỗi lần tìm, dịch vụ hỏi backend
  (`/internal/reception/v1/knowledge-authorization`) cư dân của lượt chat này được đọc phạm vi nào.
- Masteri Waterfront do Masterise Property Management vận hành, không phải Vinhomes. Dữ liệu của họ được chính
  repo đánh dấu "cần xác minh", chỉ gắn vào phạm vi Masteri và mang cờ chưa xác minh. File cấp đơn vị
  (`02-masterise/quy-trinh-chung-...md`) được gắn vào phân khu duy nhất mà đơn vị đó vận hành (Masteri
  Waterfront). Khi một đơn vị có từ hai phân khu trở lên, file cấp đơn vị không có một phạm vi duy nhất: lệnh báo
  ra và không xuất bản, không bao giờ đẩy lên cả khu.
- Vector tạo bằng OpenAI `text-embedding-3-large`: nội dung từng đoạn được gửi tới OpenAI khi nạp.

Kết quả: bộ đánh giá hội thoại sau khi có tri thức đạt kiểm tra cứng 87%, phát biểu 88%, tự nhiên 4,42/5, trễ
trung vị 5,1 giây (trước: 85–88%, 87–88%, 4,2–4,4, 6 giây); nhóm câu hỏi thông tin 100%.

Chưa đo được bằng bộ 93 câu của Team Quang: chuỗi đáp án trong `ocean-park.v1.json` không còn khớp câu chữ
của repo dữ liệu sau lần sửa văn phong 01/10/2026 (ví dụ bộ đánh giá chờ "không dừng đỗ quá 1 giờ", dữ liệu ghi
"không được dừng quá một giờ"). Cần Team Quang cập nhật đáp án hoặc ghim phiên bản dữ liệu.

## Câu hỏi không có nguồn đi vào session của BQL (03/10/2026)

- Lễ tân không trả lời được thì mở một session **không có ticket** (`agent_teams.request_message_id` = tin nhắn
  của cư dân, đúng như schema đã dành sẵn) trong group chat của đơn vị quản lý phụ trách căn hộ; câu hỏi được
  đăng vào phòng để Supervisor và BQL thấy.
- Operations, trang "Tiếp nhận phản ánh": danh sách câu hỏi chờ trả lời. BQL trả lời
  (`POST /sessions/{id}/answer`), Lễ tân chuyển câu trả lời vào đúng cuộc trò chuyện của cư dân, session đóng.
- Khi Supervisor của Team Đông chạy, nó trả lời qua cùng endpoint; phía Lễ tân không đổi.
- Màn chi tiết ticket trong Operations hiện "Trao đổi của cư dân với Lễ tân" (`GET /tickets/{id}/conversation`),
  nên BQL thấy thông tin cư dân tự bổ sung.
- Giới hạn: quyền với session hỏi đáp chỉ tính vai trò management ở phạm vi tenant hoặc đúng đơn vị quản lý;
  cư dân có nhà thuộc hai đơn vị quản lý khác nhau thì chưa chuyển được.

## Agent do model dẫn dắt (03/10/2026)

`RECEPTION_AGENT=loop` bật agent mới trong `agent-reception/src/agent`; graph của Team Hoàng giữ nguyên và vẫn
là mặc định trong code. Chi tiết và bảng điểm so sánh ở `agent-reception/README.md`, mục "Hai chế độ agent".
Backend thêm `GET /internal/reception/chats/{id}/context` (hội thoại gần nhất và yêu cầu đang mở) để agent
không phải giữ trạng thái. Policy khẩn cấp theo từ khóa vẫn chạy trước model ở cả hai chế độ.

## Bộ nhớ và vòng tự học (03/10/2026)

**Bộ nhớ cư dân.** Ngữ cảnh mỗi lượt có 5 yêu cầu gần nhất của chính cư dân (tiêu đề, danh mục, ngày, trạng
thái), nên agent nối được sự cố mới với lần trước. Không có kho riêng: chỉ đọc yêu cầu của cư dân đó.

**Học từ câu trả lời của BQL.**

1. BQL trả lời một câu hỏi → backend ghi một ứng viên tri thức (`memory_candidates`), phạm vi là phân khu của
   người hỏi.
2. Agent thẩm định (`agent-reception/src/runtime/curator.py`) chấm; backend quyết định (`v3_learning.decide`):
   có thông tin cá nhân hoặc chỉ đúng cho một người → loại; nêu phí, quy định, an toàn → chờ BQL bấm duyệt
   (Operations, trang "Tiếp nhận phản ánh", mục "Tri thức chờ duyệt"); còn lại → tự duyệt. Luật về phí/quy
   định/an toàn do code kiểm bằng từ khóa, model không vượt được. Agent thẩm định không chạy thì ứng viên
   nằm chờ người duyệt.
3. `scripts/publish_learned.ps1 -DataDir <thư mục dữ liệu>` xuất các ứng viên đã duyệt thành
   `hoi-dap-ban-quan-ly.md` trong thư mục của đúng phạm vi rồi chạy `publish.ts`. File được ghi lại toàn bộ
   mỗi lần, nên thu hồi một ứng viên rồi chạy lại là tri thức đó biến mất. Thêm `-EveryMinutes 5` thì lệnh tự
   lặp: để chạy cạnh bản demo là không còn bước tay nào (file không đổi thì không tốn lượt embedding). Bản
   production cần một job định kỳ của platform thay cho script này.

Đã kiểm đầu-cuối trên database demo với model thật: hỏi "có cho mượn xe đẩy hàng không" → chuyển BQL → BQL trả
lời → tự duyệt → xuất bản → hỏi lại ở cuộc trò chuyện mới thì Lễ tân tự trả lời.

**Sửa xếp hạng tìm kiếm (file của Team Quang, `server/src/knowledge/retrieve.ts`).** Trộn hạng vector + từ khóa
để đoạn khớp gần nguyên văn câu hỏi (độ giống 0,78) rơi khỏi top 5 vì thua các đoạn chỉ khớp từ phổ biến
("xe", "hàng", "cư dân"; độ giống 0,52). Thêm `leadClearMatch`: đoạn có độ giống hơn đoạn kế tiếp từ 0,15 trở
lên thì đứng đầu; các thứ hạng khác giữ nguyên. Có test trong `tests/knowledge/pipeline.test.ts`. Cần Team Quang
rà lại ngưỡng bằng bộ đánh giá của họ.

Chưa làm: điểm tin cậy theo phản hồi của cư dân đưa vào xếp hạng, và ngân hàng ví dụ từ các lần BQL sửa phân
loại. Cả hai cần dữ liệu thật tích lũy trước (các bảng tín hiệu hiện 0 dòng).

## Đề nghị Team Hoàng

- Rà `runtime/backend.py` và `runtime/service.py`; nếu đồng ý hợp đồng này thì PD11 (graph gọi bộ tool mới)
  có thể đổi thành: giữ graph, coi lớp chuyển đổi là cổng tool chính thức.
- Cho biết model và nhà cung cấp dùng để nghiệm thu; cần chạy lại bộ eval tiếng Việt với LLM thật.

## Chạy lại kiểm thử

Backend: `pytest` trong `services/vinhomes-api` (cần PostgreSQL thử; xem `tests/test_resident_contract.py`).
Đầu-cuối: bật backend (demo, có `RECEPTION_DELEGATION_KEY`), runtime và `tests/runtime/fake_llm.py`, rồi
`RECEPTION_E2E_BACKEND_URL=… RECEPTION_E2E_TOKEN=… pytest tests/runtime/test_resident_chat_e2e.py` trong `agent-reception`.
Chạy cho cả hai chế độ agent (runtime bật `RECEPTION_AGENT=graph` rồi `RECEPTION_AGENT=loop`); 7 test đạt ở cả hai (03/10/2026).
