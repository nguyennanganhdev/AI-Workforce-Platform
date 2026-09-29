# AI Workforce Platform + Vinhomes
# Business Analysis & Implementation Specification

**Version:** v1.0  
**Purpose:** Chuẩn hóa nghiệp vụ triển khai dự án để BA, FE, BE và AI Runtime cùng hiểu một mô hình thống nhất.

---

# 1. Tầm nhìn sản phẩm

Dự án không xây một chatbot riêng cho Vinhomes.

Mục tiêu là xây một **AI Workforce Platform dùng chung**, cho phép doanh nghiệp:

- tạo Agent;
- cấu hình Agent bằng AgentSpec;
- gắn model/tool/MCP/skill/knowledge/policy;
- evaluation;
- phê duyệt;
- publish/deploy;
- giám sát runtime;
- rollback/suspend/retire;
- cắm Agent vào nhiều domain nghiệp vụ.

Vinhomes là **domain đầu tiên**.

```text
AI Workforce Platform
├── Vinhomes
├── Vinpearl
├── Vinmec
└── Future domains
```

Thêm domain mới không được yêu cầu redesign Agent Factory, AgentVersion, Evaluation hay Runtime.

---

# 2. Ranh giới hệ thống

## 2.1 Vinhomes IAM / SSO

Sở hữu:

- identity nguồn;
- resident/corporate account;
- authentication;
- token issuance;
- SSO.

OpenBot không phải source account production của cư dân/BQL.

---

## 2.2 Platform Authorization

Sở hữu:

- role;
- permission;
- role assignment;
- scope;
- quyền sử dụng AI Platform.

Ví dụ:

```text
VH_BQL_MANAGER
AGENT_MANAGER
```

là hai role khác nhau.

BQL không mặc định có quyền quản lý/publish Agent.

---

## 2.3 Generic AI Platform

Sở hữu:

```text
Agent
AgentVersion
AgentSpec
Capability
Evaluation
PublishApproval
Deployment
WorkflowSession
AgentRun
```

Không sở hữu Incident/Task/WorkOrder.

---

## 2.4 Vinhomes Domain

Sở hữu:

```text
Project
Tower
Apartment
Membership

Case
ResidentRequest
ResidentReport
Incident
Task

ActionRequest
Approval
WorkOrder
Evidence
QC
BusinessEvent

Resident Services
Finance
Smart City
Community
Discovery
```

---

# 3. Actor model

## Resident

Có thể:

- xem nhà/căn hộ;
- quản lý thông tin resident;
- gửi phản ánh;
- dùng tiện ích;
- đăng ký khách/dịch vụ;
- xem hóa đơn/thanh toán;
- sử dụng Smart City;
- xem nội dung/sự kiện/ưu đãi;
- giao tiếp với AI Lễ tân.

---

## BQL

Có thể:

- quản lý Incident queue;
- phân loại;
- giao Task;
- kiểm SLA;
- phê duyệt action;
- review Evidence/QC;
- xem KPI/audit;
- quản lý Agent nếu được cấp Platform Role riêng.

---

## Nhân viên / Technician / Cleaning / Security

Có thể:

- nhận Task/WorkOrder;
- cập nhật tiến độ;
- upload Evidence;
- hoàn thành checklist;
- phản hồi blocker.

---

## Platform Agent Manager

Có thể:

- tạo/chỉnh Agent;
- cấu hình capability;
- chạy evaluation;
- request publish;
- deploy;
- monitor runtime.

Không nhất thiết là BQL.

---

# 4. Login và authorization

## 4.1 Login flow

```text
1. User đăng nhập Vinhomes IAM.
2. IAM cấp token.
3. FE gửi token tới Platform/API.
4. Backend validate token.
5. external_subject map về local user.
6. Backend resolve role + permission.
7. Nếu vào Vinhomes, resolve property membership/scope.
8. FE nhận Authorization Context.
9. Mọi API query/command được BE kiểm tra lại.
```

FE chỉ dùng context để render UI. Security boundary nằm ở BE.

---

## 4.2 Authorization layers

```text
Authentication
→ RBAC
→ Scope/ABAC
→ Record state
→ Business policy
```

Ví dụ BQL có `vh.incident.read` nhưng chỉ được đọc Incident trong Project/Tower nằm trong scope.

---

# 5. Resident intake

Resident có thể gửi một request gồm nhiều vấn đề.

Ví dụ:

> “Điều hòa tầng 15 bị rò nước, hành lang rất bẩn và camera có vẻ không hoạt động.”

Không tạo một mega-ticket ngay.

```text
ResidentRequest
      ↓
Case
      ↓
IssueCandidate[]
      ├── Technical
      ├── Cleaning
      └── Security
      ↓
Clarification
      ↓
ResidentReport[]
      ↓
Incident[]
```

