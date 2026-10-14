import Link from "next/link";
import { BookOpen, Cpu, ListChecks, NotebookPen } from "lucide-react";
import DueDate from "@/components/DueDate";
import ProgressBar from "@/components/ProgressBar";
import Status, { Label, lessonLabel, publishLabel } from "@/components/Status";
import { courseName, type CourseGroup } from "@/components/learn/courses";

function count(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}

// Everything of one course on Home: its name and size, how far the student is in it, then every
// lesson (in the teachers' order) and every assignment with where it stands. For a teacher
// (`asTeacher`) their own progress means nothing: they see drafts marked instead.
export default function CourseSection({ group, asTeacher }: { group: CourseGroup; asTeacher: boolean }) {
  const { lessons, assignments } = group;
  // Done: lessons completed and assignments handed in, together.
  const done = lessons.filter((lesson) => lesson.completed_at).length + assignments.filter((a) => a.submission).length;
  const total = lessons.length + assignments.length;
  const size = [
    lessons.length > 0 && count(lessons.length, "lesson", "lessons"),
    assignments.length > 0 && count(assignments.length, "assignment", "assignments"),
  ].filter(Boolean).join(" · ");
  const heading = `course-${group.id ?? "everyone"}`;

  return (
    <section aria-labelledby={heading}>
      <div className="course-head">
        <h2 id={heading}>{courseName(group.course)}</h2>
        <span className="muted">{size}</span>
        {!asTeacher && total > 0 && <ProgressBar value={done} max={total} label={`${done} of ${total} done`} />}
      </div>
      <ul className="list">
        {lessons.map((lesson) => (
          <li key={`lesson-${lesson.id}`}>
            <span className="tile"><BookOpen aria-hidden /></span>
            <div className="grow">
              <Link href={`/lessons/${lesson.id}`} className="title">{lesson.title}</Link>
              {lesson.summary && <span className="summary clamp-2">{lesson.summary}</span>}
              {lesson.questions > 0 && (
                <p className="meta">
                  <span className="fact">
                    <ListChecks aria-hidden />
                    {asTeacher || !lesson.opened_at
                      ? count(lesson.questions, "knowledge check", "knowledge checks")
                      : `${lesson.answered} of ${count(lesson.questions, "check", "checks")} done`}
                  </span>
                </p>
              )}
            </div>
            <span className="badges">
              {asTeacher ? !lesson.published && <Label standing={publishLabel(lesson)} /> : <Label standing={lessonLabel(lesson)} />}
            </span>
          </li>
        ))}
        {assignments.map((a) => (
          <li key={`assignment-${a.id}`}>
            <span className="tile"><NotebookPen aria-hidden /></span>
            <div className="grow">
              <Link href={`/assignments/${a.id}`} className="title">{a.title}</Link>
              {a.description && <span className="summary clamp-2">{a.description}</span>}
              {(a.due_at || a.requires_gpu) && (
                <p className="meta">
                  <DueDate due_at={a.due_at} done={Boolean(a.submission)} />
                  {a.requires_gpu && <span className="fact"><Cpu aria-hidden />GPU</span>}
                </p>
              )}
            </div>
            <span className="badges">
              {asTeacher ? !a.published && <Label standing={publishLabel(a)} /> : <Status assignment={a} />}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
