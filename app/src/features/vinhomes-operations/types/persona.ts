/**
 * Operations Persona & RBAC types for Vinhomes Staff & Operations Platform
 * 7 Specialized Operational Roles matching actual Vinhomes Smart City operations
 */

export type OperationsPersona =
  | 'STAFF_TECHNICAL'      // 1. Kỹ thuật viên nội bộ (Điện, Nước, MEP, Thang máy, PCCC)
  | 'STAFF_SANITATION_A5'  // 2. Nhân viên vệ sinh & cảnh quan A5 trực tiếp
  | 'STAFF_SECURITY'       // 3. Nhân viên an ninh & trật tự hiện trường
  | 'CONTRACTOR'           // 4. Nhân sự nhà thầu hoặc đối tác ngoài
  | 'SUPERVISOR'           // 5. Trưởng nhóm / Giám sát ca hiện trường
  | 'QC_INSPECTOR'         // 6. Chuyên viên kiểm định chất lượng (QC Inspector độc lập)
  | 'MANAGER';             // 7. Điều phối viên / Lãnh đạo Ban Quản Lý (BQL)

export type MenuId =
  | 'dashboard'
  | 'my-tasks'
  | 'triage'
  | 'incidents'
  | 'kanban'
  | 'work-orders'
  | 'sanitation'
  | 'security'
  | 'contractor'
  | 'evidence'
  | 'qc'
  | 'approvals';

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  role: OperationsPersona;
  roleTitle: string;
  department: string;
  phone: string;
  assignedProject: string;
  assignedTower?: string;
  avatarUrl: string;
  contractor_organization_id?: string;
  allowedMenuIds: MenuId[];
  canQC: boolean;
  canApproveBudget: boolean;
  canAssignWork: boolean;
}

