# Schema Reception ↔ Supervisor

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
