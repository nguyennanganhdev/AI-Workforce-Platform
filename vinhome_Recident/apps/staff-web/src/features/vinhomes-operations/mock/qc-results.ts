import type { VhQcResult } from '../types/qc';

export const MOCK_QC_RESULTS: VhQcResult[] = [
  // 1. QC FAIL cho Thang máy lần 1 (WO-2026-084) -> Kích hoạt Redo WO-2026-089
  {
    id: 'QC-2026-01',
    work_order_id: 'WO-2026-084',
    checklist_version_id: 'CKL-VER-ELEV-01',
    outcome: 'FAIL',
    criteria: [
      {
        criterion_id: 'CRIT-ELEV-01',
        label: 'Độ rung chấn cơ khí thang máy không vượt quá 0.20 m/s2',
        passed: false,
        note: 'Độ rung thực tế đo được 0.35m/s2 vượt mức cho phép',
      },
      {
        criterion_id: 'CRIT-ELEV-02',
        label: 'Khe hở guốc dẫn hướng và ray trượt trong phạm vi 1.0 - 2.0 mm',
        passed: false,
        note: 'Khe hở đo được 3.5mm do mòn lệch',
      },
      {
        criterion_id: 'CRIT-ELEV-03',
        label: 'Kiểm tra hoạt động phanh hãm dừng tầng chính xác và êm ái',
        passed: true,
      },
      {
        criterion_id: 'CRIT-ELEV-04',
        label: 'Ảnh chụp thiết bị đo độ rung và biên bản kiểm định thang',
        passed: true,
      },
    ],
    failed_criteria: ['CRIT-ELEV-01: Độ rung chấn cơ khí thang máy vượt ngưỡng cho phép (0.35 m/s2 > 0.20 m/s2)'],
    redo_required: true,
    note: 'Yêu cầu nhà thầu Otis thay thế toàn bộ guốc dẫn hướng giảm chấn và cân chỉnh ray lần 2.',
    checked_by: 'usr-qc-01',
    checked_by_name: 'Đặng Quốc Tuấn (Kỹ sư QC Độc lập)',
    checked_at: new Date(Date.now() - 85 * 60 * 1000).toISOString(),
  },

  // 2. QC PASS cho Thang máy sau khi REDO (WO-2026-089)
  {
    id: 'QC-2026-02',
    work_order_id: 'WO-2026-089',
    checklist_version_id: 'CKL-VER-ELEV-01',
    outcome: 'PASS',
    criteria: [
      {
        criterion_id: 'CRIT-ELEV-01',
        label: 'Độ rung chấn cơ khí thang máy không vượt quá 0.20 m/s2',
        passed: true,
        note: 'Độ rung đo lại đạt 0.12m/s2, chạy êm ái',
      },
      {
        criterion_id: 'CRIT-ELEV-02',
        label: 'Khe hở guốc dẫn hướng và ray trượt trong phạm vi 1.0 - 2.0 mm',
        passed: true,
      },
      {
        criterion_id: 'CRIT-ELEV-03',
        label: 'Kiểm tra hoạt động phanh hãm dừng tầng chính xác và êm ái',
        passed: true,
      },
      {
        criterion_id: 'CRIT-ELEV-04',
        label: 'Ảnh chụp thiết bị đo độ rung và biên bản kiểm định thang',
        passed: true,
      },
    ],
    failed_criteria: [],
    redo_required: false,
    note: 'Nghiệm thu đạt yêu cầu vận hành trở lại phục vụ cư dân.',
    checked_by: 'usr-qc-01',
    checked_by_name: 'Đặng Quốc Tuấn (Kỹ sư QC Độc lập)',
    checked_at: new Date(Date.now() - 15 * 60 * 1000).toISOString(),
  },

  // 3. QC FAIL cho Khóa van cấp nước lần 1 (WO-2026-081) -> Kích hoạt Redo WO-2026-085
  {
    id: 'QC-2026-03',
    work_order_id: 'WO-2026-081',
    checklist_version_id: 'CKL-VER-MEP-01',
    outcome: 'FAIL',
    criteria: [
      {
        criterion_id: 'CRIT-MEP-01',
        label: 'Thử áp lực đường ống đạt 8-10 bar trong 30 phút không tụt áp',
        passed: false,
        note: 'Áp lực nước thử tải chưa đạt chuẩn 3.5 bar theo thiết kế kỹ thuật, vẫn còn rỉ nhẹ ở co nối',
      },
      {
        criterion_id: 'CRIT-MEP-02',
        label: 'Không còn hiện tượng rò rỉ nước tại các khớp nối',
        passed: false,
        note: 'Rỉ nhẹ tại co góc trục cấp C',
      },
      {
        criterion_id: 'CRIT-MEP-05',
        label: 'Ảnh chụp mặt đồng hồ đo và hiện trạng hoàn thiện',
        passed: true,
      },
    ],
    failed_criteria: ['CRIT-MEP-01: Áp lực nước thử tải chưa đạt chuẩn 3.5 bar theo thiết kế kỹ thuật'],
    redo_required: true,
    note: 'Áp lực nước thử tải chưa đạt chuẩn 3.5 bar theo thiết kế kỹ thuật, vẫn còn rỉ nhẹ ở co nối. Yêu cầu làm lại theo WO-2026-085.',
    checked_by: 'usr-qc-01',
    checked_by_name: 'Đặng Quốc Tuấn (Kỹ sư QC Độc lập)',
    checked_at: new Date(Date.now() - 35 * 60 * 1000).toISOString(),
  },

  // 4. QC PASS cho Vệ sinh mặt đường cổng an ninh 2 (WO-2026-080)
  {
    id: 'QC-2026-04',
    work_order_id: 'WO-2026-080',
    checklist_version_id: 'CKL-VER-SAN-01',
    outcome: 'PASS',
    criteria: [
      {
        criterion_id: 'CRIT-SAN-01',
        label: 'Sạch sẽ hoàn toàn rác bề mặt, không còn bao bì vương vãi',
        passed: true,
      },
      {
        criterion_id: 'CRIT-SAN-02',
        label: 'Sàn nhà khô ráo, không còn vũng nước đọng hoặc vết ố dầu mỡ',
        passed: true,
      },
      {
        criterion_id: 'CRIT-SAN-03',
        label: 'Không còn mùi hôi thối khó chịu sau khi xử lý hóa chất',
        passed: true,
      },
      {
        criterion_id: 'CRIT-SAN-05',
        label: 'Đầy đủ bộ ảnh đối chứng Trước (BEFORE) và Sau (AFTER)',
        passed: true,
      },
    ],
    failed_criteria: [],
    redo_required: false,
    note: 'Đã rửa sạch mặt đường cổng 2, đảm bảo mỹ quan đô thị và an toàn giao thông.',
    checked_by: 'usr-qc-01',
    checked_by_name: 'Đặng Quốc Tuấn (Kỹ sư QC Độc lập)',
    checked_at: new Date(Date.now() - 20 * 60 * 1000).toISOString(),
  },
];
