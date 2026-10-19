"use client";
import Link from "next/link";
import { useEffect, useRef } from "react";
import { CalendarClock } from "lucide-react";
import { Label, publishLabel, submissionLabel } from "@/components/Status";
import type { MyAssignment } from "@/lib/api";
import { dayKey, dueText, hoursUntil, isPast } from "@/lib/dates";

// How pressing a due date is, in the tones of the rest of the site: past and not handed in (bad),
// less than two days left (warn), handed in (good), or neither (""). For teachers there is no
// handing in: only drafts stand out, quieter (neutral).
export type DueTone = "" | "good" | "warn" | "bad" | "neutral";

export function dueTone(a: MyAssignment, asTeacher: boolean): DueTone {
  if (asTeacher) return a.published ? "" : "neutral";
  if (a.submission) return "good";
  if (isPast(a.due_at!)) return "bad";
  return hoursUntil(a.due_at!) < 48 ? "warn" : "";
}

// The most pressing tone of several things due on one day.
export function worstTone(tones: DueTone[]): DueTone {
  for (const tone of ["bad", "warn", "", "neutral", "good"] as const) if (tones.includes(tone)) return tone;
  return "";
}

// One day of the timeline, or the overdue assignments before it. `key` is the day ("2026-10-19"),
// or "overdue".
export type TimelineDay = { key: string; label: string; items: MyAssignment[]; tone: DueTone };

// What is coming, by day, soonest first. For a student: what is past its due date and not handed
// in (in one group at the top), then every assignment still to come, handed in or not. For a
// teacher: every assignment still to come, drafts included. Only assignments have dates: lessons
// are never in it.
export function timeline(assignments: MyAssignment[], asTeacher: boolean, today: Date): TimelineDay[] {
  const dated = assignments
    .filter((a) => a.due_at !== null)
    .sort((a, b) => new Date(a.due_at!).getTime() - new Date(b.due_at!).getTime());
  const overdue = asTeacher ? [] : dated.filter((a) => isPast(a.due_at!) && !a.submission);
  const coming = dated.filter((a) => !isPast(a.due_at!));

  const days: TimelineDay[] = [];
  if (overdue.length > 0) days.push({ key: "overdue", label: "Overdue", items: overdue, tone: "bad" });
  const tomorrow = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1);
  for (const a of coming) {
    const due = new Date(a.due_at!);
    const key = dayKey(due);
    let day = days.find((d) => d.key === key);
    if (!day) {
      const date = due.toLocaleDateString(undefined, {
        weekday: "short", month: "short", day: "numeric",
        year: due.getFullYear() === today.getFullYear() ? undefined : "numeric",
      });
      const label = key === dayKey(today) ? `Today · ${date}` : key === dayKey(tomorrow) ? `Tomorrow · ${date}` : date;
      day = { key, label, items: [], tone: "" };
      days.push(day);
    }
    day.items.push(a);
  }
  for (const day of days) day.tone = worstTone(day.items.map((a) => dueTone(a, asTeacher)));
  return days;
}

// The id of a day's place in the timeline: the calendar's days link to it.
export function dayAnchor(key: string): string {
  return `due-${key}`;
}

// Beside Home's lists: everything with a due date, as a line of days with what is due on each.
// `picked`: the day clicked in the calendar. The list scrolls to it (the page does not move) and
// marks it, and the keyboard goes on from there.
export default function Timeline({ days, asTeacher, picked = null }: {
  days: TimelineDay[];
  asTeacher: boolean;
  picked?: { key: string; n: number } | null;
}) {
  const list = useRef<HTMLOListElement | null>(null);
  useEffect(() => {
    const day = picked && document.getElementById(dayAnchor(picked.key));
    if (!day || !list.current) return;
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    list.current.scrollTo({ top: day.offsetTop, behavior: still ? "auto" : "smooth" });
    day.focus({ preventScroll: true });
  }, [picked]);

  return (
    <section className="side-box timeline-box" aria-labelledby="timeline">
      <h2 id="timeline" className="check-label">Timeline</h2>
      {days.length === 0 ? (
        <p className="muted">
          {asTeacher ? "No due dates coming up." : "Nothing is due. Assignments with a due date show up here, in order."}
        </p>
      ) : (
        <ol className="timeline" ref={list}>
          {days.map((day) => (
            <li key={day.key} id={dayAnchor(day.key)} className={`tl-day ${day.tone} ${picked?.key === day.key ? "picked" : ""}`} tabIndex={-1}>
              <p className="tl-when">{day.label}</p>
              <ul>
                {day.items.map((a) => {
                  const standing = asTeacher ? (a.published ? null : publishLabel(a)) : a.submission ? submissionLabel(a.submission) : null;
                  const when = day.key === "overdue"
                    ? `Was due ${dueText(a.due_at!)}`
                    : new Date(a.due_at!).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
                  return (
                    <li key={a.id}>
                      <Link href={`/assignments/${a.id}`} className="title">{a.title}</Link>
                      <p className="meta">
                        <span className={`fact ${day.key === "overdue" ? "bad" : ""}`}><CalendarClock aria-hidden />{when}</span>
                        {a.course && <span>{a.course}</span>}
                      </p>
                      {standing && <Label standing={standing} />}
                    </li>
                  );
                })}
              </ul>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
