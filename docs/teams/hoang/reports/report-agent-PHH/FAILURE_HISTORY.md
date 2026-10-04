# Lịch sử lỗi trong lần thu hẹp Report tools

Ngày 04/10/2026. Chỉ dùng bằng chứng của lần viết lại bốn tool. Kết quả cũ không dùng để nghiệm thu bản mới.

## Windows timer fixture

Kết quả trước sửa: {"tests": 156, "failures": 1, "errors": 0, "skipped": 0, "passed": 155}

Nguyên nhân: Test assumed two requests within a 40 ms deadline; only one was sent and BACKEND_UNAVAILABLE was correct.

Sửa: Give each scope read an explicit duration and a larger budget so scope reads jointly exceed the deadline.

Ca lỗi:
```json
[
  {
    "case": "server.tests.reporting.tools.test_adversarial::test_total_deadline_includes_scope_reads",
    "outcome": "failed",
    "message": "AssertionError: assert ('BACKEND_UNAVAILABLE' == 'BACKEND_UNAVAILABLE'\n  \n    BACKEND_UNAVAILABLE and 1 == 2)\n +  where 1 = len([<Request('GET', 'https://business.example/catalogs')>])"
  }
]
```

Đối chiếu ở lần cuối:
```json
[
  {
    "case": "server.tests.reporting.tools.test_adversarial::test_total_deadline_includes_scope_reads",
    "outcome": "passed"
  }
]
```

## Incorrect SQL fake type

Kết quả trước sửa: {"tests": 160, "failures": 1, "errors": 0, "skipped": 0, "passed": 159}

Nguyên nhân: Invoice SQL fake returned grand_total as string, causing backend str minus int. Real SQL NUMERIC is Decimal.

Sửa: Make SQL fake return Decimal. This does not demonstrate a production SQL bug.

Ca lỗi:
```json
[
  {
    "case": "server.tests.reporting.tools.test_existing_routes::test_four_tools_with_existing_real_fastapi_routes[get_repair_bill_summary-args1]",
    "outcome": "failed",
    "message": "TypeError: unsupported operand type(s) for -: 'str' and 'int'"
  }
]
```

Đối chiếu ở lần cuối:
```json
[
  {
    "case": "server.tests.reporting.tools.test_existing_routes::test_four_tools_with_existing_real_fastapi_routes[get_repair_bill_summary-args1]",
    "outcome": "passed"
  }
]
```

## Consumer and real serialization mismatch

Kết quả trước sửa: {"tests": 4, "failures": 1, "errors": 0, "skipped": 0, "passed": 3}

Nguyên nhân: Actual untyped invoice-detail router serialized synthetic Decimal 9007199254740993.01 as a rounded JSON number; comparing to the typed list price rejected the invoice.

Sửa: Use supporting-records grand_total only for arithmetic. Read detail for ID/status/category binding. Add precise-list/lossy-detail regression; backend serializer itself remains unchanged.

Ca lỗi:
```json
[
  {
    "case": "server.tests.reporting.tools.test_existing_routes::test_four_tools_with_existing_real_fastapi_routes[get_repair_bill_summary-args1]",
    "outcome": "failed",
    "message": "AssertionError: {'outcome': 'failure', 'error': 'BACKEND_CONTRACT_INVALID', 'retryable': False}\nassert 'failure' == 'success'\n  \n  - success\n  + failure"
  }
]
```

Đối chiếu ở lần cuối:
```json
[
  {
    "case": "server.tests.reporting.tools.test_existing_routes::test_four_tools_with_existing_real_fastapi_routes[get_repair_bill_summary-args1]",
    "outcome": "passed"
  }
]
```

## Consumer timestamp comparison bug

Kết quả trước sửa: {"tests": 4, "failures": 1, "errors": 0, "skipped": 0, "passed": 3}

Nguyên nhân: With actual datetime values at the SQL boundary, typed list returned a UTC Z timestamp while untyped detail returned +00:00. The same instant was rejected by string comparison.

Sửa: Parse both aware timestamps and compare instants. Preserve rejection for different instants; add Z/+00:00/+07:00 regressions.

Ca lỗi:
```json
[
  {
    "case": "server.tests.reporting.tools.test_existing_routes::test_four_tools_with_existing_real_fastapi_routes[get_repair_bill_summary-args1]",
    "outcome": "failed",
    "message": "AssertionError: {'outcome': 'failure', 'error': 'BACKEND_CONTRACT_INVALID', 'retryable': False}\nassert 'failure' == 'success'\n  \n  - success\n  + failure"
  }
]
```

Đối chiếu ở lần cuối:
```json
[
  {
    "case": "server.tests.reporting.tools.test_existing_routes::test_four_tools_with_existing_real_fastapi_routes[get_repair_bill_summary-args1]",
    "outcome": "passed"
  }
]
```

## Thay đổi test và lint

- Removed two variants asserting invoice detail monetary fields which are intentionally no longer used; replaced with an explicit precision regression.
- Added 11 cases for valid empty data and transient read retries, then 3 timestamp representation cases; final total 173.
- Initial lint found import order and unused imports plus duplicate startswith checks. Formatter expanded one-line test statements. Path preparation moved to conftest so router imports pass E402. Final lint and formatting both pass.

Cuối cùng: 173 tool PASS; 34 narrative regression PASS; không fail/error/skip. Không chạy PostgreSQL/SSO/RLS hoặc AgentScope gateway thật.

Chi tiết: evidence/failure-history.json, final-results.json, coverage-summary.json. Backend serializer tiền của invoice detail chưa được sửa.
