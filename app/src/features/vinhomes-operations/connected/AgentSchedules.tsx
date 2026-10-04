import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { changeRoomRoutineMutationOptions, createRoomRoutineMutationOptions, removeRoomRoutineMutationOptions, switchRoomRoutineMutationOptions } from "@/lib/room-routines/mutations";
import { roomRoutinesQueryOptions, type RoomRoutine } from "@/lib/room-routines/queries";
import { queryClient } from "@/query-client";

const DAYS = ["Chủ nhật", "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy"];
const WORKING_DAYS = [1, 2, 3, 4, 5];
const two = (n: number) => String(n).padStart(2, "0");

/** The schedule in the words management reads; an expression this screen did not make is shown as it is. */
export function scheduleLabel({ schedule, cron }: Pick<RoomRoutine, "schedule" | "cron">): string {
  if (!schedule) return cron;
  const time = `${two(schedule.hour)}:${two(schedule.minute)}`;
  if (!schedule.days.length || schedule.days.length === 7) return `Hằng ngày lúc ${time}`;
  if (schedule.days.join() === WORKING_DAYS.join()) return `Thứ Hai đến Thứ Sáu lúc ${time}`;
  return `${schedule.days.map((day) => DAYS[day]).join(", ")} lúc ${time}`;
}

/** What became of the latest firing. A run with no outcome yet is the agent still answering. */
function lastRun(routine: RoomRoutine, at: (iso: string) => string): string {
  if (!routine.last_run_at) return "Chưa chạy lần nào";
  if (routine.last_status === null) return `Đang chờ agent trả lời · ${at(routine.last_run_at)}`;
  if (routine.last_status === "succeeded") return `Lần gần nhất ${at(routine.last_run_at)}: agent đã trả lời trong nhóm`;
  return `Lần gần nhất ${at(routine.last_run_at)}: ${routine.last_status === "failed" ? "lỗi" : "bỏ qua"}${routine.last_error ? ` · ${routine.last_error}` : ""}`;
}

