# Lõi platform trung lập: kế hoạch triển khai

Nhánh: `feat/platform-core` (tách từ `dev_Vinhome`). Cập nhật: 09/10/2026.
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
| 6 | Lõi hoàn thiện trước. Gói Vinhomes nối vào lõi qua một cổng nhận vụ việc trung lập. Kịch bản vàng của Vinhomes chưa commit nên chưa đưa vào kiểm thử. |

## 3. Kiến trúc

```
Ứng dụng domain (Vinhomes)      Lõi platform (awp)                    AgentScope
 Reception ──ticket──►  Cổng nhận vụ việc  ─► Case file (DB riêng)
                         /platform/v1/intake     │  sự kiện, bằng chứng, việc, quyết định
                              │                  ▼
                              └──► Phòng xử lý (leader + chuyên viên) ◄── bản tin phòng (digest)
                                       │  tool có kiểu: Báo cáo / Hỏi / Phản biện / Trả lời / Chốt
                                       ▼
 Reception ◄─callback── Kết quả đã qua cổng chống bịa ◄── Cổng chống bịa (mã + Jev)
                          Sổ chi phí, định tuyến model, giới hạn tool theo vai
```

Cắm vào AgentScope bằng các điểm mở rộng có sẵn: `extra_agent_middlewares`, `extra_agent_tools`, `custom_subagent_templates`, middleware ASGI và REST công khai.

## 4. Sáu khối

| Khối | Nội dung | Mã |
|---|---|---|
| Hồ sơ agent | Vai, phạm vi, tool được phép, kiến thức, bộ nhớ, model, ngân sách, leo thang. Có bản nháp và bản công bố. Biên dịch thành mẫu sub-agent. | `awp/profiles` |
| Case file | Sự kiện có bằng chứng, việc, quyết định, câu hỏi mở, bằng chứng tự ghi từ kết quả tool. Chỉ ghi thêm, không sửa. | `awp/casefile` |
| Bản tin phòng | Mỗi lượt, mỗi agent nhận một đoạn ngắn: ai nói gì, ai đang làm gì, còn gì chờ. Chỉ phần mới từ lần xem trước. | `awp/middleware/digest.py` |
| Giao thức | Tool có kiểu thay cho tin tự do. Nhắn thẳng người nhận. Mỗi sự kiện tối đa 2 vòng phản biện, sau đó leader chốt. | `awp/protocol` |
| Cổng chống bịa | Mọi khẳng định phải dẫn mã bằng chứng. Code kiểm mã có thật, số, mã, trạng thái có trong bằng chứng. Jev (nếu bật) chấm khẳng định có được bằng chứng ủng hộ không. Sai thì trả lỗi để agent sửa, hết lượt thì "chưa đủ thông tin" và leo thang. | `awp/guard` |
| Chi phí | Cắt tool theo vai trước mỗi lần gọi model. Sổ chi phí theo vụ, agent, model. Ngân sách theo vụ. Định tuyến model theo tầng. | `awp/middleware/ledger.py`, `awp/routing.py` |

## 5. Nối với Vinhomes

1. Reception nhận yêu cầu của cư dân, tự xử lý phần đơn giản. Với vụ cần nhiều bên, nó gửi một ticket tới `POST /platform/v1/intake` (khóa dịch vụ riêng cho từng domain).
2. Cổng nhận vụ việc chuyển ticket thành `CaseIntake` trung lập, tạo case file, tạo phiên cho leader (Supervisor) và bắt đầu xử lý.
3. Leader mời các chuyên viên theo hồ sơ của gói Vinhomes. Chuyên viên gọi tool của gói, các tool này gọi backend Vinhomes bằng token ủy quyền của vụ việc.
4. Khi leader chốt, kết quả đi qua cổng chống bịa rồi gửi về Reception qua callback (có chữ ký). Reception báo lại cư dân.
5. Bộ chuyển đổi Vinhomes (`packs/vinhomes`) ánh xạ hợp đồng `schema_v2` của Reception với `CaseIntake` và `CaseResult`. Lõi không chứa tên Vinhomes.

Chi tiết hợp đồng nằm trong `packs/vinhomes/README.md` khi hoàn thành.

## 6. Giai đoạn và kiểm chứng

| Giai đoạn | Nội dung | Kiểm chứng |
|---|---|---|
| G1 | Khung gói, cấu hình, nhà cung cấp, case file, giao thức, bản tin phòng | Test đơn vị; test hai chuyên viên hỏi và phản biện nhau, leader chốt |
| G2 | Hồ sơ agent, cắt tool, sổ chi phí, ngân sách | Số token nền mỗi lượt giảm so với mốc 994/1085; chi phí ghi đúng theo vụ |
| G3 | Cổng chống bịa (mã + Jev tùy chọn) | Khẳng định thiếu bằng chứng bị chặn; số sai bị chặn; "chưa đủ thông tin" hợp lệ |
| G4 | Cổng nhận vụ việc, callback, gói Vinhomes, xác thực khóa, che khóa API | Test đầu-cuối bằng model giả: ticket vào, leader mời chuyên viên, kết quả ra callback |

Model giả (không tốn tiền) dùng để kiểm đường ống. Chất lượng câu trả lời thật chỉ đo được khi có khóa model.

## 7. Giới hạn đã biết

- Chưa đo bằng model thật vì chưa có khóa còn hạn mức.
- Kịch bản vàng Vinhomes chưa có, nên chưa đo tỷ lệ bịa trên dữ liệu thật.
- Số liệu Jev (giá, tốc độ) là của hãng. Cần đo trên dữ liệu của ta trước khi dựa vào.
- Bộ nhớ dài hạn theo agent dùng middleware có sẵn của AgentScope (`AgenticMemory`, `Mem0`, `ReMe`), chưa được thử ở đây.
- Giao diện quản trị chưa thuộc phạm vi G1–G4.

## 8. Trạng thái (09/10/2026, cuối ngày)

| Mục | Trạng thái | Bằng chứng |
|---|---|---|
| G1 khung, case file, giao thức, bản tin phòng | Xong | `platform_VP/core`, 20+ test |
| G2 hồ sơ agent, cắt tool, sổ chi phí, ngân sách | Xong | Cắt tool giảm khoảng 74–77% ký tự schema tool trong test (`/platform/v1/metrics`); chi phí ghi theo tầng model |
| G3 cổng chống bịa | Xong phần mã; Jev mới kiểm với bản giả | Test: con số bịa bị từ chối, ý kiến thứ hai chặn được |
| G4 cổng nhận vụ việc, callback, bảo mật | Xong | Test đầu-cuối với dịch vụ AgentScope thật + model giả |
| Gói Vinhomes | Xong phần kết nối (`platform_VP/packs/vinhomes`) | 65 test với backend giả mô phỏng `/integration/v1/*`; chưa chạy với vinhomes-api thật |
| Rà soát độc lập | Xong, đã sửa 12 lỗi chắc chắn | `core/tests/test_review_fixes.py` |
| Chạy bằng model thật | Chưa | Chờ khóa còn hạn mức |

Sửa một nhận định trước đó: con số "khoảng 1000 token nền mỗi lượt" tôi nêu ở lượt chạy thử đầu *không* tính tool (model giả chỉ ước lượng token từ tin nhắn). Phép đo mới ở trên đếm đúng ký tự schema tool gửi đi: ví dụ một lần chạy có 20 lượt gọi model, schema tool toàn bộ khoảng 29 nghìn ký tự mỗi lượt, sau khi cắt còn khoảng 7 nghìn ký tự. Đó là ký tự, không phải token, và là phép đo trên bộ tool thử nghiệm.
