import { formatDue, isPast } from "@/lib/dates";

export default function DueDate({ due_at, done = false }: { due_at: string | null; done?: boolean }) {
  if (!due_at) return null;
  const past = isPast(due_at);
  return <span className={`badge ${past && !done ? "late" : ""}`}>{past ? "Was due" : "Due"} {formatDue(due_at)}</span>;
}
