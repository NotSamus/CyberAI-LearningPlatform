"use client";
import { BookOpen, ChevronRight, NotebookPen, Plus, School, Users } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useCallback, useEffect, useState } from "react";
import Dialog from "@/components/Dialog";
import EmptyState from "@/components/EmptyState";
import PageHeader from "@/components/PageHeader";
import { plural } from "@/components/teach/given";
import { api, type Course, type ManagedAssignment } from "@/lib/api";
import { JSON_HEADERS, message } from "@/lib/errors";
import type { ManagedLesson } from "@/lib/lessons";

// Courses group students, so a lesson, an assignment or an announcement can be given to a whole
// class at once. Each course has its own page: its content in the order students get it, and its students.
// `?new=1` (from the overview, when there is no course yet) opens "New course" at once.
export default function CoursesPage({ searchParams }: { searchParams: Promise<{ new?: string }> }) {
  const { new: asked } = use(searchParams);
  const [courses, setCourses] = useState<Course[] | null>(null);
  const [lessons, setLessons] = useState<ManagedLesson[]>([]);
  const [assignments, setAssignments] = useState<ManagedAssignment[]>([]);
  const [loadError, setLoadError] = useState("");
  const [creating, setCreating] = useState(asked === "1");

  const load = useCallback(() => {
    Promise.all([api<Course[]>("/teach/courses"), api<ManagedLesson[]>("/teach/lessons"), api<ManagedAssignment[]>("/teach/assignments")])
      .then(([classes, written, notebooks]) => { setCourses(classes); setLessons(written); setAssignments(notebooks); })
      .catch((e) => setLoadError(message(e)));
  }, []);
  useEffect(load, [load]);

  const newCourse = <button onClick={() => setCreating(true)}><Plus aria-hidden />New course</button>;
  const header = (
    <PageHeader
      title="Courses"
      description="A course is a group of students. Give it lessons, assignments and announcements, and all its students get them, including students you add to it later."
      actions={courses && courses.length > 0 ? newCourse : undefined}      // with none yet, the empty list below offers it
    />
  );

  const dialog = <NewCourseDialog open={creating} onClose={() => setCreating(false)} />;
  if (loadError) return <>{header}<p className="error" role="alert">{loadError}</p>{dialog}</>;
  if (!courses) return <>{header}<p className="muted">Loading…</p>{dialog}</>;

  return (
    <>
      {header}
      {courses.length === 0 ? (
        <EmptyState icon={School} title="No courses yet" action={newCourse}>
          Make a course for each class or section, then choose its students.
        </EmptyState>
      ) : (
        <ul className="list links">
          {courses.map((course) => {
            const ownLessons = lessons.filter((l) => !l.for_everyone && l.course_id === course.id).length;
            const ownAssignments = assignments.filter((a) => a.course_id === course.id).length;
            return (
              <li key={course.id}>
                <span className="tile"><School aria-hidden /></span>
                <div className="grow">
                  <Link className="title" href={`/teach/courses/${course.id}`}>{course.name}</Link>
                  <p className="meta">
                    <span className="fact"><Users aria-hidden />{plural(course.student_ids.length, "student")}</span>
                    <span className="fact"><BookOpen aria-hidden />{plural(ownLessons, "lesson")}</span>
                    <span className="fact"><NotebookPen aria-hidden />{plural(ownAssignments, "assignment")}</span>
                  </p>
                </div>
                <ChevronRight aria-hidden className="go" />
              </li>
            );
          })}
        </ul>
      )}
      {dialog}
    </>
  );
}

function NewCourseDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const course = await api<Course>("/teach/courses", { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ name }) });
      router.push(`/teach/courses/${course.id}/students`);        // straight on to choosing its students
    } catch (e) {
      setError(message(e));
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} title="New course" onClose={onClose}>
      <form onSubmit={create}>
        <div className="dialog-body">
          <label>
            Name
            <input required autoFocus maxLength={120} placeholder="CS 101, section 2" value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <p className="muted">Next, you choose its students.</p>
          {error && <p className="error" role="alert">{error}</p>}
        </div>
        <div className="dialog-foot">
          <button type="button" className="secondary" onClick={onClose}>Cancel</button>
          <button type="submit" disabled={busy}>{busy ? "Creating…" : "Create course"}</button>
        </div>
      </form>
    </Dialog>
  );
}
