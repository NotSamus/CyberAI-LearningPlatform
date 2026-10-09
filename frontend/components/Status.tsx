import type { MyAssignment, SubmissionSummary } from "@/lib/api";
import { isPast } from "@/lib/dates";

export function points(n: number | null): string {
  return n === null ? "?" : String(Math.round(n * 100) / 100);
}

export function submissionLabel(s: SubmissionSummary): { text: string; tone: string } {
  if (s.status === "graded") return { text: `Score ${points(s.score)} / ${points(s.max_score)}`, tone: "live" };
  if (s.status === "failed") return { text: "Could not be graded", tone: "late" };
  if (s.status === "submitted") return { text: "Submitted", tone: "live" };
  return { text: "Grading…", tone: "" };
}

// Where a student is with an assignment: not started, opened, overdue, submitted, graded.
export default function Status({ assignment }: { assignment: Pick<MyAssignment, "opened_at" | "submission" | "due_at"> }) {
  const { submission, opened_at, due_at } = assignment;
  if (submission) {
    const { text, tone } = submissionLabel(submission);
    return (
      <>
        <span className={`badge ${tone}`}>{text}</span>
        {submission.late && <span className="badge late">Late</span>}
      </>
    );
  }
  if (due_at && isPast(due_at)) return <span className="badge late">Overdue</span>;
  return <span className="badge">{opened_at ? "Opened" : "Not started"}</span>;
}