---

## 5.1 Case

Case là hồ sơ hỗ trợ cấp trên.

Một Case có thể chứa:

- nhiều request/messages;
- nhiều clarifications;
- nhiều IssueCandidates;
- nhiều ResidentReports;
- nhiều Incidents.

---

## 5.2 IssueCandidate

P0 không cần table riêng.

Lưu trong `vh_case.intake_state_json`.

Agent Lễ tân đề xuất:

```json
{
  "category": "TECHNICAL",
  "summary": "HVAC water leak",
  "confidence": 0.95,
  "missingFields": [],
  "status": "READY"
}
```

Domain service mới quyết định materialize.

---

# 6. Incident là Ticket canonical

Không có cả `Ticket` và `Incident`.

```text
UI term: Ticket
DB term: Incident
```

Incident chứa:

- category;
- severity;
- owner;
- SLA;
- status;
- stage;
- tasks;
- actions;
- work orders;
- evidence;
- QC;
- event history.

---

# 7. Main operational flow

```text
ResidentReport
→ Incident
→ Task
→ ActionRequest
→ RuleDecision
→ Approval nếu cần
→ WorkOrder
→ Evidence
→ QC
→ RESOLVED
→ Resident Confirmation
→ CLOSED
```

Business core vẫn chạy được khi Agent Runtime lỗi hoặc bị tắt.

---

# 8. Triage Incident

Khi ResidentReport được submit:

1. validate resident/property context;
2. chống duplicate/idempotency;
3. tìm Incident liên quan;
4. link report vào Incident cũ nếu phù hợp;
5. nếu không, tạo Incident mới;
6. xác định category/severity/SLA;
7. ghi BusinessEvent;
8. BQL thấy cùng Incident trong queue.

---

# 9. Task planning

Incident có thể có nhiều Task.

Ví dụ rò nước gần tủ điện:

```text
Incident
├── Task 1: Technical inspection
├── Task 2: Electrical safety check
└── Task 3: Cleaning affected area
```

Không đặt toàn Incident thành `WAITING_APPROVAL` chỉ vì một Task đang chờ duyệt.

---

# 10. ActionRequest

Mọi side effect phải qua:

```text
Human
System
Automation
Agent
External Service
     ↓
ActionRequest
```

Ví dụ:

```text
ASSIGN_WORK_ORDER
ISOLATE_ELECTRICAL_AREA
CREATE_SERVICE_ORDER
CHANGE_INCIDENT_PRIORITY
REQUEST_CAMERA_ACCESS
```

ActionRequest lưu:

- source actor;
- source version;
- target;
- payload;
- payload hash;
- correlation ID;
- business version.

---

# 11. RuleDecision & Approval

RuleDecision:

```text
ALLOW
REQUIRE_APPROVAL
DENY
```

Ví dụ:

```text
Tạo work order vệ sinh
→ ALLOW

Ngắt điện toàn tầng
→ REQUIRE_APPROVAL

Camera access ngoài scope
→ DENY
```

Approval gắn exact `payload_hash`.

Payload đổi → approval cũ invalid → tạo ActionRequest mới.

---

# 12. ActionExecutor

Boundary duy nhất cho WRITE.

```text
ActionRequest
   ↓
state/version validation
   ↓
permission/scope validation
   ↓
RuleDecision
   ↓
Approval Gate
   ↓
Idempotency
   ↓
Execution Grant
   ↓
MCP/provider WRITE
   ↓
Business DB update
   ↓
BusinessEvent + Outbox
```

Agent song song chỉ READ / ANALYZE / PROPOSE.

---

# 13. WorkOrder & QC

WorkOrder là execution record.

```text
Task
  ↓
WorkOrder #1
  ↓
QC FAIL
  ↓
WorkOrder #2
redo_of = #1
```

Không reset WorkOrder cũ.

QC:

```text
PASS
FAIL
INCONCLUSIVE
```

- PASS: đạt yêu cầu.
- FAIL: redo.
- INCONCLUSIVE: cần thêm evidence.

QCResult immutable.

---

# 14. Close Incident

Incident chỉ được `RESOLVED` khi:

- required Tasks done;
- không còn required Approval pending;
- required WorkOrders hoàn thành;
- required Evidence đủ;
- QC đạt.

Sau đó resident:

```text
CONFIRM
→ CLOSED

REOPEN / DISPUTE
→ OPEN
```

---

# 15. Agent Lễ tân

Agent Lễ tân hỗ trợ gần đầy đủ Resident domain.

## Intent groups

