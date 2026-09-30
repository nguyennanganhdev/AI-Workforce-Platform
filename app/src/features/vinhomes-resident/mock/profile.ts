import type { ResidentProfile } from '../types';

/**
 * Cư dân của bản trải nghiệm. Khi có API, lấy từ GET /me; không dùng làm căn cứ phân quyền.
 */
export const DEMO_RESIDENT: ResidentProfile = {
  userId: 'usr-resident-01',
  name: 'Minh An',
  phone: '0901 234 567',
  projectName: 'Vinhomes Smart City',
  towerCode: 'S2.02',
  floor: 12,
  apartmentCode: '1208',
  apartmentLabel: 'S2.02 · 1208',
};
