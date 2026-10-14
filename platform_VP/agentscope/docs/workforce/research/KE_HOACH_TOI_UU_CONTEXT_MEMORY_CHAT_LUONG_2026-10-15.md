# Tối ưu context, memory, chất lượng và chi phí token — hiện trạng và kế hoạch

15/10/2026 · `develop2` + PR #87 · Người đọc: PM

Tài liệu này trả lời câu hỏi: những phần context, Shared Context, bộ nhớ dài hạn,
học từ kết quả, kiểm soát chất lượng và chi phí token đã làm tốt chưa, còn
thiếu gì, và làm tiếp thế nào. Phần hiện trạng đo từ code và log thật; phần
giải pháp dựa trên tài liệu gốc của OpenAI/Anthropic và các bài báo, xem
[NGHIEN_CUU_TOI_UU_CONTEXT_MEMORY_CHI_PHI_2026-10-15.md](NGHIEN_CUU_TOI_UU_CONTEXT_MEMORY_CHI_PHI_2026-10-15.md).

## 1. Hiện trạng (đo từ code và log)

### 1.1 Kích thước một lần gọi model (log `Model input`, kịch bản offline có prompt và tool thật)

| Agent | Tool schema | System prompt | Hội thoại + Shared Context | Tổng |
|---|---|---|---|---|
| Leader (gpt-5.5) | 2.461 | 2.081 | 173 → 4.299 trong một lượt | 4,7k → 8,8k |
| Thành viên (mini) | 340–414 | 1.256–1.266 | 1.187 → 2.814 | 2,8k → 4,5k |

Trước thiết kế phòng: Leader đối tác 13–15k token mỗi lần gọi, 9–15 lần mỗi phiếu.
Phần cố định của Leader (tool + system ≈ 4,5k) được cache nếu prefix không đổi.

### 1.2 Đã có

| Mảng | Đã có | Ghi chú |
|---|---|---|
| Shared Context | Gói ngữ cảnh chung có ngân sách 12k token; tóm tắt sự kiện cũ khi vượt 80% ngân sách; gộp kết quả tool trùng; kết quả tool đối tác chỉ giữ 1.200 ký tự; gói đặt ở CUỐI prompt để giữ prefix cache | Tốt |
| Prompt cache | `prompt_cache_key` theo agent (bật ở local) | Tốt |
| Phân tầng model | Leader gpt-5.5; thành viên mini | Tốt |
| Giới hạn phòng | ≤24 lượt trao đổi, ≤16 lần gọi, ≤200k token, ≤180 s mỗi nhánh; chặn hỏi vòng | Tốt |
| Chống bịa | Mã bằng chứng E; CaseSay từ chối con số không có trong bằng chứng; cụm từ cấm; câu trả lời an toàn | Tốt |
| Bộ nhớ dài hạn | Trích ký ức sau phiếu thành công (có nguồn), hợp nhất ADD/UPDATE/NOOP (kiểu mem0), tìm theo từ khóa BM25, mỗi lượt ≤5 ký ức / 2.400 ký tự | Khá |
| Tự cải thiện | Đề xuất luật mới, chỉ nhận khi bộ test của agent không tụt (tắt cho agent đối tác) | Khá |
| Kiểm thử | Studio: ≥3 kịch bản, tool đọc thật, tool ghi giả lập, model chấm, ≥80% mới phát hành | Khá |
| Theo dõi | Token vào/ra/cache theo agent và theo phiếu; dòng thời gian phòng | Tốt |

### 1.3 Thiếu hoặc chưa tối ưu

| # | Vấn đề | Bằng chứng trong code | Ảnh hưởng |
|---|---|---|---|
| G1 | Lịch sử riêng của Leader không bao giờ được tóm tắt: ngưỡng nén là 80% cửa sổ context, mà card `gpt-5.5` ghi 1.050.000 token → chỉ nén khi vượt ~840k. `gpt-5.4-mini` không có card nên lấy mặc định 32.768 → thành viên nén quanh ~26k | `ContextConfig.trigger_ratio=0.8`; `_openai_chat/_models/gpt-5.5.yaml`; `_service/_chat.py` (private_prompt_limit) | Phiếu nhiều lượt: mỗi lượt Leader gửi lại toàn bộ hội thoại cũ trên model đắt nhất → chi phí tăng theo số lượt |
| G2 | Kết quả tool cũ nằm nguyên trong lịch sử riêng của thành viên | Không có bước thay kết quả cũ bằng tham chiếu | Thành viên trả tiền cho dữ liệu đã dùng xong |
| G3 | Không đặt `reasoning_effort` / độ dài trả lời; không đếm token suy luận | `_openai_chat/_model.py`: chỉ gửi khi `thinking_enable`; app không đặt | Không kiểm soát được phần chi phí lớn nhất của model suy luận |
| G4 | Tool schema của Leader 2,5k token (AgentInvite mô tả mọi agent, TeamDelete không cần) | Log `tools=2461` | Mỗi lần gọi Leader |
| G5 | Học kinh nghiệm chạy khi Leader MỜI xác nhận, không phải khi cư dân XÁC NHẬN; không học từ "Chưa đạt"/mở lại | `_runner._case_turn`: `_learn_from_room` ở `AWAITING_CONFIRMATION` | Học cả phiếu cư dân sau đó chê; bỏ phí tín hiệu thật |
| G6 | Bộ nhớ không có quên/giảm dần, không ghi ký ức nào được dùng và có giúp không | `_agent_memory.py` không có trường dùng/hiệu quả | Bộ nhớ phình, ký ức sai sống mãi |
| G7 | Biến `MEMORY_EMBEDDING_*` có trong `.env` nhưng code không dùng | grep | Cấu hình gây hiểu nhầm |
| G8 | Chưa có chỉ số chất lượng theo phiếu: tỉ lệ CaseSay bị từ chối, phiếu `needs_attention`, cư dân xác nhận lần đầu, mở lại, token/phiếu thành công | Chỉ có token | Không biết thay đổi nào làm tốt hơn |
| G9 | Chưa có bộ đánh giá cho cả phòng nhiều agent (chỉ chấm từng agent) | Studio tests | Không bắt được lỗi phối hợp |
| G10 | Phiếu lỗi lượt (`needs_attention`) không tự chạy lại | — | Đã ghi ở kế hoạch trước |

