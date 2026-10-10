# Plan Phase A — Builder của Bùi Hữu Nghĩa

Ngày cập nhật: 10/10/2026. Branch đề xuất: `feat/wf-builder`.

Nguồn: [kế hoạch chung](../../KE_HOACH_TRIEN_KHAI.md), đặc biệt mục 3, 6, 9, 14 và 17.4–17.9; định hướng bổ sung của Bùi Hữu Nghĩa trong phiên làm việc này.

Trạng thái: đã thực hiện phần độc lập của Phase A, bàn giao [schema, mẫu, khảo sát code, prompt và kiểm tra local](phase_a/README.md). Chưa có code production hoặc contract chung được freeze; BHN-01–14 và gate MA chưa hoàn thành. Tên field mới và chữ ký chưa có trong hợp đồng chung bên dưới là đề xuất cần thống nhất với owner; xem [STATUS.md](STATUS.md).

Cập nhật sau pull `a99d506`: Foundation đã có contract nền version 1; [đối chiếu mới](phase_a/PULL_UPDATE.md) ghi rõ DTO/ports đã dùng, mẫu canonical đã kiểm tra và phần policy/model adapter/fake còn thiếu. Các bước dưới đây dùng export có sẵn cho DTO nền, chỉ đề xuất bổ sung phần chưa có.

## 1. Định hướng sản phẩm đã chốt

- Builder chủ yếu dùng model để sinh thông tin/cấu hình agent từ yêu cầu bằng ngôn ngữ tự nhiên. Người dùng mô tả mục tiêu, xem đề xuất, chỉnh sửa và xác nhận.
- Làm hoàn chỉnh luồng tạo **một agent trước**, rồi mở rộng tạo nhiều agent trong một lần chat. Giữ task IDs hiện có; chưa triển khai batch orchestration/UI trước khi luồng một agent đạt tiêu chí ở mục 6.
- Có lựa chọn **model dùng để sinh agent**, từ các model và credential đã cấu hình mà người dùng được phép sử dụng. Lưu lựa chọn theo build session; kiểm tra khả năng structured output qua adapter hiện có và báo lỗi rõ nếu không đáp ứng. Không âm thầm đổi model người dùng đã chọn.
- Model dùng để sinh và model agent dùng khi chạy là hai cấu hình riêng. Có thể dùng cùng model, nhưng không tự ghi đè cấu hình runtime bằng lựa chọn trong Builder.
- Tự sinh hoặc chọn khi đủ dữ kiện; chỉ hỏi lại phần thiếu làm thay đổi nghiệp vụ, quyền, chi phí hoặc phạm vi cam kết. Mọi đề xuất đều cho người dùng xem/chỉnh trước xác nhận; phát hành vẫn là quyết định của người dùng sau validate/evaluate.
- “Tạo team” trong Builder là batch nhiều agent độc lập. Sau này tái sử dụng luồng một agent cho từng item, thêm tiến độ/lỗi/retry riêng. Group production chỉ được tập hợp khi runtime xử lý request.

| Nội dung | Cách Builder xử lý |
|---|---|
| Tên, mô tả, nhiệm vụ, system prompt | Model sinh theo yêu cầu; người dùng sửa được |
| Tool, KB, skill | Tự đề xuất từ tài nguyên có thật, khả dụng và đúng manager Scope; kèm lý do/coverage |
| Model runtime, context/react config | Đề xuất cấu hình phù hợp trên cấu trúc và mặc định hiện có; phân biệt với model sinh |
| Agent đã đáp ứng nghiệp vụ | Đề xuất reuse reference; thiếu năng lực thì revise cùng identity nếu phù hợp |
| Dữ kiện quan trọng còn thiếu | Hỏi làm rõ, không tự đoán cam kết |
| Capability bắt buộc không có | Trả blocker/MISSING_REQUIRED_CAPABILITY; giảm phạm vi phải được người dùng đồng ý |

## 2. Tận dụng repo và thư viện khi code

Trước mỗi phần triển khai, đọc implementation và test liên quan; ghi vào handoff phần tái sử dụng, phần cần adapter và lý do phần phải viết mới. Ưu tiên public API/extension point và dependency đã có. Không viết lại model client, agent loop, structured-output engine, credential store hoặc bộ UI tương đương khi repo đã cung cấp khả năng phù hợp.

