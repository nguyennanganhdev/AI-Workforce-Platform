# Bàn giao — Phó Tiến Anh

## Phạm vi bàn giao

Phase A: đặc tả dữ liệu validation và evaluation snapshot cho từng agent,
theo mục 17.9 của [kế hoạch triển khai](../../KE_HOACH_TRIEN_KHAI.md).
Đầu việc liên quan: PTA-14–PTA-16, phần đặc tả dữ liệu.

## Hồ sơ bàn giao

- [Baseline Phase A](BASELINE_PHASE_A.md): cấu trúc dữ liệu, nguyên tắc nghiệp vụ và trách nhiệm tích hợp.
- [Schema bundle](phase_a/schemas.json): JSON Schema phiên bản `pta-phase-a-1`.
- [Mẫu dữ liệu](phase_a/samples.json): validation, evaluation record và async policy.
- [Trạng thái nghiệm thu](STATUS.md): kết quả kiểm tra đặc tả và điều kiện chấp thuận.

Phạm vi nghiệm thu hiện tại là đặc tả dữ liệu. Logic validation, eval suites,
runner, publish, retention, API và UI thuộc các mốc triển khai tiếp theo.
Mỗi phase có phạm vi và điều kiện nghiệm thu riêng trước khi chuyển mốc.
