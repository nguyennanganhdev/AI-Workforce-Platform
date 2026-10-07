# Cấu trúc dự án

Cập nhật: 08/10/2026. Tài liệu này trả lời ba câu: thư mục nào là gì, code mới đặt ở đâu, và tệp cấu hình nào dùng cho việc gì.

Thiết kế nền tảng: [KE_HOACH_TAI_CAU_TRUC_PLATFORM_2026-10-08.md](KE_HOACH_TAI_CAU_TRUC_PLATFORM_2026-10-08.md). Việc từng team: [PHAN_CONG_VA_BAN_GIAO_2026-10-08.md](PHAN_CONG_VA_BAN_GIAO_2026-10-08.md).

## 1. Nguyên tắc

1. **Ba tầng.** Bề mặt (giao diện), lõi nền tảng, gói lĩnh vực. Gói biết lõi; lõi không biết gói.
2. **Mỗi thư mục một chủ.** Sửa ngoài vùng của mình thì viết yêu cầu.
3. **Không di chuyển code đang chạy trước 22/10.** Đường dẫn thư mục nằm cứng trong Dockerfile, compose, CI và lệnh import. Việc sắp xếp lại lớn làm sau buổi demo (mục 6).
4. **Code mới đặt đúng chỗ ngay từ đầu** (mục 3), để sau này không phải chuyển.

## 2. Bản đồ hiện tại

### 2.1. Đang chạy trong hệ thống

| Thư mục | Là gì | Ngôn ngữ | Team giữ |
|---|---|---|---|
| `services/vinhomes-api/` | API nghiệp vụ: vụ việc, phiên, agent, đánh giá, model, cổng gọi tool. Sẽ tách thành package lõi và phần riêng của Vinhomes | Python | Chiến |
| `agent-coordination/` | Supervisor, phòng điều phối, bộ đánh giá agent (`src/agent_eval`, Team Hoàng giữ) | Python | Đông |
| `agent-reception/` | Agent Tiếp nhận | Python | Hoàng |
| `agent-bot/` | Bot của OpenBot, dùng cho chat cá nhân | TypeScript | Chiến |
| `agent-factory/` | Sinh định nghĩa agent | TypeScript | Phái |
| `agent-report/` | Mẫu và cấu hình agent Báo cáo | Python | Hoàng |
| `server/` | Máy chủ OpenBot. Chứa bộ tool (`src/technical-tools`, `cleaning-tools`, `security-tools`), kiến thức (`src/knowledge`), báo cáo (`src/reporting`), lược đồ cơ sở dữ liệu (`src/db`, `drizzle/`) | TypeScript | Chiến; riêng tool và kiến thức: Quang; `cleaning-tools`, `reporting`: Hoàng; `security-tools`: Phái |
| `app/` | Giao diện điều hành và quản trị | TypeScript | Chiến |
| `resident-app/` | Ứng dụng cư dân. Sẽ là ứng dụng mẫu của gói Vinhomes | TypeScript | Chiến |
| `shared/` | Code và hợp đồng dùng chung giữa các dịch vụ | TypeScript, Python | Theo từng thư mục con |
| `deploy/vinhomes/` | Dockerfile, compose và script triển khai của hệ thống đang dùng | | Phái |
| `scripts/` | Script sinh lược đồ, tiện ích | | Chiến, Phái |

### 2.2. Thuộc bản gốc OpenBot, luồng hiện tại không dùng

Giữ nguyên tới sau 22/10 vì CI và Dockerfile gốc còn tham chiếu. Không thêm code mới vào đây.

| Thư mục | Là gì |
|---|---|
| `desktop/` | Ứng dụng máy tính của OpenBot |
| `agent-computer/`, `supervisor/` | Máy tính riêng cho agent và trình quản lý container của OpenBot. Lưu ý: `supervisor/` này **không phải** Supervisor điều phối agent |
| `agent-langgraph/`, `agent-langgraph-agui/` | Agent mẫu mà build gốc còn dùng |
| `worker/` | Tiến trình nền của OpenBot |
| `charts/`, `spire/`, `docker/` | Triển khai Kubernetes và hạ tầng của OpenBot |
| `examples/` | Ví dụ của OpenBot, gồm gói mẫu `examples/fintech/` |
| `Dockerfile`, `docker-compose.yml` ở gốc | Bản dựng và compose của OpenBot gốc. **Hệ thống của dự án dùng `deploy/vinhomes/compose.yml`** |

### 2.3. Tài liệu và ghi chép

| Thư mục | Là gì |
|---|---|
| `docs/` | Tài liệu dự án. `docs/teams/<team>/` chứa `handoffs/` và `requests/` của từng team (Team Phái dùng `docs/teams/platform/`) |
| `changes/` | Ghi chú thay đổi theo ngày |
| `tasks/` | Danh sách việc cũ; bảng tiến độ mới ở `docs/teams/platform/TIEN_DO.md` |
| `tests/` | Kiểm thử xuyên dịch vụ |

### 2.4. Đã gỡ ngày 08/10

- 11 thư mục agent mẫu của OpenBot không được build nào dùng: `agent-adk`, `agent-ag2`, `agent-agno`, `agent-claude-sdk`, `agent-crewai`, `agent-langroid`, `agent-llamaindex`, `agent-mastra`, `agent-microsoft`, `agent-pydantic-ai`, `agent-strands`. Lấy lại được từ lịch sử Git hoặc repo OpenBot gốc.
- Một tệp rỗng ở gốc repo.
- Thư mục `docx/`: tệp duy nhất trong đó đã chuyển vào `docs/`.

