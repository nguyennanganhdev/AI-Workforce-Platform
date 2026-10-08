export const OPERATIONS_STORAGE_PREFIX = "vhm_operations_data_v10";
// Preserve v9 unchanged. A new snapshot is written by the existing persistence effect.
// Only structured severity fields migrate; text, IDs and user notes remain untouched.
export function readOperationsSnapshot(
  key: string,
  storage: Pick<Storage, "getItem"> = localStorage,
): string | null {
  const current = storage.getItem(key);
  if (current !== null) return current;
  const old = storage.getItem(
    key.replace(OPERATIONS_STORAGE_PREFIX, "vhm_operations_data_v9"),
  );
  if (old === null) return null;
  return JSON.stringify(
    JSON.parse(old, (field, value) =>
      field === "severity" &&
      typeof value === "string" &&
      /^P[1-4]$/.test(value)
        ? `P${Number(value[1]) - 1}`
        : value,
    ),
  );
}
