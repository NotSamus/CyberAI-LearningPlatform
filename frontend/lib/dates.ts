// Due dates travel as ISO strings in UTC and are shown in the viewer's own time zone.

// "Oct 13, 10:40 PM": the year only when it is not this one, so that tables stay narrow.
function dateAndTime(date: Date): string {
  const year = date.getFullYear() === new Date().getFullYear() ? undefined : "numeric";
  return date.toLocaleString(undefined, { month: "short", day: "numeric", year, hour: "numeric", minute: "2-digit" });
}

export function formatDue(iso: string): string {
  return dateAndTime(new Date(iso));
}

export function formatWhen(iso: string | null): string {
  return iso ? dateAndTime(new Date(iso)) : "";
}

export function isPast(iso: string): boolean {
  return new Date(iso).getTime() < Date.now();
}

// To and from the value of <input type="datetime-local"> ("2026-10-31T23:59", local time, no zone).
export function toLocalInput(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
}

export function fromLocalInput(value: string): string | null {
  return value ? new Date(value).toISOString() : null;
}

export function hoursUntil(iso: string): number {
  return (new Date(iso).getTime() - Date.now()) / 3_600_000;
}

// A due date in words: "today, 11:59 PM", "tomorrow, ...", the weekday within the coming week,
// and the date further away.
export function dueText(iso: string): string {
  const due = new Date(iso);
  const time = due.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  const day = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((day(due) - day(new Date())) / 86_400_000);
  if (days === 0) return `today, ${time}`;
  if (days === 1) return `tomorrow, ${time}`;
  if (days === -1) return `yesterday, ${time}`;
  if (days > 1 && days < 7) return `${due.toLocaleDateString(undefined, { weekday: "long" })}, ${time}`;
  return formatDue(iso);
}

// A day as "2026-10-19", in the viewer's own time zone: the same for every time on that day.
export function dayKey(date: Date): string {
  const two = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${two(date.getMonth() + 1)}-${two(date.getDate())}`;
}

// Which day of its year a date is (January 1 is day 1), and how many days that year has.
export function dayOfYear(date: Date): number {
  return Math.round((Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) - Date.UTC(date.getFullYear(), 0, 1)) / 86_400_000) + 1;
}

export function daysInYear(year: number): number {
  return dayOfYear(new Date(year, 11, 31));
}
