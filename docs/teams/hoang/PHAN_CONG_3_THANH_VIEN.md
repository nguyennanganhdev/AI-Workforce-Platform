# Phân công Team Hoàng — Reception và Report agent cho 3 thành viên

## 1. Phạm vi và cách sử dụng

Phân công này cụ thể hóa **H01–H10** trong [kế hoạch 5 team](../../KE_HOACH_HOAN_THIEN_5_TEAM.md), cập nhật theo đính chính: Team Hoàng làm **Reception agent và năng lực Report agent để BQL dễ dàng tự tạo agent trên platform**. Phần học kinh nghiệm vẫn đọc thêm [thiết kế self-help và giá](../../THIET_KE_HOC_KINH_NGHIEM_SELF_HELP_GIA.md).

Team có hai đầu ra:

- Reception cố định bằng LangGraph TypeScript tại `agent-reception/`: tiếp nhận đúng khách/session, tạo/theo dõi ticket, đề xuất assessment, self-help và giá qua tool.
- Report capability: template/config schema/prompt tại `agent-report/`, report tools/metrics/application service/rendering tại `server/src/reporting/`, export job tại `worker/src/jobs/reporting/`. BQL tạo agent riêng từ template qua UI builder Chiến xây; agent chạy trong AgentScope do Đông tích hợp. Không tạo Report runtime LangGraph thứ hai, không hardcode một Report agent dùng chung mọi BQL.

Team Hoàng sở hữu hành vi và đầu ra báo cáo; Chiến sở hữu DB/migration, authorized data repositories, persistence ports và UI; Đông sở hữu groupchat/runtime; Team 5 sở hữu deployment/worker host. API/port giữa các phần cần chốt trước khi code song song.

Phân công dựa trên module, chưa giả định ai có kinh nghiệm hơn. **Phan Hoàng là đầu mối tích hợp kỹ thuật được đề xuất trong kế hoạch này**, không phải quyền sửa thay tất cả thành viên.

Hiện `agent-reception/` mới có các folder `src/graph`, `src/tools`, `src/adapters`, `src/persistence`, `tests` và `.gitkeep`; chưa có service Reception hoàn chỉnh. Đường dẫn chi tiết bên dưới là vị trí dự kiến để triển khai, không khẳng định file đã tồn tại. Chỉ tạo khi thực hiện task, không tạo skeleton hàng loạt.

## 2. Chia việc chính

Cập nhật phân công ngày 30/09/2026: Phan Dũng nhận phần graph/hội thoại/template Report trước đây của Dương Dũng; Dương Dũng nhận phần tools/API/metrics trước đây của Phan Dũng. Mã task đổi tương ứng: `DD01–DD07` cũ thành `PD01–PD07`; `PD01–PD06` cũ thành `DD01–DD06`. Khi đọc handoff cũ cần đối chiếu mapping này. Nhiệm vụ và mã `PH01–PH07` của Phan Hoàng giữ nguyên.

| Thành viên | Trách nhiệm chính | Phần H01–H10 |
|---|---|---|
| **Phan Dũng** | Reception graph/hội thoại; Report template, câu hỏi builder, cấu hình đầu ra, narrative/prompt và bố cục báo cáo | H01/H02/H05/H06/H07 phần hội thoại; **H08 chính**, H10 nội dung |
| **Dương Dũng** | Reception tools/API client; report tools, chuẩn hóa yêu cầu, định nghĩa/tính chỉ số và source lineage qua authorized data ports | H03 chính, H07 tools; **H09 chính** |
| **Phan Hoàng** | Reception service/session/checkpoint; tích hợp Report với builder/runtime/worker/storage, render artifact và test xuyên module | H01/H04 chính, H05 reliability; **H10 chính**, tích hợp H08/H09 |

Mỗi người viết test cho module của mình. Phan Hoàng nối module và chạy integration Reception/Report; Team 5 vẫn phụ trách E2E toàn nền tảng. Không giao toàn bộ Report cho một người làm sau khi Reception xong: PD06/DD05/PH06 khởi động song song từ mốc đầu.

## 3. Quyền sửa folder/file

