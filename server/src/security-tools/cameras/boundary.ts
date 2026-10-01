/**
 * Ranh giới camera (spec v0.3 §6.3): Security MCP chỉ trả metadata camera.
 *
 * Chạy ở hai chỗ:
 * - Provider adapter: `toCameraSummary`/`toIncidentCamera` dựng DTO mới từ whitelist field. Upstream
 *   có field ngoài whitelist (stream_url, snapshot, credential...) hoặc sai shape → fail
 *   PROVIDER_INVALID_RESPONSE, không bỏ qua field lạ, không log raw body.
 * - Response wrapper: `cameraOutputIssues` quét lại data đã validate trước khi serialize.
 *
 * reference_id chỉ là ID đối soát; boundary không bao giờ dereference nó thành nội dung media.
 */
import { fail } from "../common/errors";
import { validate } from "../schema";
import type { Location } from "../guards/types";
import type { CameraSummary, IncidentCamera } from "./types";

const LOCATION_KEYS = ["location_id", "building", "floor", "zone"] as const;
const CAMERA_KEYS = ["camera_id", "location", "status", "camera_type", "reference_id", "last_seen_at"] as const;
const INCIDENT_CAMERA_KEYS = ["incident_id", "camera", "relation"] as const;

/** Tên field gợi ý media/credential. Dùng để quét output, kể cả object lồng. */
const FORBIDDEN_KEY = /stream|rtsp|hls|webrtc|url|uri|href|frame|snapshot|image|video|thumbnail|playback|recording|face|password|passwd|credential|token|secret|username|api_?key/i;
/** Chuỗi trông như địa chỉ tải được: scheme://, data:, blob:. */
const ADDRESS_LIKE = /[a-z][a-z0-9+.-]*:\/\/|\bdata:|\bblob:/i;

/** Dựng CameraSummary từ dữ liệu upstream. Mọi sai lệch → PROVIDER_INVALID_RESPONSE. */
export function toCameraSummary(raw: unknown): CameraSummary {
  const source = exactObject(raw, CAMERA_KEYS);
  const camera: CameraSummary = {
    camera_id: source.camera_id as string,
    location: toLocation(source.location),
    status: source.status as CameraSummary["status"],
    camera_type: source.camera_type as CameraSummary["camera_type"],
    reference_id: source.reference_id as string | null,
    last_seen_at: source.last_seen_at as string | null,
  };
  return checked("CameraSummary", camera);
}

export function toIncidentCamera(raw: unknown): IncidentCamera {
  const source = exactObject(raw, INCIDENT_CAMERA_KEYS);
  const item: IncidentCamera = {
    incident_id: source.incident_id as string,
    camera: toCameraSummary(source.camera),
    relation: source.relation as IncidentCamera["relation"],
  };
  return checked("IncidentCamera", item);
}

/**
 * Kiểm tra output của tool camera ngoài JSON Schema: không field tên media/credential và không chuỗi
 * dạng địa chỉ ở bất kỳ độ sâu nào. Trả danh sách vấn đề theo đường dẫn, không chép giá trị.
 */
export function cameraOutputIssues(data: unknown): string[] {
  const issues: string[] = [];
  const walk = (node: unknown, path: string) => {
    if (typeof node === "string") {
      if (ADDRESS_LIKE.test(node)) issues.push(`${path}: chuỗi dạng địa chỉ media`);
    } else if (Array.isArray(node)) {
      node.forEach((item, index) => walk(item, `${path}/${index}`));
    } else if (node !== null && typeof node === "object") {
      for (const [key, value] of Object.entries(node)) {
        if (FORBIDDEN_KEY.test(key) && key !== "reference_id") issues.push(`${path}/${key}: field không thuộc metadata`);
        walk(value, `${path}/${key}`);
      }
    }
  };
  walk(data, "");
  return issues;
}

function toLocation(raw: unknown): Location {
  const source = exactObject(raw, LOCATION_KEYS);
  return {
    location_id: source.location_id as string,
    building: source.building as string | null,
    floor: source.floor as string | null,
    zone: source.zone as string | null,
  };
}

function exactObject<K extends string>(raw: unknown, keys: readonly K[]): Record<K, unknown> {
  if (raw === null || typeof raw !== "object" || Array.isArray(raw)) invalid();
  const actual = Object.keys(raw as object);
  if (actual.length !== keys.length || !actual.every((key) => (keys as readonly string[]).includes(key))) invalid();
  return raw as Record<K, unknown>;
}

function checked<T>(def: "CameraSummary" | "IncidentCamera", value: T): T {
  if (!validate(`common.schema.json#/$defs/${def}`, value).ok || cameraOutputIssues(value).length > 0) invalid();
  return value;
}

function invalid(): never {
  // Message cố định: không đưa field/giá trị upstream vào lỗi.
  return fail("PROVIDER_INVALID_RESPONSE", "Dữ liệu camera từ provider không đúng metadata contract.");
}
