import type { VhActionApproval } from '../types/action';
import { MOCK_ACTION_REQUESTS } from './action-requests';

export const MOCK_APPROVALS: VhActionApproval[] = [
  // 1. Phê duyệt PENDING: Chi phí khẩn cấp thay van DN50 (12.5 triệu VND)
  {
    id: 'APP-2026-001',
    action_request_id: 'ACT-2026-03',
    action_payload_hash: 'sha256:ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb',
    status: 'PENDING',
    requested_by_id: 'agent-vinhomes-dispatcher',
    reviewer_id: null,
    reviewer_name: undefined,
    expires_at: new Date(Date.now() + 30 * 60 * 1000).toISOString(), // Còn 30 phút để duyệt
    decided_at: null,
    reason: null,
    version: 1,
    action_request: MOCK_ACTION_REQUESTS.find((a) => a.id === 'ACT-2026-03'),
    estimated_cost_vnd: 12500000,
    urgency_level: 'CRITICAL',
  },

  // 2. Phê duyệt APPROVED: Hợp đồng sửa chữa guốc thang máy Otis (8.2 triệu VND)
  {
    id: 'APP-2026-002',
    action_request_id: 'ACT-2026-05',
    action_payload_hash: 'sha256:2c6a465997aac80e9360f4d64d43a3fa533ff7228f10963b43ebd624d4076d88',
    status: 'APPROVED',
    requested_by_id: 'usr-tech-01',
    reviewer_id: 'usr-mgr-01',
    reviewer_name: 'Vũ Đức Thịnh (Trưởng BQL)',
    expires_at: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
    decided_at: new Date(Date.now() - 170 * 60 * 1000).toISOString(),
    reason: 'Đồng ý duyệt theo gói bảo trì định kỳ của tòa nhà, yêu cầu hoàn thành trước 17h.',
    version: 2,
    action_request: MOCK_ACTION_REQUESTS.find((a) => a.id === 'ACT-2026-05'),
    estimated_cost_vnd: 8200000,
    urgency_level: 'HIGH',
  },

  // 3. Phê duyệt REJECTED: Đề xuất thay toàn bộ cáp kéo thang máy (120 triệu VND)
  {
    id: 'APP-2026-003',
    action_request_id: 'ACT-2026-08',
    action_payload_hash: 'sha256:8899aabbccddeeff00112233445566778899aabbccddeeff0011223344556677',
    status: 'REJECTED',
    requested_by_id: 'usr-contractor-01',
    reviewer_id: 'usr-mgr-01',
    reviewer_name: 'Vũ Đức Thịnh (Trưởng BQL)',
    expires_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    decided_at: new Date(Date.now() - 25 * 60 * 1000).toISOString(),
    reason: 'Chưa đủ điều kiện thay thế theo chu kỳ kiểm định kỹ thuật 6 tháng. Yêu cầu kiểm tra lại độ mòn cáp và thí nghiệm kéo mẫu trước.',
    version: 2,
    action_request: MOCK_ACTION_REQUESTS.find((a) => a.id === 'ACT-2026-08'),
    estimated_cost_vnd: 120000000,
    urgency_level: 'NORMAL',
  },

  // 4. Phê duyệt EXPIRED: Đề xuất thuê xe thang phun nước cổng chào
  {
    id: 'APP-2026-004',
    action_request_id: 'ACT-2026-07',
    action_payload_hash: 'sha256:11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff',
    status: 'EXPIRED',
    requested_by_id: 'agent-vinhomes-dispatcher',
    reviewer_id: null,
    expires_at: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString(),
    decided_at: null,
    reason: 'Hết hạn phản hồi (Quá hạn 12 giờ tự động hủy yêu cầu).',
    version: 1,
    action_request: MOCK_ACTION_REQUESTS.find((a) => a.id === 'ACT-2026-07'),
    estimated_cost_vnd: 4500000,
    urgency_level: 'NORMAL',
  },
];
