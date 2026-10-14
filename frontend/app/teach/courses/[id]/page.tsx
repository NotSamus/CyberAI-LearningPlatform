"use client";
import { BookOpen, Globe, NotebookPen, Plus, Upload } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import DueDate from "@/components/DueDate";
import EmptyState from "@/components/EmptyState";
import { Label, publishLabel } from "@/components/Status";
import AssignmentRows from "@/components/teach/AssignmentRows";
import LessonRows from "@/components/teach/LessonRows";
import { useCoursePage } from "@/components/teach/context";
import { api, type ManagedAssignment } from "@/lib/api";
import { message } from "@/lib/errors";
import type { ManagedLesson } from "@/lib/lessons";

// A course's content: its lessons in the order its students get them, its assignments, and what
// every student gets, this course's included.
export default function CourseContent() {
  const { course, courses, newLesson } = useCoursePage();
  const [lessons, setLessons] = useState<ManagedLesson[] | null>(null);
  const [assignments, setAssignments] = useState<ManagedAssignment[]>([]);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(() => {
    Promise.all([api<ManagedLesson[]>("/teach/lessons"), api<ManagedAssignment[]>("/teach/assignments")])
      .then(([written, notebooks]) => { setLessons(written); setAssignments(notebooks); })
      .catch((e) => setLoadError(message(e)));
  }, []);
  useEffect(load, [load]);

  if (loadError) return <p className="error" role="alert">{loadError}</p>;
  if (!lessons) return <p className="muted">Loading…</p>;

  const own = lessons.filter((l) => !l.for_everyone && l.course_id === course.id);
  const ownAssignments = assignments.filter((a) => a.course_id === course.id);
  const sharedLessons = lessons.filter((l) => l.for_everyone);
  const sharedAssignments = assignments.filter((a) => a.for_everyone);
  const upload = `/teach/assignments/new?course=${course.id}`;

  return (
    <>
      {error && <p className="error" role="alert">{error}</p>}

      <section>
        <div className="section-head">
          <h2>Lessons</h2>
          {own.length > 1 && <span className="muted">Its students get them in this order. Use the arrows to change it.</span>}
        </div>
        {own.length === 0
          ? (
            <EmptyState icon={BookOpen} title="No lessons in this course yet" action={<button className="secondary" onClick={newLesson}><Plus aria-hidden />New lesson</button>}>
              Lessons you write for this course show up here, in the order its students get them.
            </EmptyState>
          )
          : <LessonRows lessons={own} order={lessons.map((l) => l.id)} courses={courses} reorder withinCourse onChanged={load} onError={setError} />}
      </section>

      <section>
        <div className="section-head"><h2>Assignments</h2></div>
        {ownAssignments.length === 0
          ? (
            <EmptyState icon={NotebookPen} title="No assignments in this course yet" action={<Link href={upload} className="button secondary"><Upload aria-hidden />Upload notebook</Link>}>
              Upload a Jupyter notebook: it is given to this course, and you publish it when it is ready.
            </EmptyState>
          )
          : <AssignmentRows assignments={ownAssignments} />}
      </section>

      {(sharedLessons.length > 0 || sharedAssignments.length > 0) && (
        <section>
          <div className="section-head">
            <h2>Also for all students</h2>
            <span className="muted">Every student gets these, this course’s students included. Change their order under Lessons, with “For all students”.</span>
          </div>
          <ul className="list">
            {sharedLessons.map((lesson) => (
              <li key={`lesson-${lesson.id}`}>
                <span className="tile"><Globe aria-hidden /></span>
                <div className="grow">
                  <div className="title-line">
                    <Link className="title" href={`/teach/lessons/${lesson.id}`}>{lesson.title}</Link>
                    <Label standing={publishLabel(lesson)} />
                  </div>
                  <p className="meta"><span className="fact"><BookOpen aria-hidden />Lesson</span></p>
                </div>
              </li>
            ))}
            {sharedAssignments.map((a) => (
              <li key={`assignment-${a.id}`}>
                <span className="tile"><Globe aria-hidden /></span>
                <div className="grow">
                  <div className="title-line">
                    <Link className="title" href={`/teach/assignments/${a.id}`}>{a.title}</Link>
                    <Label standing={publishLabel(a)} />
                  </div>
                  <p className="meta">
                    <span className="fact"><NotebookPen aria-hidden />Assignment</span>
                    <DueDate due_at={a.due_at} done />
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
