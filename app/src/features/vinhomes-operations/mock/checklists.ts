import type { VhChecklist, VhChecklistVersion } from '../types/qc';

export const MOCK_CHECKLISTS: VhChecklist[] = [
  {
    id: 'CKL-MEP-01',
    tenant_id: 'tenant-vhm-sc',
    code: 'MEP_PLUMBING_CHECK',
    name: 'Kiểm định Kỹ thuật Hệ thống Cấp thoát nước & Thang máy',
    category: 'TECHNICAL',
    status: 'ACTIVE',
  },
  {
    id: 'CKL-SAN-01',
    tenant_id: 'tenant-vhm-sc',
    code: 'A5_SANITATION_CHECK',
    name: 'Nghiệm thu Vệ sinh Môi trường & Cảnh quan (Chuẩn A5)',
    category: 'SANITATION',
    status: 'ACTIVE',
  },
];

export const MOCK_CHECKLIST_VERSIONS: VhChecklistVersion[] = [
  {
    id: 'CKL-VER-MEP-01',
    checklist_id: 'CKL-MEP-01',
    version_no: 1,
    status: 'PUBLISHED',
    criteria_json: [
      {
        id: 'CRIT-MEP-01',
        code: 'PRESSURE_TEST',
        label: 'Thử áp lực đường ống đạt 8-10 bar trong 30 phút không tụt áp',
        required: true,
        type: 'NUMERIC_RANGE',
        acceptableMin: 8,
        acceptableMax: 10,
      },
      {
        id: 'CRIT-MEP-02',
        code: 'NO_LEAKAGE',
        label: 'Không còn hiện tượng rò rỉ nước tại các khớp nối',
        required: true,
        type: 'BOOLEAN',
      },
      {
        id: 'CRIT-MEP-03',
        code: 'VIBRATION_LEVEL',
        label: 'Độ rung chấn cơ khí thang máy/bơm không vượt quá 0.20 m/s2',
        required: true,
        type: 'NUMERIC_RANGE',
        acceptableMin: 0,
        acceptableMax: 0.2,
      },
      {
        id: 'CRIT-MEP-04',
        code: 'SAFETY_SHUTOFF',
        label: 'Kiểm tra hoạt động ngắt tự động khi quá tải/quá áp',
        required: true,
        type: 'BOOLEAN',
      },
      {
        id: 'CRIT-MEP-05',
        code: 'PHOTO_CONFIRM',
        label: 'Ảnh chụp mặt đồng hồ đo và hiện trạng hoàn thiện',
        required: true,
        type: 'IMAGE_CONFIRMATION',
      },
    ],
    published_at: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
    created_by: 'usr-tech-01',
  },
  {
    id: 'CKL-VER-SAN-01',
    checklist_id: 'CKL-SAN-01',
    version_no: 1,
    status: 'PUBLISHED',
    criteria_json: [
      {
        id: 'CRIT-SAN-01',
        code: 'NO_VISIBLE_WASTE',
        label: 'Sạch sẽ hoàn toàn rác bề mặt, không còn bao bì vương vãi',
        required: true,
        type: 'BOOLEAN',
      },
      {
        id: 'CRIT-SAN-02',
        code: 'FLOOR_DRY_CLEAN',
        label: 'Sàn nhà khô ráo, không còn vũng nước đọng hoặc vết ố dầu mỡ',
        required: true,
        type: 'BOOLEAN',
      },
      {
        id: 'CRIT-SAN-03',
        code: 'NO_FOUL_ODOR',
        label: 'Không còn mùi hôi thối khó chịu sau khi xử lý hóa chất',
        required: true,
        type: 'BOOLEAN',
      },
      {
        id: 'CRIT-SAN-04',
        code: 'BIN_COVER_SAFETY',
        label: 'Thùng rác có nắp đậy kín và đặt đúng vạch định vị an toàn',
        required: true,
        type: 'BOOLEAN',
      },
      {
        id: 'CRIT-SAN-05',
        code: 'PHOTO_BEFORE_AFTER',
        label: 'Đầy đủ bộ ảnh đối chứng Trước (BEFORE) và Sau (AFTER)',
        required: true,
        type: 'IMAGE_CONFIRMATION',
      },
    ],
    published_at: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
    created_by: 'usr-san-01',
  },
];
