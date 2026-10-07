# Agent Eval V1: kế hoạch đã sửa và trạng thái triển khai

Cập nhật 07/10/2026. Bản này thay bản kế hoạch ban đầu. Mục 1 ghi những chỗ đã sửa và lý do. Mục 2–5 mô tả hệ thống đã viết. Mục 6 là cách vận hành. Mục 7 nêu những gì chưa kiểm chứng.

Các quyết định đã chốt vẫn giữ nguyên, trừ điểm cô lập ở mục 1.1 và quy tắc đạt (người phụ trách đổi ngày 07/10/2026: 6 ca tự sinh, đạt từ 4 ca):

- Mỗi bộ có đúng 6 ca, mặc định do model sinh; BQL bấm một nút để sinh, duyệt và chạy.
- Đánh giá có ba lớp: 9 nhóm kiểm tra bằng code, LLM-as-judge với 4 tiêu chí chấm từ 1 đến 5, và metric thư viện.
- Một ca đạt khi đạt đồng thời cả ba lớp. Lớp này không bù được cho lớp kia.
- Bộ đạt khi cả 6 ca đều có kết quả và ít nhất 4 ca đạt (`contracts.SUITE_SIZE`, `PASS_MINIMUM`).
- Eval đạt không tự phát hành agent.

## 1. Những chỗ đã sửa so với bản kế hoạch

### 1.1. Sandbox là một database riêng trong cùng cụm PostgreSQL

Bản cũ dùng một tenant eval nằm chung database với production. Thiết kế đó không cô lập được, vì bốn lý do đã kiểm trong mã:

1. **Khóa chính dạng text là duy nhất trên toàn database.** Ví dụ `channels.id`, `agents.id`, `mcp_servers.id`. Ngoài ra gateway hard-code `technical-tools` và `cleaning-tools`. Tenant eval nằm chung database sẽ không dùng được các id này, và đường code sẽ khác production.
2. **RLS chỉ dựa vào `app.tenant_id`.** Role nào cũng tự đặt được biến này. Khoảng 183 bảng không có ràng buộc role theo tenant.
3. **Mỗi process API chỉ phục vụ một tenant** (`VINHOMES_API_TENANT_ID`). Vì vậy dù chọn cách nào cũng phải chạy một stack thứ hai.
4. **Database riêng cho cách cô lập mạnh nhất với ít thay đổi nhất.** Role sandbox chỉ có quyền CONNECT vào database sandbox, và chính PostgreSQL từ chối kết nối sang production. Điều này đã kiểm bằng test, xem mục 5.

Phần còn lại vẫn đúng như bản cũ:

- Metadata, bộ ca, kết quả và báo cáo nằm trong database production, thuộc tenant nguồn.
- Dữ liệu thực thi nằm trong sandbox.

### 1.2. Không role DB nào đi qua hai database

Đường dữ liệu là: API nguồn → worker → API sandbox.

- **API nguồn** chụp snapshot cấu hình.
- **Worker** mang snapshot đó sang sandbox qua `POST /install`.
- **Worker** không giữ kết nối database nào.

### 1.3. Ghi bằng chứng tool chỉ trong sandbox

Hiện chưa nơi nào lưu tham số và kết quả của tool: audit chỉ có tên tool và trạng thái, còn quyết định của Supervisor chỉ nằm trong checkpoint. Cách xử lý:

- Gateway gọi `record_tool_trace`. Hàm này ghi bảng `vh_agent_eval_tool_traces` **chỉ khi** database có marker sandbox.
- Production không có marker nên không lưu tham số hay kết quả tool. Điều này có test.
- Phần định tuyến lấy từ `team_members`, phần lượt chạy lấy từ `agent_runs`.
- Phần truy xuất lấy từ `retrieval_runs`, `retrieval_hits` và `knowledge_chunks`, gồm cả nội dung đoạn trích.

### 1.4. Ngữ cảnh kỳ vọng lấy từ hồ sơ mẫu