| Intent | Domain |
|---|---|
| Nhà & tài khoản | apartment, membership, handover, access card |
| Phản ánh | case, report, incident |
| Tiện ích | facility, booking |
| Dịch vụ | service request, visitor pass, charging, pet |
| Tài chính | invoice, payment, fee, loyalty |
| Smart City | face, intercom, parking, sensor, camera |
| Cộng đồng | construction, feedback, content, event |
| Khám phá | transit, map, offer, miniapp |

Nguyên tắc:

```text
UNDERSTAND
CLARIFY
RETRIEVE
PROPOSE
```

Không:

```text
BYPASS PERMISSION
WRITE DB DIRECTLY
SELF-APPROVE
```

---

# 16. Supervisor

Supervisor nhận Incident đã chuẩn hóa.

```text
Incident
  ↓
Supervisor
  ↓
SessionPlan
  ↓
WorkflowSession
  ↓
Specialist Agents
```

Supervisor:

- chọn published AgentVersion;
- phân rã execution;
- xác định dependency;
- chọn parallel/sequential/review;
- retry/replan/escalate.

Platform:

- quản lý session state;
- pin AgentVersion;
- timeout/checkpoint;
- permission;
- audit.

---

# 17. Runtime patterns

Không phải Incident nào cũng GroupChat.

```text
Simple
→ Single Agent

Independent lookups
→ Parallel

Dependencies
→ Sequential

Responsibility transfer
→ Handoff

Conflict/high risk
→ GroupChat / Review
```

GroupChat là strategy có điều kiện, không phải default.

---

# 18. Memory model

```text
Business State
→ PostgreSQL

Workflow State
→ WorkflowSession

Agent Run Context
→ Runtime

Shared Structured Evidence
→ output/evidence refs

Semantic Memory
→ PostgreSQL metadata + Qdrant vectors

Knowledge
→ approved source/KB
```

Memory không override business facts.

---

# 19. Resident Services coverage

## Nhà & tài khoản
- apartment;
- membership;
- handover;
- access card.

## Tiện ích
- facility;
- time slot;
- booking;
- booking history;
- cancellation.

## Dịch vụ
- generic service request;
- visitor pass;
- EV charging;
- pet profile.

## Finance
- fee schedule;
- invoice;
- invoice lines;
- payment attempt;
- loyalty/VPoint.

## Smart City
- face enrollment;
- intercom;
- parking permit;
- sensor/environment;
- camera request.

## Community
- construction permit;
- feedback;
- content;
- community event;
- registration;
- offer.

## Discovery
- transit/VinBus;
- map places;
- miniapp catalog.

---

# 20. External integration strategy

Không cần provider production cho mọi module ở P0.

## CORE_REAL

Phải thật:

- authz;
- resident report;
- incident;
- task;
- action;
- approval;
- work order;
- evidence;
- QC.

## CRUD_REAL

State thật, workflow đơn giản:

- booking;
- pet;
- construction;
- community event.

## SIMULATED_EXTERNAL

DB state thật, provider mock:

- payment;
- charging;
- face;
- camera;
- intercom;
- sensor.

## READ_SEED

- fee schedule;
- content;
- offers;
- transit;
- map;
- miniapp.

---

# 21. Agent Factory

Manager:

> “Tạo Agent xử lý phản ánh kỹ thuật cư dân.”

Flow:

```text
Business description
→ Factory clarification
→ Draft AgentSpec
→ Capability binding
→ Validation
→ Evaluation
→ Domain/Security Review
→ Publish Approval
→ AgentVersion PUBLISHED
→ Deployment
```

Factory không tự grant permission nhạy cảm, tự PASS evaluation hay tự publish.

---

# 22. AgentVersion

Agent có:

```text
v1
v2
v3
...
```

Version pin:

- instructions;
- model;
- capability;
- tools;
- knowledge;
- policies;
- runtime config.

Published version immutable.

Rollback = activate previous published version.

---

# 23. Capability model P0

Catalog chung:

```text
MODEL
MCP_TOOL
SKILL
KNOWLEDGE
POLICY
CONNECTOR
```

Capability map tới OpenBot plugin/skill/MCP/KB implementation thật.

Khi scale lớn mới normalize thêm.

---

# 24. Evaluation

P0 dùng EvalRun.

Result:

```text
PASS
REVISE
BLOCK
INCONCLUSIVE
```

Publish chỉ được phép khi evaluation và required approvals thỏa.

---

# 25. RBAC mẫu

## Resident

```text
vh.incident.create
vh.incident.read_own
vh.booking.create
vh.invoice.read_own
vh.profile.read
assistant.use
```

## BQL Manager

```text
vh.incident.read/update/assign
vh.task.create/assign
vh.approval.decide.operational
vh.qc.review
vh.audit.read
```

## Technician

```text
vh.task.read_assigned
vh.workorder.execute
vh.evidence.upload
```

