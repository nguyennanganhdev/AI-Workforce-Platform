/**
 * Schema Camera: tham chiếu JSON Schema v0.3 cho wrapper, cộng kiểm tra runtime (§6.3, §7).
 */
import { cameraOutputIssues } from "./boundary";
import type { CameraSummary } from "./types";

export const CAMERA_SCHEMAS = {
  CameraSummary: "common.schema.json#/$defs/CameraSummary",
  IncidentCamera: "common.schema.json#/$defs/IncidentCamera",
  GetCameraMetadataInput: "common.schema.json#/$defs/GetCameraMetadataInput",
  SearchCamerasInput: "common.schema.json#/$defs/SearchCamerasInput",
  GetCamerasByLocationInput:
    "common.schema.json#/$defs/GetCamerasByLocationInput",
  GetIncidentCamerasInput: "common.schema.json#/$defs/GetIncidentCamerasInput",
  GetCameraMetadataOutput:
    "security_mcp.schema.json#/$defs/GetCameraMetadataOutput",
  SearchCamerasOutput: "security_mcp.schema.json#/$defs/SearchCamerasOutput",
  GetCamerasByLocationOutput:
    "security_mcp.schema.json#/$defs/GetCamerasByLocationOutput",
  GetIncidentCamerasOutput:
    "security_mcp.schema.json#/$defs/GetIncidentCamerasOutput",
} as const;

/** Trang camera: boundary metadata, camera_id tăng dần (theo camera.camera_id với IncidentCamera). */
export function cameraPageIssues(data: unknown): string[] {
  const issues = cameraOutputIssues(data);
  const items = (data as { cameras?: unknown }).cameras;
  if (Array.isArray(items)) {
    const ids = items.map(
      (item: { camera_id?: string; camera?: CameraSummary }) =>
        item.camera?.camera_id ?? item.camera_id ?? "",
    );
    ids.forEach((id, index) => {
      const previous = index > 0 ? ids[index - 1] : undefined;
      if (previous !== undefined && previous >= id)
        issues.push(`/cameras/${index}: không tăng dần theo camera_id`);
    });
  }
  return issues;
}
