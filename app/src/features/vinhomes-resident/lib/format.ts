const time = new Intl.DateTimeFormat('vi-VN', { hour: '2-digit', minute: '2-digit' });
const dayTime = new Intl.DateTimeFormat('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
const day = new Intl.DateTimeFormat('vi-VN', { day: '2-digit', month: '2-digit' });

const sameDay = (a: Date, b: Date) => a.toDateString() === b.toDateString();

/** "14:05" hôm nay, "28/09 14:05" ngày khác. */
export function formatTime(iso: string): string {
  const d = new Date(iso);
  if (!Number.isFinite(d.getTime())) return '';
  return sameDay(d, new Date()) ? time.format(d) : dayTime.format(d);
}

/** Nhãn ngắn cho danh sách: "14:05" hôm nay, "28/09" ngày khác. */
export function formatShort(iso: string): string {
  const d = new Date(iso);
  if (!Number.isFinite(d.getTime())) return '';
  return sameDay(d, new Date()) ? time.format(d) : day.format(d);
}

/** "2 ngày 5 giờ" đến hạn tự hoàn tất. */
export function formatRemaining(untilIso: string | null, now = Date.now()): string | null {
  if (!untilIso) return null;
  const ms = new Date(untilIso).getTime() - now;
  if (ms <= 0) return null;
  const minutes = Math.floor(ms / 60000);
  const d = Math.floor(minutes / 1440);
  const h = Math.floor((minutes % 1440) / 60);
  if (d > 0) return `${d} ngày ${h} giờ`;
  if (h > 0) return `${h} giờ ${minutes % 60} phút`;
  return `${minutes} phút`;
}