`context_integrity` so ngữ cảnh của lần chạy với **hồ sơ mẫu của ca** (cư dân, căn hộ, tòa). Nó không so với những gì lần chạy tự báo về chính nó.

### 1.5. Metric thư viện mặc định không bắt buộc

Ngưỡng Ragas chưa được hiệu chỉnh cho tiếng Việt. Nếu bắt buộc ngay, việc phát hành sẽ bị chặn một cách tùy tiện.

- Profile mặc định là `none`.
- Profile `ragas-rag-v1` gồm Faithfulness ≥0,80, AnswerRelevancy ≥0,70 và ContextPrecisionWithoutReference ≥0,70.
- Bật profile bằng `VINHOMES_API_EVAL_METRIC_PROFILE`. Profile được ghi vào snapshot trước khi chạy.

### 1.6. Cổng phát hành chỉ bật khi đã có sandbox

Khi tenant đã có môi trường eval ở trạng thái `ready`, BQL chỉ phát hành được review gắn với một run V1 thỏa cả ba điều kiện:

- run đã hoàn tất;
- đạt ít nhất 4/6;
- `configuration_hash` khớp cấu hình đang xét.

Trước khi có sandbox, luồng 6 câu cũ vẫn là bằng chứng hợp lệ, để không đơn vị nào bị khóa phát hành. Admin vẫn duyệt và thu hồi như hiện nay.

### 1.7. Thay đổi schema so với đề xuất

- **`vh_agent_eval_case_results`:** dùng một cột `trace` (Trace đầy đủ, mọi bản ghi có id làm bằng chứng) thay cho hai cột `conversation` và `contexts`. Thêm cột `failure_layers` để báo cáo phân biệt lỗi do code, giám khảo, metric, môi trường hay thực thi.
- **`vh_agent_eval_environments`:** thêm `catalog`, gồm hồ sơ mẫu, tài liệu và tool của sandbox do worker đăng ký. Nhờ đó API kiểm được bộ ca viết tay mà không phải gọi sandbox.
- **Bảng mới phía sandbox:** `vh_agent_eval_sandbox` (marker), `vh_agent_eval_fixtures` và `vh_agent_eval_tool_traces`.
- **`admin_role_models`:** thêm vai trò model `evaluator` cho giám khảo và bộ sinh ca, tách khỏi model của agent đang thử.

### 1.8. Rủi ro cần ghi rõ

- **6 ca chạy một lần là một mẫu.** Agent kỹ thuật từng đạt bộ 10 ca chỉ 4/7 lần chạy trên `gpt-5.4-mini`. Một lần "rớt" có thể do model dao động. Báo cáo độ ổn định (chạy lặp) để ở mục phát triển thêm.
- **Trạng thái kết thúc dựa trên dữ liệu ghi lại.** Có hai heuristic, được ghi trong `v3_agent_eval_sandbox.build_trace`:
  - Lễ tân trả lời kết thúc bằng dấu "?" được tính là `information_requested`.
  - Phiên Supervisor đang chờ BQL được tính là `approval_pending`.
- **Trích dẫn tính theo tiêu đề.** Một tài liệu được coi là đã trích dẫn khi tiêu đề của nó xuất hiện trong câu trả lời cư dân đọc. Tín hiệu này yếu. Judge mới là lớp chấm việc bám nguồn.

## 2. Luồng

1. **BQL soạn bộ ca** ở bước "Thử" trong trang Agent: sinh 6 ca (`POST /eval-suites mode=generate`) hoặc tự soạn.
   - Ngữ cảnh sinh ca gồm nhiệm vụ, tool được cấp, các agent đã phát hành cùng phòng, tài liệu và hồ sơ mẫu của sandbox. **Ngữ cảnh này không chứa chỉ dẫn chi tiết của agent**, và dịch vụ sinh ca từ chối nếu có.
