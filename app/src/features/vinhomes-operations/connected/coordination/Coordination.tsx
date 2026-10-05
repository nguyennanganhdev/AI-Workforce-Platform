import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { IconMessages } from "@tabler/icons-react";
import { Skeleton } from "@/components/ui/skeleton";
import { roomQueryOptions, roomsQueryOptions, type RoomSession } from "@/lib/rooms/queries";
import { cn } from "@/lib/utils";
import { ago, sessionState, type SessionGroup } from "./model";
import { RoomThread } from "./RoomThread";
import { SessionThread } from "./SessionThread";

const GROUPS: [SessionGroup, string][] = [["attention", "Cần bạn xử lý"], ["running", "Đang điều phối"], ["done", "Đã xong"]];
const FOLDED = 5;
// An API one release behind this page has no updated_at yet.
const changed = (s: RoomSession) => s.updated_at || s.created_at;

function Row({ title, line, time, open, dot, onOpen }: { title: string; line: string; time?: string; open: boolean; dot?: boolean; onOpen: () => void }) {
  return (
    <button type="button" onClick={onOpen} aria-current={open ? "true" : undefined}
      className={cn("flex w-full flex-col gap-0.5 rounded-lg px-3 py-2 text-left hover:bg-muted", open && "bg-primary/8 hover:bg-primary/8")}>
      <span className="flex items-center gap-2">
        <span className={cn("min-w-0 flex-1 truncate text-sm", open || dot ? "font-medium text-foreground" : "text-foreground")}>{title}</span>
        {time && <time className="shrink-0 text-xs text-muted-foreground">{time}</time>}
      </span>
      <span className="flex items-center gap-2 text-xs text-muted-foreground">
        {dot && <span aria-hidden="true" className="size-2 shrink-0 rounded-full bg-primary" />}
        <span className="truncate">{line}</span>
      </span>
    </button>
  );
}

/**
 * Management's coordination room: the sessions the Supervisor runs on the left, one conversation on
 * the right. The list is ordered by who has to act, so what waits for management is read first.
 */
export function Coordination({ userId }: { userId: string }) {
  const listed = useQuery(roomsQueryOptions());
  const rooms = listed.data?.items || [];
  const [chosenRoom, setRoom] = useState("");
  const roomId = chosenRoom || rooms[0]?.id || "";
  const room = useQuery(roomQueryOptions(roomId));
  // "" is the room's own conversation; the address keeps the choice so a notification can link to it.
  const [open, setOpen] = useState(() => new URLSearchParams(location.search).get("session") || "");
  const [reading, setReading] = useState(() => new URLSearchParams(location.search).has("session"));
  const [all, setAll] = useState(false);
  const sessions = room.data?.sessions || [];
  const current = sessions.find((s) => s.id === open);
  function show(id: string) {
    setOpen(id);
    setReading(true);
    history.replaceState(null, "", id ? `?session=${encodeURIComponent(id)}` : location.pathname);
  }
  const grouped = (group: SessionGroup): RoomSession[] =>
    sessions.filter((s) => sessionState(s).group === group).sort((a, b) => changed(b).localeCompare(changed(a)));
  const error = listed.error || room.error;
  return (
    <div className="flex h-full min-h-0 bg-background">
      <aside aria-label="Phiên điều phối" className={cn("flex w-full shrink-0 flex-col border-r border-border md:w-80", reading && "hidden md:flex")}>
        <div className="border-b border-border px-4 py-3">
          <h1 className="text-base font-semibold text-foreground">Điều phối</h1>
          {rooms.length > 1 ? (
            <select aria-label="Nhóm điều phối" value={roomId} onChange={(e) => { setRoom(e.target.value); show(""); }}
              className="mt-2 h-9 w-full rounded-md border border-input bg-background px-2 text-sm text-foreground">
              {rooms.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </select>
          ) : <p className="mt-0.5 text-xs text-muted-foreground">Supervisor điều phối từng yêu cầu của cư dân</p>}
        </div>
        <nav aria-label="Hội thoại" className="min-h-0 flex-1 space-y-4 overflow-y-auto p-2">
          {error && <p role="alert" className="px-3 text-sm text-destructive">{error.message}</p>}
          {listed.isPending || (roomId && room.isPending) ? <Skeleton className="mx-1 h-40" /> : !roomId ? (
            <p className="px-3 py-6 text-sm text-muted-foreground">Tài khoản chưa được thêm vào nhóm điều phối nào.</p>
          ) : (
            <>
              <Row title={rooms.find((r) => r.id === roomId)?.name || "Phòng nhóm"} line="Trao đổi chung và hỏi agent" open={!current} onOpen={() => show("")} />
              {GROUPS.map(([group, label]) => {
                const items = grouped(group);
                if (!items.length) return null;
                const shown = group === "done" && !all ? items.slice(0, FOLDED) : items;
                return (
                  <section key={group} aria-label={label}>
                    <h2 className="px-3 pb-1 text-xs font-medium text-muted-foreground">{label} · {items.length}</h2>
                    {shown.map((s) => (
                      <Row key={s.id} title={s.ticket_title} line={sessionState(s).label} time={ago(changed(s))}
                        open={s.id === open} dot={group === "attention"} onOpen={() => show(s.id)} />
                    ))}
                    {shown.length < items.length && (
                      <button type="button" className="px-3 py-1.5 text-xs font-medium text-primary hover:underline" onClick={() => setAll(true)}>
                        Xem thêm {items.length - shown.length} phiên
                      </button>
                    )}
                  </section>
                );
              })}
              {!sessions.length && <p className="px-3 text-xs text-muted-foreground">Chưa có phiên nào. Phiên được mở khi Lễ tân tiếp nhận một yêu cầu của cư dân.</p>}
            </>
          )}
        </nav>
      </aside>
      <section className={cn("min-w-0 flex-1 flex-col", reading ? "flex" : "hidden md:flex")}>
        {!roomId || !room.data ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 text-muted-foreground">
            <IconMessages className="size-8" stroke={1.5} />
            <p className="text-sm">Chọn một phiên để xem diễn biến.</p>
          </div>
        ) : current ? (
          <SessionThread key={current.id} roomId={roomId} session={current} messages={room.data.messages} agents={room.data.agents} userId={userId} onBack={() => setReading(false)} />
        ) : (
          <RoomThread key={roomId} roomId={roomId} name={rooms.find((r) => r.id === roomId)?.name || "Phòng nhóm"}
            messages={room.data.messages} agents={room.data.agents} userId={userId} onBack={() => setReading(false)} />
        )}
      </section>
    </div>
  );
}