**Mỗi đường dẫn có một owner.** Mọi file chưa được phân công trong `agent-reception/` phải được Phan Hoàng phân loại trước khi sửa; điều này không cấp quyền cho Phan Hoàng sửa folder đã thuộc người khác. Có thể đọc code toàn repo, nhưng không được sửa ngoài vùng được giao.

| Owner | Được tạo/sửa trực tiếp | Nội dung |
|---|---|---|
| Phan Dũng | `agent-reception/src/graph/**` | State, nodes, edges, graph factory, interrupt decisions và routing hội thoại |
| Phan Dũng | `agent-reception/src/prompts/**` — mới | System prompt, template hỏi/đáp, prompt version |
| Phan Dũng | `agent-reception/tests/graph/**`, `agent-reception/tests/evals/**` — mới | Test graph và bộ tình huống tiếng Việt; dữ liệu tổng hợp đã khử PII |
| Dương Dũng | `agent-reception/src/tools/**` | Tool definitions, input/output validation, mapping sang backend operations |
| Dương Dũng | `agent-reception/src/adapters/backend/**` — mới | HTTP client, error mapping, request correlation; không tự suy ra quyền từ prompt |
| Dương Dũng | `agent-reception/tests/tools/**`, `agent-reception/tests/adapters/backend/**` — mới | Test tool/client với contract fixtures và server test |
| Phan Hoàng | `agent-reception/src/persistence/**` | Framework checkpointer adapter, binding resolver, concurrency/recovery |
| Phan Hoàng | `agent-reception/src/adapters/transport/**`, `agent-reception/src/adapters/events/**`, `agent-reception/src/adapters/model/**` — mới | AG-UI/HTTP streaming, event ingress/resume, model factory |
| Phan Hoàng | `agent-reception/src/contracts/**` — mới | Interface nội bộ nối graph/tools/runtime; không thay hợp đồng API nền tảng |
| Phan Hoàng | `agent-reception/src/index.ts`, `agent-reception/src/config.ts`, `agent-reception/src/observability/**` | Entrypoint, dependency injection, config validation, trace đã lọc dữ liệu nhạy cảm |
| Phan Hoàng | `agent-reception/tests/runtime/**`, `agent-reception/tests/persistence/**`, `agent-reception/tests/integration/**`, `agent-reception/tests/support/**`, `agent-reception/tests/adapters/transport/**`, `agent-reception/tests/adapters/events/**`, `agent-reception/tests/adapters/model/**` — mới | Session/restart/concurrency, adapter tests và fixture dùng chung |
| Phan Hoàng | `agent-reception/package.json`, `agent-reception/bun.lock`, `agent-reception/tsconfig.json`, `agent-reception/bunfig.toml`, `agent-reception/Dockerfile`, `agent-reception/.env.example`, `agent-reception/README.md` | Cấu hình package riêng; không chứa secret; phối hợp Team 5 về build/deploy |
| Phan Hoàng | `agent-langgraph/**` khi cần reuse thực sự | Adapter mẫu; ưu tiên đọc/reuse, không đổi sample thành Reception thứ hai |

**Bổ sung quyền Report — cùng mức bắt buộc với bảng trên:**

| Owner | Đường dẫn được sửa — đều là MỚI | Trách nhiệm |
|---|---|---|
| Phan Dũng | `agent-report/templates/**`, `agent-report/schemas/**`, `agent-report/prompts/**`, `agent-report/examples/**`, `agent-report/tests/templates/**`; `server/src/reporting/narrative/**`, `server/src/reporting/layouts/**`, `server/tests/reporting/narrative/**`, `server/tests/reporting/layouts/**` | Template, config questions/validation schema, narrative và layout; không tự cấp quyền dữ liệu |
| Dương Dũng | `server/src/reporting/tools/**`, `server/src/reporting/metrics/**`, `server/src/reporting/application/**`, `server/tests/reporting/tools/**`, `server/tests/reporting/metrics/**`, `server/tests/reporting/application/**` | Tool/application flow, metric code và provenance; gọi data/persistence ports, không tự SQL nghiệp vụ |
| Phan Hoàng | `agent-report/README.md`, `agent-report/manifest.json`, `agent-report/tests/integration/**`; `server/src/reporting/contracts/**`, `server/src/reporting/rendering/**`, `server/src/reporting/adapters/**`, `server/src/reporting/index.ts`, `server/tests/reporting/integration/**`, `server/tests/reporting/rendering/**`, `server/tests/reporting/adapters/**`, `server/tests/reporting/support/**`; `worker/src/jobs/reporting/**` | Manifest tích hợp, interface nội bộ, adapter gọi port Chiến, render/export và job handler; không tự mount route/worker |