Còn sót, cố ý chưa sửa: `desktop/src-tauri/src/harness.rs` và `server/src/agents/plan-model.ts` vẫn nhắc tên các agent mẫu dưới dạng tên ảnh Docker. Chúng không đọc thư mục nên không gãy; dọn cùng lúc với `desktop/` sau 22/10.

## 3. Code mới đặt ở đâu

| Thứ cần thêm | Đặt ở | Ghi chú |
|---|---|---|
| Năng lực nền tảng phía API (hồ sơ vụ việc, sổ chi phí, bộ đọc gói) | Package lõi trong `services/vinhomes-api/src/` (Team Chiến tạo, việc CN-0) | Không đặt trong `vinhomes_api/` |
| Code điều phối trung lập | `agent-coordination/src/` ngoài thư mục `vinhomes/` | Thư mục `vinhomes/` chỉ còn phần nối riêng của lĩnh vực |
| Giao diện phòng điều hành | Thư mục giao diện lõi trong `app/src/features/` (việc CN-0) | Không đặt trong `vinhomes-operations/` |
| Hợp đồng giữa các team | `shared/contracts/v2/<mã>/` | Chỉ chủ hợp đồng sửa |
| Thư viện Python dùng chung giữa các dịch vụ | `shared/python/<tên>/` | Chỉ dùng thư viện chuẩn; mỗi ảnh Docker cần chép thư mục này vào |
| Mọi thứ riêng của Vinhomes: thương hiệu, từ vựng, định nghĩa agent, prompt, bản khai tool, dữ liệu mẫu | Thư mục gói Vinhomes (Team Phái tạo, việc PH-2) | Dữ liệu mẫu nằm trong `data/` của gói |
| Migration | `server/drizzle/` | Chỉ một người của Team Chiến viết |
| Tệp triển khai | `deploy/vinhomes/` | Không thêm Dockerfile hay compose ở nơi khác |

Không tạo thêm thư mục ở gốc repo. Không tạo thêm dịch vụ mới khi một dịch vụ đang có làm được việc đó.

## 4. Tệp cấu hình môi trường

Không đưa tệp chứa khóa thật vào Git. Trong Git chỉ có tệp mẫu.

| Chạy cái gì | Tệp mẫu trong Git | Tệp thật trên máy (ngoài Git) |
|---|---|---|
| **Toàn bộ hệ thống bằng Docker** (cách chính, dùng cho môi trường tích hợp và demo) | `deploy/vinhomes/deployment.env.example` | `deploy/vinhomes/deployment.env` |
| Tiếp nhận chạy riêng trên máy | `agent-reception/.env.example` | `agent-reception/.env` |
| Bộ điều phối chạy riêng trên máy | `agent-coordination/.env.example` | `agent-coordination/.env` |
| Agent Factory chạy riêng | `agent-factory/.env.example` | |
| API chạy riêng trên máy, nối cơ sở dữ liệu thật | `services/vinhomes-api/connected.env.example`, `knowledge.env.example`, `technical-api.env.example` | `services/vinhomes-api/.env.connected`, thư mục `.local-connected/` |
| OpenBot gốc | `.env.example` ở gốc | `.env` ở gốc |

Người mới chỉ cần dòng đầu tiên. Các dòng còn lại dành cho người phát triển đúng dịch vụ đó.

Thư mục `services/vinhomes-api/.local-v3-faker/` trên máy thuộc về cơ sở dữ liệu demo cũ đã gỡ ngày 07/10; không còn dùng.

## 5. Docker và gói phụ thuộc

- **Một tệp compose cho hệ thống của dự án:** `deploy/vinhomes/compose.yml`. Tệp `compose.postgres.local.yml` bên cạnh chỉ để chạy riêng cơ sở dữ liệu. `services/vinhomes-api/docker-compose.demo.yml` thuộc bản demo cũ.
- **Dockerfile của hệ thống:** các tệp trong `deploy/vinhomes/`, cùng `services/vinhomes-api/Dockerfile`, `agent-coordination/Dockerfile.vinhomes`, `agent-reception/Dockerfile`, `agent-factory/Dockerfile`, `agent-bot/Dockerfile`. Các Dockerfile còn lại thuộc OpenBot gốc.
- **JavaScript:** dùng `bun`. Gốc repo là một workspace gồm `app`, `server`, `worker`, `resident-app`; chạy `bun install` ở gốc. `agent-bot`, `agent-factory`, `desktop`, `supervisor`, `agent-computer` có tệp khóa riêng.
- **Python:** `services/vinhomes-api` và `agent-coordination` dùng `pyproject.toml`; `agent-reception` dùng `requirements.txt`. Mỗi dịch vụ một môi trường ảo riêng trong thư mục của nó.

## 6. Bố cục đích, làm sau 22/10

Đây là hướng, chưa phải việc của hai tuần này.

```
apps/        console (app), ứng dụng công việc, ứng dụng mẫu của gói
core/        api (lõi nền tảng), coordination, reception, tools, knowledge
packs/       vinhomes/ (brand, domain, agents, tools, knowledge, data), các gói sau
shared/      contracts/, python/, ts/
deploy/      compose, Dockerfile, script
docs/
```

Thứ tự làm sau demo: gỡ các phần OpenBot không dùng (mục 2.2) cùng CI của chúng; đổi tên `services/vinhomes-api` và các biến `VINHOMES_*`; rồi mới chuyển thư mục về bố cục trên, mỗi lần một dịch vụ, có CI xanh sau từng bước.