| G11 | Ký ức gợi lại (recall) được nối vào CUỐI system message. Recall tính lại mỗi lượt theo câu mới của người dùng, nên khi nó đổi thì toàn bộ lịch sử phía sau system message mất cache | `_service/_chat.py`: `system_prompt = runtime_system_prompt + attachment` (attachment gồm `_recalled_memory`) | Cache hit thấp ở các lượt sau của thành viên có bộ nhớ |
| G12 | Mọi agent OpenAI chạy qua Chat Completions (`OpenAIChatModel`), nên reasoning của model không được truyền lại giữa các lần gọi tool. OpenAI khuyến nghị truyền lại; cookbook ghi cache tăng 40% → 80% khi chuyển sang Responses | `credential/_openai.py: get_chat_model_class → OpenAIChatModel`; fork đã có `_openai_response` | Chất lượng và cache của Leader |

## 2. Điều nghiên cứu thay đổi kế hoạch

Chi tiết và nguồn trong file nghiên cứu. Ba điều ảnh hưởng trực tiếp:

- **Không fine-tune / RFT được trên OpenAI**: tổ chức chưa từng fine-tune bị chặn từ 07/05/2026; RFT chỉ cho `o4-mini`. Vì vậy "học tăng cường" của ta = luật, prompt và bộ nhớ học từ kết quả thật, có cổng kiểm thử, không phải huấn luyện lại model.
- **OpenAI Evals tắt 30/11/2026**: giữ bộ kiểm thử của mình (Studio tests + kịch bản phòng), không chuyển sang Evals.
- **Bộ nhớ chỉ có lợi khi lọc chặt**: lưu chỉ kinh nghiệm đã qua bộ chấm nghiêm tăng 15–25 điểm thành công và bộ nhớ nhỏ hơn 14–58% (Xiong et al. 2025); ký ức sai bị agent bắt chước và lan lỗi.

## 3. Kế hoạch

Nguyên tắc: mỗi thay đổi có một chỉ số chứng minh và một test; đo trước, sửa sau.

### Đợt 1 — trước demo 22/10 (rủi ro thấp, đo được ngay)

| Việc | Sửa gì | Giải quyết | Xong khi (chỉ số) |
|---|---|---|---|
| 1.1 Nén lịch sử riêng theo token tuyệt đối | Ngưỡng nén lịch sử riêng = min(80% cửa sổ, N token), N cho Leader ~16k, thành viên ~12k; tóm tắt theo mẫu cố định (việc đã làm, mã E/ID, giả định, vướng mắc, bước tiếp); không nâng mức thẩm quyền | G1 | Input mỗi lần gọi Leader ở lượt thứ 3+ không vượt ~20k; kịch bản nhiều lượt đạt |
| 1.2 Thu dọn kết quả tool cũ | Trong lịch sử riêng, kết quả tool đã có trong báo cáo → thay bằng "E7: (đã dùng, xem nhật ký phiếu)"; chỉ làm khi giải phóng đủ ≥2k token (để không phá cache liên tục) | G2 | Token vào của thành viên ở lượt sau giảm; không tăng CaseSay bị từ chối |
| 1.3 Đưa recall ra cuối prompt | Ký ức gợi lại vào cùng tin đính kèm cuối (cạnh gói Shared Context), không nối vào system | G11 | Cache hit thành viên lượt 2+ tăng (log `cached_input_tokens`) |
| 1.4 Cố định reasoning/độ dài theo vai trò | Đặt `reasoning_effort` cố định theo vai trò (không đổi giữa các lần gọi để giữ cache); thử `low` cho thành viên và bước học/tóm tắt, Leader giữ `medium` cho tới khi bộ đánh giá phòng cho thấy `low` không tụt; đếm reasoning token vào thống kê | G3 | Output/phiếu giảm; Studio tests không tụt |
| 1.5 Gọn tool của Leader | Bỏ TeamDelete khỏi Leader phiếu đối tác; mô tả AgentInvite chỉ còn thành viên của tuyến | G4 | `tools=` của Leader từ 2.461 xuống <1.500 |
| 1.6 Học khi cư dân xác nhận, không khi Leader mời | Gọi học ở lúc đóng phiếu với `resident_confirmed`; phiếu "Chưa đạt"/mở lại → ghi kinh nghiệm thất bại, không lưu thành ký ức tốt | G5 | Không còn ký ức từ phiếu bị chê; test |
| 1.7 Chỉ số chất lượng theo phiếu | Thêm vào bảng Hoạt động: tỉ lệ CaseSay bị từ chối, phiếu `needs_attention`, cư dân xác nhận lần đầu, mở lại, token và $ / phiếu thành công, cache % | G8 | Hiện trên UI, có số thật sau một ngày chạy |

