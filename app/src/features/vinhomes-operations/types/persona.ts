/**
 * Operations Persona types for Vinhomes Staff & Operations / BQL Workspace
 */

export type OperationsPersona = 'STAFF_TECHNICAL' | 'STAFF_SANITATION' | 'MANAGER';

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  role: OperationsPersona;
  roleTitle: string;
  phone: string;
  assignedProject: string;
  assignedTower?: string;
  avatarUrl: string;
}

export const PERSONA_PROFILES: Record<OperationsPersona, UserProfile> = {
  STAFF_TECHNICAL: {
    id: 'usr-tech-01',
    name: 'Nguyễn Văn Hùng',
    email: 'hung.nv@vinhomes.vn',
    role: 'STAFF_TECHNICAL',
    roleTitle: 'Kỹ sư Trưởng MEP & PCCC',
    phone: '0912 345 678',
    assignedProject: 'Vinhomes Smart City',
    assignedTower: 'Tòa S2.01 - S2.05',
    avatarUrl: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80',
  },
  STAFF_SANITATION: {
    id: 'usr-san-01',
    name: 'Trần Thị Mai',
    email: 'mai.tt@vinhomes.vn',
    role: 'STAFF_SANITATION',
    roleTitle: 'Giám sát Vệ sinh & Cảnh quan',
    phone: '0988 765 432',
    assignedProject: 'Vinhomes Smart City',
    assignedTower: 'Phân khu Sapphire',
    avatarUrl: 'https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=120&auto=format&fit=crop&q=80',
  },
  MANAGER: {
    id: 'usr-mgr-01',
    name: 'Vũ Đức Thịnh',
    email: 'thinh.vd@vinhomes.vn',
    role: 'MANAGER',
    roleTitle: 'Trưởng Ban Quản Lý Đô Thị',
    phone: '0903 888 999',
    assignedProject: 'Vinhomes Smart City',
    assignedTower: 'Toàn khu đô thị',
    avatarUrl: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=120&auto=format&fit=crop&q=80',
  },
};
