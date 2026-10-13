// Due dates travel as ISO strings in UTC and are shown in the viewer's own time zone.

export function formatDue(iso: string): string {
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function formatWhen(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "";
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
