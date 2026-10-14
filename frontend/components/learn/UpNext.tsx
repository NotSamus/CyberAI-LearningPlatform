import Link from "next/link";
import { BookOpen, CircleAlert, CircleCheck, GraduationCap, NotebookPen, type LucideIcon } from "lucide-react";
import ProgressBar from "@/components/ProgressBar";
import type { MyAssignment } from "@/lib/api";
import { dueText, hoursUntil, isPast } from "@/lib/dates";
import type { MyLesson } from "@/lib/lessons";

// One thing a student could do now, with why it is listed.
export type Next = {
  key: string;
  href: string;
  kind: "Lesson" | "Notebook assignment";
  title: string;
  course: string | null;
  reason: string;
  tone: "" | "warn" | "bad";
  action: string;               // the words of the button, on the main card
  progress?: { value: number; max: number; label: string };
};

const WEEK = 7 * 24;            // hours

function notebook(a: MyAssignment, reason: string, tone: Next["tone"]): Next {
  return {
    key: `assignment-${a.id}`, href: `/assignments/${a.id}`, kind: "Notebook assignment", title: a.title, course: a.course,
    reason, tone, action: a.opened_at ? "Continue working" : "Open the notebook",
  };
}

// `end`: straight to the end of the lesson, where Mark as complete is (see LessonReader).
function lessonItem(lesson: MyLesson, reason: string, action: string, end = false): Next {
  const checks = lesson.questions > 0 && lesson.opened_at
    ? { value: lesson.answered, max: lesson.questions, label: `${lesson.answered} of ${lesson.questions} checks done` }
    : undefined;
  return {
    key: `lesson-${lesson.id}`, href: `/lessons/${lesson.id}${end ? "#end" : ""}`, kind: "Lesson", title: lesson.title, course: lesson.course,
    reason, tone: "", action, progress: checks,
  };
}

// What to do next, most pressing first: a submission that could not be graded, an assignment past
// its due date, one due within a week, a lesson that only needs marking complete, a lesson in
// progress, the next lesson of each course not opened yet, and last the other assignments not
// handed in. Each thing comes once.
export function whatIsNext(lessons: MyLesson[], assignments: MyAssignment[]): Next[] {
  const open = assignments.filter((a) => !a.submission);
  const late = (a: MyAssignment) => a.due_at !== null && isPast(a.due_at);
  const soon = (a: MyAssignment) => a.due_at !== null && !isPast(a.due_at) && hoursUntil(a.due_at) <= WEEK;
  const started = lessons.filter((l) => l.opened_at && !l.completed_at);
  const checksDone = (l: MyLesson) => l.questions > 0 && l.answered >= l.questions;

  const firstNotOpened = new Map<number | null, MyLesson>();
  for (const lesson of lessons) {
    if (!lesson.opened_at && !firstNotOpened.has(lesson.course_id)) firstNotOpened.set(lesson.course_id, lesson);
  }

  const found: Next[] = [
    ...assignments.filter((a) => a.submission?.status === "failed")
      .map((a) => notebook(a, "Could not be graded: open it, fix it and submit again", "bad")),
    ...open.filter(late).map((a) => notebook(a, `Was due ${dueText(a.due_at!)}: still accepted, marked late`, "bad")),
    ...open.filter(soon).map((a) => notebook(a, `Due ${dueText(a.due_at!)}`, hoursUntil(a.due_at!) < 48 ? "warn" : "")),
    ...started.filter(checksDone).map((l) => lessonItem(l, "Every check is done: mark it complete", "Finish the lesson", true)),
    ...started.filter((l) => !checksDone(l)).map((l) => lessonItem(l, "In progress: pick up where you left off", "Continue the lesson")),
    ...[...firstNotOpened.values()].map((l) => lessonItem(l, "Next in order, not started yet", "Start the lesson")),
    ...open.filter((a) => !late(a) && !soon(a)).map((a) => notebook(a, a.due_at ? `Due ${dueText(a.due_at)}` : "Not handed in yet", "")),
  ];
  const seen = new Set<string>();
  return found.filter((item) => {
    if (seen.has(item.key)) return false;
    seen.add(item.key);
    return true;
  });
}

function icon(item: Next): LucideIcon {
  if (item.tone === "bad") return CircleAlert;
  return item.kind === "Lesson" ? BookOpen : NotebookPen;
}

// How many things Up next shows: the main one and three more. Home leaves these out of Due soon.
export const SHOWN = 4;

// The top of a student's home: the one thing to do now (the page's only filled button), then up
// to three more, in one box.
export default function UpNext({ lessons, assignments }: { lessons: MyLesson[]; assignments: MyAssignment[] }) {
  const [first, ...more] = whatIsNext(lessons, assignments);

  if (!first) {
    return (
      <section aria-labelledby="up-next">
        <h2 id="up-next">Up next</h2>
        <ul className="list next-list">
          <li className="next-main">
            <span className="tile large good"><CircleCheck aria-hidden /></span>
            <div className="what">
              <h3>All caught up</h3>
              <p className="reason">Every lesson is complete and every assignment is handed in.</p>
            </div>
          </li>
        </ul>
      </section>
    );
  }

  const Icon = icon(first);
  return (
    <section aria-labelledby="up-next">
      <h2 id="up-next">Up next</h2>
      <ul className="list next-list">
        <li className="next-main">
          <span className={`tile large ${first.tone}`}><Icon aria-hidden /></span>
          <div className="what">
            <p className="check-label">{first.kind}{first.course && ` · ${first.course}`}</p>
            <h3>{first.title}</h3>
            <p className={`reason ${first.tone}`}>{first.reason}</p>
            {first.progress && <ProgressBar {...first.progress} />}
          </div>
          <Link href={first.href} className="button">{first.action}</Link>
        </li>
          {more.slice(0, SHOWN - 1).map((item) => {
            const RowIcon = icon(item);
            return (
              <li key={item.key}>
                <span className={`tile ${item.tone}`}><RowIcon aria-hidden /></span>
                <div className="grow">
                  <Link href={item.href} className="title">{item.title}</Link>
                  <p className="meta">
                    <span className={`reason ${item.tone}`}>{item.reason}</span>
                    {item.course && <span className="fact"><GraduationCap aria-hidden />{item.course}</span>}
                  </p>
                </div>
                {item.progress && <ProgressBar {...item.progress} />}
              </li>
            );
          })}
      </ul>
    </section>
  );
}
