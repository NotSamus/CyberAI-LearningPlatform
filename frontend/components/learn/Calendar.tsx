"use client";
import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import ProgressBar from "@/components/ProgressBar";
import { dayAnchor, dueTone, worstTone } from "@/components/learn/Timeline";
import type { MyAssignment } from "@/lib/api";
import { dayKey, dayOfYear, daysInYear } from "@/lib/dates";

// January 4, 2026 was a Sunday: the names of the days, from there, in the viewer's language.
const WEEKDAYS = Array.from({ length: 7 }, (_, n) => new Date(2026, 0, 4 + n));

// The weeks of a month, Sunday first, with null for the days of the months around it.
function weeks(year: number, month: number): (Date | null)[][] {
  const first = new Date(year, month, 1);
  const days = new Date(year, month + 1, 0).getDate();
  const cells: (Date | null)[] = [...Array(first.getDay()).fill(null)];
  for (let day = 1; day <= days; day++) cells.push(new Date(year, month, day));
  while (cells.length % 7 > 0) cells.push(null);
  return Array.from({ length: cells.length / 7 }, (_, n) => cells.slice(7 * n, 7 * n + 7));
}

// Beside Home's lists: today, how far into the year it is, and a month of this year at a time with
// the days something is due marked. A marked day links to its place in the timeline (`linked`: the
// timeline's days, and "overdue"), past days with something overdue to the overdue group at its
// top. `onPick` is told which, so that only the timeline scrolls, not the page. Only this year's
// months: January to December.
export default function Calendar({ today, assignments, asTeacher, linked, onPick }: {
  today: Date;
  assignments: MyAssignment[];
  asTeacher: boolean;
  linked: Set<string>;
  onPick: (key: string) => void;
}) {
  const year = today.getFullYear();
  const [month, setMonth] = useState(today.getMonth());
  // At midnight into a new month (or year), the calendar goes along to it.
  const todayMonth = today.getMonth();
  useEffect(() => setMonth(todayMonth), [todayMonth, year]);

  const due = new Map<string, MyAssignment[]>();
  for (const a of assignments) {
    if (!a.due_at) continue;
    const key = dayKey(new Date(a.due_at));
    due.set(key, [...(due.get(key) ?? []), a]);
  }

  const todayKey = dayKey(today);
  const day = dayOfYear(today);
  const total = daysInYear(year);
  const monthName = new Date(year, month, 1).toLocaleDateString(undefined, { month: "long", year: "numeric" });

  return (
    <section className="side-box calendar" aria-labelledby="calendar-month">
      <div className="today">
        <p className="check-label">Today</p>
        <p className="today-date">{today.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}</p>
        <ProgressBar value={day} max={total} label={`Day ${day} of ${total}`} />
      </div>
      <div className="month-bar">
        <button type="button" className="icon" onClick={() => setMonth(month - 1)} disabled={month === 0} aria-label="Previous month">
          <ChevronLeft aria-hidden />
        </button>
        <h2 id="calendar-month" aria-live="polite">{monthName}</h2>
        <button type="button" className="icon" onClick={() => setMonth(month + 1)} disabled={month === 11} aria-label="Next month">
          <ChevronRight aria-hidden />
        </button>
      </div>
      <table className="month">
        <thead>
          <tr>
            {WEEKDAYS.map((weekday) => (
              <th key={weekday.getDay()} scope="col">
                <abbr title={weekday.toLocaleDateString(undefined, { weekday: "long" })}>
                  {weekday.toLocaleDateString(undefined, { weekday: "narrow" })}
                </abbr>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {weeks(year, month).map((week, n) => (
            <tr key={n}>
              {week.map((date, i) => {
                if (!date) return <td key={i} />;
                const key = dayKey(date);
                const items = due.get(key) ?? [];
                const tone = items.length > 0 ? worstTone(items.map((a) => dueTone(a, asTeacher))) : null;
                const what = items.map((a) => a.title).join(", ");
                const longDate = date.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
                const target = linked.has(key) ? key : tone === "bad" && linked.has("overdue") ? "overdue" : null;
                const classes = [key === todayKey && "is-today", key < todayKey && "past"].filter(Boolean).join(" ");
                const number = (
                  <>
                    {date.getDate()}
                    {items.length > 0 && <span className="visually-hidden">, due: {what}</span>}
                    {tone !== null && <span className={`dot ${tone}`} aria-hidden />}
                  </>
                );
                return (
                  <td key={i} className={classes} aria-current={key === todayKey ? "date" : undefined}>
                    {target
                      ? (
                        <a
                          href={`#${dayAnchor(target)}`} title={what} aria-label={`${longDate}, due: ${what}`}
                          onClick={(event) => { event.preventDefault(); onPick(target); }}
                        >
                          {number}
                        </a>
                      )
                      : <span title={what || undefined}>{number}</span>}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {month !== todayMonth && (
        <button type="button" className="text-button" onClick={() => setMonth(todayMonth)}>Back to today</button>
      )}
    </section>
  );
}