### Đợt 2 — sau demo (chất lượng và bộ nhớ)

| Việc | Sửa gì | Giải quyết | Xong khi |
|---|---|---|---|
| 2.1 Lọc ký ức chặt | Chỉ lưu ký ức mà mọi sự kiện nguồn là `tool_verified`/`customer_confirmed`; mâu thuẫn → đánh dấu hết hiệu lực kèm thời điểm (không xoá) | G6 | Số ký ức/agent giảm; pass rate kịch bản có/không bộ nhớ |
| 2.2 Theo dõi ký ức được dùng | Ghi ký ức nào được gợi lại ở phiếu nào và kết quả phiếu; định kỳ bỏ ký ức hay đi cùng phiếu thất bại hoặc lâu không dùng; điểm gợi lại = liên quan + mới + quan trọng | G6 | Báo cáo ký ức có hại; pass rate không giảm |
| 2.3 Bộ đánh giá phòng | 20–30 kịch bản phòng lấy từ lỗi thật (Vinhome 12 kịch bản vàng làm gốc), chạy model thật k=3 lần (pass^k), chấm theo kết quả cuối trong DB đối tác + bộ chấm MAST | G9 | Báo cáo pass^3 theo kịch bản; chạy trước mỗi lần đổi prompt |
| 2.4 Việc nền chạy Flex | Trích/hợp nhất ký ức, tự cải thiện, Studio tests, chấm vết dùng `service_tier=flex` (rẻ 50%) | Chi phí | $ việc nền/tuần giảm ~50% |
| 2.5 Thay đổi prompt/luật = một bản phát hành | Có version, bộ hồi quy ~100%, pass^k, người duyệt, quay lại một nút (đã có một phần ở `self_improve`) | An toàn | Không có hồi quy lọt |
| 2.6 Tự chạy lại phiếu lỗi lượt | `needs_attention` do lỗi model/hết tiền → tự thử lại có giới hạn | G10 | Phiếu không kẹt |

### Đợt 3 — khi bộ đánh giá phòng ổn định

| Việc | Ghi chú |
|---|---|
| 3.1 Chuyển Leader sang Responses API, truyền lại reasoning items | G12; đo cache và chất lượng bằng bộ đánh giá phòng trước khi bật cho mọi agent |
| 3.2 Báo cáo thành viên có cấu trúc (Structured Outputs: kết luận, mã E, điều chưa chắc, câu đề xuất) | Leader đọc ít hơn, ít gọi hơn |
| 3.3 Thử model rẻ hơn (gpt-5.6-luna cho thành viên, gpt-5.6-sol cho Leader) | Chỉ đổi khi pass^k không giảm; luật cache GPT-5.6 khác |
| 3.4 Tối ưu prompt offline (GEPA/DSPy) trên bộ kịch bản | Cần bộ chấm có lý do trượt; chạy bằng Flex |

### Không làm

Fine-tune/RFT trên OpenAI; chuyển kiểm thử sang OpenAI Evals; dùng compaction mã hoá của OpenAI thay Shared Context (không đọc và trích dẫn được); Predicted Outputs (không hỗ trợ GPT-5.x và tools); tăng `reasoning_effort` khi chưa có bằng chứng từ kiểm thử.

## 4. Ước tính tác động (cần đo lại bằng số thật khi có key)

Giá gpt-5.5: $5 / 1M input, $0,50 cached, $30 output; gpt-5.4-mini: $0,75 / $0,075 / $4,50.
Trước thiết kế phòng ước khoảng $0,64 model mạnh mỗi phiếu (12 lần × 14k token, cache 65%, giả định 800 token output/lần).
Thiết kế phòng (PR #87) đã cắt phần lớn: Leader ~4 lần gọi × 5–9k token. Đợt 1 nhắm vào phần còn lại:
lịch sử dài ở phiếu nhiều lượt (1.1–1.3), output/reasoning (1.4), và tool cố định (1.5).
