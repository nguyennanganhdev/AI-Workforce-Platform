# awp: lõi platform trung lập

Chạy trên AgentScope 2.0 (không sửa `platform_VP/agentscope/src`). Lõi không chứa tên domain nào và không có mã domain trong repo platform. Đối tác nối vào qua **một** API: Workforce v1 (`/workforce/v1`). Hợp đồng là `docs/contract/CONTRACT_TICH_HOP_DOI_TAC.md`; cách làm ở phía platform là `docs/WORKFORCE_V1_DAC_TA_TRIEN_KHAI.md`; các quyết định của người triển khai là `docs/WORKFORCE_V1_QUYET_DINH.md`. Cách nối một đối tác (cho người tích hợp và người vận hành) ở `docs/WORKFORCE_V1_HUONG_DAN_KET_NOI.md`. API cũ (`/platform/v1/intake`, webhook, `CaseRequest`, `DomainPack`, khóa dịch vụ) đã bị gỡ ở phase P4.

## Nó làm gì

Đối tác gửi tin của một cư dân (`POST /workforce/v1/partner/requests`). Mỗi tin thuộc một *workflow*: một vụ việc (case file), một phiên leader AgentScope sống lâu, và một trạng thái công khai. Leader mời chuyên viên khi cần, gọi tool của đối tác qua MCP, xin cư dân đồng ý chi phí (approval), nhận tiến độ từ backend nghiệp vụ (Provider Event API). Cư dân chỉ đọc những gì leader nói qua `CaseSay`/`CaseFinalize`, đã qua cổng chống bịa. Chỉ `POST close` của đối tác mới đóng workflow.

| Khối | Mã | Việc |
|---|---|---|
| API đối tác | `workforce/` | Khóa `ApiKey dp_<id>.<secret>`, request/idempotency, snapshot, history, SSE, approval, close, Provider Event API có chữ ký HMAC, API admin `/platform/v1/wf` (client, khóa, route, MCP, integration). Xem các mục T1, T2 và S1-S4 của `docs/WORKFORCE_V1_QUYET_DINH.md`. |
| Engine | `workforce/runner.py`, `settling.py`, `decide.py`, `expiry.py` | Hàng đợi job tuần tự mỗi workflow, `TurnRecorder`, settle khi phiên rảnh, nudge, hết hạn, hồi phục job mất chủ. |
| Hồ sơ agent | `profiles/` | Vai, phạm vi, tool được phép, kiến thức, bộ nhớ, tầng model, ngân sách. Bản nháp → công bố → thu hồi. Biên dịch thành system prompt có đánh dấu `<awp-profile key v>` và `SubAgentTemplate`. |
| Case file | `casefile/` | Danh sách chỉ-ghi-thêm: bằng chứng (E), sự kiện (F), câu hỏi (Q), phản biện (C), trả lời (A), "không biết" (G), quyết định (D), báo cáo (R), kết quả (X). |
| Giao thức | `protocol/` | `CaseFact`, `CaseGap`, `CaseAsk`, `CaseAnswer`, `CaseChallenge`, `CaseRead`, `CaseDecide`, `CaseFinalize` (gửi câu trả lời, không đóng vụ), `CaseSay`, `CaseAskConsent`, `calc_sum`. Chuyên viên không thấy `CaseDecide`/`CaseFinalize`/`CaseSay`. |
| Bản tin phòng | `casefile/digest.py`, `middleware/room.py` | Mỗi lượt suy luận agent nhận đoạn ngắn: ai nói gì, việc nào đang chờ mình. Chỉ phần mới; không có gì mới thì không tốn token. |
| Chống bịa | `guard/` | Mỗi tool result có mã bằng chứng. Con số, ngày, mã không có trong bằng chứng được dẫn thì bị từ chối; luật của route (cụm từ cấm, "đã xong" cần dấu `<platform-verified>`). Jev là ý kiến thứ hai tùy chọn. Sai quá 3 lần thì gửi câu trả lời an toàn và `needs_human`. |
| Chi phí | `cost.py`, `providers.py`, `middleware/room.py` | Sổ chi phí mỗi lượt gọi model (theo vụ, agent, model). Tầng model theo hồ sơ. Ngân sách theo workflow: hết thì chỉ còn tool kết thúc. Lọc tool theo vai trước mỗi lần gọi. |
| Bảo mật | `security.py` | Khóa admin cho từng tenant (`AWP_ADMIN_KEYS`). `X-User-ID` bị thay bằng người dùng dịch vụ của tenant. Khóa API bị che trong mọi phản hồi `/credential`. Khóa đối tác (`dp_…`) chỉ dùng được ở `/workforce`. |

