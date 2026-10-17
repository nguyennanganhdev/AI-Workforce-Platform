# ticket_timeline — PHH Phase B

Owner: **Phan Huy Hoàng**. Phạm vi PHH-17: state/timeline của từng ticket, receipt/snapshot/event reducer, cursor reconnect, dedupe và close đúng workflow.

State được khóa theo identity + conversation + workflow + external ticket; không dùng “ticket gần nhất”. `api.ts` tái sử dụng shared `event_transport`; `TicketTimeline.tsx` tái sử dụng approval component của Execution.

Chạy test reducer:

```powershell
node --experimental-strip-types --test src\features\workforce\chat\ticket_timeline\state.test.mjs
```
