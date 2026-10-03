# Báo cáo kiểm tra luồng vai trò và dữ liệu Vinhomes Operations

## 1. Mục tiêu

Báo cáo đánh giá các luồng trong `app/src/features/vinhomes-operations/` theo từng vai trò và kiểm tra tính nhất quán của chuỗi dữ liệu:

```text
Incident
  → Task
  → ActionRequest và Approval
  → WorkOrder
  → Evidence
  → QC
  → Redo nếu QC Fail
  → Task DONE
  → Incident RESOLVED hoặc CLOSED
```

Các vai trò được kiểm tra:

1. Kỹ thuật viên nội bộ.
2. Nhân viên vệ sinh và cảnh quan A5.
3. Nhân viên an ninh.
4. Nhân sự nhà thầu.
5. Trưởng nhóm hoặc giám sát.
6. QC Inspector.
7. Manager hoặc Ban quản lý.

## 2. Kết luận tổng quan

Các giao diện theo vai trò đã tương đối đầy đủ, nhưng dữ liệu giữa các luồng hiện chưa khớp nhau. Vấn đề chính nằm ở mock data và liên kết giữa `Incident`, `Task`, `WorkOrder`, `Evidence`, `QC` và `Approval`.

Kiểm tra tự động phát hiện ít nhất 28 lỗi toàn vẹn dữ liệu cốt lõi, chưa tính các sai lệch về Approval và trạng thái Incident.

| Vai trò | UI flow | Dữ liệu liên kết | Kết luận |
|---|---:|---:|---|
| Kỹ thuật viên | Tốt | Sai redo và Incident–Task | Cần sửa |
| Vệ sinh A5 | Tốt | Sai ID assignee và một số WorkOrder | Cần sửa |
| An ninh | Tốt | Chưa nối đúng Task và WorkOrder | Chưa đạt |
| Nhà thầu | Tốt | Sai Incident–Task, thiếu checklist | Chưa đạt |
| Supervisor | Tốt | Dữ liệu phân công chưa được ràng buộc đầy đủ | Cần sửa |
| QC Inspector | Tốt | Seed QC không hợp lệ | Chưa đạt |
| Manager/BQL | Tốt | Approval, Grant và WorkOrder chưa khớp | Cần sửa |

Không nên tiếp tục mở rộng UI trước khi chuẩn hóa bộ mock data. Cùng một WorkOrder hiện có thể hiển thị sự cố, Task hoặc vị trí khác nhau tùy màn hình.

## 3. Kiểm tra theo từng vai trò

### 3.1. Kỹ thuật viên nội bộ

Kỹ thuật viên hiện nhìn thấy:

```text
WO-2026-083  IN_PROGRESS
WO-2026-086  ASSIGNED
WO-2026-087  BLOCKED
WO-2026-085  ASSIGNED, REDO
WO-2026-081  COMPLETED
```

Các vấn đề:

- `WO-2026-086` thuộc `INC-2026-003`, nhưng Task `TSK-2026-104` thuộc `INC-2026-001`.
- `WO-2026-087` thuộc `INC-2026-004`, nhưng Task `TSK-2026-106` thuộc `INC-2026-002`.
- `WO-2026-085` khai báo làm lại của `WO-2026-081`, nhưng hai WorkOrder không cùng Task.
- `WO-2026-081` đã có QC PASS nhưng vẫn có một WorkOrder redo đang chờ thực hiện.
- QC của `WO-2026-081` do chính `usr-tech-01` ký, vi phạm nguyên tắc người thi công không tự QC.

Luồng đúng:

```text
Incident 001
  → Task 101
    → WorkOrder attempt 1
      → QC FAIL
        → WorkOrder attempt 2 cùng Task 101
          → QC PASS
```

`redo_of_work_order_id` phải cùng `incident_id`, `task_id`, checklist và có `attempt_no` tăng dần.

### 3.2. Nhân viên vệ sinh và cảnh quan A5

Nhân viên A5 hiện nhìn thấy:

```text
WO-2026-082  IN_PROGRESS
WO-2026-088  ASSIGNED
```

`WO-2026-082` có chuỗi liên kết đúng:

```text
INC-2026-001
  → TSK-2026-102 SANITATION
    → WO-2026-082
      → usr-cleaner-01
```

Các vấn đề:

- `WO-2026-088` thuộc `INC-2026-005`, nhưng Task `TSK-2026-105` thuộc `INC-2026-002`.
- `INC-2026-005` đã `RESOLVED`, nhưng `WO-2026-088` vẫn `ASSIGNED`.
- Các Task `TSK-2026-102`, `TSK-2026-105`, `TSK-2026-106` và `TSK-2026-109` vẫn dùng ID cũ `usr-san-01`.
- Persona mới của nhân viên vệ sinh là `usr-cleaner-01`.
- Action Request A5 vẫn sử dụng `usr-san-01`.

Cần cập nhật đồng bộ:

```ts
assignee_id: 'usr-cleaner-01'
```

### 3.3. Nhân viên an ninh

Nhân viên an ninh hiện nhìn thấy:

```text
WO-2026-090  IN_PROGRESS
```

Các vấn đề:

- `incident_id = INC-2026-002`, là Incident vệ sinh A5.
- `task_id = TSK-2026-108`, là Task MEP thuộc `INC-2026-004`.
- `checklist_version_id = CKL-VER-SEC-01`, nhưng checklist này chưa được định nghĩa.
- Chưa có Task `domain_type = SECURITY` nối với WorkOrder an ninh.

Luồng đúng:

```text
Security incident hoặc report
  → Escalate
  → Incident category SECURITY
  → Task domain_type SECURITY
  → WorkOrder giao cho usr-sec-01
  → Evidence
  → Supervisor hoặc QC confirmation nếu cần
```

Khi `escalateSecurityIncident()` tạo Incident, hệ thống nên tạo Task an ninh tương ứng hoặc chuyển Incident vào hàng đợi điều phối.

### 3.4. Nhân sự nhà thầu

Nhà thầu hiện nhìn thấy:

```text
WO-2026-084  IN_PROGRESS
WO-2026-089  ASSIGNED
```

`WO-2026-084` có các lỗi:

- Incident là `INC-2026-002`, thuộc vệ sinh.
- Task là `TSK-2026-104`, thuộc MEP của Incident 001.
- Checklist `CKL-VER-ELEV-01` không tồn tại.

`WO-2026-089` có các lỗi:

- Incident là `INC-2026-006`, đã `CLOSED`.
- Task là `TSK-2026-107`, thuộc `INC-2026-003`.
- Task 107 đã `DONE`, nhưng WorkOrder vẫn `ASSIGNED/PENDING_ACCEPTANCE`.
- Checklist `CKL-VER-ELEV-01` không tồn tại.

Mock WorkOrder nhà thầu chưa có `contractor_organization_id`. Cần thêm:

```ts
contractor_organization_id: 'org-otis'
```

### 3.5. Trưởng nhóm và giám sát

Supervisor nhìn thấy toàn bộ 10 WorkOrder. UI điều phối đã tương đối đầy đủ, nhưng dữ liệu nền chưa khớp.

Các vấn đề:

- 6 WorkOrder trỏ tới Task thuộc Incident khác.
- Form giao việc cho chọn các checklist chưa tồn tại: `CKL-VER-A5-01`, `CKL-VER-SEC-01`, `CKL-VER-ELEV-01`.
- Mock checklist hiện chỉ có `CKL-VER-MEP-01` và `CKL-VER-SAN-01`.
- GreenX có ID `usr-contractor-02` nhưng không có trong `PERSONA_PROFILES`.
- Mọi nhà thầu mới có nguy cơ mặc định nhận `contractor_organization_id = org-otis`.
- Người dùng có thể đổi `executorType` độc lập với người đã chọn.
- Checklist có thể không phù hợp với domain của Task.

Nguyên tắc giao việc đề xuất:

```text
Task.domain_type
  → danh sách executor hợp lệ
  → executor_type
  → contractor organization nếu có
  → checklist version phù hợp
```

### 3.6. QC Inspector

QC Inspector hiện chỉ nhìn thấy:

```text
WO-2026-081  COMPLETED
```

WorkOrder này đã có QC PASS, vì vậy hiện không có WorkOrder thực sự đang chờ QC.

Các vấn đề QC:

- `QC-2026-01` trỏ `WO-2026-074` không tồn tại.
- `QC-2026-02` trỏ `WO-2026-079` không tồn tại.
- `QC-2026-03` do `usr-tech-01` ký; đồng thời `usr-tech-01` là executor.
- `QC-2026-04` do `usr-san-01` ký; user này không có quyền QC.
- `QC-2026-04` PASS cho `WO-2026-085` dù WorkOrder đang `ASSIGNED`.

Tất cả mock QC hợp lệ nên dùng:

```ts
checked_by: 'usr-qc-01'
```

QC chỉ được tham chiếu WorkOrder đáp ứng:

- WorkOrder tồn tại.
- WorkOrder đang `COMPLETED` hoặc `AWAITING_QC`.
- Có đủ Before/After Evidence.
- Chưa có final QC khác.
- `checked_by !== executor_id`.

### 3.7. Manager và Ban quản lý

Chức năng quản lý đã có, nhưng liên kết Approval, Execution Grant và WorkOrder chưa đúng.

Các vấn đề:

- `ACT-2026-03` vẫn `PROPOSED` và đang chờ duyệt.
- `WO-2026-083` đã `IN_PROGRESS` và gắn `action_request_id = ACT-2026-03`.
- `APP-2026-003` trỏ `ACT-2026-REJECTED` không tồn tại.
- `APP-2026-004` trỏ `ACT-2026-EXPIRED` không tồn tại.
- Khi Manager approve, `granted_to` đang nhận `currentProfile.id`, tức cấp grant cho reviewer thay vì requester hoặc executor.

Các guard cần bổ sung:

- Chỉ approve Approval đang `PENDING`.
- Từ chối Approval đã hết hạn.
- Kiểm tra payload hash của Approval và Action Request.
- Không tạo nhiều Execution Grant cho cùng Approval.
- Chỉ consume grant đúng Action Request, Task, Incident và action type.

## 4. Kết quả kiểm tra liên kết dữ liệu

### 4.1. Task assignee không tồn tại trong persona

```text
TSK-2026-102 → usr-san-01
TSK-2026-105 → usr-san-01
TSK-2026-106 → usr-san-01
TSK-2026-107 → usr-contractor-otis
TSK-2026-109 → usr-san-01
```

### 4.2. WorkOrder và Task thuộc Incident khác nhau

| WorkOrder | Incident của WorkOrder | Task | Incident của Task |
|---|---|---|---|
| WO-2026-086 | INC-2026-003 | TSK-2026-104 | INC-2026-001 |
| WO-2026-087 | INC-2026-004 | TSK-2026-106 | INC-2026-002 |
| WO-2026-088 | INC-2026-005 | TSK-2026-105 | INC-2026-002 |
| WO-2026-084 | INC-2026-002 | TSK-2026-104 | INC-2026-001 |
| WO-2026-089 | INC-2026-006 | TSK-2026-107 | INC-2026-003 |
| WO-2026-090 | INC-2026-002 | TSK-2026-108 | INC-2026-004 |

Invariant bắt buộc:

```ts
workOrder.incident_id === task.incident_id
```

### 4.3. Redo chain không hợp lệ

`WO-2026-085` là redo của `WO-2026-081`, nhưng hai WorkOrder không cùng Task.

Redo hợp lệ phải đảm bảo:

```ts
redo.incident_id === original.incident_id
redo.task_id === original.task_id
redo.attempt_no === original.attempt_no + 1
```

### 4.4. Checklist không tồn tại

