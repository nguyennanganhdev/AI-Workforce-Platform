# Đưa backend API và demo lên nhánh backend

- Ngày: 2026-10-01
- Yêu cầu: commit/push thay đổi backend API lên `dev_TeamChien-beHuy`, gồm `services/CHAY_DEMO_API.cmd`.

## Thay đổi

- Đóng gói backend FastAPI V3, seed/config Docker local, Hono demo gateway, giao diện demo và launcher CMD/PowerShell.
- Đưa kèm hướng dẫn API/demo và context thay đổi liên quan.
- Giữ frontend `app/src/routeTree.gen.ts`, bộ Agent-rules và tài liệu nghiệp vụ tổng hợp ngoài commit này.

## Quyết định & giả định

- Credentials, file ảnh local, log, database volume và virtualenv không được đưa vào Git; `.local-v3-faker` được gitignore.
- Không force push; kiểm tra remote trước khi ghi commit.

## Xác minh

- Đã fetch remote, kiểm tra danh sách file và `git diff --check`.
- Không chạy test trong task push; kiểm tra runtime/giới hạn nằm trong context các task trước.

## Rủi ro / việc còn lại

- Giao diện nghiệp vụ chưa được thử toàn bộ luồng trên trình duyệt; backend còn các việc trong kế hoạch V3.
