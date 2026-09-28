import type { VhQcResult } from '../types/qc';

export const MOCK_QC_RESULTS: VhQcResult[] = [
  // 1. QC FAIL cho Thang máy lần 1 (WO-2026-074) -> Kích hoạt Redo WO-2026-079
  {
    id: 'QC-2026-01',
    work_order_id: 'WO-2026-074',
    outcome: 'FAIL',
    criteria: [
      { criterion_id: 'CRIT-MEP-01', label: 'Thử áp lực / tải trọng an toàn', passed: true },
      { criterion_id: 'CRIT-MEP-03', label: 'Độ rung chấn cơ khí thang máy < 0.20 m/s2', passed: false, note: 'Độ rung thực tế đo được 0.35m/s2 vượt mức cho phép' },
      { criterion_id: 'CRIT-MEP-05', label: 'Ảnh chụp mặt đồng hồ đo hiện trạng', passed: true },
    ],
    failed_criteria: ['CRIT-MEP-03: Độ rung chấn cơ khí thang máy vượt ngưỡng cho phép (0.35 m/s2 > 0.20 m/s2)'],
    redo_required: true,
    note: 'Yêu cầu nhà thầu Schindler thay thế toàn bộ guốc dẫn hướng và cân chỉnh ray lần 2.',
    checked_by: 'usr-tech-01',
    checked_by_name: 'Nguyễn Văn Hùng (Kỹ sư Trưởng)',
    checked_at: new Date(Date.now() - 85 * 60 * 1000).toISOString(),
  },

  // 2. QC PASS cho Thang máy sau khi REDO (WO-2026-079)
  {
    id: 'QC-2026-02',
    work_order_id: 'WO-2026-079',
    outcome: 'PASS',
    criteria: [
      { criterion_id: 'CRIT-MEP-01', label: 'Thử tải trọng an toàn thang máy', passed: true },
      { criterion_id: 'CRIT-MEP-03', label: 'Độ rung chấn cơ khí thang máy < 0.20 m/s2', passed: true, note: 'Độ rung đo lại đạt 0.12m/s2, chạy êm ái' },
      { criterion_id: 'CRIT-MEP-04', label: 'Kiểm tra hoạt động phanh hãm an toàn', passed: true },
      { criterion_id: 'CRIT-MEP-05', label: 'Ảnh chụp đo đạc và biên bản kiểm định', passed: true },
    ],
    failed_criteria: [],
    redo_required: false,
    note: 'Nghiệm thu đạt yêu cầu vận hành trở lại phục vụ cư dân.',
    checked_by: 'usr-tech-01',
    checked_by_name: 'Nguyễn Văn Hùng (Kỹ sư Trưởng)',
    checked_at: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
  },

  // 3. QC PASS cho Khóa van cấp nước (WO-2026-081)
  {
    id: 'QC-2026-03',
    work_order_id: 'WO-2026-081',
    outcome: 'PASS',
    criteria: [
      { criterion_id: 'CRIT-MEP-02', label: 'Không còn rò rỉ nước tại van khóa', passed: true },
      { criterion_id: 'CRIT-MEP-05', label: 'Ảnh chụp van khóa ở trạng thái đóng hoàn toàn', passed: true },
    ],
    failed_criteria: [],
    redo_required: false,
    note: 'Đã cô lập hoàn toàn nguồn nước cấp lên tầng 12, an toàn để hàn ống.',
    checked_by: 'usr-tech-01',
    checked_by_name: 'Nguyễn Văn Hùng (Kỹ sư Trưởng)',
    checked_at: new Date(Date.now() - 38 * 60 * 1000).toISOString(),
  },

  // 4. QC PASS cho Vệ sinh mặt đường cổng an ninh 2 (WO-2026-085)
  {
    id: 'QC-2026-04',
    work_order_id: 'WO-2026-085',
    outcome: 'PASS',
    criteria: [
      { criterion_id: 'CRIT-SAN-01', label: 'Sạch sẽ hoàn toàn rác và bùn đất mặt đường', passed: true },
      { criterion_id: 'CRIT-SAN-02', label: 'Đường khô ráo, không còn vệt bùn trơn trượt', passed: true },
      { criterion_id: 'CRIT-SAN-05', label: 'Đầy đủ bộ ảnh Before và After', passed: true },
    ],
    failed_criteria: [],
    redo_required: false,
    note: 'Đã rửa sạch mặt đường cổng 2, đảm bảo mỹ quan đô thị.',
    checked_by: 'usr-san-01',
    checked_by_name: 'Trần Thị Mai (Giám sát Vệ sinh)',
    checked_at: new Date(Date.now() - 20 * 60 * 1000).toISOString(),
  },
];