`agent-report/` là gói template có phiên bản, không tự dựng server/package độc lập nếu runtime Đông không cần. File mới chưa có owner trong bốn vùng reporting của Hoàng phải được phân công trước; không có quyền mặc định sửa chéo folder thành viên. Các thay đổi API chính thức trong `shared/contracts/` vẫn do Chiến sở hữu.

Tài liệu mỗi người, trong vùng `docs/teams/hoang/`:

- Phan Dũng: `members/phan-dung/**`, `requests/phan-dung/**`, `handoffs/phan-dung/**`.
- Dương Dũng: `members/duong-dung/**`, `requests/duong-dung/**`, `handoffs/duong-dung/**`.
- Phan Hoàng: `members/phan-hoang/**`, `requests/phan-hoang/**`, `handoffs/phan-hoang/**`, `integration/**`, `README.md` và file phân công này.

Các thư mục tài liệu con trên cũng là **mới, tạo khi cần**. Không đổi `.gitkeep` hoặc tài liệu người khác để tạo commit trống.

### 3.1. Các vùng cả 3 người không được sửa trực tiếp

| Vùng | Owner ở kế hoạch toàn dự án | Cách phối hợp |
|---|---|---|
| `server/src/**` ngoài `reporting/**`, `server/drizzle/**`, DB catalog/generator, `app/**` | Chiến, trừ vùng Quang | Hoàng chỉ sửa reporting theo bảng trên; gửi API/UI/schema request, không tự sửa DB/repository |
| `shared/contracts/**` | Chiến | Đề xuất contract và fixture; chỉ dùng version đã chốt |
| `server/src/knowledge/**`, `server/src/technical-tools/**` | Quang | Yêu cầu tool retrieval/price, không tự dựng RAG hoặc bộ thống kê giá trong Reception |
| `agent-coordination/**` | Đông | Dùng kết quả/event qua backend; không sửa supervisor hoặc groupchat |
| `supervisor/**`, `worker/**` ngoài `src/jobs/reporting/**`, `docker-compose*.yml`, `charts/**`, `.github/**`, root manifests/lockfile | Team 5 hoặc ngoại lệ Chiến/Quang | Hoàng xuất job handler reporting; Team 5 đăng ký host; không tự sửa entrypoint/hạ tầng |
| `agent-langgraph-agui/**`, các framework sample khác | Team 5 | Chỉ tham khảo; Reception chính dùng TypeScript đã thống nhất |

Trong nhóm, cần sửa file khác owner thì gửi yêu cầu với chữ ký interface và test mong đợi. Owner thực hiện thay đổi; không chặn các phần độc lập còn lại. Shared fixture `tests/support/` do Phan Hoàng duy trì, fixture riêng giữ trong folder test của người viết.

## 4. Cây cấu trúc và hướng phụ thuộc

```text
agent-reception/
  src/
    index.ts                       Phan Hoàng: nối tất cả dependency
    config.ts                      Phan Hoàng
    contracts/                     Phan Hoàng: interface nội bộ
    graph/                         Phan Dũng
    prompts/                       Phan Dũng
    tools/                         Dương Dũng
    adapters/
      backend/                     Dương Dũng
      transport/                   Phan Hoàng
      events/                      Phan Hoàng
      model/                       Phan Hoàng
    persistence/                   Phan Hoàng
    observability/                 Phan Hoàng
  tests/                           Phân chia theo mục 3
```

Graph phụ thuộc interface tool/model/checkpointer, không import HTTP server hoặc tự tạo database pool. Tools phụ thuộc backend client, không import graph. Entrypoint của Phan Hoàng tạo dependency rồi truyền vào graph. Không tạo vòng import giữa graph và tools. Module không tự khởi động server/job khi được import trong test.

