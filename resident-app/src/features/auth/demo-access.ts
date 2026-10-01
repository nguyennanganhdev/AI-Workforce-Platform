// This flag opens mock UI only; it is not an authenticated session.
const key = "resident.ui-preview";
export function isResidentPreview() {
  try {
    return sessionStorage.getItem(key) === "true";
  } catch {
    return false;
  }
}
export function startResidentPreview() {
  sessionStorage.setItem(key, "true");
  location.assign("/#/");
}
export function exitResidentPreview() {
  try {
    sessionStorage.removeItem(key);
  } finally {
    location.assign("/login");
  }
}
