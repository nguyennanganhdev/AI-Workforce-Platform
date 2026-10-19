# Phối hợp ngang giữa agent và điểm dừng runtime

## Quy tắc

Leader giao mục tiêu; specialist trao đổi trực tiếp qua `TeamSay`. Nội dung có
chữ `@agent` đơn thuần không phải một lời gọi định tuyến. Tool yêu cầu tên/handle
trong roster, nhiệm vụ cụ thể và loại thông điệp.

- `question`: đăng ký agent đang chờ, agent cung cấp và `handoff_id`.
- `answer`: trả lời bằng `in_reply_to`; runtime chuyển đến bên đang chờ. Kết quả
  chia sẻ được chuyển cho Leader qua cùng cơ chế inbox/outbox bền vững.
- `progress`: không phải kết quả cuối và không đủ để worker kết thúc lượt.
- `result`/`error`: báo kết quả hoặc phần không hoàn tất, kèm nguồn khi có.
- Worker gọi `requires_user_input` được chuyển thành `user_input_proposal` nội bộ.
  Chưa hỏi người dùng và chưa làm cả nhóm ngủ. Reply owner xét Shared Context,
  hỏi đồng đội nếu thiếu dữ liệu nội bộ, rồi mới duyệt câu hỏi thực sự của người dùng.
- Chỉ một câu hỏi đã duyệt được chờ trả lời. Trong lúc này worker không gọi model/tool.
- `conflict`: phải dẫn ít nhất hai event nguồn hiện hành; chuyển reply owner xét.

Ví dụ tổng quát: agent lập phương án hỏi agent tra cứu tài nguyên, nhận kết quả,
rồi nhờ agent tính toán. Dữ liệu quan trọng nằm trong Shared Context; agent mới
tham gia đọc dữ liệu chung, không yêu cầu người dùng gửi lại đầu ra của đồng đội.
Trao đổi độc lập dùng `context_mode=isolated`, mặc định `result_scope=caller`;
nội dung riêng không tự phát ra shared packet hay gửi cho Leader.

## Ba chế độ định tuyến của team

Chế độ do server gán khi tạo team. `peer` lưu ở `TeamData.collaboration_mode`.
`collaborative` là team `reviewed` có cờ `TeamData.direct_member_routing=true`;
dùng cờ riêng để bản phát hành cũ đọc team này như `reviewed` khi quay lui.

| Chế độ | Dùng cho | Thành viên với nhau | Trả lời khách |
| --- | --- | --- | --- |
| `reviewed` | Team tạo trước 19/10/2026, nhóm BQL | Chỉ `question`/`answer` | Leader |
| `collaborative` | Phiếu đối tác và team của kênh tạo mới | `question`/`answer`, `handoff`, `result` có `to` | Leader |
| `peer` | Chat của người dùng trên web | Như `collaborative` | Thành viên tự đăng kết quả |

Trong `collaborative` và `peer`:

- Worker gửi `handoff` cho một đồng đội: đăng ký phụ thuộc như `question`, người
  gửi ngủ ở `waiting_peer`. Đồng đội trả `result` không kèm `to`; runtime gửi về
  người đã chuyển việc, không gửi Leader. Không được `handoff` cho Leader.
- Worker gửi `result` có `to=<đồng đội>`: chỉ người nhận đó nhận. Leader không
  nhận bản sao nhưng vẫn tính thành viên đó đã xong khi chờ báo cáo.
- `error` luôn đến Leader, vì Leader quyết định phần việc bị lỗi.

- Worker vừa có việc Leader giao vừa nhận một phần việc đồng đội chuyển sang
  phải ghi `to` khi gửi `result`, để runtime biết kết quả trả cho việc nào.

`WORKFORCE_TEAM_COLLABORATION=reviewed` rồi khởi động lại app: mọi team
`collaborative`, kể cả team đã tạo, quay về định tuyến cũ; team mới tạo là
`reviewed`. Team `peer` không đổi. Trong team `reviewed`, `handoff` giữa thành
viên bị từ chối với hướng dẫn dùng `question`.

## Leader quyết định điểm dừng

`TeamSay(to=<worker>, kind="handoff", resolution=...)`:

| Resolution | Kiểm soát |
| --- | --- |
| `complete` | Phải có result/answer của worker cùng bằng chứng tool/provider hiện hành, đúng task; không còn dependency đang chờ. |
| `verify` | Yêu cầu kiểm chứng bổ sung, tối đa số lần cấu hình; không xóa ngân sách đã dùng. |
| `stop` | Dừng assignment, giải phóng các agent đang chờ dependency đó; phải nói rõ phần chưa hoàn tất. |

Đủ nguồn là điều kiện cần; Leader vẫn phải xét nguồn có đáp ứng mục tiêu hay không.
Validator không chứng minh mọi câu văn của model đều đúng chỉ vì đã đính kèm nguồn.

Branch đã `completed` có thể nhận yêu cầu bổ sung cụ thể, nhưng giữ nguyên counters
trong chu kỳ hiện tại. Branch đã `stopped` do giới hạn không được hồi sinh bằng
một handoff đổi tên. Yêu cầu mới từ người dùng mở chu kỳ xử lý mới **trong cùng
ticket/group**, không tạo ticket mới và không mất lịch sử.

Kết thúc trao đổi nội bộ không thay đổi lifecycle ticket thành `closed`.
`ContextDelta.status` qua TeamSay bị từ chối; đóng ticket thuộc workflow/customer.
Khi người dùng chủ động `@agent`, agent đó là reply owner của lượt và vẫn có thể
trả lời trực tiếp, đồng thời lưu kết quả quan trọng vào Shared Context.

