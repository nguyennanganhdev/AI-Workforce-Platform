# Phase D release checklist

- [ ] D4 và lượt integration hiện tại đã merge vào `develop2`.
- [ ] D5 mock E2E chạy đủ Customer POST → Leader/group → operation/provider
      event → resume → event log/SSE → customer close.
- [ ] Fault cases duplicate/out-of-order/crash/unknown/reconnect/two-ticket pass.
- [ ] PostgreSQL concurrency suites chạy thật, không skip do thiếu DSN.
- [ ] Alembic upgrade và backup/restore rehearsal pass trên cùng commit.
- [ ] Frontend lint/build và Builder browser regression pass.
- [ ] Mọi JUnit report có `failures=0`, `errors=0`, `skipped=0`.
- [ ] Proxy SSE đã kiểm tra qua proxy, không chỉ ASGI in-process.
- [ ] Metrics/alerts được load; secret/raw private payload không xuất hiện.
- [ ] Sandbox evidence được đính kèm, hoặc ghi rõ `NOT_VERIFIED` cùng lý do.
- [ ] D7 report ghi đúng full commit SHA của `develop2`.
- [ ] Chỉ gắn Release Candidate sau khi workflow `Workforce Phase D Gate` xanh.

Release Candidate không đồng nghĩa production pass khi sandbox/UAT chưa được
xác minh. Việc mở production cần change approval, backup gần nhất, rollback owner
và người trực vận hành.