2. **API kiểm bộ ca.** Bộ ca phải có:
   - đúng 6 ca, tên khác nhau;
   - id agent, tool, tài liệu và hồ sơ đều có thật trong phạm vi;
   - không có kỳ vọng vừa bắt buộc vừa cấm;
   - ca `in_scope` yêu cầu agent đang đánh giá, ca `out_of_scope` cấm agent đó, ca `collaboration` yêu cầu ít nhất 2 agent;
   - có ít nhất một ca `in_scope` và một ca `out_of_scope`. Thiếu một trong hai thì bộ ca có thể đạt mà không chứng minh agent làm được việc của mình, cũng như không nhận việc của người khác.

   Lỗi được lưu vào `problems`. Id do model bịa ra bị báo lỗi, không bị thay thế âm thầm.
3. **Duyệt bộ ca.** Bộ đã duyệt không sửa được, nhờ cả API lẫn trigger trong database. Muốn đổi thì tạo bản mới.
4. **Chạy.** `POST /eval-runs {suite_id, configuration_hash, request_id}` trả về `202`.
   - Gửi lại cùng `request_id` sẽ nhận lại đúng run cũ; khác nội dung thì nhận `409`.
   - Mỗi môi trường chỉ có một run ở trạng thái queued hoặc running.
   - Run bị từ chối nếu agent dùng MCP ngoài (`provenance=custom`), hoặc sandbox thiếu tool.
   - Snapshot chỉ ghi profile model (provider/tên), không ghi khóa.
5. **Worker chơi từng ca.**
   1. Claim run với lease 60 giây và heartbeat mỗi 15 giây.
   2. Kiểm cô lập môi trường trước khi cài và trước mỗi ca.
   3. Cài bản sao agent làm specialist duy nhất được phát hành trong phòng sandbox.
   4. Mở hội thoại bằng hồ sơ cư dân mẫu, qua chính hàm route resident của production. Lễ tân, Supervisor và specialist chạy như production.
   5. Chỉ gửi câu trả lời bổ sung đã khai báo, và chỉ khi hệ thống hỏi lại. Các câu đã khai báo được gửi gộp trong một tin, như một người trả lời đủ các điều được hỏi.
   6. Chờ trạng thái ổn định qua hai lần đọc liên tiếp, hoặc tới timeout 5 phút. Ca gặp lỗi hạ tầng hoặc không có trạng thái kết thúc được chơi lại một lần trong hội thoại mới; lần đầu vẫn lưu trong `execution_refs.first_attempt`.
   7. Đóng phần việc của hội thoại: hủy ticket, phiên và mục chờ.
   8. Chạy 9 kiểm tra, judge và metric, rồi gửi kết quả.
6. **API tự tính đạt/rớt** bằng chính `contracts.case_verdict`. Worker và trình duyệt không gửi được cờ `passed` (hợp đồng từ chối với `422`).
   - Bằng chứng judge trích phải tồn tại trong trace.
   - Run đạt từ 4/6 sẽ tạo hoặc cập nhật review `pending` có `evaluation_run_id`. BQL phát hành ở bước 4.
7. **Lease hết hạn** thì run chuyển `interrupted` và không tự chạy lại. **Hủy** thì worker dừng ở nhịp heartbeat kế tiếp.

## 3. Ba lớp chấm

**Lớp 1 — `agent_eval/checks.py`.** Có 9 khóa: `required_agents`, `forbidden_agents`, `required_tools`, `forbidden_tools`, `required_sources`, `valid_output`, `runtime_guards`, `context_integrity`, `internal_leakage`.

- Mỗi khóa trả về `{passed, reason, evidence_refs}`. Kỳ vọng rỗng vẫn có khóa và lý do.
- Tool bắt buộc phải được cấp, trả `OK` và có tham số khớp. Có thể dùng `$fixture.building_id`, `$fixture.unit_id`, `$fixture.resident_id`.
- Tool bị cấm tính cả những lần gọi đã bị gateway từ chối.
- Kiểm lộ thông tin quét các mẫu sau, và báo cáo không bao giờ in lại giá trị bị lộ:
  - khóa hoặc bí mật;
  - mã `VH-…` và UUID;
  - tên tool;
  - id bản sao agent, tenant eval và ticket.

