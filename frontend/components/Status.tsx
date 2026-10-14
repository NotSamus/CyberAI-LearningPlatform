import { Circle, CircleAlert, CircleCheck, CircleDashed, Clock, LoaderCircle, Pencil, type LucideIcon } from "lucide-react";
import Chip, { type Tone } from "@/components/Chip";
import type { MyAssignment, SubmissionSummary } from "@/lib/api";
import { isPast } from "@/lib/dates";
import type { MyLesson } from "@/lib/lessons";

export function points(n: number | null): string {
  return n === null ? "?" : String(Math.round(n * 100) / 100);
}

// Where something stands, in words, a tone and an icon (shown with <Label>).
export type Standing = { text: string; tone: Tone; icon: LucideIcon };

export function Label({ standing }: { standing: Standing }) {
  return <Chip tone={standing.tone} icon={standing.icon}>{standing.text}</Chip>;
}

// A submission: graded, waiting for the teacher, with the autograder, or could not be graded.
export function submissionLabel(s: SubmissionSummary): Standing {
  if (s.status === "graded") return { text: `Score ${points(s.score)} / ${points(s.max_score)}`, tone: "good", icon: CircleCheck };
  if (s.status === "failed") return { text: "Could not be graded", tone: "bad", icon: CircleAlert };
  if (s.status === "submitted") return { text: "Submitted", tone: "good", icon: CircleCheck };
  return { text: "Grading…", tone: "info", icon: LoaderCircle };
}

// A lesson, for the student reading it.
export function lessonLabel(lesson: Pick<MyLesson, "opened_at" | "completed_at" | "questions" | "answered">): Standing {
  if (lesson.completed_at) return { text: "Completed", tone: "good", icon: CircleCheck };
  if (!lesson.opened_at) return { text: "Not started", tone: "neutral", icon: Circle };
  if (lesson.questions > 0 && lesson.answered >= lesson.questions) return { text: "Checks done: mark it complete", tone: "info", icon: CircleDashed };
  return { text: "In progress", tone: "info", icon: CircleDashed };
}

// A lesson or an assignment, for teachers: a draft, published, or published with changes waiting.
export function publishLabel(item: { published: boolean; changed?: boolean }): Standing {
  if (!item.published) return { text: "Draft", tone: "neutral", icon: Pencil };
  if (item.changed) return { text: "Changes not published", tone: "warn", icon: Clock };
  return { text: "Published", tone: "good", icon: CircleCheck };
}

// Where a student is with an assignment: not started, opened, overdue, submitted, graded.
export default function Status({ assignment }: { assignment: Pick<MyAssignment, "opened_at" | "submission" | "due_at"> }) {
  const { submission, opened_at, due_at } = assignment;
  if (submission) {
    return (
      <>
        <Label standing={submissionLabel(submission)} />
        {submission.late && <Chip tone="bad" icon={Clock}>Late</Chip>}
      </>
    );
  }
  if (due_at && isPast(due_at)) return <Chip tone="bad" icon={CircleAlert}>Overdue</Chip>;
  return opened_at ? <Chip tone="info" icon={CircleDashed}>Opened</Chip> : <Chip icon={Circle}>Not started</Chip>;
}