Hợp đồng nền tảng từ `shared/contracts/` do Chiến cung cấp; `src/contracts/` chỉ mô tả các port nội bộ. Không sao chép DTO để tự sửa thành một API khác. Tên interface dưới đây là đề xuất cho buổi chốt đầu tiên, chưa phải code có sẵn:

| Interface | Người chốt | Người cung cấp/tiêu thụ | Nội dung phải thống nhất |
|---|---|---|---|
| `VerifiedReceptionContext` | Phan Hoàng, đối chiếu C06 | Transport/persistence → graph/tools | Principal, tenant, user khởi tạo, binding, run, quyền hạn được backend xác minh; không đồng nhất customer và service principal |
| `ReceptionToolPort` | Phan Hoàng + Dương Dũng | Tools → graph | Operation, validated payload, typed result/error, idempotency key, cancellation/timeout |
| `ReceptionGraphFactory` | Phan Hoàng + Phan Dũng | Graph → entrypoint | State/schema version, model/tool/checkpointer injection, stream/interrupt/resume và result |
| `ReceptionResumeEvent` | Phan Hoàng | Backend/event adapter → graph | Event ID, aggregate version, ticket/generation, binding/interrupt; xác thực nguồn và dedup |
| `ReportTemplateConfig` | Phan Dũng, Phan Hoàng tích hợp | Template → builder Chiến/runtime Đông | Template/schema version, loại báo cáo, metric IDs, scope selection, kỳ/timezone, định dạng; quyền do backend xác minh |
| `ReportDataPort` / `ReportPersistencePort` | Phan Hoàng + Dương Dũng, Chiến cung cấp implementation | Report application → backend | Authorized snapshot/as_of, dataset/metric version/hash, request/source/result lifecycle, idempotency/cancel |
| `ReportArtifactPort` | Phan Hoàng, đối chiếu C07/C14 | Renderer/job → storage backend | File nội bộ, MIME/hash, access check; không public URL |

Phan Hoàng chỉ commit interface sau khi hai consumer liên quan thống nhất. Phiên bản hóa thay đổi state; không sửa shape state làm checkpoint cũ không đọc được mà thiếu kế hoạch migrate hoặc chấm dứt phiên có kiểm soát.

## 5. Task cụ thể cho Phan Dũng

| Mã | Công việc | Dependency | Tiêu chí bàn giao |
|---|---|---|---|
| PD01 | State và graph factory: intake, clarify, awaiting tool, awaiting resident, handoff, completion | PH01 interface | Graph chạy với fake ports trong test, không cần LLM/network; phân biệt facts xác nhận với suy luận |
| PD02 | Hội thoại tiếp nhận: loại yêu cầu, căn hộ cần chọn, mô tả/ảnh còn thiếu; tạo ticket sau xác minh bằng tool | PD01, DD02; C03/C04 khi tích hợp | Nhiều căn hộ không tự chọn; tool từ chối quyền thì không tiếp tục; câu hỏi không lặp vô hạn |
| PD03 | Đề xuất assessment và phản hồi tiến độ; không tự ghi priority hoặc quyết định ban quản lý | DD02, PH03; C05/C08 | Thiếu facts cần hỏi/review; thông báo đúng ticket và không nói hoàn thành khi chỉ accepted |
| PD04 | Luồng self-help: hỏi đồng ý, hướng dẫn đúng procedure version, khách từ chối/thất bại/dừng → handoff; giá diễn đạt từ tool | DD03; C13/Q07/Q08 | Không suy từ “nhẹ” ra “được tự sửa”; không tự sinh thao tác ngoài quy trình; không bịa số khi thiếu giá |
| PD05 | Eval tiếng Việt và prompt version: đa ticket, mơ hồ, thiếu dữ liệu, prompt injection, self-help, giá | PD02–PD04 | Dataset có expected behavior và source/version; báo failure cases và kết quả; không dùng real PII |
| PD06 | Template Report: bộ câu hỏi tạo agent, config JSON Schema, metric selection, prompt hệ thống và examples preview | C01/C09/C14/D02 contract; PH06 | BQL chỉ cấu hình chứ không code; phân biệt template/version với instance của BQL; không cấu hình SQL/tool tùy ý |
| PD07 | Narrative/layout báo cáo ticket/SLA/phân công, empty/partial/error states, prompt eval chống bịa số | PD06, DD05/DD06 schema | LLM diễn giải số đã tính; mọi nhận xét có nguồn; không đồng nhất lỗi truy vấn với số 0; layout bàn giao renderer |