/** The schedules of one published agent: at the set time its instruction is asked in the room. */
export function AgentSchedules({ roomId, agentId }: { roomId: string; agentId: string }) {
  const routines = useQuery(roomRoutinesQueryOptions(roomId));
  const create = useMutation(createRoomRoutineMutationOptions(queryClient));
  const change = useMutation(changeRoomRoutineMutationOptions(queryClient));
  const flip = useMutation(switchRoomRoutineMutationOptions(queryClient));
  const remove = useMutation(removeRoomRoutineMutationOptions(queryClient));
  const [instruction, setInstruction] = useState("");
  const [every, setEvery] = useState<"daily" | "working" | "weekly">("working");
  const [day, setDay] = useState(1);
  const [time, setTime] = useState("08:00");
  // The schedule the form is changing; "" while it makes a new one.
  const [editing, setEditing] = useState("");
  const busy = create.isPending || change.isPending || flip.isPending || remove.isPending;
  const error = routines.error || create.error || change.error || flip.error || remove.error;
  function edit(routine?: RoomRoutine) {
    const days = routine?.schedule?.days;
    setEditing(routine?.id ?? "");
    setInstruction(routine?.instruction ?? "");
    setEvery(!routine?.schedule ? "working" : !days!.length || days!.length === 7 ? "daily" : days!.join() === WORKING_DAYS.join() ? "working" : "weekly");
    setDay(days?.length && days.length < 7 ? days[0]! : 1);
    setTime(routine?.schedule ? `${two(routine.schedule.hour)}:${two(routine.schedule.minute)}` : "08:00");
  }
  const items = (routines.data?.items || []).filter((routine) => routine.agent_id === agentId);
  const at = (iso: string) => new Date(iso).toLocaleString("vi-VN",
    { timeZone: routines.data?.timezone, weekday: "long", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  const [hour, minute] = time.split(":").map(Number);
  const select = "h-9 rounded-md border border-input bg-background px-2 text-sm text-foreground";
  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">
        Đến giờ, chỉ dẫn được đăng trong nhóm dưới tên người đặt lịch và nhắc agent này; agent trả lời ngay trong nhóm. Giờ theo múi giờ Việt Nam.
      </p>
      {routines.isPending ? <Skeleton className="h-16" /> : items.length ? (
        <ul aria-label="Lịch đã đặt" className="divide-y divide-border rounded-lg border border-border">
          {items.map((routine) => (
            <li key={routine.id} className="space-y-1.5 px-3 py-2.5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-medium text-foreground">{scheduleLabel(routine)}</span>
                <Badge variant={routine.enabled ? "default" : "secondary"}>{routine.enabled ? "Đang bật" : "Đang tắt"}</Badge>
                <span className="ml-auto flex gap-2">
                  <Button size="sm" variant="outline" disabled={busy}
                    onClick={() => flip.mutate({ roomId, id: routine.id, enabled: !routine.enabled })}>{routine.enabled ? "Tắt" : "Bật"}</Button>
                  <Button size="sm" variant="outline" disabled={busy} aria-label={`Sửa lịch ${scheduleLabel(routine)}`} onClick={() => edit(routine)}>Sửa</Button>
                  <Button size="sm" variant="ghost" disabled={busy} aria-label={`Xóa lịch ${scheduleLabel(routine)}`}
                    onClick={() => remove.mutate({ roomId, id: routine.id })}>Xóa</Button>
                </span>
              </div>
              <p className="whitespace-pre-wrap break-words text-sm text-foreground">{routine.instruction}</p>
              <p className="text-xs text-muted-foreground">
                {routine.enabled ? `Lần tới: ${at(routine.next_run_at)} · ` : ""}{lastRun(routine, at)} · Đặt bởi {routine.owner_name}
              </p>
            </li>
          ))}
        </ul>
      ) : <p className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-sm text-muted-foreground">Agent này chưa có lịch nào.</p>}
      <form className="space-y-3 rounded-lg border border-border p-3" onSubmit={async (event) => {
        event.preventDefault();
        const timing = { roomId, instruction: instruction.trim(), hour, minute, days: every === "daily" ? [] : every === "working" ? WORKING_DAYS : [day] };
        try {
          if (editing) await change.mutateAsync({ ...timing, id: editing });
          else await create.mutateAsync({ ...timing, agent_id: agentId });
          edit();
        } catch { /* visible mutation error */ }
      }}>
        <p className="text-sm font-medium">{editing ? "Sửa lịch" : "Đặt lịch mới"}</p>
        <div className="space-y-1.5">
          <label htmlFor="schedule-instruction" className="text-xs text-muted-foreground">Chỉ dẫn gửi cho agent mỗi lần chạy</label>
          <Textarea id="schedule-instruction" rows={3} maxLength={2000} value={instruction} disabled={busy}
            placeholder="Ví dụ: Tóm tắt các yêu cầu mới và các yêu cầu quá hạn của ngày hôm qua." onChange={(e) => setInstruction(e.target.value)} />
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <div className="space-y-1.5">
            <label htmlFor="schedule-every" className="block text-xs text-muted-foreground">Lặp lại</label>
            <select id="schedule-every" className={select} value={every} disabled={busy} onChange={(e) => setEvery(e.target.value as typeof every)}>
              <option value="working">Thứ Hai đến Thứ Sáu</option>
              <option value="daily">Hằng ngày</option>
              <option value="weekly">Hằng tuần</option>
            </select>
          </div>
          {every === "weekly" && (
            <div className="space-y-1.5">
              <label htmlFor="schedule-day" className="block text-xs text-muted-foreground">Vào</label>
              <select id="schedule-day" className={select} value={day} disabled={busy} onChange={(e) => setDay(Number(e.target.value))}>
                {[1, 2, 3, 4, 5, 6, 0].map((d) => <option key={d} value={d}>{DAYS[d]}</option>)}
              </select>
            </div>
          )}
          <div className="space-y-1.5">
            <label htmlFor="schedule-time" className="block text-xs text-muted-foreground">Lúc</label>
            <Input id="schedule-time" type="time" className="w-32" value={time} disabled={busy} onChange={(e) => setTime(e.target.value)} />
          </div>
          <Button type="submit" size="sm" disabled={busy || !instruction.trim() || !Number.isInteger(hour) || !Number.isInteger(minute)}>
            {create.isPending || change.isPending ? "Đang lưu…" : editing ? "Lưu thay đổi" : "Đặt lịch"}
          </Button>
          {editing && <Button type="button" size="sm" variant="outline" disabled={busy} onClick={() => edit()}>Hủy</Button>}
        </div>
      </form>
      {error && <p role="alert" className="text-sm text-destructive">{error.message}</p>}
    </div>
  );
}