## Chạy

```
cd platform_VP/core
cp .env.example .env            # điền khóa; cp models.example.yaml models.yaml
..\agentscope\.venv\Scripts\python.exe -m pip install -e .   # hoặc đặt PYTHONPATH=src
..\agentscope\.venv\Scripts\python.exe -m awp
```

Cần `AWP_ADMIN_KEYS` (hoặc `AWP_DEV_OPEN=1` để làm việc cục bộ) và `AWP_SECRET_KEY` (khóa Fernet). Không có khóa model thì dịch vụ vẫn lên nhưng workflow thành `needs_attention` (`engine_error`). Model nào thiếu khóa thì không được dùng. Ollama chỉ bật khi có `OLLAMA_HOST`.

Cơ sở dữ liệu: SQLite cho phát triển (lõi tự tạo bảng, `AWP_AUTO_CREATE=1`); **PostgreSQL 16** cho production (`pip install "awp[postgres]"`, URL `postgresql+asyncpg://…`) với bảng tạo bằng migration Alembic: `python -m awp migrate --storage` (bảng của awp, rồi bảng của AgentScope bằng script của AgentScope), `python -m awp migrate --check` (DB đúng revision và đúng mô hình), và `AWP_AUTO_CREATE=0`. Một file `awp.db` tạo trước P4 còn cột `awp_cases.intake` và hai bảng cũ: xóa và tạo lại. Một DB tạo bằng `create_all` sau P4 nhận lịch sử migration bằng `python -m awp migrate --stamp`. Biến môi trường, pool kết nối, sao lưu, các vòng quét nền và lịch dọn dữ liệu: `docs/WORKFORCE_V1_VAN_HANH.md`.

## API admin (`/platform/v1`, khóa trong `Authorization: Bearer <khóa admin>`)

| Đường | Việc |
|---|---|
| `GET /health` | Sống hay không (không cần khóa). |
| `GET/POST /profiles`, `PUT /profiles/{key}/versions/{v}`, `POST …/retire` | Quản lý hồ sơ agent. Chỉ bản nháp được sửa. |
| `POST /builder/sessions`, `POST …/{id}/messages`, `GET …/{id}`, `POST …/{id}/apply` | Build agent qua chat: model đề xuất, platform chặn trùng (`reuse`) và lọc tool theo kho; `apply` chỉ tạo **bản nháp**. |
| `GET/POST /profiles/{key}/eval-cases`, `PUT/DELETE …/{id}`, `POST/GET /profiles/{key}/versions/{v}/evals` | Ca đánh giá của tenant (bộ ca của platform luôn chạy kèm) và các lần chạy đánh giá trong sandbox. |
| `POST /profiles/{key}/versions/{v}/publish`, `POST /profiles/{key}/rollback`, `GET /profiles/{key}/history` | Phát hành sau khi đánh giá đạt (`409 EVAL_REQUIRED` nếu chưa; admin ghi đè bằng `override_reason`), quay về version cũ, lịch sử. Khóa manager làm được các việc này với hồ sơ chỉ route của mình dùng. |
| `GET /cases`, `/cases/{id}`, `/cases/{id}/items`, `/cases/{id}/cost` | Vụ việc của tenant (mỗi workflow có một vụ): trạng thái, hồ sơ, chi phí theo agent và model. Tenant khác nhận 404. |
| `GET /models`, `/cost`, `/metrics`, `/jev` | Model dùng được, chi phí theo model, mức tiết kiệm schema tool, thống kê Jev. |
| `/wf/…` | API admin của đối tác: client, khóa, manager và khóa manager, route, kho tool MCP (bật/tắt/refresh, kích hoạt từng tool), integration, xem workflow/operation/approval/receipt, `resolve`. Khóa manager (`Bearer mk_…`) chỉ thấy phần thuộc route của mình. Cách dùng: `docs/WORKFORCE_V1_HUONG_DAN_KET_NOI.md`. |