Không tạo rule quyết định nguy hiểm/giá bằng prompt thay policy backend. Không tự học/publication procedure từ lời cư dân. Đối với giá, giữ nguyên khoảng/tiền tệ/điều kiện tool đã trả; nếu cần diễn đạt số tiền phải có deterministic formatting test.

## 6. Task cụ thể cho Dương Dũng

| Mã | Công việc | Dependency | Tiêu chí bàn giao |
|---|---|---|---|
| DD01 | Backend client, schema validation, errors, timeout, trace/correlation; mock contract server cho test | PH01; C01/C06 contract | Validate cả response; không log secret; token audience/expiry đúng; không retry mọi mutation vô điều kiện |
| DD02 | Tools context cư dân, create/read/update ticket, submit assessment, trạng thái và file metadata được cấp quyền | DD01; C03/C04/C05/C07 | Tool chỉ gọi API đã authorize; identity không lấy từ model; duplicate request không tạo việc trùng |
| DD03 | Tools quy trình/eligibility, self-help lifecycle/handoff, price estimate; map typed outcomes cho graph | DD01; C13/Q07/Q08 | Chưa published/expired/revoked không được dùng; declined/failed gọi backend đúng ticket; giá không tự tính trong wrapper |
| DD04 | Contract tests và failure matrix: 401/403/404, stale version, 409, 429, timeout, response sai schema, lỗi dịch vụ | DD02/DD03 | Lỗi retryable/permanent được phân biệt; tool result không tuyên bố mutation thành công khi timeout chưa xác định |
| DD05 | Metric catalog và report tools: validate scope/kỳ/timezone/filter; định nghĩa tử/mẫu số, reopen/cancel, version và query template IDs | PD06, PH06; C14 data contract | Report query allowlist; KPI tính bằng code, không LLM/SQL tự sinh; test boundary kỳ `[from,to)` |
| DD06 | Application pipeline create request → snapshot → metrics → sources → render request/status; idempotency và error/cancel | DD05; C14 persistence/data ports, PH07 render port | Nguồn/row count/hash truy vết được; snapshot nhất quán; cross-scope bị từ chối; retry không sinh báo cáo chính thức đúp |

Giới hạn rõ: Quang xây `find_self_help_procedure` và `estimate_repair_price` ở backend; Dương Dũng chỉ xây **client/tool wrapper của Reception** để gọi chúng. Chiến làm actual-cost API và dữ liệu; Dương Dũng không tạo thêm bảng giá hoặc đọc PostgreSQL trực tiếp.

Idempotency key thuộc operation bền vững của phiên, được tạo/lưu trước khi gọi backend; không đổi key mỗi lần retry, không chỉ dùng `run_id` vì một run có nhiều thao tác. Dương Dũng cùng Phan Hoàng chốt cách lưu key và truy hồi kết quả khi response bị mất.

## 7. Task cụ thể cho Phan Hoàng

