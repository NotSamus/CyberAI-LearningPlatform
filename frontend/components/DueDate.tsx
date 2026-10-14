import { CalendarClock, CircleAlert } from "lucide-react";
import { dueText, hoursUntil } from "@/lib/dates";

// When something is due, as a fact with an icon: yellow when less than two days are left, red once
// it has passed and nothing was handed in (`done`: it was).
export default function DueDate({ due_at, done = false }: { due_at: string | null; done?: boolean }) {
  if (!due_at) return null;
  const hours = hoursUntil(due_at);
  const tone = done ? "" : hours < 0 ? "bad" : hours < 48 ? "warn" : "";
  const Icon = tone === "bad" ? CircleAlert : CalendarClock;
  return <span className={`fact ${tone}`}><Icon aria-hidden />{hours < 0 ? "Was due" : "Due"} {dueText(due_at)}</span>;
}
