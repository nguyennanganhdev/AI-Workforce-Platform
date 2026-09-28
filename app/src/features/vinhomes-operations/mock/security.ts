import type { SecurityCheckpoint, SecurityIncidentReport, SecurityShiftHandover } from '../types/security';

export const MOCK_SECURITY_CHECKPOINTS: SecurityCheckpoint[] = [
  {
    id: 'CP-01',
    name: 'Cổng kiểm soát xe Barrier số 2',
    location: 'Cổng phía Tây - Tòa S2.01',
    order: 1,
    status: 'CHECKED',
    checked_at: new Date(Date.now() - 45 * 60 * 1000).toISOString(),
    guard_id: 'usr-sec-01',
    guard_name: 'Phạm Văn Đạt',
    notes: 'Hệ thống thẻ từ và camera biển số hoạt động bình thường',
  },
  {
    id: 'CP-02',
    name: 'Sảnh đón khách & Hòm thư cư dân',
    location: 'Sảnh Tầng 1 - Tòa S2.02',
    order: 2,
    status: 'CHECKED',
    checked_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
    guard_id: 'usr-sec-01',
    guard_name: 'Phạm Văn Đạt',
    notes: 'Trật tự an ninh tốt, không có người lạ lảng vảng',
  },
  {
    id: 'CP-03',
    name: 'Hầm gửi xe B1 - Khu sạc xe điện',
    location: 'Tầng Hầm B1 - Phân khu S2',
    order: 3,
    status: 'PENDING',
    notes: 'Kiểm tra bình chữa cháy và nhiệt độ tủ sạc VinFast',
  },
  {
    id: 'CP-04',
    name: 'Lối thoát hiểm & Cửa chống cháy Tầng 10',
    location: 'Thang bộ thoát hiểm Tòa S2.01',
    order: 4,
    status: 'PENDING',
    notes: 'Kiểm tra cửa thoát hiểm không bị chèn gạch hoặc đồ đạc',
  },
  {
    id: 'CP-05',
    name: 'Khu công viên BBQ & Sân chơi trẻ em',
    location: 'Nội khu Sapphire 2',
    order: 5,
    status: 'PENDING',
    notes: 'Kiểm tra đèn chiếu sáng và loa thông báo',
  },
];

export const MOCK_SECURITY_INCIDENTS: SecurityIncidentReport[] = [
  {
    id: 'SEC-INC-001',
    incident_id: 'INC-2026-002',
    title: 'Xe giao hàng đỗ chắn lối xe cứu hỏa',
    location: 'Đường nội bộ trước sảnh Tòa S2.02',
    severity: 'P2',
    reported_at: new Date(Date.now() - 2 * 3600 * 1000).toISOString(),
    guard_id: 'usr-sec-01',
    guard_name: 'Phạm Văn Đạt',
    persons_involved: [
      {
        name: 'Trần Văn Mạnh',
        role: 'DELIVERY',
        phone: '0901 234 567',
      },
    ],
    vehicles_involved: [
      {
        license_plate: '29C-882.19',
        vehicle_type: 'TRUCK',
        notes: 'Xe tải giao hàng 1.25 tấn',
      },
    ],
    area_isolated: true,
    action_taken: 'Đã lập biên bản nhắc nhở, hướng dẫn tài xế di chuyển vào vị trí bốc dỡ hàng theo quy định.',
    evidence_urls: [
      'https://images.unsplash.com/photo-1541888946425-d0fbb18f15f7?w=800&auto=format&fit=crop&q=80',
    ],
    status: 'RESOLVED',
  },
  {
    id: 'SEC-INC-002',
    title: 'Phát hiện khói nhẹ tại hành lang kỹ thuật tầng 12',
    location: 'Hành lang Tầng 12 - Tòa S2.05',
    severity: 'P1',
    reported_at: new Date(Date.now() - 25 * 60 * 1000).toISOString(),
    guard_id: 'usr-sec-01',
    guard_name: 'Phạm Văn Đạt',
    persons_involved: [],
    vehicles_involved: [],
    area_isolated: true,
    support_requested: ['FIRE_SAFETY', 'TECHNICAL', 'BQL'],
    action_taken: 'Đã phối hợp kỹ thuật kiểm tra phát hiện chập bóng đèn compact, đã cắt CB và thông báo BQL.',
    evidence_urls: [
      'https://images.unsplash.com/photo-1518770660439-4636190af475?w=800&auto=format&fit=crop&q=80',
    ],
    status: 'INVESTIGATING',
  },
];

export const MOCK_SECURITY_HANDOVERS: SecurityShiftHandover[] = [
  {
    id: 'SH-2026-0928-1',
    shift_name: 'CA_SANG',
    date: '2026-09-28',
    handover_from_id: 'usr-sec-night',
    handover_from_name: 'Hoàng Văn Tuấn (Ca Đêm)',
    handover_to_id: 'usr-sec-01',
    handover_to_name: 'Phạm Văn Đạt (Ca Ngày)',
    handover_at: '2026-09-28T06:00:00Z',
    equipment_status: {
      walkie_talkie_count: 6,
      patrol_baton_count: 4,
      flashlight_count: 4,
      master_keys_intact: true,
    },
    open_security_issues: ['Cửa từ tầng hầm B1 Tòa S2.01 hơi kẹt cần kỹ thuật bôi trơn'],
    notes: 'Ca đêm an toàn, không có sự cố đột nhập hay mất mát tài sản.',
    confirmed: true,
  },
];