| Mã | Công việc | Dependency | Tiêu chí bàn giao |
|---|---|---|---|
| PH01 | Package Reception, config/model factory, interface nội bộ, healthcheck và test harness; kế hoạch reuse sample | C01/P01 phối hợp | Có scripts cài/chạy/test/typecheck thực; không thêm root workspace/lockfile ngoài quyền; health không lộ config secret |
| PH02 | AG-UI transport, service authentication và binding resolver theo backend C06 | PH01, DD01; C06 | Không tin thread/user/tenant từ browser; ownership được kiểm tra trước read/run/resume; streaming lỗi kết thúc đúng |
| PH03 | Durable checkpoint adapter, interrupt/resume, lease/fencing, event dedup, cancel và recovery | PH02; C06/P02, C08/D04 cho events | Restart không mất phiên; hai replica không chạy side effect đúp; event lặp/stale không resume sai ticket |
| PH04 | Nối graph/tools/model/persistence; integration intake, notification, self-help và price | PD02–PD04, DD02/DD03, PH03 | Hai user/hai ticket không lẫn context; error/handoff đi hết luồng; không có production mock |
| PH05 | Telemetry đã lọc dữ liệu, runtime/restart tests, tài liệu vận hành và bàn giao cho Team 5 | PH04, PD05, DD04 | Trace nối request/run/ticket; có test/known limits; runtime outage không mất trạng thái hoặc lộ nội dung khách khác |
| PH06 | Contract/manifest Report và tích hợp template với builder Chiến, runtime AgentScope Đông; review gap DB request/source/version | PD06/DD05 cùng chốt contract; C09/C14/D08 | Report agent do BQL tạo chạy như subagent riêng; không sửa code runtime Đông hoặc UI Chiến; pin release/template/metric version |
| PH07 | Renderer DOCX, artifact adapter, export job và integration tests; runtime registration qua owner | DD06 interface, PD07 layout; C07/C14/P03 | File đúng nguồn/scope; render kiểm tra bố cục; download kiểm tra quyền lại; cancel/retry/revoke không công bố sai artifact |

Phan Hoàng chịu trách nhiệm **adapter checkpoint của LangGraph**, không tự thêm cột vào checkpoint framework hoặc triển khai DB nghiệp vụ C06. Phải pin dependency và kiểm chứng capability thật; RAM-only saver chỉ được dùng cho unit test. Credential framework storage tách quyền với database nghiệp vụ.

Event ingress là consumer thông báo đã được backend authorize, không tự dựng notification service thứ hai. Không giữ HTTP request mở nhiều giờ chờ nhân viên xử lý; persist wait/interrupt và resume khi có sự kiện phù hợp.

## 8. Thứ tự làm song song và điều kiện tích hợp

Reception và Report là **hai luồng song song**. Từ H-A: PD06 chốt cấu hình, DD05 chốt metric/data contract, PH06 chốt integration với Chiến/Đông. Không phụ thuộc Report vào self-help/giá để có thể demo report ticket trước; actual-cost/self-help metrics chỉ thêm khi C13 có dữ liệu chuẩn.

### Mốc H-A: chốt hợp đồng và khởi tạo

- Phan Hoàng làm PH01, thống nhất interface và state version với hai thành viên; gửi yêu cầu C01/C06/P01.
- Phan Dũng làm PD01 bằng port giả trong test và viết trước tình huống PD05.
- Dương Dũng làm DD01 với contract fixture được thống nhất; chưa có backend thật phải ghi rõ blocked integration, không gọi mock là đã tích hợp.

### Mốc H-B: intake chạy thật

- Dương Dũng hoàn thành DD02; Phan Dũng nối PD02/PD03; Phan Hoàng nối PH02 và persistence tối thiểu của PH03.
- Nghiệm thu: khách đăng nhập, chọn căn hộ hợp lệ, tạo đúng một ticket dù gửi lại, nhận trạng thái đúng người. Backend quyết định routing và triage.

### Mốc H-C: session bền vững

- Phan Hoàng hoàn thiện PH03; Dương Dũng kiểm tra idempotency/timeouts; Phan Dũng xử lý interrupt/restart trong graph.
- Nghiệm thu: restart giữa tool call; khách B thử thread A; callback lặp/out-of-order; một khách có hai ticket; quyền vừa bị thu hồi. Không lỗi nào được che bằng tạo phiên hoặc ticket mới tùy tiện.

### Mốc H-D: học kinh nghiệm và giá

- C13/Q07/Q08 cung cấp contract/schema trước, rồi service thực để đóng task. Team Hoàng không cần đợi mới viết test nhưng không được đóng nghiệm thu chỉ bằng stub.
- Dương Dũng làm DD03, Phan Dũng làm PD04; Phan Hoàng tích hợp PH04 và recovery.
- Nghiệm thu: procedure được duyệt → tìm đúng → đồng ý/từ chối → ghi outcome/handoff; tool giá trả đủ/thiếu dữ liệu → Reception trả lời đúng; không hardcode 500.000–1.000.000 đồng.

