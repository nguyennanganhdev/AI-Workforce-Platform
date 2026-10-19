# Chỉ mục nghiên cứu Workforce

- [Bàn giao bản tích hợp Docker/VPS P0–P2](../BAO_CAO_BAN_GIAO_DOCKER_VPS_P0_P2_2026-10-16.md).

Các tài liệu ngày 13–15/10 là kế hoạch và bằng chứng tại thời điểm viết, không
tự chứng minh trạng thái VPS hiện tại. Đối chiếu báo cáo triển khai theo manifest.

- [Báo cáo tổng thể 16/10](../BAO_CAO_TOAN_DIEN_PLATFORM_2026-10-16.md).
- [Nghiệm thu P0](../BAO_CAO_HOAN_THANH_P0_2026-10-16.md).
- [Kết quả P2](../BAO_CAO_HOAN_THANH_P2_2026-10-16.md).
- [Runbook P2: ledger, memory, offsite, restore và cảnh báo](../../../deploy/vps/P2_RUNBOOK.md).
- [Nghiên cứu context/memory/chi phí](NGHIEN_CUU_TOI_UU_CONTEXT_MEMORY_CHI_PHI_2026-10-15.md).
- [Kế hoạch tối ưu và chất lượng](KE_HOACH_TOI_UU_CONTEXT_MEMORY_CHAT_LUONG_2026-10-15.md).
- [Kế hoạch đối tác và sandbox](KE_HOACH_DOI_TAC_VA_SANDBOX_2026-10-14.md).

P2 thay thế cách gán giá cứng theo model cuối bằng ledger từng attempt và giá
endpoint có phiên bản; giá thực tế chưa có nên cost unknown. Memory mới có CAS,
evidence cho mọi kind, provenance/TTL/retire và ablation hồi quy offline. Offsite
dùng Domain VPS, khóa giải mã ngoài hai host; diễn tập dữ liệu không phải cutover
production. Chưa coi ablation hồi quy là cải thiện business outcome đã nghiệm thu.
