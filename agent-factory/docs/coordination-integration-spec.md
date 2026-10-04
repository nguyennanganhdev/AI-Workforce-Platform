# Đặc tả tích hợp Agent Factory với Coordination — bản đề xuất v0

Ngày viết: 2026-10-02. Người viết: phía Agent Factory.

**Trạng thái: đề xuất, chưa được duyệt.** Team Coordination (Đông) và team Backend
(Chiến) chưa xem tài liệu này. Phần "Yêu cầu" ở mục 4 được rút ra từ code hiện có của
Coordination; phần "Quyết định còn mở" ở mục 6 thuộc quyền của các team đó, tài liệu
này chỉ nêu câu hỏi và phương án. Không có code nào được viết hay sửa theo tài liệu này.

Nguồn đối chiếu:

| Phía | Ref | Ghi chú |
|---|---|---|
| Coordination | `origin/develop` @ `13b911f` | `agent-coordination/**`, `docs/teams/dong/**`. Các file này **chưa có** trên nhánh `devTeamPhai` |
| Review của team Đông | `origin/dev_TeamDong` @ `fec1746` | `docs/teams/dong/review_team_dong.md`, chưa vào `develop` |
| Factory | `devTeamPhai` @ `649d3f0` | `agent-factory/**`. Thư mục này **chưa có** trên `develop` |
| Schema DB | `server/src/db/schema/tables.ts` | Bảng `agent_versions`, `agent_releases`, `agent_build_requests` |

## 1. Phạm vi

Trong phạm vi: một agent do Factory tạo trở thành participant trong phòng họp agent
của Coordination như thế nào, và cần những điều kiện gì.

Ngoài phạm vi: giao thức Reception ↔ Supervisor (team Đông đã có schema V2), ticket,
luồng duyệt phương án, DAG, và mọi thay đổi wire contract của Factory. Tích hợp
Factory với Backend nằm ở [đặc tả Backend](backend-integration-spec.md).

Ba nguyên tắc ranh giới:

- Factory không gọi Coordination và Coordination không gọi Factory. Backend đứng giữa.
- Factory tạo spec cho **một** agent. Nó không biết phòng, roster, supervisor, ticket
  hay tenant.
- `spec.resources` và `spec.defaultTools` chỉ là khai báo. Quyền gọi tool do grant và
  authorization lúc thực thi quyết định.

## 2. Hiện trạng đã kiểm chứng

| Thành phần | Trạng thái | Bằng chứng |
|---|---|---|
| Phòng họp, task board, mailbox, context builder | Có code | `agent-coordination/src/groupchat/**` |
| Supervisor (planner, approval flow) | Có code | `agent-coordination/src/supervisor/**` |
| Adapter AgentScope | Có code, chỉ nhận agent không tool | `src/adapters/agentscope_adapter.py` |
| Loader agent đã publish | **Chưa có** | `src/agents/` chỉ có `.gitkeep`; `config_loader.py` trong phân công chưa được viết |
| `AgentSessionProvider`, `ParticipantResolver`, `Authority` | **Chỉ là interface** | `src/groupchat/ports.py`, `src/supervisor/ports.py`; bản giả nằm trong `tests/` |
| Pin phiên bản AgentScope, ADR của D01 | **Chưa có** | Không có `pyproject.toml`/lockfile; review của team Đông ghi D01 "dở", D02 "chưa làm" |
| Backend publish agent version | **Chưa có** | Trên `develop`, `server/src/platform/` và `server/src/runtime/` chỉ có `.gitkeep`; không có code ngoài schema dùng `agent_versions`/`agent_releases` |
| Lưu kết quả Evaluation và duyệt admin cho agent | **Chưa có** | Schema không có bảng nào cho việc này; `agent_releases.status` chỉ có `draft`, `published`, `revoked` |
| Factory construction | Có, chạy độc lập | `agent-factory check`: 44 pass |
| Backend nối Factory | **Chưa nối** | Route `/api/agent-factory/*` không mount; adapter tham khảo lưu vào `agents.configuration` |

## 3. Luồng mục tiêu

```text
BQL mô tả agent
  -> Backend: xác thực, đọc catalogue đúng scope
  -> Factory POST /v1/constructions        (đặc tả Backend)
  <- spec + systemPrompt + specHash + verification
  -> Backend: kiểm tra integrity, lưu agent version (bản nháp)
  -> Evaluation -> admin duyệt -> publish   (mục 4 tài liệu phân công của team Đông)
  -> Coordination: ParticipantResolver.resolve(agent_version_id)
  -> AgentSessionProvider cấp agent đã ghim cho phòng
  -> Supervisor giao task, agent trả lời trong phòng
```