### Mốc H-E: bàn giao

PD05 + DD04 + PH05 hợp thành báo cáo H06. PD06/PD07 + DD05/DD06 + PH06/PH07 bàn giao H08–H10. Team 5 chạy E2E với backend/RAG/Coordination thực. Chỉ đóng H01–H10 khi dependency trong kế hoạch tổng thể và các luồng thật đã đạt.

### Luồng Report phải demo trước khi bàn giao

1. Hai tài khoản BQL chọn cùng template Report qua UI Chiến; chọn chỉ số, kỳ, scope được cấp và cấu hình riêng; preview rồi publish agent/release.
2. Đông nạp hai Report agent vào hai groupchat; Hoàng cung cấp manifest/prompt/tools, không tự tạo groupchat thứ ba.
3. BQL yêu cầu báo cáo từ message thật. Backend xác minh scope và tạo report request; tool/application Dương Dũng lấy dataset snapshot qua data port Chiến, tính KPI và ghi nguồn.
4. Narrative Phan Dũng diễn giải kết quả; job/renderer Phan Hoàng tạo DOCX qua storage backend, trả artifact có quyền và trace đến request/source.
5. Cố truy xuất report khác BQL, revoke grant giữa run/download, retry job và dữ liệu thiếu đều phải có test. Mốc dữ liệu và thuật toán được pin; `as_of` không tự bảo đảm truy vấn lịch sử nếu chưa có snapshot/history.

MVP: báo cáo ticket theo trạng thái/loại/kỳ, SLA và phân công/kết quả xử lý, định dạng DOCX. Chốt chi tiết metric và layout với BQL; không tự thêm lịch gửi email định kỳ, PDF/XLSX hoặc báo cáo tài chính. Nếu được yêu cầu thêm, cập nhật task/contract trước triển khai.

## 9. Ai phối hợp với team ngoài?

| Chủ đề | Đầu mối Team Hoàng | Team nhận yêu cầu |
|---|---|---|
| API ticket/context/assessment/files và typed errors | Dương Dũng | Chiến |
| Binding, quyền runtime, lease, checkpoint infrastructure, event resume | Phan Hoàng | Chiến + Team 5 |
| Retrieval quy trình, giá tham khảo, metadata eligibility | Dương Dũng, Phan Dũng review nhu cầu hội thoại | Quang + Chiến |
| Kết quả xử lý từ supervisor và chờ người phê duyệt | Phan Hoàng, Phan Dũng review nội dung phản hồi | Đông + Chiến |
| Nghiệp vụ hỏi/đáp, điều kiện tự sửa, câu trả lời mẫu | Phan Dũng | Chủ sản phẩm/người phụ trách nghiệp vụ; Chiến hiện thực policy |
| Build/deploy, secret, observability và E2E | Phan Hoàng | Team 5 |
| Report template, câu hỏi builder, layout và bộ chỉ số BQL cần | Phan Dũng | Chiến (UI), BQL/chủ sản phẩm |
| Report data/persistence, snapshot/as_of, query allowlist và provenance | Dương Dũng | Chiến C14 |
| Report manifest/runtime/tool grants và artifact worker | Phan Hoàng | Đông D08, Chiến C07/C09/C14, Team 5 P03/P04 |

Yêu cầu ngoài scope phải ghi: task ID, endpoint/port cần có, request/response schema, auth/idempotency/error semantics, fixture, test mong đợi và phần đang bị chặn. Các điều kiện chuyên môn phải do người có thẩm quyền xác nhận, không do team Reception tự đặt theo phỏng đoán.

## 10. Quy tắc tránh xung đột và tiêu chí hoàn thành