export const PERSONA_PROFILES: Record<OperationsPersona, UserProfile> = {
  STAFF_TECHNICAL: {
    id: 'usr-tech-01',
    name: 'Nguyễn Văn Hùng',
    email: 'hung.nv@vinhomes.vn',
    role: 'STAFF_TECHNICAL',
    roleTitle: 'Kỹ thuật viên Kỹ nghệ MEP & PCCC',
    department: 'Ban Kỹ Thuật Tòa Nhà',
    phone: '0912 345 678',
    assignedProject: 'Vinhomes Smart City',
    assignedTower: 'Tòa S2.01 - S2.05',
    avatarUrl: 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&auto=format&fit=crop&q=80',
    allowedMenuIds: ['my-tasks', 'work-orders', 'evidence'],
    canQC: false, // Kỹ thuật viên không được tự QC chính công việc của mình
    canApproveBudget: false,
    canAssignWork: false,
  },
  STAFF_SANITATION_A5: {
    id: 'usr-cleaner-01',
    name: 'Lê Thị Bích',
    email: 'bich.lt@vinhomes.vn',
    role: 'STAFF_SANITATION_A5',
    roleTitle: 'Nhân viên Vệ sinh Môi trường & Cảnh quan A5',
    department: 'Đội Vệ Sinh Đô Thị',
    phone: '0977 123 456',
    assignedProject: 'Vinhomes Smart City',
    assignedTower: 'Phân khu Grand Sapphire',
    avatarUrl: 'https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=120&auto=format&fit=crop&q=80',
    allowedMenuIds: ['my-tasks', 'sanitation', 'evidence'],
    canQC: false,
    canApproveBudget: false,
    canAssignWork: false,
  },
  STAFF_SECURITY: {
    id: 'usr-sec-01',
    name: 'Phạm Văn Đạt',
    email: 'dat.pv@vinhomes.vn',
    role: 'STAFF_SECURITY',
    roleTitle: 'Nhân viên An ninh & Tuần tra Hiện trường',
    department: 'Đội An Ninh & Trật Tự Đô Thị',
    phone: '0966 888 777',
    assignedProject: 'Vinhomes Smart City',
    assignedTower: 'Cổng số 2 & Tuyến vành đai S1-S3',
    avatarUrl: 'https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=120&auto=format&fit=crop&q=80',
    allowedMenuIds: ['my-tasks', 'security', 'incidents', 'evidence'],
    canQC: false,
    canApproveBudget: false,
    canAssignWork: false,
  },
  CONTRACTOR: {
    id: 'usr-contractor-01',
    name: 'Hoàng Long (Nhà thầu Otis)',
    email: 'long.hoang@otis-vietnam.com',
    role: 'CONTRACTOR',
    roleTitle: 'Đại diện Kỹ thuật Nhà thầu Thang máy Otis',
    department: 'Đối tác Kỹ thuật Ngoài',
    contractor_organization_id: 'org-otis',
    phone: '0933 555 444',
    assignedProject: 'Vinhomes Smart City',
    assignedTower: 'Cụm thang máy Tòa S2.01 - S2.03',
    avatarUrl: 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=120&auto=format&fit=crop&q=80',
    allowedMenuIds: ['my-tasks', 'contractor', 'work-orders', 'evidence'],
    canQC: false,
    canApproveBudget: false,
    canAssignWork: false,
  },
  SUPERVISOR: {
    id: 'usr-sup-01',
    name: 'Trần Thị Mai',
    email: 'mai.tt@vinhomes.vn',
    role: 'SUPERVISOR',
    roleTitle: 'Trưởng ca & Giám sát Vận hành Hiện trường',
    department: 'Ban Vận Hành Đô Thị',
    phone: '0988 765 432',
    assignedProject: 'Vinhomes Smart City',
    assignedTower: 'Toàn phân khu Sapphire',
    avatarUrl: 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=120&auto=format&fit=crop&q=80',
    allowedMenuIds: ['dashboard', 'my-tasks', 'kanban', 'work-orders', 'sanitation', 'security', 'evidence', 'incidents'],
    canQC: false, // Nếu giám sát trực tiếp thì không được QC công việc đó
    canApproveBudget: false,
    canAssignWork: true,
  },
  QC_INSPECTOR: {
    id: 'usr-qc-01',
    name: 'Đặng Quốc Tuấn',
    email: 'tuan.dq@vinhomes.vn',
    role: 'QC_INSPECTOR',
    roleTitle: 'Kỹ sư Độc lập Kiểm định Chất lượng (QC)',
    department: 'Phòng Quản Lý Chất Lượng & Tuân Thủ',
    phone: '0918 222 333',
    assignedProject: 'Vinhomes Smart City',
    assignedTower: 'Toàn bộ dự án',
    avatarUrl: 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=120&auto=format&fit=crop&q=80',
    allowedMenuIds: ['dashboard', 'my-tasks', 'qc', 'work-orders', 'evidence'],
    canQC: true, // Được quyền chấm checklist và ban hành biên bản QC
    canApproveBudget: false,
    canAssignWork: false,
  },
  MANAGER: {
    id: 'usr-mgr-01',
    name: 'Vũ Đức Thịnh',
    email: 'thinh.vd@vinhomes.vn',
    role: 'MANAGER',
    roleTitle: 'Trưởng Ban Quản Lý Đô Thị (BQL)',
    department: 'Ban Giám Đốc BQL Đô Thị',
    phone: '0903 888 999',
    assignedProject: 'Vinhomes Smart City',
    assignedTower: 'Toàn khu đô thị',
    avatarUrl: 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=120&auto=format&fit=crop&q=80',
    allowedMenuIds: [
      'dashboard',
      'my-tasks',
      'triage',
      'incidents',
      'kanban',
      'work-orders',
      'evidence',
      'qc',
      'approvals',
      'sanitation',
      'security',
      'contractor',
    ],
    canQC: false, // Manager giám sát QC nhưng không thay người QC chuyên môn
    canApproveBudget: true,
    canAssignWork: true,
  },
};