Admin cũng dùng được API AgentScope gốc (`/agent/`, `/sessions/`, `/credential/`…) bằng cùng khóa.

## Kiểm thử

```
..\agentscope\.venv\Scripts\python.exe -m pytest -q -n 8 -p no:cacheprovider   # cả bộ song song (pytest-xdist, extra `test`): khoảng 5 phút; chỉ với SQLite
..\agentscope\.venv\Scripts\python.exe -m pytest -q          # cả bộ tuần tự, khoảng 30 phút (PostgreSQL: luôn tuần tự, xem sổ tay vận hành mục 8)
..\agentscope\.venv\Scripts\python.exe -m pytest -q -m "not slow"   # vòng nhanh: bỏ các test từ 10 giây trở lên
# cả bộ trên PostgreSQL thật (mỗi test hai database nhân bản từ template, xóa khi xong; docs/WORKFORCE_V1_VAN_HANH.md mục 8):
$env:AWP_TEST_PG_URL="postgresql://awp:awp@127.0.0.1:55432/postgres"; ..\agentscope\.venv\Scripts\python.exe -m pytest -q
```

Test dùng model giả có kịch bản (`tests/fake_llm.py`), một MCP server thật làm đối tác giả (`tests/workforce/partnerkit.py`) và một provider giả có ký (`t2kit.py`); chỉ kiểm đường ống, không nói gì về chất lượng model thật. `tests/probes/` (không chạy mặc định) là các kiểm chứng P0 có crash thật. Bộ kiểm tuân thủ hợp đồng là `tests/workforce/test_compliance.py`; bảng từng dòng và trạng thái ở `docs/WORKFORCE_V1_KIEM_THU_TUAN_THU.md`. Các test cần "chậm" dùng cổng (`threading.Event`: `Plan(hold=…)`, `hold_leader()`, `MODE["answer_gate"]`) và chờ điều kiện với trần rộng, không đo thời gian chạy; còn vài `sleep` để khẳng định điều *không* xảy ra (xem `docs/WORKFORCE_V1_QUYET_DINH.md`, mục P4). Máy xách tay vào Modern Standby giữa lúc chạy sẽ làm một test đơn lẻ trông như chạy hàng giờ; giữ máy thức khi chạy cả bộ.

## Chưa làm hoặc chưa kiểm

- Chưa chạy bằng model thật (chưa có khóa còn hạn mức). Chất lượng trả lời, tiếng Việt và chi phí thật chưa đo.
- Chạy nhiều tiến trình cần bus Redis (`message_bus=`): chưa nối vào `python -m awp` (phần S7b của P5; extra `redis` đã khai). PostgreSQL, migration Alembic và lịch dọn dữ liệu (một tiến trình mỗi chu kỳ, dưới lease trong bảng `wf_leases`) đã có và cả bộ test đã chạy trên PostgreSQL 16 trong Docker; chưa chạy trên PostgreSQL ngoài Docker cục bộ, chưa chạy nhiều tiến trình thật.
- Kho kiến thức theo hồ sơ (`knowledge.knowledge_base_ids`) nối vào `RAGMiddleware` nhưng chưa chạy với kho thật. Bộ nhớ dài hạn (`memory.enabled`, thư mục theo tenant, hồ sơ và workflow) mới kiểm là dịch vụ vẫn chạy; `scope: team` chưa làm.
- Mẫu sub-agent là một từ điển chung toàn dịch vụ: khóa hồ sơ phải khác nhau giữa các tenant (lõi từ chối trùng).
- Guard so con số theo từng token; ngày viết khác định dạng (09/10/2026 so với 2026-10-09) bị coi là khác. Công cụ của đối tác nên in ngày giờ theo đúng dạng agent sẽ dùng.
- Jev chạy qua `agentscope.classifier.JevClassifierModel` (cần `typesafe-sdk` và `TYPESAFE_API_KEY`); mới kiểm với bản giả.
- Chưa có giao diện quản trị và SDK cho đối tác.
