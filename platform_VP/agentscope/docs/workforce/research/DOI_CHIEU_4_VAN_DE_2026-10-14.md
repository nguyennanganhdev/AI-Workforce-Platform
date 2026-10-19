# Đối chiếu 4 vấn đề (13/10) với code hiện tại

14/10/2026 · `develop2@f92613f7` + nhánh `feat/wf-partner-room` · Người đọc: PM

Kế hoạch gốc: [BAO_CAO_4_VAN_DE_VA_KE_HOACH_2026-10-13.md](BAO_CAO_4_VAN_DE_VA_KE_HOACH_2026-10-13.md).
Mỗi dòng dưới đây đã được kiểm lại trong code, không chỉ chép từ báo cáo
triển khai.

Ký hiệu: ✅ xong · 🟡 làm một phần · ❌ chưa làm.

## Tóm tắt

| Vấn đề | Mức hoàn thành | Còn thiếu chính |
|---|---|---|
| 1. Agent phối hợp kém | 🟡 Cơ chế xong, **chưa đo bằng model thật** | Bộ kịch bản phối hợp chưa chạy lần nào với model thật; bộ nhận diện "tin chỉ báo tiến độ" vẫn dùng từ khoá |
| 2. Token, memory, context | 🟡 Phần lớn xong | Chưa dọn kết quả tool cũ; phiếu đối tác chưa ghi token vào sổ của workflow; chưa có báo cáo chi phí theo phiếu trên UI |
| 3. Builder cứng | ✅ | Chất lượng copilot với model thật chưa đo |
| 4. Trang quản lý agent | 🟡 9/11 phần | Thiếu tab **Hoạt động** (ticket, token, chi phí, cache) và **chat thử** (playground) |

Ba việc "làm ngay" của kế hoạch: CI xanh ✅; Agent Spec ✅; **số đo gốc bằng
model thật ❌**. Lượt chạy thật duy nhất tới nay là một phiếu Vinhome (14/10,
đạt), chưa phải bộ kịch bản phối hợp.

## Vấn đề 1: phối hợp giữa agent

| Đề xuất 13/10 | Trạng thái | Bằng chứng trong code |
|---|---|---|
| Sổ nhiệm vụ do runtime giữ (owner, phụ thuộc, tiêu chí xong) | ✅ | `SharedTaskState.assignments`, `done_when`, `depends_on` (`_shared_context.py`); việc phụ thuộc tự giao khi việc trước báo xong |
| Model chỉ điền phần cần nghĩ | ✅ (khác thiết kế) | Thay vì 4 tool nhỏ, `TeamSay` gọn theo vai: leader chỉ thấy handoff/review/ask_customer, worker thấy result/error/question/answer/need_customer_info; runtime tự điền người nhận, id câu hỏi, bằng chứng |
| Vòng phản biện có giới hạn | ✅ | `TeamSay(kind="review", decision="accept"/"challenge"/"stop")`, giới hạn `COLLABORATION_MAX_VERIFICATIONS` |
| Prompt leader trung lập, ≤ 800 token | ✅ | `WORKFORCE_LEADER_PROMPT` = **729 token** (o200k); không còn luật du lịch; luật nghiệp vụ ở `docs/workforce/domain_packs/` và mẫu agent |
| Bỏ vá hành vi bằng từ khoá | 🟡 | Đã bỏ cổng "tính chi phí". **Còn** `_PROGRESS_ONLY_MARKERS` ("đang tìm", "please wait"…) trong `_tool/_team_say.py` |
| Model theo vai | ✅ | `WORKFORCE_LEADER_MODEL_NAME` (`gpt-5.5`) cho leader/người chấm; `gpt-5.4-mini` cho worker và tóm tắt |
| Đo trước, sửa sau (10–15 kịch bản model thật) | ❌ | Script `scripts/workforce/eval/` (7 kịch bản, chấm tự động) có sẵn nhưng **chưa chạy với model thật** |
| Phiếu đối tác dùng phòng và mời agent | ✅ (nhánh `feat/wf-partner-room`) | Leader của tuyến lập phòng khi cần, mời agent chuyên môn do đối tác khai báo, chờ báo cáo trong lượt rồi trả lời bằng `CaseSay` |

## Vấn đề 2: token, context, memory, tri thức

