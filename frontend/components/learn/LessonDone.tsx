"use client";
import Link from "next/link";
import { useEffect, useRef } from "react";
import { ArrowRight, CircleCheck, GraduationCap, House, ListChecks } from "lucide-react";
import { courseName } from "@/components/learn/courses";
import { formatWhen } from "@/lib/dates";
import type { MyLesson } from "@/lib/lessons";

// The end of a completed lesson: how far that brings the reader in its course, how the knowledge
// checks went, and the next lesson as one big link. `fresh`: it was completed just now, on this
// page (the panel then takes the focus, so that it is read out at once).
export default function LessonDone({ lesson, course, checks, firstTry, next, fresh }: {
  lesson: MyLesson;
  course: MyLesson[];             // the lessons of its course, this one included
  checks: number;
  firstTry: number;
  next: { id: number; title: string } | null;
  fresh: boolean;
}) {
  const panel = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (fresh) panel.current?.focus();
  }, [fresh]);

  const completed = course.filter((other) => other.completed_at).length;
  const summary = next && course.find((other) => other.id === next.id)?.summary;

  return (
    <section ref={panel} tabIndex={-1} className="card done-panel" aria-labelledby="lesson-done">
      <div className="done-head">
        <span className="tile large good"><CircleCheck aria-hidden /></span>
        <div>
          <h2 id="lesson-done">{fresh ? "Lesson complete" : "You completed this lesson"}</h2>
          <p className="meta">
            {!fresh && lesson.completed_at && <span>On {formatWhen(lesson.completed_at)}</span>}
            {course.length > 0 && (
              <span className="fact"><GraduationCap aria-hidden />{completed} of {course.length} lessons done in {courseName(lesson.course)}</span>
            )}
            {checks > 0 && (
              <span className="fact"><ListChecks aria-hidden />{firstTry} of {checks} {checks === 1 ? "check" : "checks"} right at the first try</span>
            )}
          </p>
        </div>
      </div>
      {next ? (
        <Link href={`/lessons/${next.id}`} className="next-lesson">
          <span className="grow">
            <span className="check-label">Next lesson</span>
            <strong>{next.title}</strong>
            {summary && <span className="muted clamp-2">{summary}</span>}
          </span>
          <ArrowRight aria-hidden />
        </Link>
      ) : (
        <div className="row">
          <p className="muted">That was the last lesson {lesson.course ? `of ${lesson.course}` : "for all students"}.</p>
          <Link href="/" className="button secondary"><House aria-hidden />Back to Home</Link>
        </div>
      )}
    </section>
  );
}