Các checklist version đang được tham chiếu nhưng chưa được định nghĩa:

```text
CKL-VER-ELEV-01
CKL-VER-SEC-01
CKL-VER-A5-01
```

Cần bổ sung:

- `CKL-ELEV-01` và `CKL-VER-ELEV-01`.
- `CKL-SEC-01` và `CKL-VER-SEC-01`.

Đồng thời cần thống nhất một mã A5. Mock dùng `CKL-VER-SAN-01`, trong khi form giao việc dùng `CKL-VER-A5-01`.

### 4.5. Evidence không khớp WorkOrder

Evidence orphan:

```text
EVD-2026-07 → WO-2026-074 không tồn tại
EVD-2026-08 → WO-2026-074 không tồn tại
EVD-2026-09 → WO-2026-079 không tồn tại
EVD-2026-10 → WO-2026-079 không tồn tại
```

Evidence sai `incident_id/task_id`:

```text
EVD-2026-05 và EVD-2026-06
  Evidence: INC-2026-002 / TSK-2026-105
  WO-2026-084: INC-2026-002 / TSK-2026-104

EVD-2026-11 và EVD-2026-12
  Evidence: INC-2026-005 / TSK-2026-109
  WO-2026-085: INC-2026-001 / TSK-2026-102
```

Invariant bắt buộc:

```ts
evidence.incident_id === workOrder.incident_id
evidence.task_id === workOrder.task_id
```

### 4.6. QC không hợp lệ

Phát hiện:

- 2 QC trỏ WorkOrder không tồn tại.
- 1 QC do chính executor thực hiện.
- 2 QC do người không có quyền `canQC` thực hiện.
- 1 QC PASS cho WorkOrder chưa hoàn thành.

## 5. Sai lệch vòng đời Incident và Task

### Task DONE nhưng còn WorkOrder hoạt động

```text
TSK-2026-107 = DONE
WO-2026-089 = ASSIGNED
```

### Incident ở QC nhưng không có WorkOrder hoàn thành hợp lệ

```text
INC-2026-003.stage = QC
```

Nhưng không có WorkOrder `COMPLETED` hợp lệ thuộc đúng Incident này.

### Incident đã resolved hoặc closed nhưng còn WorkOrder hoạt động

```text
INC-2026-005 = RESOLVED
WO-2026-088 = ASSIGNED

INC-2026-006 = CLOSED
WO-2026-089 = ASSIGNED
```

Điều kiện resolve Incident cần bổ sung:

- Mọi WorkOrder bắt buộc đã có final QC PASS.
- Không còn redo đang hoạt động.
- Evidence bắt buộc đầy đủ.
- Không còn Approval bắt buộc đang pending.
- Không còn Task dependency chưa hoàn thành.
- Resident confirmation được thực hiện bởi actor hợp lệ.

## 6. Task dependency chưa được thực thi

Các dependency đã khai báo:

```text
TSK-2026-103 phụ thuộc TSK-2026-101
TSK-2026-104 phụ thuộc TSK-2026-103
TSK-2026-102 phụ thuộc TSK-2026-101
TSK-2026-106 phụ thuộc TSK-2026-105
```

Khi WorkOrder chuyển từ `ASSIGNED` sang `IN_PROGRESS`, hệ thống chưa kiểm tra dependency.

Guard đề xuất:

```ts
const unresolvedDependencies = dependencies
  .filter(dependency => dependency.task_id === task.id && dependency.required)
  .filter(dependency => tasksById[dependency.depends_on_task_id]?.status !== 'DONE');

if (unresolvedDependencies.length > 0) {
  throw new Error('Task tiền nhiệm chưa hoàn thành');
}
```

## 7. Các invariant dữ liệu bắt buộc

### Incident và Task

```text
task.incident_id phải tham chiếu Incident tồn tại
```

### Task và WorkOrder

```text
workOrder.task_id phải tham chiếu Task tồn tại
workOrder.incident_id phải bằng task.incident_id
```

### Evidence