## Agent Manager

```text
platform.agent.read/create/edit
platform.capability.read
platform.eval.read
```

## Agent Publisher

```text
platform.agent.publish
platform.agent.deploy
```

Không dùng một role `ADMIN` chung cho mọi thứ.

---

# 26. FE organization

```text
/resident
  /home
  /apartment
  /reports
  /services
  /finance
  /smart-city
  /assistant

/operations
  /my-tasks
  /work-orders
  /evidence

/management
  /dashboard
  /incidents
  /tasks
  /approvals
  /qc
  /audit

/platform
  /agents
  /capabilities
  /evaluations
  /deployments

/platform/admin
  /users
  /roles
  /permissions
  /domains
```

---

# 27. BE organization

```text
server/src/
├── auth/
├── platform/
│   ├── agents/
│   ├── capabilities/
│   ├── evaluation/
│   ├── deployments/
│   ├── runtime/
│   └── domains/
└── domains/
    └── vinhomes/
        ├── property/
        ├── intake/
        ├── incidents/
        ├── tasks/
        ├── actions/
        ├── approvals/
        ├── work-orders/
        ├── evidence/
        ├── qc/
        └── resident-services/
```

---

# 28. Runtime service

```text
agent-runtime/
├── runtime/
│   ├── base.py
│   └── agentscope_adapter.py
├── agents/
├── supervisor/
└── domain_adapters/
    └── vinhomes.py
```

Platform/domain code không import trực tiếp AgentScope classes.

---

# 29. P0 Vertical Slice #1

Resident:

> “Điều hòa tầng 15 bị rò nước, hành lang bị ướt.”

Expected:

```text
Vinhomes login
→ ResidentRequest
→ Case
→ clarification
→ Technical/Cleaning Report
→ Incident(s)
→ BQL triage
→ Task(s)
→ Agent/Supervisor optional
→ ActionRequest
→ RuleDecision
→ WorkOrder
→ Evidence
→ QC
→ Resolve
→ Resident confirmation
```

---

# 30. P0 Vertical Slice #2

Manager:

> “Tạo Agent hỗ trợ HVAC.”

Expected:

```text
Manager login
→ Agent Factory
→ Draft AgentVersion
→ Capability binding
→ EvalRun PASS
→ Publish Approval
→ Deploy
→ Supervisor resolves published version
→ AgentRun
```

---

# 31. Architecture acceptance criteria

Hệ thống đi đúng hướng khi:

1. Tắt Agent Runtime nhưng BQL vẫn xử lý Incident thủ công.
2. Vinhomes SSO identity không bị duplicate password/account ở Platform.
3. BQL không đọc project ngoài scope.
4. BQL role không tự có quyền publish Agent.
5. Agent không direct-write Incident/WorkOrder.
6. ActionRequest có audit và approval exact payload.
7. WorkOrder redo giữ lịch sử.
8. AgentVersion được pin trong runtime session.
9. Có thể thêm domain `VINPEARL` qua DomainAdapter mà không sửa Agent Factory schema.
10. OpenBot upstream vẫn có khả năng merge vì project extensions không nhồi business semantics vào vendor tables.

---

# 32. Roadmap

## Phase 0 — Architecture Freeze
- ERD;
- RBAC;
- state machine;
- API contracts;
- RuntimeAdapter;
- DomainAdapter.

## Phase 1 — Identity + Platform Skeleton
- Vinhomes SSO adapter/mock;
- `/me/context`;
- RBAC;
- Agent/AgentVersion;
- capability;
- PostgreSQL/Qdrant.

## Phase 2 — Vinhomes Operations
- Case;
- Report;
- Incident;
- Task;
- Action;
- Approval;
- WorkOrder;
- Evidence;
- QC.

## Phase 3 — Resident Services
- Booking;
- Services;
- Finance;
- Smart City;
- Community;
- Discovery.

## Phase 4 — Runtime
- AgentScope;
- Receptionist;
- Supervisor;
- WorkflowSession;
- AgentRun.

## Phase 5 — Factory/Evaluation
- AgentSpec;
- EvalRun;
- publish/deployment.

## Phase 6 — Production Hardening
- policy;
- audit;
- OpenTelemetry;
- retry;
- idempotency;
- load/security;
- AGT/WSO2 spike conclusions.

---

# 33. Nguyên tắc cuối

> **Identity đến từ Vinhomes.**  
> **Platform quản lý quyền dùng AI và Agent lifecycle.**  
> **Domain quản lý quyền nghiệp vụ và business state.**  
> **PostgreSQL giữ sự thật.**  
> **Agent chỉ hiểu, phân tích và đề xuất.**  
> **ActionExecutor là cổng duy nhất cho side effect nghiệp vụ.**
