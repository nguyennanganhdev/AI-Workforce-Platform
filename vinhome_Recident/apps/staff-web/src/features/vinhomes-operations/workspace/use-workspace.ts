import { useEffect, useState } from "react";
import { previewAccount } from "../auth/demo-access";
import { seedWorkspace, type WorkspaceState } from "./model";
import { readWorkspace, writeWorkspace } from "./service";
export function useWorkspace() {
  const [initial] = useState(() => {
    try {
      return { state: readWorkspace(), error: "" };
    } catch (error) {
      return {
        state: seedWorkspace(),
        error:
          error instanceof Error
            ? error.message
            : "Không đọc được dữ liệu mẫu.",
      };
    }
  });
  const [state, setState] = useState(initial.state),
    [error, setError] = useState(initial.error),
    [notice, setNotice] = useState("");
  useEffect(() => {
    const refresh = () => {
      try {
        setState(readWorkspace());
      } catch (e) {
        setError(e instanceof Error ? e.message : "Không đọc được dữ liệu.");
      }
    };
    window.addEventListener("storage", refresh);
    window.addEventListener("operations-workspace-change", refresh);
    return () => {
      window.removeEventListener("storage", refresh);
      window.removeEventListener("operations-workspace-change", refresh);
    };
  }, []);
  const account = previewAccount();
  function run(
    change: (s: WorkspaceState) => WorkspaceState,
    message = "Đã cập nhật dữ liệu mẫu.",
  ) {
    setError("");
    setNotice("");
    try {
      const next = change(readWorkspace());
      writeWorkspace(next);
      setState(next);
      setNotice(message);
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không thể lưu thay đổi.");
      return false;
    }
  }
  return { state, account, error, notice, run, setError };
}
