/**
 * Security Domain types for Field Security Operations (An Ninh Hiện Trường)
 */

export interface SecurityCheckpoint {
  id: string;
  name: string;
  location: string;
  order: number;
  status: 'PENDING' | 'CHECKED' | 'MISSED';
  checked_at?: string;
  guard_id?: string;
  guard_name?: string;
  photo_url?: string;
  notes?: string;
}

export interface SecurityIncidentReport {
  id: string;
  incident_id?: string;
  title: string;
  location: string;
  severity: 'P0' | 'P1' | 'P2' | 'P3';
  reported_at: string;
  guard_id: string;
  guard_name: string;
  persons_involved: Array<{
    name: string;
    id_card?: string;
    role: 'RESIDENT' | 'GUEST' | 'DELIVERY' | 'SUSPECT' | 'VICTIM';
    phone?: string;
  }>;
  vehicles_involved: Array<{
    license_plate: string;
    vehicle_type: 'CAR' | 'MOTORBIKE' | 'TRUCK' | 'BICYCLE';
    notes?: string;
  }>;
  area_isolated: boolean;
  support_requested?: Array<'FIRE_SAFETY' | 'MEDICAL' | 'POLICE' | 'TECHNICAL' | 'BQL'>;
  action_taken: string;
  evidence_urls: string[];
  status: 'INVESTIGATING' | 'RESOLVED' | 'ESCALATED_TO_POLICE';
}

export interface SecurityShiftHandover {
  id: string;
  shift_name: 'CA_SANG' | 'CA_CHIEU' | 'CA_DEM';
  date: string;
  handover_from_id: string;
  handover_from_name: string;
  handover_to_id: string;
  handover_to_name: string;
  handover_at: string;
  equipment_status: {
    walkie_talkie_count: number;
    patrol_baton_count: number;
    flashlight_count: number;
    master_keys_intact: boolean;
  };
  open_security_issues: string[];
  notes: string;
  confirmed: boolean;
}
