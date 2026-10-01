# Schema Reception ↔ Supervisor

Cập nhật ngày 01/10/2026. Bản cũ giữ nguyên để đối chiếu; schema_v2 bên dưới là phương án đã chốt.

**schema_v1 (bản cũ)**

## Reception gửi ticket cho Supervisor

```typescript
type Fact = {
  key: string;
  value: string | number | boolean | null;
  source: "customer_report" | "staff_verified" | "agent_inference";
  source_message_id: string;
};

type ReceptionToSupervisorMessage = {
  schema_version: "1.0";
  message_id: string;
  correlation_id: string;
  sent_at: string;

  tenant_id: string;
  domain_id: string;
  domain_name: string;
  workspace_id: string;
  team_id: string;

  ticket_id: string;
  ticket_code: string;
  ticket_generation: number;
  ticket_version: string;

  resident: {
    resident_id: string;
    resident_name: string;
    phone_number: string;
  };

  location: {
    location_scope_id: string;
    unit_id: string;
    unit_number: string;
    building_id: string;
    building_code: string;
    building_name: string;
  };

  request: {
    title: string;
    description: string;
    request_kind: "incident" | "service_request";
    category_id?: string;
    priority: "low" | "normal" | "high" | "critical";
    severity: "unknown" | "minor" | "moderate" | "major" | "critical" | "not_applicable";
    is_emergency: boolean;
    triage_decision_id?: string;
    handoff_reason: "needs_staff" | "self_help_declined" | "self_help_failed" | "emergency";
  };

  facts: Fact[];
  file_ids: string[];
  created_at: string;

  // Có khi cư dân bổ sung thông tin sau lúc ticket đã được bàn giao.
  additional_information?: {
    source_message_id: string;
    message: string;
    facts: Fact[];
    file_ids: string[];
  };

  // Có khi cư dân yêu cầu hủy. Backend/Supervisor vẫn phải xác nhận kết quả hủy.
  cancel_request?: {
    source_message_id: string;
    reason: string;
    requested_at: string;
  };
};
```

## Supervisor trả kết quả cho Reception

```typescript
type SupervisorToReceptionResult = {
  schema_version: "1.0";
  message_id: string;
  correlation_id: string;
  sent_at: string;

  tenant_id: string;
  workspace_id: string;
  team_id: string;
  ticket_id: string;
  ticket_code: string;
  ticket_generation: number;
  ticket_version: string;

  supervisor_run_id: string;
  status: "accepted" | "in_progress" | "waiting_for_customer" | "completed" | "failed";
  customer_message: string;

  requested_information?: {
    interaction_id: string;
    questions: {
      field_id: string;
      question: string;
      required: boolean;
    }[];
  };

  result?: {
    outcome: "work_completed" | "needs_human_review" | "unable_to_resolve";
    summary: string;
    work_order_ids: string[];
    evidence_ids: string[];
  };

  error?: {
    code: string;
    retryable: boolean;
    message: string;
  };
};
```

### schema_v2 — Bản chốt ngày 01/10/2026

Chỉ dùng **một schema Reception → Supervisor** và **một schema Supervisor → Reception**. `message_type` xác định cách xử lý; `message` chứa nội dung câu hỏi, phương án, phản hồi hoặc thông báo. Các giá trị `message_type` là enum cố định, không suy diễn quyết định duyệt từ câu chữ trong `message`.

Hai schema này chỉ áp dụng cho giao tiếp Reception ↔ Supervisor qua backend. API duyệt quản lý, giao việc/nhận việc nhân viên, nghiệm thu, xác nhận hoàn thành và đóng/mở ticket vẫn thuộc backend. Backend có thể tiếp tục dùng các mã phương án, phê duyệt và kết quả nội bộ; các mã đó không bắt buộc xuất hiện trong hai schema này.

#### Reception gửi cho Supervisor — input

```typescript
type Fact = {
  key: string;
  value: string | number | boolean | null;
  source: "customer_report" | "staff_verified" | "agent_inference";
  source_message_id: string;
};

type ReceptionToSupervisorMessage = {
  schema_version: "2.0";
  message_id: string;
  correlation_id: string;
  sent_at: string;

  message_type:
    | "ticket_submitted"
    | "information_provided"
    | "plan_approved"
    | "plan_rejected"
    | "plan_change_requested"
    | "cancel_requested";
  message: string;
  source_message_id?: string;

  tenant_id: string;
  domain_id: string;
  domain_name: string;
  workspace_id: string;
  team_id: string;

  ticket_id: string;
  ticket_code: string;
  ticket_generation: number;
  ticket_version: string;

  resident: {
    resident_id: string;
    resident_name: string;
    phone_number: string;
  };

  location: {
    location_scope_id: string;
    unit_id: string;
    unit_number: string;
    building_id: string;
    building_code: string;
    building_name: string;
  };

  request: {
    title: string;
    description: string;
    request_kind: "incident" | "service_request";
    category_id?: string;
    priority: "low" | "normal" | "high" | "critical";
    severity: "unknown" | "minor" | "moderate" | "major" | "critical" | "not_applicable";
    is_emergency: boolean;
    triage_decision_id?: string;
    handoff_reason: "needs_staff" | "self_help_declined" | "self_help_failed" | "emergency";
  };

  facts: Fact[];
  file_ids: string[];
  created_at: string;
};
```