**Lớp 2 — `agent_eval/judge.py`.** Model riêng, vai trò `evaluator`.

- Giám khảo đọc toàn bộ bằng chứng theo id: tin nhắn, định tuyến, tham số và kết quả tool, **nội dung đoạn nguồn** và kết quả 9 kiểm tra.
- Mọi nội dung bằng chứng được coi là dữ liệu, không phải chỉ dẫn.
- Mỗi bản ghi bằng chứng là một dòng JSON, và kết quả kiểm tra bằng code nằm ở mục riêng. Nhờ vậy câu trả lời của agent không giả được một bản ghi hay một dòng "ĐẠT".
- Kết quả bị loại nếu thiếu tiêu chí, điểm không phải số nguyên 1–5 (0, 6, NaN, 4.5, "5"), lý do rỗng, hoặc bằng chứng không tồn tại. Các trường hợp này cho `error`, không bao giờ cho đạt.

**Lớp 3 — `agent_eval/metrics.py`.** Dùng Ragas 0.4.3, là phụ thuộc tùy chọn (`pip install -e .[eval-metrics]`). Chữ ký hàm đã đối chiếu với mã nguồn gói.

- Answer relevancy không áp dụng cho ca hỏi thêm hoặc chờ duyệt.
- Context precision chỉ đọc đoạn RAG.
- Ca yêu cầu nguồn mà không có ngữ cảnh thì báo `error`, không chuyển thành `not_applicable`.

## 4. Mã nguồn

| Phần | Vị trí |
|---|---|
| Hợp đồng và verdict (bản copy nguyên văn sang API có test chống lệch) | `agent-coordination/src/agent_eval/contracts.py`, `services/vinhomes-api/src/vinhomes_api/_vendor/agent_eval/contracts.py` |
| Worker và dịch vụ `python -m agent_eval` (cổng 4400, `/internal/generate`) | `agent-coordination/src/agent_eval/{worker,service,generator,judge,checks,metrics,llm}.py` |
| API nguồn: suite, run, báo cáo, hợp đồng worker | `services/vinhomes-api/src/vinhomes_api/v3_agent_evals.py` |
| API sandbox: catalog, attestation, install, hội thoại, trace | `services/vinhomes-api/src/vinhomes_api/v3_agent_eval_sandbox.py` |
| Migration | `server/drizzle/0020_agent_evaluations.sql` |
| Dựng sandbox | `services/vinhomes-api/scripts/provision_eval_sandbox.py` |
| Giao diện BQL | `app/src/features/vinhomes-operations/connected/AgentEvaluation.tsx` (gắn vào bước 2–3 của `AgentBuilder.tsx`) |
| Triển khai | `deploy/vinhomes/compose.yml`: service `evaluator` thuộc profile `eval`, cùng các biến `EVAL_*` của `api` |

## 5. Kiểm chứng đã chạy (07/10/2026)

| Bộ test | Kết quả |
|---|---|
| `agent-coordination` `tests/agent_evaluation` (checks, judge, generator, verdict, metrics, worker, service) | 89 pass |
| Toàn bộ `agent-coordination` | 544 pass |
| API trên PostgreSQL tạm: `test_v3_agent_evals.py`, `test_v3_agent_eval_sandbox.py`, `test_agent_eval_vendor.py`, `test_v3_agent_eval_e2e.py` | 13 pass |
| Toàn bộ `services/vinhomes-api` | 142 pass, 1 fail, 11 skip |
| Script dựng sandbox trên DB tạm | chạy đúng |
| UI `operations-agent-evaluation.test.tsx` và `operations-agent-trial.test.tsx` | pass |
| `tsc` | sạch |

Các test API trên PostgreSQL tạm kiểm những điểm sau:

