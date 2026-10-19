"use client";
import { useState } from "react";
import Calendar from "@/components/learn/Calendar";
import Timeline, { timeline } from "@/components/learn/Timeline";
import type { MyAssignment } from "@/lib/api";

// The column to the right of Home's lists (above them on an iPad held upright): the calendar of
// this year, and the timeline of what is due. A day clicked in the calendar is shown in the timeline.
export default function HomeSide({ today, assignments, asTeacher }: { today: Date; assignments: MyAssignment[]; asTeacher: boolean }) {
  const days = timeline(assignments, asTeacher, today);
  // `n` counts the clicks, so that clicking the same day again scrolls to it again.
  const [picked, setPicked] = useState<{ key: string; n: number } | null>(null);
  return (
    <aside className="home-side" aria-label="Calendar and timeline">
      <Calendar
        today={today} assignments={assignments} asTeacher={asTeacher} linked={new Set(days.map((day) => day.key))}
        onPick={(key) => setPicked((last) => ({ key, n: (last?.n ?? 0) + 1 }))}
      />
      <Timeline days={days} asTeacher={asTeacher} picked={picked} />
    </aside>
  );
}