- `ticket_submitted`: bàn giao ticket; `message` mô tả yêu cầu của cư dân.
- `information_provided`: câu trả lời hoặc thông tin bổ sung trong `message`; dữ kiện và tệp bổ sung được đưa vào `facts`/`file_ids` của bản dữ liệu ticket gửi kèm.
- `plan_approved`, `plan_rejected`, `plan_change_requested`: quyết định về phương án đang chờ; `message` lưu lời trả lời hoặc yêu cầu sửa của cư dân.
- `cancel_requested`: `message` nêu lý do yêu cầu hủy; yêu cầu này chưa có nghĩa ticket đã bị hủy.

Giữ các trường thông tin ticket bắt buộc như bản schema đính kèm ban đầu: mọi input đều kèm bản dữ liệu ticket tương ứng. Backend/gateway lấy dữ liệu đã xác minh để điền; model không tự tạo lại tên, ID, số điện thoại hoặc địa chỉ. Việc tối giản bản tin thành chỉ ID và nội dung chưa thuộc thay đổi lần này.

`source_message_id` bắt buộc với các input ngoài `ticket_submitted`, để truy lại câu trả lời gốc của cư dân. Đây là mã tin nhắn nguồn, không phải mã câu hỏi mới. `sent_at` là lúc gửi bản tin giữa dịch vụ; thời điểm cư dân gửi tin được tra từ tin nhắn nguồn. `created_at` là thời điểm tạo ticket. Các thời gian dùng chuỗi ISO 8601 có múi giờ.

#### Supervisor gửi cho Reception — output

```typescript
type SupervisorToReceptionResult = {
  schema_version: "2.0";
  message_id: string;
  correlation_id: string;
  sent_at: string;

  message_type:
    | "accepted"
    | "in_progress"
    | "information_requested"
    | "plan_approval_requested"
    | "completed"
    | "failed"
    | "cancelled";
  message: string;

  tenant_id: string;
  workspace_id: string;
  team_id: string;
  ticket_id: string;
  ticket_code: string;
  ticket_generation: number;
  ticket_version: string;

  supervisor_run_id: string;

  result?: {
    outcome: "work_completed" | "needs_human_review" | "unable_to_resolve";
    summary: string;
    work_order_ids: string[];
    evidence_ids: string[];
  };

  error?: {
    code: string;
    retryable: boolean;
    message: string;
  };
};
```

- `accepted`, `in_progress`: đã nhận hoặc đang xử lý; `message` là thông báo cho cư dân.
- `information_requested`: `message` là câu hỏi cần cư dân trả lời; chờ `information_provided`.
- `plan_approval_requested`: `message` là phương án cần đồng ý, gồm việc sẽ làm, thời gian dự kiến, chi phí và điều kiện thực hiện; chờ một trong ba loại quyết định về phương án.
- `completed`: toàn bộ việc trong phạm vi xử lý đã hoàn thành và backend cho phép thông báo sau kiểm tra/nghiệm thu. Bắt buộc có `result` với `outcome = work_completed`. Việc một nhân viên báo xong chưa đủ để gửi loại này.
- `failed`: không xử lý được; `message` giải thích cho cư dân, `result` và/hoặc `error` bổ sung kết quả hoặc lỗi kỹ thuật. `error.message` là thông tin kỹ thuật, không tự chuyển nguyên văn cho cư dân.
- `cancelled`: backend đã xác nhận hủy thành công. Nếu không thể hủy và công việc vẫn tiếp tục, gửi `in_progress` kèm lý do trong `message`.

Không còn `status`, `customer_message`, `requires_resident_approval`, `resident_decision`, `additional_information`, `cancel_request` và `requested_information` trong schema V2. Nội dung trao đổi được chuyển vào `message`; loại thao tác được chuyển vào `message_type`. `facts`, `file_ids`, `result`, `error` và các mã đối chiếu vẫn là dữ liệu có cấu trúc.

