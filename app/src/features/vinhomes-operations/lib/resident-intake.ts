/**
 * Resident app → operations intake rules (bản trải nghiệm, thay cho Reception + Supervisor agent).
 * Pure helpers so the same rules are reused by the store and by tests; the real backend replaces them.
 */
import type { IncidentSeverity, LocationJson, VhIncident } from '../types/incident';
import type { VhCase, VhIssueCandidate } from '../types/intake';
import type { DomainType, VhTask } from '../types/task';
import type { VhWorkOrder } from '../types/work-order';
import { PERSONA_PROFILES, type OperationsPersona } from '../types/persona';
import { emptyFieldFlow } from './field-flow';

export interface IssueClassification {
  domain: DomainType;
  /** Incident category, drives the field checklist (ELEC → điện, PLUMB → nước). */
  category: string;
  severity: IncidentSeverity;
  /** Nhóm xử lý hiển thị cho cư dân. */
  teamLabel: string;
}

export const normalizeVi = (text: string) =>
  text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/đ/g, 'd');

/** Whole-phrase match on accent-free text ("den" alone would also match "đến"). */
const phrases = (...alts: string[]) => new RegExp(`\\b(${alts.join('|')})\\b`);

const RULES: Array<{ test: RegExp; result: Omit<IssueClassification, 'severity'> }> = [
  { test: phrases('thang may'), result: { domain: 'ELEVATOR', category: 'ELEVATOR', teamLabel: 'Đội thang máy' } },
  {
    test: phrases('on ao', 'tieng on', 'gay on', 'karaoke', 'trom', 'nguoi la', 'au da', 'danh nhau', 'dot nhap', 'do xe', 'dau xe', 'an ninh'),
    result: { domain: 'SECURITY', category: 'SECURITY_NOISE', teamLabel: 'Đội an ninh' },
  },
  {
    test: phrases('rac', 'ban thiu', 'rat ban', 'bi ban', 'vet ban', 've sinh', 'mui hoi', 'hoi thoi', 'tron truot', 'san tron', 'bi tron'),
    result: { domain: 'SANITATION', category: 'SANITATION_A5', teamLabel: 'Đội vệ sinh' },
  },
  {
    test: phrases('dien', 'mat dien', 'bong den', 'den hanh lang', 'den nhap nhay', 'den khong sang', 'den bi hong', 'den hong', 'aptomat', 'cau dao', 'o cam', 'cong tac', 'chap', 'nhap nhay', 'dieu hoa'),
    result: { domain: 'MEP', category: 'ELECTRICAL', teamLabel: 'Đội kỹ thuật điện' },
  },
  {
    test: phrases('nuoc', 'ro ri', 'bi ro', 'tac', 'voi', 'ong nuoc', 'vo ong', 'bon cau', 'bon rua', 'lavabo', 'ngap', 'tham'),
    result: { domain: 'MEP', category: 'MEP_PLUMBING', teamLabel: 'Đội kỹ thuật nước' },
  },
];

export function classifyIssue(text: string): IssueClassification {
  const key = normalizeVi(text);
  const match = RULES.find((r) => r.test.test(key))?.result ?? {
    domain: 'TECHNICAL' as DomainType,
    category: 'TECHNICAL',
    teamLabel: 'Đội kỹ thuật',
  };
  const severity: IncidentSeverity = phrases('bi chay', 'dam chay', 'boc chay', 'chay no', 'co khoi', 'boc khoi', 'ngap', 'chap dien', 'dot nhap', 'au da', 'danh nhau', 'bi thuong').test(key)
    ? 'P1'
    : phrases('mat dien', 'mat nuoc', 'vo ong', 'trom').test(key)
      ? 'P2'
      : 'P3';
  return { ...match, severity };
}

/** True when the text mentions a known kind of incident (điện, nước, vệ sinh, an ninh, thang máy). */
export function looksLikeIssue(text: string): boolean {
  const key = normalizeVi(text);
  return RULES.some((r) => r.test.test(key));
}

/** Nhóm xử lý hiển thị cho cư dân, theo category đã phân loại. */
export function teamLabelOf(category: string): string {
  return RULES.find((r) => r.result.category === category)?.result.teamLabel ?? 'Đội kỹ thuật';
}

export interface ResidentCaseInput {
  resident: {
    userId: string;
    name: string;
    phone: string;
    towerCode: string;
    floor: number;
    apartmentCode: string;
  };
  description: string;
  location: string;
  photoUrls: string[];
}

