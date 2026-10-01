/**
 * Kiểu Camera — P2 sở hữu (spec v0.3 §2.2, §6.3). Chỉ metadata: không có stream, frame, URL tải
 * hay credential. Nguồn cấu trúc là schema/common.schema.json.
 */
import type { Location } from "../guards/types";

export type CameraStatus = "ONLINE" | "OFFLINE" | "MAINTENANCE" | "UNKNOWN";
/** Biết loại ngoài taxonomy → OTHER; chưa biết → UNKNOWN. Không nullable. */
export type CameraType = "FIXED" | "PTZ" | "PANORAMIC" | "OTHER" | "UNKNOWN";
/** Core cấp, agent không tự suy diễn khoảng cách. */
export type CameraIncidentRelation = "AT_LOCATION" | "NEAR_LOCATION" | "MANUALLY_LINKED";

export const CAMERA_STATUSES: readonly CameraStatus[] = ["ONLINE", "OFFLINE", "MAINTENANCE", "UNKNOWN"];
export const CAMERA_TYPES: readonly CameraType[] = ["FIXED", "PTZ", "PANORAMIC", "OTHER", "UNKNOWN"];
export const CAMERA_INCIDENT_RELATIONS: readonly CameraIncidentRelation[] = ["AT_LOCATION", "NEAR_LOCATION", "MANUALLY_LINKED"];

export type CameraSummary = {
  camera_id: string;
  location: Location;
  status: CameraStatus;
  camera_type: CameraType;
  /** ID nội bộ để đối soát; không phải link tải hay token, không được dereference. */
  reference_id: string | null;
  /** null: chưa từng quan sát/không biết. */
  last_seen_at: string | null;
};

export type IncidentCamera = {
  incident_id: string;
  camera: CameraSummary;
  relation: CameraIncidentRelation;
};

export type GetCameraMetadataInput = { camera_id: string };
export type SearchCamerasInput = {
  building?: string;
  floor?: string;
  zone?: string;
  status?: CameraStatus;
  limit?: number;
  cursor?: string;
};
export type GetCamerasByLocationInput = { location_id: string; limit?: number; cursor?: string };
export type GetIncidentCamerasInput = { incident_id: string; limit?: number; cursor?: string };

export type CameraPage = { cameras: CameraSummary[]; next_cursor: string | null };
export type IncidentCameraPage = { cameras: IncidentCamera[]; next_cursor: string | null };