- bộ thiếu ca, id bịa;
- bộ đã duyệt bất biến (API và trigger);
- idempotency;
- một run hoạt động mỗi môi trường;
- lease hết hạn chuyển `interrupted`;
- hủy run;
- cờ `passed` gửi từ worker bị từ chối;
- verdict tính lại;
- cổng phát hành;
- production không lưu tham số tool;
- route sandbox trả `404` ở production.

`test_v3_agent_eval_e2e.py` chạy worker thật giữa hai process API thật, với database sandbox và role riêng:

- Lần chạy đầu: role sandbox còn kết nối được database nguồn qua PUBLIC, nên run kết thúc `environment_unsafe`.
- Sau khi thu hồi quyền CONNECT của PUBLIC, worker chạy đủ 4 ca. Ba ca đạt. Ca `in_scope` rớt ở lớp code (`required_agents`) dù giám khảo chấm cao, vì test không chạy Supervisor nên agent không bao giờ được chọn. Run không đạt và không mở review nào.
- Luồng "đạt 4/4 → review chờ → BQL phát hành" được kiểm ở `test_v3_agent_evals.py`.

Ghi chú về các test còn lại:

- **Toàn bộ `services/vinhomes-api`:** test rớt là `test_v3_admin::atomically`. Nguyên nhân là thay đổi chưa commit của phiên khác ở `report_bootstrap.py`, không liên quan eval.
- **Script dựng sandbox:** lần chạy không có `--isolate-source` cảnh báo chưa cô lập. Lần chạy có `--isolate-source` thì PostgreSQL từ chối kết nối thật sang nguồn. Tool `custom` không bị chép, và chạy lại không lỗi.
- **UI:** `agent-factory-ui` và `agent-dialog-built-in-edit` rớt vì tìm nhãn tiếng Anh, không import mã eval.

Một agent review độc lập đã soi code và tìm ra 2 lỗi mức cao (bản sao agent có model không cài được; mất heartbeat thì worker vẫn chạy khi không còn lease) cùng 4 lỗi mức trung bình và 3 lỗi mức thấp. Tất cả đã được sửa và có test, trừ một lỗi mức thấp: sinh ca vẫn giữ kết nối DB trong lúc chờ model, giống cách Factory đang làm.

### 5.1. Chạy live trên stack Docker local (07/10/2026)

Sandbox `vinhomes_eval` và compose project `vinhomes-eval` đã dựng; bốn lần chạy với model thật, agent là bản nháp sao y "Agent Kỹ thuật A2".

| Lần | Kết quả | Ghi chú |
|---|---|---|
| 1 | 0/4, hoàn tất | Lộ ra các lỗi trace và cài bản sao (đã sửa ở `61669ec`) |
| 2 | Hủy giữa chừng | Sandbox thiếu model mặc định theo vai trò; lệnh hủy hoạt động đúng |
| 3 | 0/4, hoàn tất | Ca ngoài năng lực chạy trọn luồng tới "phương án chờ cư dân duyệt"; lộ lỗi chờ Lễ tân sau câu trả lời cho Supervisor (đã sửa) |
| 4 | 0/4, không có giá trị | Khóa model hết tín dụng (`insufficient_quota`) |

Đã chạy thật được: sinh 4 ca, duyệt, claim theo lease, kiểm cô lập, cài bản sao, Lễ tân, mở ticket, Supervisor chọn agent, agent gọi tool qua gateway (có ghi trace), Supervisor hỏi lại và worker trả lời, giám khảo chấm, API tính kết quả, hủy run.

Chưa có lần chạy nào đạt 4/4. Lý do thuộc về sandbox và cách thử, không phải đường ống:

- Bản nháp sao y trùng danh mục với agent đang phát hành, nên Supervisor chọn cả hai.
- Kho tri thức sandbox rỗng; `sop_kb.retrieve` trả `NOT_FOUND`.
- Supervisor chọn agent theo một danh mục của ticket, nên ca phối hợp giữa hai danh mục không xảy ra.
- Giới hạn 5 phút mỗi ca ngắn khi hai agent chạy nối tiếp; một lần đứt mạng khi gọi model làm Supervisor dừng chờ đối soát.