#### Quy tắc dùng chung

1. Mỗi ticket trong một `ticket_generation` có tối đa một yêu cầu chờ cư dân trả lời tại một thời điểm: hỏi thông tin hoặc duyệt phương án. Đây là điều kiện phải kiểm tra, không chỉ là thói quen sử dụng. Thông tin bổ sung tự phát vẫn có thể đến, nhưng không tự chuyển thành quyết định duyệt.
2. Backend lưu nguyên phương án đã đưa cho cư dân cùng `ticket_version` và trạng thái chờ. Reception hiển thị đúng phương án, số tiền và điều kiện; chưa xác định giá thì ghi rõ chưa xác định. Mỗi lần thay phương án hoặc thay yêu cầu đang chờ phải có phiên bản ticket mới do backend cấp. Phản hồi giữ phiên bản của yêu cầu mà cư dân đã thấy; gateway không tự gắn phiên bản mới nhất vào một câu trả lời cũ.
3. Backend kiểm người trả lời từ nguồn đã xác thực, tenant, ticket, generation, phiên bản và bước đang chờ trước khi chấp nhận `plan_approved` hoặc phản hồi khác. Chỉ loại thông điệp phù hợp với bước đang chờ mới cho tiếp tục. Câu trả lời mơ hồ phải được Reception làm rõ; `message_type` do model tạo không tự cấp quyền thực hiện.
4. Trước khi chạy, Supervisor vẫn cần kết quả quản lý duyệt qua backend. Nếu backend xác định sự cố chung không cần cư dân đồng ý thì tiếp tục theo quyền đã được duyệt, không gửi `plan_approval_requested`. Không suy ra miễn duyệt chỉ vì bản tin không có cờ duyệt. Sửa phương án hoặc phát sinh vượt phạm vi/chi phí đã đồng ý phải đi lại các bước duyệt áp dụng cho bản mới.
5. `message_id` nhận diện một bản tin; gửi lại cùng bản tin giữ nguyên ID và nội dung. Backend lưu kết quả xử lý theo `(tenant_id, message_id)` để chống xử lý lặp; cùng ID nhưng khác nội dung phải báo conflict. Một quyết định gửi lại bằng ID mới cũng không được thực hiện công việc lần hai: backend đối chiếu quyết định đã lưu cho bước chờ. `correlation_id` dùng theo dõi chuỗi trao đổi, không thay thế kiểm quyền hoặc phiên bản. Backend ánh xạ các mã này sang request/event nội bộ; sự kiện backend vẫn dùng envelope sự kiện của backend.
6. `completed` là hoàn thành công việc của Supervisor, chưa đồng nghĩa ticket đã đóng. Backend sở hữu việc xin cư dân xác nhận, nhận phản ánh chưa hài lòng và quyết định đóng/mở hoặc tiếp tục xử lý. Hai schema này không thêm `completion.requested`/`completion.responded`. Khi cần xử lý tiếp, backend chuyển ngữ cảnh hợp lệ qua gateway; nếu ticket đã đóng rồi mở lại thì dùng generation mới.
7. V2 dùng `schema_version = 2.0` vì thay đổi tên trường và loại thông điệp. Input/output mỗi hướng có một bộ kiểm tra schema; các điều kiện theo `message_type` nằm trong bộ kiểm tra đó. Không tự nhận V1 như V2, không đổi tên các mã v1 `request_id`/`trace_id`/`binding_id` sang mã V2 nếu chưa xác định đúng ý nghĩa. Định tuyến phòng và quyền được backend tra từ ngữ cảnh đã xác thực.

Ví dụ nội dung dưới đây chỉ trích ba trường để đọc nhanh; bản tin thực tế phải có đủ các trường bắt buộc ở hai schema trên:

```json
{
  "message_type": "plan_approval_requested",
  "message": "Thay đoạn ống rò tại bếp, dự kiến 45 phút, chi phí dự kiến 300.000 VND. Anh/chị có đồng ý thực hiện không?",
  "ticket_version": "12"
}
```

```json
{
  "message_type": "plan_approved",
  "message": "Tôi đồng ý phương án và chi phí trên.",
  "ticket_version": "12"
}
```

Luồng trao đổi: `ticket_submitted` → `accepted` → (`information_requested` → `information_provided` nếu thiếu thông tin) → (`plan_approval_requested` → quyết định cư dân nếu cần duyệt) → `in_progress` → `completed`. Đây là luồng minh họa; trường hợp từ chối, sửa, hủy hoặc thất bại được xử lý theo `message_type` tương ứng và trạng thái backend.
