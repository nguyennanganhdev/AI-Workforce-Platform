# Quy ước tổ chức code cho team

## Một module backend

Mỗi thư mục hiện có là một feature/business capability. Khi use case đầu tiên xuất hiện,
chỉ thêm những file cần thiết:

```text
incidents/
  index.ts             Public application API/types mà module khác được dùng
  routes.ts            HTTP parse/validation/auth middleware → use case
  service.ts           Use case, transaction, authorization và state transition
  repository.ts        Persistence của module; không export cho platform
  incidents.test.ts    Test hành vi hoặc đặt trong tests/ tùy test runner
```

Chỉ tách `application/`, `domain/`, `infrastructure/` khi module đã lớn và có nhu cầu thực tế.
Không tạo controller/service/repository cho từng table chỉ để đủ tầng. Domain model khác DTO API.
Tránh global service locator; inject port/client/repository từ `server/src/app.ts`.

## Quy tắc theo layer

- Route không chứa business rule; nhận RequestContext từ middleware đã xác thực.
- Application service kiểm tra tenant/actor, subject, version và payload trước mutation; sở hữu transaction.
- Repository chỉ đọc/ghi dữ liệu của module; schema dưới `server/src/db/schema` theo owner.
- Public contract ở `shared` chỉ chứa DTO/type và pure domain constants; không import Hono, ORM, AgentScope.
- UI feature không import backend implementation. Thành phần UI dùng chung toàn shell thêm khi nhập upstream.
- Runtime generic nhận mapping domain qua port; concrete adapter/prompt nằm tại `domain_adapters`.
- MCP provider chứa client hệ thống ngoài. Không đưa rule/approval hoặc DB business repository vào MCP.

TypeScript dùng strict mode, ESM và relative import với đuôi `.js` (TypeScript resolve sang `.ts`).
Scaffold dùng một npm package ở root để tránh chọn lại workspace conventions trước khi nhập OpenBot.
Chưa thêm path alias/package workspace; nếu thêm phải cập nhật boundary checker và CI cùng PR.

## Luồng xử lý chuẩn

```text
HTTP → authenticated RequestContext → application service
     → actor/scope/version/payload validation
     → transaction: business state + outbox + idempotency record
     → response DTO

Agent → ActionProposal → DomainAdapter.submitAction
      → ActionRequest → RuleDecision → Approval nếu cần
      → Execution grant → MCP WRITE → WorkOrder/Evidence/QC
```

`validateAction` là kiểm tra trước, không cấp quyền thực thi; `submitAction` phải kiểm tra lại
trong transaction để tránh time-of-check/time-of-use. Receipt chỉ xác nhận intake.
Proposal producer metadata là provenance cần xác minh từ integration tin cậy, không phải actor authorization.

## Contract, database và event

1. Cập nhật contract/OpenAPI, consumer và tests cùng PR khi đổi boundary.
2. Chọn database schema đúng owner. Migration có thứ tự thống nhất; file đã deploy không sửa lại.
3. Không hard FK từ domain tới runtime/agent tables. Dùng identity FK hoặc snapshot/ref phù hợp.
4. Event platform và Vinhomes có discriminant stream riêng; cụ thể hóa payload union khi có producer/consumer.
5. Idempotency của business command persist ở PostgreSQL, kiểm tra payload hash và trả lại kết quả cũ khi retry hợp lệ.
6. Không dùng in-memory map làm idempotency store cho production.

## Kiểm tra và PR

```sh
npm run check
```

Lệnh này chạy TypeScript check, import boundary, Python syntax/import smoke và test scaffold.
Thêm test module vào script test hoặc test runner phù hợp cùng PR; hiện tại script chỉ chạy `tests/*.test.*`.
Khi nhập React/OpenBot, thêm TSX config/test/build của upstream vào CI; scaffold hiện chưa build UI.

PR mô tả trigger và hành vi sau thay đổi, owner, contract/schema đổi gì và kết quả kiểm tra.
Business features cần test quyền tenant/actor, state transition, concurrency/idempotency khi liên quan.
Không trả mock success cho route/provider/runtime chưa triển khai. Cập nhật trạng thái README module khi có code thật.
