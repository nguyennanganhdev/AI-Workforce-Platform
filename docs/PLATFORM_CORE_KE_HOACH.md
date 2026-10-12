# Lõi platform trung lập: kế hoạch triển khai

Nhánh: `feat/platform-core` (tách từ `dev_Vinhome`). Cập nhật: 10/10/2026.
Mã nguồn: `platform_VP/core` (gói Python `awp`). Không sửa `platform_VP/agentscope/src`.

## 1. Mục tiêu

Mỗi agent tạo ra có hồ sơ riêng (vai, kiến thức, bộ nhớ, tool, model, ngân sách). Khi vào một vụ việc, các agent trao đổi và phản biện nhau trên một hồ sơ chung. Một leader giữ quyết định cuối. Chi phí kiểm soát được và câu trả lời không bịa.

## 2. Quyết định đã chốt (PM, 09/10)

| # | Quyết định |
|---|---|
| 1 | Jev: làm thử nghiệm ngay, dùng `agentscope.classifier.JevClassifierModel` có sẵn. Bật bằng biến môi trường, tắt thì hệ thống vẫn chạy. |
| 2 | Mỗi vụ một leader giữ quyết định cuối. Chuyên viên hỏi nhau, phản biện, nhưng không tự quyết. Leader tổng hợp từ hồ sơ chung bằng bản tóm tắt tối ưu. |
| 3 | Case file là một dịch vụ riêng, đặt ở lõi trung lập, có cơ sở dữ liệu riêng. |
| 4 | Hỗ trợ nhiều nhà cung cấp và model. PM cấp khóa vào `.env` sau. |
| 5 | Người dùng platform nạp kiến thức cho từng agent qua tài liệu, knowledge base, MCP và tool. |
| 6 | Hoàn thiện platform trước, không chứa mã domain nào. Vinhomes nối sau, từ package `vinhome_Recident`, chỉ qua API của platform. |

## 3. Kiến trúc

```
Backend đối tác ──ApiKey──► /workforce/v1/partner/*        ┐
Backend nghiệp vụ ─ApiKey+HMAC─► /workforce/v1/provider/*   │  awp/workforce/ (router, auth, engine)
Admin platform ───Bearer──► /platform/v1/wf/*              ┘
                                      │
        DB của ta: clients, khóa, route, residence, conversation, workflow, request, message, event,
                   turn, job, approval, operation, hộp thư provider  (+ hồ sơ agent, case file, sổ chi phí)
                                      │ job tuần tự mỗi workflow
                              Engine ─┴──► leader (một phiên AgentScope sống suốt workflow)
                                                │  CaseSay / CaseFinalize / CaseAskConsent + Case* + TeamSay
                                                ├─► chuyên viên (worker), phản biện nhau trên case file chung
                                                └─► PartnerTool: tool của đối tác qua MCP (tra cứu, hành động)
```

Một **workflow** = một vụ (`awp_cases`) + một phiên leader AgentScope sống lâu + trạng thái công khai (`wf_workflows`). Mọi vụ đều có một dòng `wf_workflows`. Cư dân chỉ đọc những gì `CaseSay`/`CaseFinalize` ghi, đã qua cổng chống bịa; vụ không bị leader đóng, chỉ `POST close` của đối tác đóng nó. Phần agent cắm vào AgentScope bằng các điểm mở rộng có sẵn: `extra_agent_middlewares`, `extra_agent_tools`, `custom_subagent_templates`, `custom_agent_cls`, middleware ASGI và REST công khai.

## 4. Sáu khối

| Khối | Nội dung | Mã |
|---|---|---|
| Hồ sơ agent | Vai, phạm vi, tool được phép, kiến thức, bộ nhớ, model, ngân sách, leo thang. Có bản nháp và bản công bố. Biên dịch thành mẫu sub-agent. | `awp/profiles` |
| Case file | Sự kiện có bằng chứng, câu hỏi mở, phản biện, bằng chứng tự ghi từ kết quả tool và sự kiện provider. Chỉ ghi thêm, không sửa. | `awp/casefile` |
| Bản tin phòng | Mỗi lượt, mỗi agent nhận một đoạn ngắn: ai nói gì, ai đang làm gì, còn gì chờ. Chỉ phần mới từ lần xem trước. Leader còn nhận khối `<workflow-state>` dựng từ DB mỗi lượt. | `awp/casefile/digest.py`, `awp/middleware/room.py`, `awp/workforce/context.py` |
| Giao thức | Tool có kiểu thay cho tin tự do. Nhắn thẳng người nhận. Mỗi sự kiện tối đa 2 vòng phản biện, sau đó leader chốt. Lời nói với cư dân chỉ qua `CaseSay`. | `awp/protocol` |
| Cổng chống bịa | Mọi khẳng định phải dẫn mã bằng chứng. Code kiểm số, mã, trạng thái có trong bằng chứng; cụm "đã xong" chỉ mở bằng dấu `<platform-verified>` do nền tảng thêm. Jev (nếu bật) là ý kiến thứ hai. Sai thì trả lỗi để agent sửa, hết lượt thì câu trả lời an toàn và leo thang. | `awp/guard`, `awp/workforce/lookup.py` |
| Chi phí | Cắt tool theo vai trước mỗi lần gọi model. Sổ chi phí theo vụ, agent, model. Ngân sách theo workflow. Định tuyến model theo tầng. | `awp/middleware/room.py`, `awp/cost.py`, `awp/providers.py` |

