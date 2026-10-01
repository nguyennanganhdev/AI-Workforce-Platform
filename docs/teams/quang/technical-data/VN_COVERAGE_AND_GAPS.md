# Độ phủ dữ liệu Việt Nam và mức sẵn sàng RAG

Rà soát 2026-10-01. `VN_SOURCE_FACTS.jsonl` là tri thức tham khảo có provenance; `VN_PUBLIC_CASES.jsonl` là **10 phản ánh công khai đã diễn giải** từ một cổng ở Huế, không phải ticket Vinhomes, không có work order/ảnh được cấp quyền. Không suy từ `agency_response` thành kết quả sửa đã xác minh. Cả 10 ca chỉ phục vụ test retrieval, triage, phân biệt scope và kiểm tra nhãn bằng chứng. Chúng không làm tăng số ca kỹ thuật viên Vinhomes đã xác minh.

| Issue A2 | Nguồn VN sát nhất | Ca công khai trực tiếp | Khoảng trống quan trọng |
| --- | --- | --- | --- |
| `TECH.ELEC.BREAKER_TRIP` | VN-PMC-02, VN-MOIT-01 | Chưa có | CB/asset, sơ đồ nhánh, kết quả đo và policy điện đúng tòa |
| `TECH.ELEC.FIXTURE_FAILURE` | VN-PMC-02, VN-MOIT-01 | Không; VN-CASE-008 là đèn **đường ngoài tòa** | Phân ranh asset chung cư/đô thị, manual và work order |
| `TECH.PLUMB.WATER_HEATER` | VN-PN-02 | Chưa có | Model thực tế, manual đúng model, nguyên nhân và nghiệm thu |
| `TECH.PLUMB.WATER_FILTER_LOW_FLOW` | VN-PN-03: quy trình bảo dưỡng RO Panasonic | Chưa có | Asset/model/lõi, đo lưu lượng và chất lượng nước; không suy nước uống an toàn từ TDS |
| `TECH.HVAC.CONDENSATION` | VN-DK-01, VN-PN-01 | Chưa có | Model dàn lạnh, nguồn rò xác nhận, ảnh/số đo và thử thoát |
| `TECH.PLUMB.CONCEALED_LEAK` | VN-PMC-01, VN-WEBER-01 | VN-CASE-006: **người dân báo thấm nhưng không thấy lúc kiểm tra**, không gán mã xác nhận | Ca dương tính đã xác minh, quyền tiếp cận căn liên quan |
| `TECH.PLUMB.SHOWER_SEAL` | VN-WEBER-01 gián tiếp; chưa có manual đúng vách/model | Chưa có | Cấu hình vách, thử nước có kiểm soát, nghiệm thu |
| `TECH.PLUMB.TOILET_LEAK` | VN-INAX-01 | Chưa có | Phân biệt rò nước sạch/nước thải/trong bồn, model bộ xả |
| `TECH.PLUMB.TRAP_ODOR` | VN-PMC-01, VN-INAX-01 | Chưa có | Nguồn mùi được kỹ thuật viên xác nhận, nhiều căn hay đơn lẻ |
| `TECH.PLUMB.SUPPLY_DRAIN_JOINT` | VN-PMC-01 | Không; VN-CASE-002 là thiếu nước toàn tòa | Ca đúng một fixture/đầu nối, áp lực/lưu lượng thực đo |
| `TECH.ARCH.DOOR_WINDOW` | VN-PMC-03 | Chưa có | Asset cửa, bộ phụ kiện, kết quả kiểm tra nguy cơ rơi |
| `TECH.ARCH.CABINET_SAG` | VN-BLUM-01 cho bản lề, không cho neo thân tủ | Chưa có | Loại tủ, điểm neo, tải, manual nhà cung cấp |
| `TECH.ARCH.CRACK` | VN-IBST-01: ví dụ kiểm định nứt sàn tại chung cư Nam Đô | Chưa có | Phân loại kết cấu/hoàn thiện bởi chuyên gia, đo và theo dõi vết nứt tại tòa thực tế |
| `TECH.ARCH.PAINT_MOISTURE` | VN-WEBER-01 gián tiếp cho khu ướt | Chưa có | Nguồn ẩm, phép đo, xử lý nguồn và theo dõi tái phát |
| `TECH.ARCH.FLOOR_DAMAGE` | VN-AC-01: cấu tạo sàn gỗ công nghiệp, không xác nhận vật liệu lắp thực tế | Chưa có | Vật liệu đúng căn hộ, độ phẳng, nguồn ẩm, nghiệm thu |
| `TECH.PLUMB.SEWAGE_BACKFLOW` | VN-PMC-01 | VN-CASE-001: phản ánh trào, **chưa xác nhận đã sửa** | Nguyên nhân, vệ sinh/khử nhiễm, work order và hậu kiểm |

## Cách đưa vào RAG POC

1. Index `RAG_CHUNKS.jsonl` trong namespace `triage_reference_internal_poc` và join `RAG_SOURCE_MANIFEST.jsonl` để có URL; `VN_PUBLIC_CASES` chỉ ở namespace **case_example_vn** riêng. Không gộp case hoặc fact tham khảo với SOP. Mọi kết quả phải trả `source_id`, URL, đoạn nguồn và nhãn `claim`/`agency_response`/`verified`.
2. Chỉ dùng corpus này cho trả lời có trích nguồn, hỏi bổ sung và định tuyến bản nháp. Khi câu hỏi đòi SOP cụ thể của tòa, giá, SLA, quyền vào căn, mức khẩn chính thức hoặc khẳng định đã sửa: trả `insufficient_authorized_data` và chuyển người phụ trách.
3. Gắn `issue_code=null` cho domain ngoài 16 mã. Không ép sự cố thang máy, PCCC, điện dự phòng hoặc nước cấp toàn tòa vào lỗi fixture trong căn. Nước gần điện vẫn phải báo tín hiệu an toàn để người trực đánh giá.
4. Dùng `claim_evidence_status`, `repair_evidence_status`, `diagnosis_evidence_status` thay boolean mơ hồ. `unverified` nghĩa là **chưa có chứng cứ xác nhận**, không phải sai; `not_observed_at_inspection` chỉ nói về thời điểm kiểm tra. `agency_reports_restored_no_work_order` là lời cơ quan trên cổng, chưa phải nghiệm thu kỹ thuật A2.
5. Chỉ nhập diễn giải ngắn đã khử PII và URL. Không tải ảnh, họ tên, số căn, địa chỉ chi tiết hay bình luận. Trước triển khai thực tế cần kiểm tra giấy phép/điều khoản sử dụng từng nguồn và BQL/Domain Owner phê duyệt.

## Kết luận readiness

Đủ để dựng một **RAG POC có citation và refusal/abstention**, kiểm tra phân loại sự cố, tìm tài liệu tham khảo VN và nhận biết thiếu dữ kiện. **Chưa đủ cho RAG vận hành cư dân Vinhomes**: thiếu SOP BQL được publish theo tòa, asset/model, ticket→work order→evidence→kết quả được xác minh, policy V3 và quyền sử dụng toàn văn. Bộ ca công khai ở đây làm phong phú test nhưng không thay dữ liệu nội bộ đó.