Ba bước cuối và bước lưu version là phần chưa tồn tại.

## 4. Yêu cầu rút ra từ code của Coordination

Mỗi yêu cầu ghi nguồn trong `agent-coordination/src/` trên `develop`.

**R1. Định danh là `agent_version_id`.** Participant, task, catalog và mailbox đều ghim
theo phiên bản agent đã publish (`groupchat/models.py`: `ParticipantSpec`,
`Participant`). Resolver không được thay bản mới nhất cho bản được ghim, và một
platform agent chỉ vào một phòng một lần (`groupchat/participants.py`). Hệ quả cho
Factory: mỗi artifact là một version bất biến; reconstruct tạo version mới, không sửa
tại chỗ. `specHash` không được Coordination dùng.

**R2. Supervisor chỉ biết `role`.** Catalog mà planner nhận là
`{participant: {agent_version_id, role}, task_readers}` (`supervisor/models.py`:
`CatalogEntry`). `role` là chuỗi 1–256 ký tự. `identity.role` của Factory (1–120 ký tự)
vừa với giới hạn này. Các field `goal`, `responsibilities`, `intent` của spec hiện
không được dùng để chọn agent.

**R3. System prompt dùng nguyên vẹn.** Agent AgentScope nhận `system_prompt` khi khởi
tạo. Giá trị phải là `systemPrompt` của artifact, bằng `renderCorePrompt(spec)`.
Hướng dẫn riêng của phòng được thêm bên ngoài core prompt; sửa core prompt thì artifact
không còn là bản đã verified.

**R4. Cấu hình model.** Adapter từ chối agent có `max_retries` khác 0, có
`fallback_model`, hoặc không lan truyền cancellation
(`adapters/agentscope_adapter.py`: `_validate`).

**R5. Chưa nhận agent có tool.** Adapter từ chối mọi agent có tool, MCP hoặc skill
đăng ký ("chỉ hỗ trợ no-tools profile cho đến khi có backend tool-grant adapter").
Theo đường in-process hiện tại, chỉ artifact có `spec.resources` rỗng và
`spec.defaultTools` rỗng mới chạy đúng: prompt của artifact có tool sẽ bảo agent gọi
một tool không tồn tại.

**R6. Đầu vào mỗi lượt không phải chat trực tiếp.** Adapter xóa lịch sử của agent rồi
gửi lại mỗi lượt: các message `room-context` (mỗi message phòng là một JSON), một
message `room-data` (`ticket_id`, `ticket_generation`, `ticket_context`, `task_board`)
và instruction của lượt. Context builder chọn tối đa 20 message gần nhất và 50 mail
đang chờ, lọc theo quyền đọc (`groupchat/context_builder.py`). Prompt do Factory sinh
giả định hội thoại trực tiếp qua `ag_ui_messages` và không biết định dạng này, nên
provider phải thêm phần hướng dẫn về phòng.

**R7. Đầu ra.** Text thường được nhận nguyên văn. Text bắt đầu bằng `{` bị parse như
JSON `{content, follow_up_requests: [{recipient_agent_version_id, content}]}`; sai dạng
thì lượt thất bại, không có repair hay retry. Text rỗng cũng thất bại. Output của
Factory là text `prompt_only` nên đáp ứng được, trừ trường hợp câu trả lời mở đầu bằng
`{`.

**R8. Thời gian.** Mỗi lượt có timeout mặc định 60 giây, tối đa 3600
(`TurnPolicy.timeout_seconds`). Hết giờ mà không xác nhận được việc hủy thì phòng dừng
ở trạng thái `outcome_unknown`.

**R9. Điều kiện vào phòng.** Resolver phải xác nhận đúng phiên bản đã qua Evaluation,
được admin duyệt và đã publish; thiếu bằng chứng thì từ chối
(`groupchat/ports.py`: `ParticipantResolver.resolve`). `verification.construction ===
"PASS"` của Factory là kiểm tra lúc tạo spec, không thay được Evaluation và duyệt admin.

## 5. Ánh xạ dữ liệu đề xuất

Đề xuất gửi team Backend. Adapter tham khảo hiện không ghi vào các bảng này.