## 5. Nối với một đối tác (không có mã domain trong platform)

Platform chỉ có API. Đối tác (Vinhomes hay đối tác khác) tự viết bộ nối ở package của mình; việc khai báo diễn ra qua API admin. Hướng dẫn từng bước: `docs/WORKFORCE_V1_HUONG_DAN_KET_NOI.md`.

| Hướng | Cách | Tình trạng |
|---|---|---|
| Đối tác gửi tin cư dân | `POST /workforce/v1/partner/requests` (`start_workflow`, `workflow_reply`), idempotent theo `external_request_id` | Xong (S2, S3) |
| Đối tác đọc kết quả | 200 kèm tin, hoặc 202 rồi `GET requests/{id}`, snapshot, history, SSE (`events`) | Xong (S2) |
| Cư dân đồng ý chi phí / xác nhận hoàn thành | `POST approvals/{id}/decision`, `POST workflows/{id}/close` | Xong (S4) |
| Đối tác khai tool cho agent (tra cứu, hành động) | MCP server và tool khai theo route qua `PUT /platform/v1/wf/routes/{id}/mcp` và `.../tools` | Xong với MCP giả (T1); MCP thật của Vinhomes chưa kiểm |
| Backend nghiệp vụ báo tiến độ | `POST /workforce/v1/provider/job-events`, khóa riêng và chữ ký HMAC trên byte thô; schema sự kiện khai theo integration | Xong (T2) |
| Khai báo đối tác: client, khóa, route (hồ sơ leader, luật chống bịa, câu trả lời an toàn, chính sách), integration | `/platform/v1/wf/...` (admin) | Xong (S1) |
| Hồ sơ agent (vai, tool được phép, kiến thức, tầng model) | `/platform/v1/profiles` | Xong |
| Platform gọi ngược đối tác bằng webhook | Không có: đối tác kéo qua GET/SSE, platform chỉ gọi MCP của đối tác | Đã gỡ ở P4 (D1) |

Hợp đồng hai bên là `docs/contract/CONTRACT_TICH_HOP_DOI_TAC.md`. API cũ (`/platform/v1/intake`, `cases/by-ref/.../messages`, webhook ký HMAC, `CaseRequest`, `DomainPack`, khóa dịch vụ) đã bị xóa ở P4 theo quyết định D1; gói Vinhomes cũ nằm trong lịch sử git và chỉ để tham khảo.

## 6. Phạm vi triển khai platform

**Xong (có test, model giả, đối tác giả):** hồ sơ agent có bản nháp và công bố; case file dùng chung; tool giao thức có kiểu; bản tin phòng; cổng chống bịa; sổ chi phí, ngân sách, tầng model, cắt tool theo vai; Workforce v1 P0-P4: khóa/route/residence, request/idempotency/binding, event log, snapshot, SSE, engine thật có leader sống lâu, approval và `CaseAskConsent`, close do đối tác, công cụ đối tác qua MCP với sổ operation chống gọi hai lần, Provider Event API có chữ ký, thứ tự, hộp thư và đánh thức; vụ chờ nhân viên không bị đóng nhầm; bộ kiểm tuân thủ hợp đồng (`tests/workforce/test_compliance.py`).

**Còn lại:**
1. P5: Redis (nhiều tiến trình), PostgreSQL và Alembic, lease và phục hồi job, lên lịch dọn dữ liệu theo thời hạn lưu, tài sản (ảnh) lên MinIO, tải 20 workflow song song.
2. Chạy bằng model thật và đo chất lượng (kể cả tiếng Việt), chi phí, nén ngữ cảnh với workflow nhiều ngày (cần khóa).
3. Thử kho tri thức theo hồ sơ và bộ nhớ riêng của agent với kho thật.
4. Giao diện quản trị (hồ sơ agent, workflow, chi phí) và SDK ngắn cho ứng dụng của đối tác.
5. Khai báo thật của Vinhomes (hồ sơ agent, MCP, schema sự kiện) và bộ nối: làm ở `vinhome_Recident`, chỉ qua API này.

## 7. Giới hạn đã biết

- Chưa đo bằng model thật vì chưa có khóa còn hạn mức; mọi test dùng model giả có kịch bản và đối tác giả.
- Số liệu Jev (giá, tốc độ) là của hãng. Cần đo trên dữ liệu của ta trước khi dựa vào.
- SQLite và bus trong bộ nhớ chỉ hợp một tiến trình; Postgres/Redis chưa chạy (P5).
- Guard so con số theo từng token; ngày viết khác định dạng bị coi là khác. Luật cụm từ so khớp chuỗi con, không hiểu phủ định (xem `docs/WORKFORCE_V1_QUYET_DINH.md`, mục S3 và T2).
- Mạng gọi ra ngoài duy nhất của platform là MCP của đối tác, có kiểm SSRF và ghim địa chỉ DNS (T1).

## 8. Đo được

Cắt tool theo vai loại khoảng 74–77% ký tự schema tool gửi đi (`/platform/v1/metrics`, bộ tool thử nghiệm). Đó là ký tự, không phải token. Con số "khoảng 1000 token nền mỗi lượt" tôi nêu ở lần chạy thử đầu không tính tool và không dùng được.
