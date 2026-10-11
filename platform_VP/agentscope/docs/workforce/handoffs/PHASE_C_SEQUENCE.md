# Trình tự Phase C và trạng thái bàn giao

Cập nhật: **2026-10-11**. File này là bảng điều phối nội bộ, không phải contract
gửi đối tác và không thay đổi `KE_HOACH_TRIEN_KHAI.md`.

```text
C0 — Merge đủ Phase B và chốt một baseline chung
  ↓
C1 — Nguyễn Chí Hoàng: DB/UOW/Auth/Job/Signal/Bootstrap nền
  ↓
C2 — Nguyễn Phương Đông: Registry protocol thật ↔ Execution
  ↓
C3 ─┬─ Bùi Hữu Nghĩa: Protocol validation ↔ Builder
    └─ Phan Hoàng Dũng: Provider ingress ↔ Operation ↔ Protocol
  ↓
C4 — Phan Huy Hoàng: POST → Workflow → Event → Leader → Event log/SSE
  ↓
C5 — Phó Tiến Anh: Eval đa lượt ↔ runtime thật
  ↓
C6 — Phan Hoàng Dũng: E2E toàn lát cắt
  ↓
C7 — Nguyễn Chí Hoàng: composition/migration/CI cuối
```

## Trạng thái hiện tại

- Phase A: 6/6 đã hoàn thành và merge.
- Phase B: 6/6 đã hoàn thành; C0 đã chốt trong baseline chung.
- C1, C2 và cả hai lane C3 đã hoàn thành và merge.
- C4 của Phan Huy Hoàng đã merge qua PR #63 tại
  `develop2@86fa2931bbfd54d064798e00e0998429c6ac9cb5`.
- C5 của Phó Tiến Anh đã merge qua PR #64. Baseline chung hiện tại là
  `develop2@830cdacd56f868d509d208b91b9a6bc29d70c935`.
- **C6 của Phan Hoàng Dũng đã được mở và là bước tiếp theo.**
- **C7 của Nguyễn Chí Hoàng vẫn chờ C6 hoàn thành và merge.**

## Quy tắc tiếp tục

Mỗi owner pull baseline chung, đọc file này, kế hoạch tổng và `STATUS.md` của
mình. Chỉ bắt đầu khi bước ngay trước đã có commit trên nhánh chung. C3 có hai
lane chạy song song sau C2; các bước còn lại chạy tuần tự. Mỗi PR cập nhật
`STATUS.md`, nêu commit đầu vào, exports đã dùng, test, phần giả/live và request
tích hợp còn mở. Không sửa lại migration đã merge; gửi schema additive cho C7.

## Bảng gate C0–C7 — cập nhật ngày 2026-10-11

| Mốc | Owner | Trạng thái | Baseline / đầu ra quyết định |
|---|---|---|---|
| C0 | Cả đội | Hoàn thành | Phase B của 6/6 thành viên đã merge |
| C1 | Nguyễn Chí Hoàng | Hoàn thành | Foundation DB/UOW/Auth/Job/Signal/Bootstrap |
| C2 | Nguyễn Phương Đông | Hoàn thành | Registry protocol thật ↔ Execution |
| C3 | Bùi Hữu Nghĩa + Phan Hoàng Dũng | Hoàn thành | Builder validation và Provider ingress/Operation/Protocol đều đã merge |
| C4 | Phan Huy Hoàng | Hoàn thành, đã merge PR #63 | `86fa2931bbfd54d064798e00e0998429c6ac9cb5` |
| C5 | Phó Tiến Anh | Hoàn thành, đã merge PR #64 | `830cdacd56f868d509d208b91b9a6bc29d70c935` |
| C6 | Phan Hoàng Dũng | **Sẵn sàng triển khai** | Pull baseline C5 hiện tại; làm E2E toàn lát cắt |
| C7 | Nguyễn Chí Hoàng | **Chờ C6** | Chỉ mở sau khi C6 merge; làm composition/migration/CI cuối |

## Bàn giao C5 → C6

Phan Hoàng Dũng pull chính xác baseline
`develop2@830cdacd56f868d509d208b91b9a6bc29d70c935`, sau đó đọc:

- `pho-tien-anh/PHASE_C_C5.md` và
  `pho-tien-anh/INTEGRATION_REQUEST_PTA_C5.md`;
- `phan-huy-hoang/PHASE_C_C4.md` và
  `phan-huy-hoang/INTEGRATION_REQUEST_PHH_C4.md`;
- `phan-hoang-dung/PHASE_C_C3.md` và
  `phan-hoang-dung/INTEGRATION_REQUEST_PHD_C3.md`.

C6 phải kiểm chứng cùng một lát cắt production seam: Customer POST → durable
workflow job → Leader/Execution operation → provider event ingress/inbox/worker
→ Workflow apply trong cùng UOW → public event history/SSE → close ticket. Với
query/timer, dùng query hook thật và không tạo provider inbox giả. C6 dùng
runtime evidence/evaluation exports C5, nhưng không tự gom migration hoặc sửa
global composition thuộc C7.

Khi C6 hoàn thành, owner phải cập nhật `phan-hoang-dung/STATUS.md`, ghi commit
đầu vào, test đã chạy, phần còn fake/live và integration request rõ ràng cho C7.
Chỉ sau commit C6 xuất hiện trên `develop2` thì Nguyễn Chí Hoàng mới mở C7.