Bản sửa cuối (không chờ Lễ tân sau câu trả lời cho Supervisor) có test nhưng chưa được xác nhận bằng một lần chạy live, vì khóa model hết tín dụng.

Sau khi đổi khóa model, ba lần chạy tiếp theo (5, 6 và lần của agent mới) hoàn tất trong khoảng 4 phút mỗi lần, không còn ca hết giờ hay lỗi hệ thống.

**Custom agent mới "Agent Thang máy"** (tạo nháp rồi nhờ Factory soạn; Factory tự chọn `asset.read`, `maintenance_history.read`, `technical.get_active_outage`, `sop_kb.retrieve`): model sinh 4 ca, người duyệt sửa 3 ca cho khớp cách platform vận hành, kết quả **1/4**.

- Ca ngoài năng lực (đòi miễn phí dịch vụ) đạt cả ba lớp. Đây là ca đạt đầu tiên trên hệ thống thật.
- Ở hai ca sự cố, Supervisor mời Agent Thang máy cùng Agent Kỹ thuật A2 và giao việc cho Agent Thang máy. Các ca này rớt vì lỗi của chính agent: một lần gọi `asset.read` sai tham số bắt buộc, và không gọi `sop_kb.retrieve`.
- Ca "cửa thang bị cạy" được xếp vào danh mục an ninh, nên Agent Thang máy không được gọi.

**Quy tắc 6 ca, đạt từ 4 (chiều 07/10/2026).** Sáu lượt chạy một chạm cho "Agent Thang máy" (sinh 6 ca, duyệt, chạy):

| Lượt | Kết quả | Điều lộ ra và cách sửa |
|---|---|---|
| 1 | 0/6 | Agent gọi `asset.read` sai tham số; BQL bổ sung chỉ dẫn cho agent |
| 2 | 1/6 | Giám khảo trừ điểm agent vì dữ kiện nằm trong kịch bản mà agent chưa từng nhận: giám khảo nay chỉ thấy điều thật sự được nói |
| 3 | Hủy | Supervisor tạm dừng với lý do dài hơn 200 ký tự, API từ chối nên phiên treo (`ebaf343` sửa; sandbox phải chạy bản có commit này) |
| 4 | 2/6 | Ca bắt buộc `maintenance_history.read`, tool cần `asset_id` mà nền tảng chưa có bảng thiết bị nên không bao giờ gọi được: bộ sinh ca nay chỉ bắt buộc tool gọi được từ lời cư dân và hồ sơ mẫu |
| 5 | 3/6 | Ca ngoài năng lực rớt vì bộ phận khác dừng ở bước hỏi lại; ca thiếu thông tin rớt vì rubric đòi "chưa gọi agent" trái cách Supervisor vận hành. Cả hai đã sửa. Ca còn lại là thiếu sót thật của agent, BQL bổ sung chỉ dẫn |
| 6 | **4/6, đạt** | Run `5ea84090…` tạo review `pending`; BQL phát hành ở bước 4. Hai ca rớt vì dừng ở bước hỏi lại thay vì chờ duyệt (bộ ca lần này không khai báo câu trả lời bổ sung) |

Những điều còn đúng sau lượt 6:

- Nền tảng chưa có bảng thiết bị và lịch sử bảo trì: `asset.read` luôn trả "không tìm thấy". Kho SOP của sandbox rỗng. Agent đạt nhờ nói đúng là chưa có dữ liệu, không phải nhờ tra được dữ liệu.
- Ở vài ca, bản phân tích của agent viết "chưa rõ có ai mắc kẹt" dù cư dân đã trả lời Supervisor. Cần đội Supervisor kiểm tra câu trả lời của cư dân có tới agent hay không.
- Kết quả dao động theo bộ ca model sinh ra; một lượt là một mẫu.