Các điểm cần khảo sát theo mục 3 của kế hoạch chung (đường dẫn tính từ `platform_VP/agentscope`):

| Có sẵn | Mục đích tái sử dụng/đối chiếu |
|---|---|
| `src/agentscope/agent/`, `model/`, `formatter/` | Gọi model, agent loop, structured output và định dạng message qua abstraction hiện có |
| `src/agentscope/app/_service/_model.py`, `_router/_model.py`, `_service/_credential_binding.py` | Luồng model/credential hiện tại; xác định adapter/hook cần owner tích hợp |
| `examples/web_ui/frontend/src/hooks/useModels.ts`, `api/model.ts` | Danh sách/lựa chọn model và quy ước gọi API hiện có |
| `examples/web_ui/frontend/src/components/`, `hooks/` | UI primitives, form, chat và trạng thái tải/lỗi |
| `src/agentscope/app/storage/_model/_agent.py`, `_session.py` | Cấu trúc prompt, context/react và model/KB config; đối chiếu khi tạo manifest |
| `src/agentscope/app/rag/`, `src/agentscope/skill/`, `src/agentscope/tool/` | Khả năng KB, skill, toolkit hiện hữu; truy cập tài nguyên thông qua port/adapter đúng scope |

Đây là danh sách điểm cần khảo sát, không phải xác nhận mọi API hiện có đã phù hợp Workforce. Không import private service xuyên module hoặc sửa file owner khác; hook/contract còn thiếu ghi integration request cho owner. Không dùng `AgentCreate` có vòng đời gắn team để thay luồng draft/publish agent độc lập.

Chỉ dẫn phải đưa vào prompt cho AI triển khai:

> Trước khi code, kiểm tra code và test hiện có của repository cùng API của AgentScope/thư viện đã cài. Tái sử dụng abstraction, component, service và extension point phù hợp; viết adapter hoặc phần nghiệp vụ còn thiếu. Nêu rõ phần được tái sử dụng trong bàn giao. Giữ ownership, scope và contracts; phần cần sửa ngoài module phải ghi yêu cầu tích hợp. Không tự tạo implementation trùng hoặc thêm dependency khi chức năng hiện có đáp ứng được.

Chỉ dẫn dự kiến cho prompt Builder:

> Ưu tiên agent, tool, KB và skill đã có trong dữ liệu được backend cung cấp, đúng scope và còn khả dụng. Tự đề xuất thông tin đủ căn cứ, kèm lý do và capability coverage; hỏi phần quan trọng còn thiếu. Chỉ tham chiếu ID/version có thật. Không bịa tài nguyên, credential hoặc khả năng theo dõi. Sinh cấu hình một agent độc lập theo schema; không tự phát hành hay tạo group/job production.

Backend phải cung cấp metadata đã lọc quyền và xác minh output bằng code; prompt không thay thế authorization, schema validation hoặc capability checks. Không yêu cầu model Builder tự đọc toàn bộ source repo; repo được AI triển khai khảo sát, còn Builder nhận catalog/context phù hợp từ backend.

## 3. Các bước Phase A

1. **Requirement và tự động lựa chọn:** đặc tả input gồm yêu cầu, lựa chọn model sinh và build context; output gồm đề xuất một agent, dữ liệu tự chọn/lý do, câu hỏi còn thiếu và blocker. Scope do backend xác định. Chốt phần chỉ tạo công việc, theo dõi đến hoàn tất và xác nhận đóng.
2. **Schema policy:** đề xuất structured-output schema và `AsyncHandlingPolicy` cho capabilities/event types, facts bắt buộc, completion condition, human confirmation/timeout behavior. Không chứa ticket/job/endpoint/roster cố định. Phân biệt hỗ trợ response-only/interactive/external-tracking theo capability và effect; trạng thái operation thực tế do runtime xác minh.
3. **Hợp đồng đầu vào:** chốt dữ liệu từ RegistryPort, AsyncProtocolPort và AgentReusePort; semantics coverage/blocker, protocol snapshot/hash, catalog revision và lựa chọn model/credential reference. Không đưa secret vào manifest, prompt hay mẫu dữ liệu.
4. **Validation và reuse:** thống nhất nơi đặt policy trong manifest và evaluation snapshot với Lifecycle; reuse agent đủ năng lực, revise cùng identity khi thiếu tracking, recheck quyết định trước tạo draft. Luồng một agent dùng DraftPort; BuildBatchPort được giữ trong thiết kế mở rộng sau.
5. **Mẫu và kiểm tra hợp đồng:** chuẩn bị payload hợp lệ/không hợp lệ, ma trận hành vi ở mục 5 và yêu cầu fake. Khi DTO chung đã có, kiểm tra mẫu bằng chính schema đó. Nếu chưa có, ghi trạng thái chờ; không tạo bộ DTO production chung thứ hai.
6. **Bàn giao:** cập nhật STATUS.md, ghi `INTEGRATION_REQUEST_<task-id>.md` theo mẫu mục 14 cho các thay đổi contract/hook cần owner thực hiện. Tách rõ đề xuất của Nghĩa và phần đã được owner thống nhất.