1. Mỗi AI nhận rõ **tên người + mã task**. Nếu chỉ nói “Team Hoàng”, AI phải xác định thành viên trước khi sửa file có owner khác.
2. Làm trong clone/worktree riêng do người điều phối chuẩn bị. Không chạy ba AI cùng sửa một thư mục làm việc. Theo yêu cầu hiện tại chỉ làm `develop`; không tự tạo/sửa nhánh khác hoặc force-push. Phan Hoàng điều phối thứ tự tích hợp; mỗi người commit đúng file/task của mình, không dùng `git add -A` khi có thay đổi người khác.
3. Thay interface chung phải cập nhật consumer test và bàn giao, không gửi type mới rồi để người khác tự đoán. Không chép dữ liệu fixture thành giá/quy trình mặc định production.
4. Các test riêng nằm trong folder owner; test integration của Phan Hoàng kiểm tra kết nối các module. Không sửa test của người khác để che lỗi interface.
5. Task hoàn tất có code, test phù hợp, bằng chứng chạy, dependency thực, hướng dẫn cấu hình và handoff. Phân biệt mock/model giả, backend thật và model thật trong kết quả.
6. Không cần gọi LLM thật trong mọi unit test. Dùng scripted model/tool để kiểm tra state transition và các trường hợp lỗi; eval model thật dùng dataset/version/quota được thống nhất.
7. Phan Hoàng tạo scripts `test`/`typecheck` trong PH01 và ghi lệnh thực vào README; chưa có manifest thì không giả các lệnh đó đã chạy được. Mọi người chỉ chạy test phù hợp task, không chạy migration production.

Checklist chung trước đóng H07:

- Khách có thể yêu cầu kỹ thuật viên ngay, không bị buộc tự sửa.
- Unknown facts/thiếu hướng dẫn phù hợp không bị diễn giải thành an toàn; emergency theo workflow triage, không chờ Retrieval/ảnh mới cảnh báo.
- Nội dung chưa publish/đã revoke không được sử dụng; nếu revoke giữa phiên, kiểm tra lại và dừng/handoff.
- Khách xác nhận kết quả; gửi hết hướng dẫn không được tự đóng ticket. Chờ khách không tự pause SLA.
- Giá hiển thị đúng số/tiền tệ/điều kiện tool trả; thiếu dữ liệu phải thể hiện rõ, không đưa giá của khách khác làm ví dụ cá nhân.
- Resume/retry không tạo trùng ticket, assessment, self-help attempt hay yêu cầu phân công.
- Log/trace không chứa credential, full checkpoint hoặc PII không cần thiết.

## 11. Mẫu prompt cho AI từng người

```text
Tôi là <Phan Dũng | Dương Dũng | Phan Hoàng>, thuộc Team Hoàng.
Task hôm nay: <PD01–PD07 | DD01–DD06 | PH01–PH07>.

Đọc:
1. docs/KE_HOACH_HOAN_THIEN_5_TEAM.md
2. docs/teams/hoang/PHAN_CONG_3_THANH_VIEN.md
3. docs/THIET_KE_HOC_KINH_NGHIEM_SELF_HELP_GIA.md nếu task liên quan self-help/giá.

Kiểm tra git status, code hiện tại và AGENTS.md áp dụng.
Chỉ sửa folder/file thuộc người được nêu, không chỉ dựa vào quyền chung Team Hoàng.
Phân biệt đường dẫn dự kiến với module/API đã tồn tại; đọc contract version thực.
Không sửa nhánh khác, force-push, migration/database thật hoặc file owner khác.
Nếu thiếu dependency, ghi request tại docs/teams/hoang/requests/<slug-của-tôi>/,
rồi tiếp tục phần độc lập có thể làm trong phạm vi của tôi.
Mock chỉ dành cho test, không dùng để giả hoàn thành tích hợp production.
Triển khai và kiểm thử task, ghi handoff tại docs/teams/hoang/handoffs/<slug-của-tôi>/.
Báo file sửa, kết quả test, dependency chưa có và giới hạn còn lại.
```

Slug tương ứng: `phan-dung`, `duong-dung`, `phan-hoang`. Team Hoàng có quyền module reporting được ghi rõ ở mục 3; không có quyền sửa backend khác, DB, UI, RAG hay supervisor. Nếu xung đột với kế hoạch tổng thể, giữ giới hạn hẹp hơn và yêu cầu làm rõ trước khi sửa ngoài phạm vi.