```text
evidence.work_order_id phải tham chiếu WorkOrder tồn tại
evidence.task_id phải bằng workOrder.task_id
evidence.incident_id phải bằng workOrder.incident_id
```

### QC

```text
qc.work_order_id phải tham chiếu WorkOrder tồn tại
WorkOrder phải ở trạng thái cho phép QC
qc.checked_by phải có canQC = true
qc.checked_by không được bằng workOrder.executor_id
mỗi WorkOrder chỉ có một final QC PASS hoặc FAIL
```

### Redo

```text
redo.redo_of_work_order_id phải tồn tại
redo.task_id phải bằng original.task_id
redo.incident_id phải bằng original.incident_id
redo.attempt_no phải bằng original.attempt_no + 1
```

### Checklist

```text
workOrder.checklist_version_id phải tồn tại
checklist category phải phù hợp task.domain_type
```

### Approval và Execution Grant

```text
approval.action_request_id phải tồn tại
approval.action_payload_hash phải bằng actionRequest.payload_hash
grant.approval_id phải tham chiếu Approval đã APPROVED
grant.granted_to phải là actor thực hiện, không mặc định là reviewer
grant chỉ được consume cho đúng ActionRequest và payload đã duyệt
```

### Incident lifecycle

```text
Incident không được RESOLVED hoặc CLOSED khi còn:
- Task chưa DONE
- WorkOrder đang hoạt động
- Redo đang hoạt động
- Evidence bắt buộc còn thiếu
- Final QC chưa PASS
- Approval bắt buộc còn PENDING
```

## 8. Thứ tự sửa đề xuất

### P0 — Chuẩn hóa dữ liệu nền

1. Chuẩn hóa toàn bộ mapping `WorkOrder → Task → Incident`.
2. Đổi `usr-san-01` thành `usr-cleaner-01`.
3. Xóa hoặc khôi phục `WO-2026-074` và `WO-2026-079`.
4. Sửa toàn bộ Evidence theo WorkOrder mới.
5. Viết lại QC seed với `usr-qc-01`.
6. Sửa redo chain để cùng Task và Incident.
7. Bổ sung checklist Security và Elevator.
8. Thống nhất mã checklist A5.
9. Sửa các Approval orphan.
10. Thêm Task SECURITY thực sự.

### P1 — Siết command nghiệp vụ

1. Kiểm tra Task dependency trước khi bắt đầu WorkOrder.
2. Không cho tạo WorkOrder nếu Incident và Task không khớp.
3. Suy ra checklist từ Task domain.
4. Suy ra executor type và contractor organization từ người được chọn.
5. Kiểm tra Approval status, expiry và payload hash.
6. Cấp Execution Grant cho đúng actor thực hiện.
7. Chỉ resolve Incident khi toàn bộ final QC bắt buộc đã PASS.

### P2 — Bổ sung kiểm thử toàn vẹn dữ liệu

Tạo test import trực tiếp toàn bộ mock data và kiểm tra:

- Không có ID trùng.
- Không có foreign key orphan.
- Incident–Task–WorkOrder khớp nhau.
- Evidence khớp WorkOrder.
- QC hợp lệ.
- Redo chain hợp lệ.
- Checklist tồn tại và đúng domain.
- Incident lifecycle không mâu thuẫn.
- Approval và Grant có liên kết hợp lệ.

## 9. Kết luận cuối cùng

Phần giao diện đã mô tả tương đối đầy đủ hành vi của từng vai trò. Tuy nhiên, bộ dữ liệu mock chưa phải một tập dữ liệu nghiệp vụ thống nhất. Nếu tiếp tục phát triển trên dữ liệu hiện tại, các màn hình sẽ cho kết quả khác nhau đối với cùng một Incident hoặc WorkOrder.

Ưu tiên tiếp theo nên là chuẩn hóa một bộ dữ liệu mẫu xuyên suốt, sau đó khóa tính nhất quán bằng data integrity test trước khi tiếp tục mở rộng UI hoặc kết nối backend.