| Đề xuất 13/10 | Trạng thái | Bằng chứng trong code |
|---|---|---|
| Sắp prompt ổn định → thay đổi (cache) | ✅ | Gói Shared Context là message cuối `name="shared_context"`, không sửa system message |
| `prompt_cache_key` | ✅ (tuỳ chọn) | `_apply_prompt_cache_key` (`_service/_chat.py`), bật bằng `WORKFORCE_PROMPT_CACHE_KEY` |
| Ghi token cache vào số đo | ✅ | `provider_usage[...].cached_input_tokens`; endpoint `GET /workforce/console/tickets/{session_id}/metrics` |
| Dọn kết quả tool cũ khỏi context riêng | ❌ | Chưa có (chỉ có `ToolOffloadMiddleware` cho kết quả lớn) |
| Model rẻ cho tóm tắt | ✅ | Tóm tắt Shared Context dùng model mặc định khi leader dùng model mạnh |
| Bộ nhớ dài hạn (kinh nghiệm) có nguồn | ✅ | Bảng `agent_memories` (migration 0016); mỗi điều nhớ phải trích id sự kiện có thật; thay thế chứ không xoá |
| Luồng duyệt memory | ✅ theo quyết định | Agent tự duyệt (quyết định của PM); tab Bộ nhớ cho xem và loại bỏ |
| Tri thức (KB) gắn theo agent | ✅ | `knowledge` trong spec, dùng cả trong phiên được mời; chỉ mục Qdrant lưu đĩa |
| Chi phí theo phiếu | 🟡 | Phiếu console: có số đo theo agent. **Phiếu đối tác** (case runtime): sổ của workflow chỉ đếm lượt, **chưa cộng token**; chưa có màn hình chi phí |

## Vấn đề 3: Builder

| Đề xuất 13/10 | Trạng thái | Bằng chứng trong code |
|---|---|---|
| Agent Spec là nguồn sự thật | ✅ | `app/_agent_spec.py`; prompt dựng từ spec |
| Mỗi câu → bản vá + ≤ 3 câu hỏi | ✅ | `POST /studio/agents/{id}/copilot` |
| Hiện khác biệt trước khi áp | ✅ | Chi tiết agent trả bản chạy, bản nháp và phần khác |
| Sinh ca kiểm thử, chạy thật trước khi phát hành | ✅ | Phát hành cần ≥ 3 kịch bản và ≥ 80% đạt trên đúng bản nháp; tool đọc chạy thật, tool ghi mô phỏng |
| Phiên bản, rollback | ✅ | Phiên bản bất biến; ticket ghim phiên bản lúc được mời |
| Bỏ gợi ý du lịch trong Builder | ✅ | Mẫu theo ngành ở thư viện mẫu |

## Vấn đề 4: trang quản lý agent

| Đề xuất 13/10 | Trạng thái | Ghi chú |
|---|---|---|
| Danh sách (trạng thái, phiên bản, kiểm thử gần nhất, tool, luật) | ✅ | `/workforce/agents` |
| Cột "sử dụng 7 ngày" (số ticket, chi phí, tỉ lệ hoàn thành) | ❌ | |
| Tạo bằng mô tả, mẫu ngành, nhân bản | ✅ | |
| Tab Tổng quan, Hướng dẫn, Công cụ, Kiến thức, Phối hợp, Kiểm thử, Phiên bản | ✅ | Thêm tab Prompt và Bộ nhớ |
| Tab **Hoạt động** (ticket gần đây, token, chi phí, cache hit, lỗi) | ❌ | Endpoint số đo có, chưa có màn hình |
| **Chat thử** (playground, chế độ mô phỏng) | ❌ | Chỉ có chạy kịch bản kiểm thử |
| Mức duyệt theo tool | ✅ | `requires_consent` trong spec + `readOnlyHint=false` buộc hỏi khách |
| Builder copilot bên phải, sửa cùng spec | ✅ | |
| Kết nối đối tác | ✅ | Thêm ngoài kế hoạch |

## Đề xuất làm tiếp (theo thứ tự)

1. **Chạy bộ kịch bản phối hợp với model thật** (`scripts/workforce/eval/`, khoảng 7 kịch bản) để có số đo gốc: tỉ lệ đạt, token mỗi phiếu, tỉ lệ cache. Đây là việc duy nhất còn thiếu trong ba việc "làm ngay".
2. Tab **Hoạt động** cho từng agent, dùng endpoint số đo có sẵn; cộng token của phiếu đối tác vào sổ của workflow.
3. Thay `_PROGRESS_ONLY_MARKERS` bằng kiểm tra có cấu trúc: kết quả `kind="result"` phải kèm kết quả tool trong lượt.
4. Dọn kết quả tool cũ khỏi context riêng sau khi đã thành fact trong Shared Context.
5. Chat thử (playground) trong trang chi tiết agent.