export function buildResidentCase(input: ResidentCaseInput, now = new Date()): { kase: VhCase; candidate: VhIssueCandidate } {
  const description = input.description.trim();
  const location = input.location.trim();
  if (description.length < 8) throw new Error('Mô tả sự cố cần ít nhất 8 ký tự.');
  if (location.length < 3) throw new Error('Vui lòng cho biết vị trí sự cố.');
  if (input.photoUrls.length > 3) throw new Error('Mỗi phản ánh đính kèm tối đa 3 ảnh.');

  const iso = now.toISOString();
  const suffix = now.getTime().toString(36).toUpperCase().slice(-6);
  const classification = classifyIssue(`${description} ${location}`);
  const { resident } = input;
  const locationJson: LocationJson = {
    towerCode: resident.towerCode,
    floor: resident.floor,
    apartmentCode: resident.apartmentCode,
    description: `${description}\nVị trí: ${location}`,
  };
  const kase: VhCase = {
    id: `CASE-${now.getFullYear()}-${suffix}`,
    tenant_id: 'tenant-vhm-sc',
    resident_user_id: resident.userId,
    resident_name: resident.name,
    resident_phone: resident.phone,
    apartment_id: `${resident.towerCode}-${resident.apartmentCode}`,
    status: 'READY',
    summary: description.split('\n')[0].slice(0, 120),
    opened_at: iso,
    closed_at: null,
    version: 1,
  };
  const candidate: VhIssueCandidate = {
    id: `IC-${now.getFullYear()}-${suffix}`,
    case_id: kase.id,
    source_request_id: null,
    domain: classification.domain,
    category: classification.category,
    severity: classification.severity,
    normalized_summary: kase.summary,
    location_json: locationJson,
    confidence: 0.8,
    status: 'READY',
    required_fields_json: ['description', 'location'],
    missing_fields_json: [],
    source_channel: 'APP',
    resident_photo_urls: input.photoUrls,
    created_at: iso,
    updated_at: iso,
  };
  return { kase, candidate };
}

const DISPATCH_PERSONA: Partial<Record<DomainType, OperationsPersona>> = {
  MEP: 'STAFF_TECHNICAL',
  TECHNICAL: 'STAFF_TECHNICAL',
  GENERAL: 'STAFF_TECHNICAL',
  SANITATION: 'STAFF_SANITATION_A5',
  LANDSCAPE: 'STAFF_SANITATION_A5',
  SECURITY: 'STAFF_SECURITY',
};

const CHECKLIST_BY_DOMAIN: Partial<Record<DomainType, string>> = {
  SANITATION: 'CKL-VER-SAN-01',
  LANDSCAPE: 'CKL-VER-SAN-01',
  SECURITY: 'CKL-VER-SEC-01',
};

/**
 * Supervisor agent (mô phỏng): giao sự cố cho nhân viên hiện trường theo lĩnh vực.
 * Returns null when the domain needs BQL (thang máy → nhà thầu).
 */
export function buildDispatch(
  incident: VhIncident,
  domain: DomainType,
  now = new Date(),
): { task: VhTask; workOrder: VhWorkOrder } | null {
  const persona = DISPATCH_PERSONA[domain];
  if (!persona) return null;
  const staff = PERSONA_PROFILES[persona];
  const iso = now.toISOString();
  const suffix = now.getTime().toString(36).toUpperCase().slice(-6);
  const task: VhTask = {
    id: `TSK-${now.getFullYear()}-${suffix}`,
    incident_id: incident.id,
    title: incident.title,
    domain_type: domain,
    domain_data: null,
    domain_schema_version: 1,
    assignee_type: 'STAFF',
    assignee_id: staff.id,
    assignee_name: staff.name,
    status: 'ASSIGNED',
    priority: incident.severity === 'P1' ? 'URGENT' : incident.severity === 'P2' ? 'HIGH' : 'MEDIUM',
    due_at: incident.sla_due_at,
    version: 1,
    created_at: iso,
    updated_at: iso,
  };
  const workOrder: VhWorkOrder = {
    id: `WO-${now.getFullYear()}-${suffix}`,
    incident_id: incident.id,
    task_id: task.id,
    action_request_id: null,
    executor_type: 'STAFF',
    executor_id: staff.id,
    executor_name: staff.name,
    executor_phone: staff.phone,
    executor_avatar: staff.avatarUrl,
    status: 'ASSIGNED',
    attempt_no: 1,
    redo_of_work_order_id: null,
    checklist_version_id: CHECKLIST_BY_DOMAIN[domain] ?? 'CKL-VER-MEP-01',
    execution_started_at: null,
    execution_completed_at: null,
    result: null,
    field_flow: { ...emptyFieldFlow('ASSIGNED', incident.category, task), resident_channel: null },
    version: 1,
    created_at: iso,
    updated_at: iso,
  };
  return { task, workOrder };
}