## Giới hạn và phép đo

Cấu hình server trong `.env.example`, không do Builder/model chỉnh:

| Biến | Mặc định |
| --- | ---: |
| `COLLABORATION_MAX_EXCHANGES` | 24 |
| `COLLABORATION_MAX_MODEL_CALLS` | 16 |
| `COLLABORATION_MAX_TOKENS` | 200000 |
| `COLLABORATION_MAX_ACTIVE_SECONDS` | 180 |
| `COLLABORATION_MAX_VERIFICATIONS` | 2 |

Khóa ngân sách: user/group/task/session + revision yêu cầu người dùng. Mỗi worker
có assignment budget riêng; tạo thread/idempotency key mới không đặt lại counters.
Task ID phải do runtime cấp. Counters, dependency, quyết định và receipt được lưu
trong JSON Shared Context hiện có; bản này không thêm bảng/migration.

- Input: đo sau khi ghép context, bằng token counter của model.
- Output: dùng usage của provider; thiếu usage thì đếm nội dung trả về. Stream bị
  ngắt vẫn được tính phần nhận được, có thể tính dư với provider gửi cumulative chunks.
- Thời gian: dùng monotonic clock, tính lúc gọi model (kể cả stream) và chạy tool;
  không cộng thời gian chờ người dùng, peer, sự kiện ngoài hay SSE reconnect.
- Chặn trước lời gọi tiếp theo khi hết ngân sách; output usage được chốt cuối
  lời gọi nên tổng token có thể vượt ngưỡng bằng phần output của lần gọi cuối.
  Đây không phải hard cap thanh toán của provider.
- Chi phí summary có metrics riêng trong Shared Context; hiện chưa gộp vào
  assignment counters. Không dùng counters này làm báo cáo tổng hóa đơn LLM.
- Lặp nội dung chuẩn hóa mà không có evidence mới bị chặn; phát hiện vòng dependency
  A → B → A. Paraphrase không được coi là dedupe ngữ nghĩa hoàn hảo, nhưng vẫn bị
  giới hạn bởi số lượt/model/token/thời gian.

Shared packet bỏ receipts/signature nội bộ để không phình prompt. Trong lượt dài,
packet được làm mới khi có event mới trước lời gọi model tiếp theo; không làm mới
chỉ vì có bản ghi metrics. Dữ liệu nguồn không bị xóa.

## Phục hồi và hai đường vào

Trước khi thay đổi dependency, TeamSay ghi durable intent. HandoffDispatcher phát
lại intent nếu lỗi xảy ra giữa reservation, event và gửi inbox. Receipt và marker
ngăn tính lượt/phát lại trùng. Intent của revision người dùng cũ bị hủy khi phục hồi.

Chat trực tiếp: ChatService nối TeamSay, pause gate, refresh context, metering và
Leader review gate. Các điều kiện dựa trên task/capability, không hard-code du lịch.

API đối tác: SqlRuntimeContinuation tiêm cùng policy và đo budget/time ở ranh giới
runner; kiểm tra usage checkpoint trước khi kết quả được commit. Aggregate budget
của runner tách khỏi counters từng agent để tránh cộng hai lần vào cùng counter.
Mỗi lần thử runner giữ tối thiểu một lượt ngân sách, kể cả khi runner lỗi trước
khi trả checkpoint; thời gian ở boundary là thời gian invoke. Runner phải trả
quyết định chờ, không giữ invoke treo đến khi người dùng/provider trả lời.
Engine được inject qua `LeaderTurnRunner` phải dùng cùng TeamSay/middleware để có
peer coordination, và báo usage thực. Source hiện chưa có implementation production
của interface này; kiểm thử adapter không thay thế kiểm thử API → model/MCP thật.

## Kiểm thử và vận hành

Các regression nằm trong `tests/team_collaboration_test.py`,
`tests/team_member_middleware_test.py`, `tests/team_say_shared_context_test.py`,
`tests/team_shared_context_test.py`, `tests/leader_evidence_middleware_test.py` và
`tests/workforce/orchestration/`.

Bao gồm: peer wait/resume, worker thực không gọi thêm model lúc chờ, review câu
hỏi, một câu hỏi đang chờ, vòng dependency, replay/restart, crash giữa reservation
và delivery, intent stale, bằng chứng khi complete, giới hạn verify/model/token/time,
không đóng ticket, yêu cầu mới, isolated exchange và guard usage API đối tác.

Khởi động lại backend để nạp code/prompt/cấu hình mới. Không cần tạo lại agent,
reset database, xóa session, hay khởi tạo lại Redis/MinIO. Chưa có xác nhận chạy
end-to-end với model/MCP thật cho thay đổi này; cần chạy smoke thực tế trước phát hành.

Kết quả kiểm tra ngày 13/10/2026:

- Bộ regression chat/team/shared-context và toàn bộ `tests/workforce/orchestration/`:
  **421 passed, 128 subtests passed, 1 failed**. Không skip/bypass test lỗi.
- Test còn lỗi là `PhaseAAcceptance.test_artifacts_have_no_drift`: artifact schema
  Phase A chưa đồng bộ các trường Shared Context của `PinnedRuntimeContext` đã có
  trước thay đổi này. Bản sửa runtime không sửa artifact đó.
- Frontend `corepack pnpm --filter frontend build`: thành công, còn cảnh báo bundle lớn.
- Ruff ở các file runtime cốt lõi vừa sửa và `git diff --check`: không có lỗi.
