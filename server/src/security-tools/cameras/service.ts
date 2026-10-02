/**
 * Quy tắc tra cứu Camera (spec v0.3 §7). Hàm thuần trên metadata đã qua boundary.
 * Bộ lọc kết hợp AND, so khớp chính xác building/floor/zone sau mapping nguồn, không query tự do.
 */
import { compareIds } from "../guards/service";
import type {
  CameraSummary,
  IncidentCamera,
  SearchCamerasInput,
} from "./types";

export const sortCameras = (cameras: readonly CameraSummary[]) =>
  [...cameras].sort((a, b) => compareIds(a.camera_id, b.camera_id));

export const sortIncidentCameras = (items: readonly IncidentCamera[]) =>
  [...items].sort((a, b) => compareIds(a.camera.camera_id, b.camera.camera_id));

/** Thiếu filter nghĩa là liệt kê trong property. */
export function matchesSearch(
  camera: CameraSummary,
  filters: Omit<SearchCamerasInput, "limit" | "cursor">,
): boolean {
  return (
    (filters.building === undefined ||
      camera.location.building === filters.building) &&
    (filters.floor === undefined || camera.location.floor === filters.floor) &&
    (filters.zone === undefined || camera.location.zone === filters.zone) &&
    (filters.status === undefined || camera.status === filters.status)
  );
}

export function searchCameras(
  cameras: readonly CameraSummary[],
  filters: Omit<SearchCamerasInput, "limit" | "cursor">,
): CameraSummary[] {
  return sortCameras(
    cameras.filter((camera) => matchesSearch(camera, filters)),
  );
}

/** Camera gắn đúng location_id; không suy diễn "gần" từ building/zone. */
export function camerasAtLocation(
  cameras: readonly CameraSummary[],
  locationId: string,
): CameraSummary[] {
  return sortCameras(
    cameras.filter((camera) => camera.location.location_id === locationId),
  );
}