| Output của Factory | Cột | Ghi chú |
|---|---|---|
| `spec` | `agent_versions.config` | Lưu nguyên vẹn để integrity check còn dùng được |
| `systemPrompt` | `agent_versions.instructions` | Phải bằng `renderCorePrompt(spec)` |
| `specHash` | `agent_versions.config_hash` | Chỉ đúng nếu `config` chính là spec; nếu `config` có thêm field thì lưu `specHash` riêng |
| `spec.identity.role` | `role` trong catalog của supervisor | Xem R2 |
| `spec.runtimeProfile` | `agent_versions.runtime`, `framework_version` | Không ánh xạ trực tiếp được: Factory ghi `openbot_builtin_v1`, cột chỉ nhận `langgraph`, `agentscope`, `remote`. Xem Q1 |
| `request.name`, `request.description` | `agent_build_requests.proposed_name`, `proposed_description` | `role` chưa có cột riêng |
| 422 `NEEDS_INPUT` | `agent_build_requests.missing_fields` | Mỗi thông tin thiếu là một issue, path `intent.missingInformation.N`, nội dung ở `message` |
| `ready` / `pending_resources` | `agent_releases.status` | Artifact pending không được publish; publish còn cần Evaluation và duyệt admin (R9) |

## 6. Quyết định còn mở

| # | Câu hỏi | Owner | Vì sao chặn |
|---|---|---|---|
| Q1 | Agent Factory chạy trong phòng bằng cách nào | Đông, cùng Chiến | Quyết định giá trị `runtime` và việc tool có dùng được không |
| Q2 | Backend lưu version và phát cho resolver qua API nào | Chiến | Chưa có code; resolver không có gì để gọi |
| Q3 | Kết quả Evaluation và duyệt admin lưu ở đâu, ai chạy Evaluation | Chiến, cùng Đông | R9 không kiểm tra được nếu không có nơi lưu |
| Q4 | Tool-grant adapter | Đông, cùng Quang và Chiến | R5: không có nó thì agent có tool không vào phòng được |
| Q5 | Supervisor có cần mô tả năng lực ngoài `role` không | Đông | R2: hiện planner chọn agent chỉ theo `role` |
| Q6 | Pin phiên bản AgentScope và ADR của D01 | Đông | `framework_version` là cột NOT NULL |

### Q1. Hai phương án chạy agent

| | A. In-process AgentScope | B. Gọi từ xa qua AG-UI |
|---|---|---|
| Cách làm | Provider dựng agent AgentScope từ `systemPrompt` | Coordination gọi runtime Openbot, nơi agent Factory đang chạy |
| `agent_versions.runtime` | `agentscope` | `remote` |
| Tool | Không dùng được cho tới khi có Q4 | Giữ nguyên tool, grant và readiness gate của Backend |
| Phần còn thiếu | Provider, loader (D02) | Adapter chuyển invocation sang `RunAgentInput`, đọc stream, hủy, đối soát; endpoint service-to-service |
| Hiện trạng | Adapter có sẵn, test dùng agent giả | Runtime built-in chỉ được phục vụ qua `/api/copilotkit` sau phiên đăng nhập người dùng; review của team Đông ghi chưa có adapter |

Ý kiến phía Factory: phương án A là đường ngắn nhất cho agent không tool, vì chỉ còn
thiếu provider. Bất kỳ agent nào có tool đều cần phương án B hoặc Q4. Factory không
cần đổi code cho phương án A với agent không tool. Nếu quyết định yêu cầu Factory ghi
một runtime profile khác `openbot_builtin_v1`, đó là thay đổi contract và phải sửa kế
hoạch đã duyệt trước.

## 7. Kiểm thử chấp nhận đề xuất

Chưa có test nào dưới đây được viết hay chạy.

| # | Tình huống | Kết quả mong đợi |
|---|---|---|
| T1 | Artifact không tool được lưu thành version, publish, vào phòng và chạy một lượt | Lượt thành công, câu trả lời về đúng phòng |
| T2 | Artifact có `spec.resources` khác rỗng, theo đường in-process | Bị từ chối trước khi gọi model |
| T3 | Version chưa qua Evaluation hoặc chưa được admin duyệt | Resolver từ chối |
| T4 | `instructions` bị sửa sau khi lưu | Backend phát hiện sai integrity, version không được phát |
| T5 | Agent trả lời bằng text mở đầu `{` nhưng sai dạng | Lượt thất bại có kiểm soát, phòng không treo |
| T6 | Reconstruct agent trong lúc một phòng đang chạy | Phòng giữ version đã ghim; version mới chỉ dùng cho phòng mới |

## 8. Việc tiếp theo

1. Gửi tài liệu này cho team Đông và team Chiến để trả lời Q1–Q6.
2. Sau khi Q1 và Q2 chốt, cập nhật mục 4 và 5 thành hợp đồng, kèm JSON Schema dùng
   chung cho TypeScript và Python.
3. Viết T1–T6 ở phía sở hữu tương ứng.
