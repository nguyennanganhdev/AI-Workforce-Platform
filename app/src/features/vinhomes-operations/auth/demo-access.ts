// A UI preview flag, never a session token or a backend authorization claim.
const key = "operations.ui-preview";
import { readWorkspace } from "../workspace/service";
import { landing } from "../workspace/model";
export function previewAccount() {
  try { if(sessionStorage.getItem(key)!=="true")return null;return readWorkspace().accounts.find(a=>a.id===(sessionStorage.getItem("operations.preview-account")??"demo-tech")&&a.status==="active")??null; } catch { return null; }
}
export function previewPersona() { const role=previewAccount()?.role;return role==="manager"||role==="admin"?"MANAGER":role==="security"?"STAFF_SECURITY":role==="sanitation"?"STAFF_SANITATION_A5":"STAFF_TECHNICAL"; }
export function isOperationsPreview() {
  try {
    return !!previewAccount();
  } catch {
    return false;
  }
}
export function startOperationsPreview(accountId="demo-tech") {
  const account=readWorkspace().accounts.find(a=>a.id===accountId&&a.status==="active"&&a.role!=="resident");
  if(!account)throw new Error("Tài khoản mẫu không còn hoạt động hoặc không thuộc Operations.");
  sessionStorage.setItem(key, "true");
  sessionStorage.setItem("operations.preview-account",account.id);
  location.assign(landing(account.role));
}
export function exitOperationsPreview() {
  try {
    sessionStorage.removeItem(key);
    sessionStorage.removeItem("operations.preview-account");
  } finally {
    location.assign("/operations/login");
  }
}
