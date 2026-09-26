# Generic shared contracts

Owner: Platform; review chéo các port với consumer.

Đã có context, DomainAdapter, ActionProposal, runtime DTO và event envelope.
Thêm `agent-contracts.ts`, `capability-contracts.ts`, `evaluation-contracts.ts`,
`schemas.ts`, `errors.ts` khi use case cần. Không thêm interface rỗng hoặc sao chép model ORM vào API.
Không import domain, backend implementation hoặc framework vào đây.