## 4. Phụ thuộc cần chốt

| Owner | Đầu ra cần cho Builder |
|---|---|
| Nguyễn Chí Hoàng | DTO/ports chung, vị trí policy và cấu hình model sinh trong contract, export Python/JSON Schema/TypeScript, adapter model/credential nếu cần |
| Nguyễn Phương Đông | AsyncToolProtocol/tool snapshots, fake protocol, chữ ký cụ thể kiểm tra coverage; trường correlation, receive-status/status-query, timeout và readiness |
| Phó Tiến Anh | Validation/evaluation snapshot chứa policy + protocol hash, dữ liệu reuse candidate, contract DraftPort và hướng mở rộng BuildBatchPort |

Có thể làm đề xuất requirement/policy và ma trận mẫu trước khi các module hoàn chỉnh. Không cần chờ workflow worker, provider ingress hoặc dịch vụ đối tác thật để lập schema. Chốt Phase A cần thống nhất contract với owner; phần đang thiếu được ghi rõ trong handoff. Fake chỉ nằm trong test/demo, không trả thành công giả trong production.

## 5. Ma trận kiểm tra dự kiến

- Model sinh được chọn riêng; không làm thay đổi model runtime ngoài xác nhận; model/credential không khả dụng có lỗi rõ.
- Output sai schema được xử lý với retry hữu hạn; không tạo draft từ output không hợp lệ.
- Tự chọn tool/KB/skill có thật trong scope; từ chối ID bịa hoặc tài nguyên khác scope.
- Tra cứu đồng bộ không cần event channel; booking confirmed ngay không bị ép polling.
- Pending operation cần tracking có protocol/correlation và Provider Event hoặc MCP status-query phù hợp.
- Tool chỉ create không đáp ứng cam kết tracking: báo thiếu capability, không tự giảm phạm vi.
- Agent đủ năng lực thì reuse; thiếu tracking thì đề xuất revise cùng identity.
- Manifest không chứa runtime ticket/job/group hoặc đồng đội cố định; build không sinh production operation.

Đây là ca dự kiến cho schema và triển khai tiếp theo, chưa phải test đã chạy/pass. Phase A kiểm tra mẫu/contract có sẵn; test hành vi Builder chạy ở giai đoạn triển khai.

## 6. Điều kiện chuyển giai đoạn

**Phase A xong:** requirement/policy schema và chữ ký liên quan đã thống nhất; mẫu dùng cùng contract; đầu vào thật/fake cùng dependency còn mở được ghi rõ. Bàn giao proposal riêng chưa đủ để tuyên bố gate MA chung hoàn thành.

**Luồng một agent đủ để mở rộng batch:** chọn model sinh → nhập yêu cầu → reuse check → tự đề xuất và hỏi thiếu → xác nhận → create/update draft → validate/evaluate → người dùng phát hành qua Lifecycle. Có test phần Builder cho schema lỗi, thiếu capability, retry/idempotency và scope; ghi rõ phần nối Lifecycle thật hay fake. Sau đó mới mở rộng nhiều item với tiến độ/lỗi/retry riêng, dùng lại luồng một agent.

Phase B triển khai capability checks/UI bằng fake ports; Phase C nối module thật; Phase D kiểm thử hồi quy và bàn giao theo kế hoạch chung. Định hướng single-first không bỏ các nhiệm vụ batch và async đã được phân công.