Cổng phát hành V1 đang **bật** trên stack này (môi trường `ready`) để BQL phát hành từ run đạt. Tắt bằng cách đặt `vh_agent_eval_environments.status` về `disabled`; khi đó màn đánh giá ẩn và BQL phát hành bằng luồng 6 câu hỏi cũ.

## 6. Vận hành

1. **Dựng sandbox** (cần owner của database production):

   ```
   python scripts/provision_eval_sandbox.py --source-url <owner URL DB production> --isolate-source
   ```

   - Script tạo database `vinhomes_eval`, role `vinhomes_eval_api`, tổ chức tổng hợp với 3 hồ sơ mẫu, catalogue tool first-party và model registry. Model registry chỉ chép tham chiếu biến môi trường, không chép khóa đã niêm phong.
   - Cấu hình ghi vào `services/vinhomes-api/.local-eval/sandbox.env`, không in ra màn hình.
   - `--isolate-source` cấp CONNECT tường minh cho mọi role đang đăng nhập được, rồi thu hồi CONNECT của PUBLIC trên database production. **Đây là thay đổi quyền trên database production. Cần người phụ trách duyệt trước khi chạy.**
2. **Chạy stack sandbox** như một compose project thứ hai trên database sandbox:

   ```
   docker compose -p vinhomes-eval --env-file eval.env up -d api reception agents-net coordination openbot technical-tools knowledge
   ```

   `eval.env` chép từ `deployment.env` rồi sửa các biến sau:
   - `VINHOMES_API_DATABASE_URL` và `VINHOMES_TENANT_ID` lấy theo `sandbox.env`;
   - `EVAL_SANDBOX_TOKEN`;
   - cổng `VINHOMES_API_PORT` khác cổng production;
   - `COORDINATION_DATABASE_URL` trỏ tới checkpoint riêng;
   - database và role của tool host, knowledge riêng.

   Muốn có ca RAG thì phải phát hành kho tri thức vào database sandbox.
3. **Bật evaluator** trên stack production: `docker compose --profile eval up -d evaluator`, đặt các biến:
   - `EVAL_SERVICE_TOKEN`
   - `EVAL_SANDBOX_URL=http://host.docker.internal:<cổng API sandbox>`
   - `EVAL_SANDBOX_TOKEN_FOR_WORKER`
   - `EVAL_MODEL`, hoặc đặt model mặc định cho vai trò `evaluator`.
4. **Xác nhận:** worker tự đăng ký môi trường. Bước "Thử" trong trang Agent hiện nút "Tự sinh và chạy đánh giá" thay cho 6 câu cũ.

## 7. Chưa làm hoặc chưa kiểm chứng

- **Mới có một lần chạy live đạt (4/6)**, sau sáu lượt. Độ ổn định qua nhiều lượt chưa đo. Xem mục 5.1.
- **Chưa cài Ragas.** Chữ ký hàm đã đối chiếu với mã nguồn wheel 0.4.3, và đường gọi đã có test bằng scorer giả.
- **Kho tri thức chưa tự đồng bộ vào sandbox.** Catalog tài liệu rỗng cho tới khi phát hành tri thức vào database sandbox.
- **Trang Model của admin chưa có nhãn cho vai trò `evaluator`.** API đã nhận vai trò này; trong lúc chờ, dùng `EVAL_MODEL` của worker.
- **Script `vinhomes.publish` vẫn dùng đường review cũ** với admin duyệt. Admin không bị cổng V1 chặn, giống hiện nay.

## 8. Phát triển thêm (ngoài V1)

- Gửi báo cáo có bằng chứng cho Factory để đề xuất sửa.
- Chạy hồi quy với cùng bộ ca trên cấu hình mới.
- Chạy lặp k lần để đo độ ổn định.
- Hiệu chỉnh ngưỡng judge và Ragas bằng đánh giá của BQL.
- Mở rộng tool ghi khi có quyền thực thi phù hợp.
