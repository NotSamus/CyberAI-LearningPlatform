"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowRight, CalendarClock, ClipboardCheck } from "lucide-react";
import { api, type ManagedAssignment } from "@/lib/api";
import { hoursUntil } from "@/lib/dates";

const WEEK = 7 * 24;            // hours

// For teachers, at the top of Home: what waits for them, as one link to Teach. Not shown when the
// list cannot be had (or is still on its way).
export default function TeachStrip() {
  const [assignments, setAssignments] = useState<ManagedAssignment[] | null>(null);
  useEffect(() => {
    api<ManagedAssignment[]>("/teach/assignments").then(setAssignments).catch(() => setAssignments(null));
  }, []);
  if (!assignments) return null;

  // To grade: waiting for a grade by hand, and those the autograder could not run (the teacher looks at why).
  const toGrade = assignments.reduce((sum, a) => sum + (a.counts?.to_grade ?? 0) + (a.counts?.failed ?? 0), 0);
  const dueThisWeek = assignments.filter((a) => {
    if (!a.published || !a.due_at) return false;
    const hours = hoursUntil(a.due_at);
    return hours > 0 && hours <= WEEK;
  }).length;

  return (
    <Link href="/teach" className="teach-strip">
      <span className="fact"><ClipboardCheck aria-hidden /><strong>{toGrade}</strong> to grade</span>
      <span className="fact"><CalendarClock aria-hidden /><strong>{dueThisWeek}</strong> due this week</span>
      <span className="go">Teach <ArrowRight aria-hidden /></span>
    </Link>
  );
}
