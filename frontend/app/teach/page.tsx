"use client";
import {
  BookOpen, CalendarClock, CircleAlert, CircleCheck, Hourglass, Inbox, NotebookPen, Plus, School, Upload, Users, type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import Chip from "@/components/Chip";
import DueDate from "@/components/DueDate";
import EmptyState from "@/components/EmptyState";
import PageHeader from "@/components/PageHeader";
import ProgressBar from "@/components/ProgressBar";
import { Label, publishLabel, type Standing } from "@/components/Status";
import { Waiting } from "@/components/teach/AssignmentRows";
import NewLessonDialog from "@/components/teach/NewLessonDialog";
import { GIVEN_TO_NOBODY as NOBODY, givenToNobody, lessonForNobody, plural } from "@/components/teach/given";
import { api, type Course, type ManagedAssignment } from "@/lib/api";
import { formatWhen, hoursUntil } from "@/lib/dates";
import { message } from "@/lib/errors";
import type { ManagedLesson } from "@/lib/lessons";

// Something not finished: a lesson or an assignment, why it needs a look, and where to fix it.
type Attention = { key: string; title: string; href: string; kind: "Lesson" | "Assignment"; standing: Standing; why: string; rank: number };

// What needs the teacher now, worked out here from the lists of assignments (with how far their
// students have got), lessons and courses: submissions waiting for a grade, what is due around now,
// what is not finished, and each course at a glance.
export default function TeachOverview() {
  const [assignments, setAssignments] = useState<ManagedAssignment[] | null>(null);
  const [lessons, setLessons] = useState<ManagedLesson[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [loadError, setLoadError] = useState("");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    Promise.all([api<ManagedAssignment[]>("/teach/assignments"), api<ManagedLesson[]>("/teach/lessons"), api<Course[]>("/teach/courses")])
      .then(([notebooks, written, classes]) => { setAssignments(notebooks); setLessons(written); setCourses(classes); })
      .catch((e) => setLoadError(message(e)));
  }, []);

  const newLesson = <button className="secondary" onClick={() => setCreating(true)}><Plus aria-hidden />New lesson</button>;
  const upload = <Link href="/teach/assignments/new" className="button secondary"><Upload aria-hidden />Upload notebook</Link>;
  // Nothing made yet: "Start teaching" below offers these, with New course first.
  const nothingYet = assignments !== null && assignments.length === 0 && lessons.length === 0 && courses.length === 0;
  const header = (
    <PageHeader
      title="Overview"
      description="What needs you now: submissions to grade, what is due, and what is not finished yet."
      actions={nothingYet ? undefined : <>{newLesson}{upload}</>}
    />
  );
  const dialog = <NewLessonDialog open={creating} onClose={() => setCreating(false)} courses={courses} />;

  if (loadError) return <>{header}<p className="error" role="alert">{loadError}</p>{dialog}</>;
  if (!assignments) return <>{header}<p className="muted">Loading…</p>{dialog}</>;

  if (nothingYet) {
    return (
      <>
        {header}
        <EmptyState
          icon={School} title="Start teaching"
          action={<><Link href="/teach/courses?new=1" className="button"><Plus aria-hidden />New course</Link>{newLesson}{upload}</>}
        >
          Make a course for each class and choose its students, then write lessons and upload notebooks for it.
          What needs you will show up here.
        </EmptyState>
        {dialog}
      </>
    );
  }

  // Submissions waiting for the teacher: graded by hand, or the autograder could not run them. The
  // assignment whose oldest submission has waited longest comes first.
  const toGrade = assignments
    .filter((a) => a.counts && a.counts.to_grade + a.counts.failed > 0)
    .sort((a, b) => (a.counts?.oldest_waiting_at ?? "").localeCompare(b.counts?.oldest_waiting_at ?? ""));
  const submissionsToGrade = toGrade.reduce((sum, a) => sum + (a.counts ? a.counts.to_grade + a.counts.failed : 0), 0);

  // Published assignments due from three days ago to a week from now, soonest first.
  const dueSoon = assignments
    .filter((a) => a.published && a.due_at && hoursUntil(a.due_at) >= -72 && hoursUntil(a.due_at) <= 168)
    .sort((a, b) => (a.due_at ?? "").localeCompare(b.due_at ?? ""));

  const attention: Attention[] = [
    ...lessons.flatMap((lesson): Attention[] => {
      const at = { key: `lesson-${lesson.id}`, title: lesson.title, href: `/teach/lessons/${lesson.id}`, kind: "Lesson" as const };
      if (lesson.published && lessonForNobody(lesson)) return [{ ...at, standing: NOBODY, why: "Published, but no student can see it. Choose who it is for.", rank: 0 }];
      if (lesson.published && lesson.changed) return [{ ...at, standing: publishLabel(lesson), why: "Students still see the version published before.", rank: 1 }];
      if (!lesson.published) return [{ ...at, standing: publishLabel(lesson), why: "Students cannot see it until you publish it.", rank: 2 }];
      return [];
    }),
    ...assignments.flatMap((a): Attention[] => {
      const at = { key: `assignment-${a.id}`, title: a.title, href: `/teach/assignments/${a.id}/settings`, kind: "Assignment" as const };
      if (a.published && givenToNobody(a)) return [{ ...at, standing: NOBODY, why: "Published, but no student can see it. Choose who gets it.", rank: 0 }];
      if (!a.published) return [{ ...at, standing: publishLabel(a), why: "Choose who gets it, then publish it.", rank: 2 }];
      return [];
    }),
  ].sort((a, b) => a.rank - b.rank);

  return (
    <>
      {header}
      <div className="overview">
        <section>
          {/* The count is of submissions, as on Home and on each row, not of assignments */}
          <div className="section-head"><h2>To grade</h2>{submissionsToGrade > 0 && <Chip tone="warn">{submissionsToGrade}</Chip>}</div>
          {toGrade.length === 0
            ? <Quiet icon={CircleCheck}>Nothing to grade. Submissions that wait for you, and any the autograder could not run, show up here.</Quiet>
            : (
              <ul className="list links">
                {toGrade.map((a) => (
                  <li key={a.id}>
                    <span className="tile"><Inbox aria-hidden /></span>
                    <div className="grow">
                      <div className="title-line">
                        <Link className="title" href={`/teach/assignments/${a.id}`}>{a.title}</Link>
                        <Waiting assignment={a} />
                      </div>
                      <p className="meta">
                        {a.counts?.oldest_waiting_at && <span className="fact"><Hourglass aria-hidden />Waiting since {formatWhen(a.counts.oldest_waiting_at)}</span>}
                        {a.course && <span className="fact"><School aria-hidden />{a.course}</span>}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
        </section>

        <section>
          <div className="section-head"><h2>Due soon</h2><span className="muted">The past three days and the coming week</span></div>
          {dueSoon.length === 0
            ? <Quiet icon={CalendarClock}>No published assignment is due in the coming week, or was due in the past three days.</Quiet>
            : (
              <ul className="list links">
                {dueSoon.map((a) => {
                  const counts = a.counts;
                  const waitingToHandIn = counts ? Math.max(0, counts.opened - counts.submitted) : 0;
                  return (
                    <li key={a.id}>
                      <span className="tile"><CalendarClock aria-hidden /></span>
                      <div className="grow">
                        <Link className="title" href={`/teach/assignments/${a.id}`}>{a.title}</Link>
                        <p className="meta">
                          <DueDate due_at={a.due_at} done />
                          {counts && counts.given > 0 ? (
                            <>
                              <ProgressBar value={counts.submitted} max={counts.given} label={`${counts.submitted} of ${counts.given} submitted`} />
                              <span>{waitingToHandIn} opened, not submitted</span>
                              {counts.late > 0 && <span className="fact bad"><CircleAlert aria-hidden />{counts.late} late</span>}
                            </>
                          ) : <span className="fact bad"><CircleAlert aria-hidden />Given to no students</span>}
                        </p>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
        </section>
      </div>

      <section>
        <div className="section-head"><h2>Needs attention</h2>{attention.length > 0 && <span className="muted">Drafts, changes not published, and what is given to nobody</span>}</div>
        {attention.length === 0
          ? <Quiet icon={CircleCheck}>Everything is published and given to someone.</Quiet>
          : (
            <ul className="list links">
              {attention.map((item) => (
                <li key={item.key}>
                  <span className="tile">{item.kind === "Lesson" ? <BookOpen aria-hidden /> : <NotebookPen aria-hidden />}</span>
                  <div className="grow">
                    <div className="title-line">
                      <Link className="title" href={item.href}>{item.title}</Link>
                      <Label standing={item.standing} />
                    </div>
                    <p className="meta"><span>{item.kind}</span><span>{item.why}</span></p>
                  </div>
                </li>
              ))}
            </ul>
          )}
      </section>

      <section>
        <div className="section-head"><h2>Courses</h2></div>
        {courses.length === 0
          ? (
            <EmptyState icon={School} title="No courses yet" action={<Link href="/teach/courses?new=1" className="button secondary"><Plus aria-hidden />New course</Link>}>
              A course is a group of students: give it lessons and assignments, and all its students get them.
            </EmptyState>
          )
          : (
            <ul className="grid">
              {courses.map((course) => {
                const own = assignments.filter((a) => a.course_id === course.id);
                const waiting = own.reduce((sum, a) => sum + (a.counts ? a.counts.to_grade + a.counts.failed : 0), 0);
                return (
                  <li key={course.id}>
                    <Link href={`/teach/courses/${course.id}`} className="card course-card">
                      <h3>{course.name}</h3>
                      <p className="meta">
                        <span className="fact"><Users aria-hidden />{plural(course.student_ids.length, "student")}</span>
                        <span className="fact"><BookOpen aria-hidden />{plural(lessons.filter((l) => !l.for_everyone && l.course_id === course.id).length, "lesson")}</span>
                        <span className="fact"><NotebookPen aria-hidden />{plural(own.length, "assignment")}</span>
                      </p>
                      {waiting > 0 && <Chip tone="warn" icon={Inbox}>{waiting} to grade</Chip>}
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
      </section>
      {dialog}
    </>
  );
}

// A section with nothing in it: a short line in a quiet box, not a big empty state.
function Quiet({ icon: Icon, children }: { icon: LucideIcon; children: React.ReactNode }) {
  return <p className="quiet"><Icon aria-hidden /><span>{children}</span></p>;
}
