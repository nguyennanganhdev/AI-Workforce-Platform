# awp: lõi platform trung lập

Chạy trên AgentScope 2.0 (không sửa `platform_VP/agentscope/src`). Lõi không chứa tên domain nào. Domain nối vào bằng một *gói* (`platform_VP/packs/<domain>`).

## Nó làm gì

Một domain gửi *vụ việc* (`POST /platform/v1/intake`). Lõi tạo hồ sơ vụ việc (case file), mở một phiên cho agent leader, leader mời chuyên viên khi cần. Các agent làm việc trên hồ sơ chung bằng tool có kiểu. Leader chốt bằng `CaseFinalize`, kết quả qua cổng chống bịa rồi trả về domain.

| Khối | Mã | Việc |
|---|---|---|
| Hồ sơ agent | `profiles/` | Vai, phạm vi, tool được phép, kiến thức, bộ nhớ, tầng model, ngân sách. Có bản nháp → công bố → thu hồi. Biên dịch thành system prompt cố định (có đánh dấu `<awp-profile key v>`) và `SubAgentTemplate`. |
| Case file | `casefile/` | Danh sách chỉ-ghi-thêm: bằng chứng (E), sự kiện (F), câu hỏi (Q), phản biện (C), trả lời (A), "không biết" (G), quyết định (D), báo cáo (R), kết quả (X). |
| Giao thức | `protocol/tools.py` | `CaseFact`, `CaseGap`, `CaseAsk`, `CaseAnswer`, `CaseChallenge`, `CaseRead`, `CaseDecide`, `CaseFinalize`. Chuyên viên không thấy `CaseDecide`/`CaseFinalize`. |
| Bản tin phòng | `casefile/digest.py`, `middleware/room.py` | Mỗi lượt suy luận, agent nhận đoạn ngắn: ai nói gì, việc nào đang chờ mình. Chỉ phần mới từ lần xem trước; không có gì mới thì không tốn token. |
| Chống bịa | `guard/` | Mỗi tool result có mã bằng chứng. `CaseFact`/`CaseAnswer`/`CaseFinalize` từ chối con số, ngày, mã không có trong bằng chứng được trích dẫn. Luật theo domain (cụm từ cấm, từ nội bộ). Jev là ý kiến thứ hai tùy chọn. Sai quá 3 lần thì kết quả thành `needs_human` với câu trả lời an toàn. |
| Chi phí | `cost.py`, `providers.py`, `middleware/room.py` | Sổ chi phí mỗi lượt gọi model (theo vụ, agent, model). Tầng model theo hồ sơ. Ngân sách theo vụ: hết thì chỉ còn tool kết thúc. Lọc tool theo vai trước mỗi lần gọi. |
| Yêu cầu ra ngoài | `requests.py`, `protocol/tools.py` | `CaseRequest` gửi một biểu mẫu do domain định nghĩa (yêu cầu thi công, khai chi phí, xin cư dân xác nhận, báo tiến độ). Mọi con số trong biểu mẫu phải có trong bằng chứng. Trả lời quay về dạng có cấu trúc (`reply_to` + `data`), được kiểm theo schema rồi thành bằng chứng, và đánh thức agent đã gửi. `calc_sum` cộng chính xác. Vụ không bị đóng vì im lặng khi đang chờ trả lời; `CaseFinalize` từ chối khi còn trả lời chưa tới, hoặc khi `confirm_with` chưa được cư dân xác nhận. Quá `AWP_REQUEST_TIMEOUT_HOURS` (72) không có trả lời thì vụ thành `needs_human`. |
| Cổng nhận vụ việc | `intake/`, `router.py` | Nhận vụ việc (idempotent theo `message_id`), tin bổ sung, trả kết quả qua hàng đợi gửi lại. |
| Bảo mật | `security.py` | Khóa dịch vụ cho từng domain, khóa admin cho từng tenant. `X-User-ID` bị thay bằng người dùng dịch vụ của tenant. Khóa API bị che trong mọi phản hồi `/credential`. |

## Chạy

```
cd platform_VP/core
cp .env.example .env            # điền khóa; cp models.example.yaml models.yaml
..\agentscope\.venv\Scripts\python.exe -m pip install -e .   # hoặc đặt PYTHONPATH=src
..\agentscope\.venv\Scripts\python.exe -m awp
```

Không có khóa model thì dịch vụ vẫn lên nhưng vụ việc trả 503 ("no model is configured"). Model nào thiếu khóa thì không được dùng. Ollama chỉ bật khi có `OLLAMA_HOST` (và cần cài gói `ollama`).

