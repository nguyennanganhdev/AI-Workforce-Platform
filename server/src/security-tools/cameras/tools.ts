/**
 * Khai báo tool Camera để src/tools.ts register (spec v0.3 §7). Mọi tool chỉ trả metadata; output đi
 * qua camera boundary trước khi serialize.
 */
import type { DomainToolDefinition } from "../tools";
import { cameraOutputIssues } from "./boundary";
import { CAMERA_SCHEMAS as S, cameraPageIssues } from "./schema";

const METADATA_ONLY =
  "Chỉ metadata: không có video, ảnh, stream hay link tải; OFFLINE vẫn trả metadata.";

export const CAMERA_TOOLS: readonly DomainToolDefinition[] = [
  {
    name: "get_camera_metadata",
    mode: "READ",
    inputSchema: S.GetCameraMetadataInput,
    outputSchema: S.GetCameraMetadataOutput,
    description: `Metadata của một camera trong property: vị trí, trạng thái, loại. ${METADATA_ONLY}`,
    annotations: { readOnlyHint: true },
    outputIssues: cameraOutputIssues,
  },
  {
    name: "search_cameras",
    mode: "READ",
    inputSchema: S.SearchCamerasInput,
    outputSchema: S.SearchCamerasOutput,
    description: `Tìm camera trong property theo building/floor/zone (khớp chính xác) và status; không có filter thì liệt kê tất cả. ${METADATA_ONLY}`,
    annotations: { readOnlyHint: true },
    outputIssues: cameraPageIssues,
  },
  {
    name: "get_cameras_by_location",
    mode: "READ",
    inputSchema: S.GetCamerasByLocationInput,
    outputSchema: S.GetCamerasByLocationOutput,
    description: `Camera gắn với một location_id của property. ${METADATA_ONLY}`,
    annotations: { readOnlyHint: true },
    outputIssues: cameraPageIssues,
  },
  {
    name: "get_incident_cameras",
    mode: "READ",
    inputSchema: S.GetIncidentCamerasInput,
    outputSchema: S.GetIncidentCamerasOutput,
    description: `Camera liên quan một incident kèm quan hệ do Core ghi (AT_LOCATION, NEAR_LOCATION, MANUALLY_LINKED). ${METADATA_ONLY}`,
    annotations: { readOnlyHint: true },
    outputIssues: cameraPageIssues,
  },
];
