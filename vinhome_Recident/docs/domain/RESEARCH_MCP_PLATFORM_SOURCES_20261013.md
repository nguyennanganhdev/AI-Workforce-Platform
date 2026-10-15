# Nghiên cứu nguồn chuẩn MCP và đối chiếu hợp đồng Vinhomes

Ngày: 2026-10-13. Phạm vi: source trên `dev_Vinhome`, HEAD `8a6c167dc9426479c3528ea5953ff94a20fdfa84`; nghiên cứu chỉ đọc và tài liệu. Không gọi model, chạy Agent, gọi nghiệp vụ MCP hoặc thay đổi VPS. Kết quả dưới đây là kiểm tra mã nguồn và đặc tả, không phải nghiệm thu kết nối platform thật.

**Quyết định mới sau nghiên cứu:** giữ 7 tool, platform quản lý session/ngoại lệ; không triển khai màn hình BQL hoặc tool escalation tại domain. Phần đề xuất escalation ở mục5 đã được thay bởi [hợp đồng v2](MCP_PLATFORM_V2.md); bảng nguồn vẫn mô tả HEAD khảo sát ban đầu.

## 1. Kết luận

MCP domain đã giới hạn đúng hướng vào **7 tool xử lý ticket đã bàn giao**. Cần ưu tiên làm rõ quyền theo workflow, kết quả/lỗi và phiên bản tích hợp trước khi tăng số lượng tool. Không cần mở lại chức năng Reception hay định danh căn hộ cho platform. Bằng chứng catalog hiện tại nằm tại [platform_mcp.py:51](../../services/vinhomes-api/src/vinhomes_api/platform_mcp.py#L51) và [declaration:81](../../deploy/platform/vinhomes-declaration.json#L81).

Phân biệt ba thứ: token xác thực bên tích hợp; ticket được phép truy cập; quyền thực hiện từng hành động. Hiện tại token dùng chung của tenant cùng kiểm tra ticket đang có `platform_links` hoạt động **chưa ràng buộc riêng một workflow với một ticket**. Đây là giới hạn thiết kế đã xác định bằng source, không phải bằng chứng đã có xâm nhập. [platform_mcp.py:103](../../services/vinhomes-api/src/vinhomes_api/platform_mcp.py#L103), [platform_work.py:70](../../services/vinhomes-api/src/vinhomes_api/platform_work.py#L70).

## 2. Nguồn chính thức và phiên bản

Truy cập `/specification/latest` ngày nghiên cứu chuyển hướng tới **2026-07-28**. Đây là phiên bản tài liệu tra cứu; không được suy ra runtime hiện tại đã hỗ trợ phiên bản này. [MCP specification](https://modelcontextprotocol.io/specification/2026-07-28).

Các điểm chuẩn cần dùng:

| Chủ đề | Quy tắc từ nguồn chính thức | Nguồn |
|---|---|---|
| Authorization | Authorization tùy chọn; HTTP có hỗ trợ thì nên theo đặc tả. Bearer gửi trên từng request; OAuth token phải đúng audience; scope tuân thủ quyền tối thiểu. | [Authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization) |
| Tool output | `outputSchema` tùy chọn; nếu khai báo, structured result phải khớp schema. Lỗi thực thi dùng `isError: true`. Annotations không thay kiểm soát quyền. | [Tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools) |
| Transport | Phiên bản 2026-07-28 bỏ GET stream và protocol sessions; metadata/version có thay đổi. Origin không hợp lệ phải bị từ chối. | [Streamable HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http) |
| Thu hẹp quyền | Tránh wildcard scope và quyền quá rộng; vẫn phải kiểm tra quyền tại server. | [Security best practices](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices) |

**Suy luận áp dụng cho dự án:** không tự động nâng SDK hoặc đổi handshake theo tài liệu mới. Hai bên phải chốt protocol hỗ trợ và kiểm thử tương thích. Source đang dùng `mcp>=1.30,<2`; bài kiểm tra trực tiếp gửi `initialize` với `2025-03-26`. Hai dữ kiện này không đủ chứng minh tương thích 2026-07-28. [pyproject.toml:21](../../services/vinhomes-api/pyproject.toml#L21), [test_platform_tools.py:841](../../services/vinhomes-api/tests/test_platform_tools.py#L841).

## 3. Những gì source hiện tại đã bảo vệ

| Hạng mục | Bằng chứng hiện tại | Giới hạn cần ghi vào handoff |
|---|---|---|
| Xác thực MCP | Token ít nhất 32 ký tự; so sánh constant-time mỗi request; sai token trả 401. [MCP:103-127](../../services/vinhomes-api/src/vinhomes_api/platform_mcp.py#L103) | Static shared secret, chưa có expiry/scope/issuer claims hoặc OAuth discovery trong wrapper này. Không mô tả đây là OAuth chuẩn hoàn chỉnh. |
| Cách ly tenant/ticket | Transaction đặt `app.tenant_id`; ticket phải thuộc tenant và link trạng thái hoạt động. [MCP:36](../../services/vinhomes-api/src/vinhomes_api/platform_mcp.py#L36), [work:70](../../services/vinhomes-api/src/vinhomes_api/platform_work.py#L70) | Người giữ key biết ID ticket hoạt động khác cùng tenant vẫn vượt qua kiểm tra này; không có principal/workflow đối chiếu. |
| Chống lặp write | Receipt theo tenant + `client_reference`; khóa giao dịch; đối chiếu tool/ticket và payload hash; rollback khi từ chối. [work:348-387](../../services/vinhomes-api/src/vinhomes_api/platform_work.py#L348) | Phải giữ nguyên reference khi retry; reference mới là yêu cầu mới. Receipt cũ không có hash tiếp tục replay kết quả đã lưu. |
| Bảo vệ dispatch | Từ chối ticket đã kết thúc, cần phương án, an ninh và work order đang hoạt động; tự queue khi hết nhân viên. [work:390-440](../../services/vinhomes-api/src/vinhomes_api/platform_work.py#L390) | Không thêm tool bypass các gate này. |
| Đổi lịch/hủy | Đổi lịch chỉ queued/offered/accepted; hủy bị chặn khi arrived/in_progress/completed hoặc việc an ninh. [work:444-516](../../services/vinhomes-api/src/vinhomes_api/platform_work.py#L444) | Hủy có thể thực hiện khi en_route theo code hiện tại; cần diễn đạt đúng, không tự đổi quy tắc thành chặn mọi việc đã lên đường. |
| Quyền cư dân | Catalog không có tool trả lời báo giá hoặc xác nhận hoàn thành thay cư dân. [test:863-867](../../services/vinhomes-api/tests/test_platform_tools.py#L863), [hợp đồng:103](NOI_WORKFORCE_V1.md#L103) | `requires_consent:false` của platform không cấp quyền thay cư dân bấm các thẻ domain. |
| Browser origin | API middleware chặn cross-site hoặc Origin không cùng host/allowlist với mutation. [main:98-109](../../services/vinhomes-api/src/vinhomes_api/main.py#L98) | FastMCP tắt riêng DNS-rebinding protection; cần kiểm thử toàn chuỗi gateway/API, không kết luận hoàn toàn không kiểm Origin. [MCP:46-49](../../services/vinhomes-api/src/vinhomes_api/platform_mcp.py#L46) |

## 4. Các khoảng trống cần maintain trước mở rộng

### 4.1. Ràng buộc quyền của từng workflow — P0 trước kết nối thật

`ticket_id` là tham số model cung cấp, không phải bằng chứng quyền. `_ticket()` chỉ kiểm tra link hoạt động trong tenant. [work:70-85](../../services/vinhomes-api/src/vinhomes_api/platform_work.py#L70).

**Đề xuất thiết kế, chưa triển khai:** tách integration principal khỏi quyền thực thi của workflow; phía server xác minh binding do hệ thống cấp giữa `integration_id / workflow_id / ticket_id / allowed_actions / expiry / revision`. Không nhận `workflow_id` tự khai báo làm bằng chứng. Có thể dùng capability được ký hoặc grant lưu DB truyền qua trusted transport; chốt cách triển khai cùng platform, không bắt model tự giữ private secret. Ràng buộc còn hiệu lực trên mọi write/read và khi revoke/link đóng. Receipt replay phải chỉ trả cho principal được phép, tránh để reference biết trước trở thành đường đọc ngoài quyền.

**Nghiệm thu:** workflow A không đọc/ghi ticket B cùng tenant; token sai tenant, grant hết hạn/revoke, thiếu binding đều bị từ chối; retry hợp lệ cùng principal vẫn trả một receipt; không chạm ticket ngoài quyền khi concurrent calls.

### 4.2. Lỗi và structured output — P0/P1

Wrapper `run()` trả chuỗi JSON khi thành công; lookup bị từ chối trả plain text, write trả `{status:"failed",reason}`. Test đang cố ý xác nhận lookup ticket lạ có `isError=false`. [MCP:34-44](../../services/vinhomes-api/src/vinhomes_api/platform_mcp.py#L34), [test:874-885](../../services/vinhomes-api/tests/test_platform_tools.py#L874).

Discovery đã có `outputSchema` do FastMCP sinh từ `-> str`, nhưng chỉ mô tả lớp `{result:string}`; không kiểm tra được cấu trúc domain bên trong. Cần nói đúng là **thiếu schema nghiệp vụ**, không phải hoàn toàn thiếu outputSchema. [MCP:52](../../services/vinhomes-api/src/vinhomes_api/platform_mcp.py#L52), artifact discovery riêng ở `deploy/test-accounts-20261013/domain-audit/tools-discovery-maintain.json:20` (file ignored, chỉ dùng bằng chứng nội bộ).

**Đề xuất:** định nghĩa object có version, typed data, mã lỗi ổn định, message, retryable và correlation_id; adapter MCP trả `isError=true` cho lỗi thực thi. Phân biệt 401/403 transport với business failure/queued/pending/success. Giữ text JSON tương thích trong giai đoạn chuyển đổi. Thay đổi contract phải version hóa và cập nhật parser/tests bên platform cùng lúc.

**Nghiệm thu:** schema validate mọi success/failure; lỗi ngày giờ, stale revision, forbidden, unavailable có mã xác định; queued không bị hiểu là failed, pending không bị hiểu là nhân viên đã nhận; stack trace/key không lộ.

### 4.3. Trạng thái hoàn thành dễ hiểu sai — P0 hợp đồng

`ticket_get` xuất top-level `status:"completed"` cho cả `resolved` và `closed`. Cùng response `resolved` vẫn có `completion_request.waiting_for_resident=true`; test khẳng định hai điều cùng tồn tại. [work:131-152](../../services/vinhomes-api/src/vinhomes_api/platform_work.py#L131), [test:377-385](../../services/vinhomes-api/tests/test_platform_tools.py#L377).

**Đề xuất:** chốt riêng `work_completed`, `result_published`, `resident_confirmation_pending`, `resident_accepted`, `ticket_closed`; không dùng một `completed` chung làm bằng chứng cư dân đã chấp thuận. Tên/trạng thái cụ thể phải thống nhất với parser hiện tại trước đổi; có thể thêm typed fields tương thích rồi deprecate alias cũ. Đây là lỗi diễn đạt hợp đồng cần xử lý, chưa đủ bằng chứng platform thật đang đóng nhầm ticket.

### 4.4. Allowlist, trace, giới hạn tải — P1

Declaration liệt kê 7 tools nhưng profile vẫn `tools_allow:["vh_*"]`. [declaration:32](../../deploy/platform/vinhomes-declaration.json#L32). Đề xuất explicit allowlist theo version và profile; catalog mới không tự trở thành quyền mới. Tool readOnly annotations là metadata; quyền vẫn phải server xác minh.

MCP wrapper chưa thấy giới hạn theo principal/tool và read-call audit riêng; gateway template cũng chưa có `limit_req/limit_conn`. [MCP:33-44](../../services/vinhomes-api/src/vinhomes_api/platform_mcp.py#L33), [gateway:43](../../deploy/nginx/gateway.conf.template#L43). Cần xác minh lớp hạ tầng khác trước kết luận production không có rate limit. Đề xuất quota theo principal, timeout, bounded input/output, audit không ghi token/PII, correlation xuyên ticket/workflow/client_reference. `ticket_get` hiện đọc toàn bộ milestones theo ticket không pagination; cần giới hạn cho ticket dài. [work:127-154](../../services/vinhomes-api/src/vinhomes_api/platform_work.py#L127).

## 5. Mở rộng tool tối thiểu, theo nhu cầu thực tế

Đây là đề xuất cần nhập vào kế hoạch nghiệp vụ của domain, không phải catalog đã có.

| Nhu cầu | Cách đáp ứng ưu tiên | Khi nào cần tool mới | Điều kiện chống mở rộng sai |
|---|---|---|---|
| Cập nhật tiến độ/SLA/báo giá/ảnh đã có bao nhiêu | Bổ sung typed fields vào `vh_ticket_get`; thời hạn đã có `response_due_at/resolution_due_at`. [work:93-154](../../services/vinhomes-api/src/vinhomes_api/platform_work.py#L93) | Không cần tách nhiều lookup trùng dữ liệu | Không tra lại người/căn hộ đã có trong ticket |
| Cần BQL tiếp nhận: dispatch bị từ chối, khiếu nại, thiếu nghiệm thu, trường hợp an ninh | Một action **đề xuất `vh_ticket_escalate`** tạo yêu cầu escalation đúng management unit, có reason/type, reference, trạng thái nhận/xử lý; priority do policy domain tính | Khi platform cần tạo được nhiệm vụ tiếp nhận thực, thay vì chỉ ghi note hoặc nói sẽ chuyển | Không tự phê duyệt, không ghi rằng BQL đã nhận khi mới queued; owner và notification phải tồn tại ở domain |
| Hành động timeout/không rõ kết quả | Replay cùng client_reference; nếu cần thêm `operation_receipt` read theo ticket và principal | Chỉ khi platform không thể an toàn replay hoặc cần reconciliation chủ động | Không mở receipt toàn tenant, không tạo reference mới khi retry |
| Cần ảnh hoặc tài liệu bằng chứng thực tế | Giữ count/note hiện tại; thống nhất với partner có nhận media không trước | Có thể thêm bounded `vh_ticket_evidence_get` nếu nghiệp vụ thật đòi xem nội dung, kèm short-lived URL/ticket scope | Hiện handoff hướng text; không tự public MinIO hoặc gửi tất cả ảnh cư dân |
| Công việc cần phương án/duyệt BQL | Giữ fail-safe và route BQL theo nghiệp vụ hiện tại | Chỉ thêm proposal/status tool khi có quyết định mở luồng phương án cho platform | `NOI_WORKFORCE_V1.md:7` quy định Reception hiện `plan_required=False`, luồng phương án cũ giữ nguyên; không coi proposal tool là điều kiện bắt buộc cho V1 |

Catalog không mở lại create_ticket, chọn/xác định cư dân/căn hộ, công nợ/booking/khách/thẻ toàn hộ, generic SQL, phê duyệt báo giá thay cư dân, QC tự duyệt hoặc tự xác nhận đóng yêu cầu. Trước mỗi tool mới cần mô tả: hành động sau bàn giao nào chưa được 7 tool/envelope/event đáp ứng; ai sở hữu quyết định; quyền; idempotency; event; tiêu chí nghiệm thu âm/dương.

## 6. Phần tài liệu kỹ thuật cần bàn giao platform

1. **Compatibility matrix:** MCP protocol đã xác minh, SDK/version/image digest, transport, init/metadata/headers, đường endpoint không redirect, timeout và cách reconnect; phân biệt protocol với version nghiệp vụ.
2. **Authorization contract:** integration principal, ticket/workflow binding, action scopes, expiry/revoke/rotation, HTTP 401/403, kênh giữ key riêng; không đưa token thật vào tài liệu Git.
3. **Tool catalog có schemas:** inputs/typed outputs/mã lỗi, quyền/preconditions/side effects, reference replay, request hash conflict, receipt retention và exact allowlist/profile version.
4. **State/event contract:** work order khác ticket; resolved khác cư dân accepted/closed; event version/sequence/dedupe/out-of-order, snapshot reconciliation, retry budget.
5. **Acceptance pack không model:** fixture giả, unknown/wrong tenant/workflow, revoked/expired grant, concurrent/idempotent replay, refusal/error schema, cancellation/quote/resident-confirmation gates, partner sandbox handshake.
6. **Operations runbook:** TLS/private network, rotation và revoke khi sự cố, trace, health/readiness, retry/dead-letter/replay, rollback và catalog migration. Đây là tài liệu cần hoàn thiện; nghiên cứu này không khẳng định tất cả đã sẵn sàng production.

## 7. Giới hạn nghiên cứu

- Không truy cập VPS hoặc gọi `/mcp`; trạng thái triển khai thực tế lấy từ báo cáo maintain khác và phải ghi rõ thời điểm bằng chứng khi dùng.
- Không kiểm thử chất lượng model, Reception, Agent/leader; phần này thuộc người dùng tự nghiệm thu.
- Không kiểm tra implementation của platform để suy ra parser/grants behavior; các thay đổi wire cần đồng thuận hai bên trước triển khai.
- Ngoài một file nghiên cứu này, không sửa source, deployment hoặc secret.