## API (`/platform/v1`, khóa trong `Authorization: Bearer`)

| Đường | Ai | Việc |
|---|---|---|
| `POST /intake` | khóa domain | Gửi vụ việc (202). Gửi lại cùng `message_id` thì trả vụ cũ. |
| `POST /cases/by-ref/{external_ref}/messages` | khóa domain | Thông tin bổ sung cho vụ đang mở. |
| `GET /cases`, `/cases/{id}` | domain/admin | Trạng thái, kết quả, chi phí. |
| `GET /cases/{id}/items`, `/cases/{id}/cost` | admin | Hồ sơ vụ việc, chi phí theo agent và model. |
| `GET/POST /profiles`, `PUT /profiles/{key}/versions/{v}`, `POST …/publish`, `POST …/retire` | admin | Quản lý hồ sơ agent. Chỉ bản nháp được sửa. |
| `GET /models`, `/cost`, `/metrics`, `/jev` | admin | Model đang dùng được, chi phí theo model, mức tiết kiệm schema tool, thống kê Jev. |

Admin cũng dùng được API AgentScope gốc (`/agent/`, `/sessions/`…) bằng cùng khóa; khóa domain thì không.

## Kiểm thử

```
..\agentscope\.venv\Scripts\python.exe -m pytest tests -q
```

34 test: đơn vị (guard, case file, digest, hồ sơ, giá) và đầu-cuối qua dịch vụ AgentScope thật với model giả có kịch bản (`tests/fake_llm.py`): ticket vào, leader mời hai chuyên viên, họ hỏi nhau, leader bị từ chối khi bịa con số rồi chốt đúng, kết quả đến gói, chi phí ghi theo tầng model, ngân sách hết thì chốt `needs_human`, leader im lặng thì vụ `failed` và domain được báo. Model giả chỉ kiểm đường ống; không nói gì về chất lượng của model thật.

## Chưa làm hoặc chưa kiểm

- Khi một vụ đóng, các agent đang chạy không bị ngắt (báo cáo muộn của chuyên viên bị bỏ qua nhưng lượt gọi model đang dở vẫn tính tiền).
- Một chuyên viên lỗi giữa chừng không báo được cho leader (framework chặn sự kiện lỗi ở lớp ngoài); vụ sẽ bị đóng `failed` sau `AWP_CASE_STALL_SECONDS` (mặc định 900 giây).
- Không mở lại được vụ đã đóng. Vụ đang chờ trả lời thì vẫn mở, nên chỉ ảnh hưởng tin đến sau khi vụ đã chốt.
- Gói Vinhomes chưa khai báo `request_kinds` và `deliver_request`: chờ phía Vinhomes có endpoint nhận yêu cầu thi công, biểu mẫu chi phí, xác nhận của cư dân. Lõi đã chạy được toàn bộ luồng này với một gói thử.
- Guard so con số theo từng token; ngày viết khác định dạng (09/10/2026 so với 2026-10-09) bị coi là khác. Công cụ của domain nên in ngày giờ theo đúng dạng agent sẽ dùng.
- Callback webhook chặn địa chỉ riêng theo tên/IP nhưng chưa chống DNS rebinding.

- Chưa chạy bằng model thật (chưa có khóa còn hạn mức). Chất lượng trả lời và chi phí thật chưa đo.
- Kho kiến thức theo hồ sơ (`knowledge.knowledge_base_ids`) đã nối vào `RAGMiddleware` nhưng chưa chạy với kho thật (cần `knowledge_base_manager` truyền vào `build_app`).
- Bộ nhớ dài hạn riêng của agent (`memory.enabled`) nối `AgenticMemoryMiddleware`, thư mục theo tenant và hồ sơ; mới kiểm là dịch vụ vẫn chạy, chưa kiểm chất lượng ghi nhớ. `scope: team` (bộ nhớ chung chỉ-đọc) chưa làm.
- Chạy nhiều tiến trình cần bus Redis của AgentScope (`message_bus=`); mặc định là bus trong bộ nhớ. PostgreSQL dùng qua URL nhưng chưa thử. SQLite chỉ để phát triển.
- Mẫu sub-agent là một từ điển chung toàn dịch vụ: khóa hồ sơ phải khác nhau giữa các tenant (lõi từ chối trùng).
- Chưa có giao diện quản trị và SDK cho ứng dụng của domain.
- Jev: chạy qua `agentscope.classifier.JevClassifierModel` (cần `pip install typesafe-sdk` và `TYPESAFE_API_KEY`). Mới kiểm với bản giả; chưa gọi API thật, nên số liệu giá/tốc độ của hãng chưa được đối chiếu.
