/**
 * A5 Sanitation & Landscape CleaningPlan schema from docx/02_VINHOMES_DOMAIN_ERD.md (Section 13)
 */

export interface CleaningArea {
  siteId: string;
  locationId: string;
  towerCode?: string;
  floor?: number | string;
}

export interface CleaningActionItem {
  type: 'REMOVE_WASTE' | 'DEEP_CLEAN' | 'DISINFECT' | 'MOP_FLOOR' | 'LANDSCAPE_TRIM' | 'PRESSURE_WASH';
  executorType: 'HUMAN' | 'ROBOT' | 'CONTRACTOR';
  instruction?: string;
}

export interface CleaningPlan {
  schemaVersion: number;
  issueType: 'WASTE_OVERFLOW' | 'SPILL' | 'FOUL_ODOR' | 'LANDSCAPE_DEBRIS' | 'STAIN_REMOVAL';
  area: CleaningArea;
  actions: CleaningActionItem[];
  requiredEvidence: Array<'IMAGE_BEFORE' | 'IMAGE_AFTER' | 'CHECKLIST' | 'SENSOR_LOG'>;
  qcCriteria: string[];
  rootCauseCheckRequired: boolean;
}
