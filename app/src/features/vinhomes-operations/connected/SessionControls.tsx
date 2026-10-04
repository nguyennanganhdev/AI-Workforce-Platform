import { useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { IconPlayerPause, IconPlayerPlay, IconPlayerStop } from "@tabler/icons-react";
import { Button } from "@/components/ui/button";
import { sessionControlsQueryOptions } from "@/lib/coordination/queries";
import { controlSessionMutationOptions, type ControlInput } from "@/lib/coordination/mutations";
import { queryClient } from "@/query-client";

const reasons: Record<string, string> = { session_changed: "Phiên đã thay đổi. Hãy kiểm tra trạng thái và gửi lại.",
  outcome_unknown: "Một lượt đang chạy hoặc chưa đối soát được kết quả. Chờ lượt đó hoàn tất trước khi điều khiển.",
  session_finished: "Phiên đã kết thúc." };
export function SessionControls({ teamId }: { teamId: string }) {
  const state = useQuery(sessionControlsQueryOptions(teamId));
  const control = useMutation(controlSessionMutationOptions(queryClient));
  const pending = useRef<ControlInput | null>(null);
  const [confirmStop, setConfirmStop] = useState(false);
  if (state.isPending) return null;
  if (state.error) return <p role="alert">{state.error.message}</p>;
  if (!state.data) return null;
  const data = state.data;
  const waiting = data.items.some(c => c.status === "queued");
  const last = data.items.at(-1);
  const paused = data.runtime?.phase === "paused";
  async function send(operation: ControlInput["operation"]) {
    if (!data.runtime) return;
    if (pending.current?.teamId !== teamId || pending.current.operation !== operation || pending.current.expected_version !== data.runtime.stateVersion)
      pending.current = { teamId, operation, expected_version: data.runtime.stateVersion, request_id: crypto.randomUUID() };
    try { await control.mutateAsync(pending.current); pending.current = null; setConfirmStop(false); } catch { /* Mutation owns the visible error; retain the request id for retry. */ }
  }
  return <div className="flex flex-col gap-2 mt-3" aria-label="Điều khiển phiên Supervisor">
    {data.canControl && <div className="flex flex-wrap gap-2">
      <Button size="sm" variant="outline" disabled={waiting || control.isPending} onClick={() => void send(paused ? "resume" : "pause")}>
        {paused ? <IconPlayerPlay /> : <IconPlayerPause />}{paused ? "Chạy tiếp" : "Tạm dừng"}
      </Button>
      <Button size="sm" variant="destructive" disabled={waiting || control.isPending} onClick={() => setConfirmStop(true)}><IconPlayerStop />Dừng phiên</Button>
    </div>}
    {confirmStop && <div role="group" aria-label="Xác nhận dừng phiên" className="text-sm">
      <p>Dừng điều phối và đóng phòng của phiên này. Ticket vẫn được BQL xử lý.</p>
      <div className="flex gap-2 mt-2"><Button size="sm" variant="destructive" disabled={control.isPending} onClick={() => void send("stop")}>Xác nhận dừng</Button>
        <Button size="sm" variant="ghost" onClick={() => setConfirmStop(false)}>Quay lại</Button></div>
    </div>}
    {waiting && <p role="status" className="text-sm">Đã gửi lệnh, chờ Supervisor xác nhận.</p>}
    {last?.status === "refused" && <p role="alert" className="text-sm">{reasons[last.result?.reason || ""] || "Supervisor chưa áp dụng được lệnh. Kiểm tra trạng thái phiên."}</p>}
    {data.runtime?.pauseReason === "management_pause" && <p role="status" className="text-sm">BQL đã tạm dừng phiên.</p>}
    {data.runtime?.pauseReason === "management_stopped" && <p role="status" className="text-sm">BQL đã dừng phiên.</p>}
    {control.error && <p role="alert" className="text-sm text-destructive">{control.error.message}</p>}
  </div>;
}
