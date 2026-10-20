"use client";
import { BookOpen, Download, Plus, Upload } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import EmptyState from "@/components/EmptyState";
import PageHeader from "@/components/PageHeader";
import ImportLessonsDialog from "@/components/teach/ImportLessonsDialog";
import LessonRows from "@/components/teach/LessonRows";
import NewLessonDialog from "@/components/teach/NewLessonDialog";
import { lessonForNobody } from "@/components/teach/given";
import { api, download, type Course } from "@/lib/api";
import { message } from "@/lib/errors";
import { lessonsZip, MAX_EXPORT_LESSONS, type ManagedLesson } from "@/lib/lessons";

// Which lessons the list shows: all of them, those for every student, those given to nobody, or a
// course's ("course-<id>").
type Filter = "all" | "everyone" | "none" | `course-${number}`;

// Lessons are written here, in the platform: text, code, pictures, videos and knowledge checks.
export default function LessonsPage() {
  const [items, setItems] = useState<ManagedLesson[] | null>(null);
  const [courses, setCourses] = useState<Course[]>([]);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [creating, setCreating] = useState(false);
  const [importing, setImporting] = useState(false);
  const [exporting, setExporting] = useState(false);

  const load = useCallback(() => {
    Promise.all([api<ManagedLesson[]>("/teach/lessons"), api<Course[]>("/teach/courses")])
      .then(([lessons, classes]) => { setItems(lessons); setCourses(classes); })
      .catch((e) => setLoadError(message(e)));
  }, []);
  useEffect(load, [load]);

  const courseId = filter.startsWith("course-") ? Number(filter.slice("course-".length)) : null;
  const shown = (items ?? []).filter((lesson) => {
    if (filter === "everyone") return lesson.for_everyone;
    if (filter === "none") return lessonForNobody(lesson);
    if (courseId !== null) return !lesson.for_everyone && lesson.course_id === courseId;
    return true;
  });
  // The order only means something within what one group of students sees: a course's lessons, or
  // those for everyone. All lessons together mix several groups, so the arrows are not offered there.
  const reorder = filter === "everyone" || courseId !== null;
  const audience = filter === "everyone" ? "everyone" : courseId !== null ? String(courseId) : "none";

  // The lessons shown, as one .zip with their pictures and notebooks, to import here or elsewhere.
  async function exportShown() {
    setExporting(true);
    setError("");
    try {
      await download(lessonsZip(shown.map((lesson) => lesson.id)));
    } catch (e) {
      setError(message(e));
    }
    setExporting(false);
  }

  const newLesson = <button onClick={() => setCreating(true)}><Plus aria-hidden />New lesson</button>;
  const importButton = <button className="secondary" onClick={() => setImporting(true)}><Upload aria-hidden />Import</button>;
  const header = (
    <PageHeader
      title="Lessons"
      description="Write lessons block by block: text, code, pictures, videos, and knowledge checks that are checked as students answer. Students see a lesson once it is published and given to them."
      actions={items && items.length > 0 ? <>{importButton}{newLesson}</> : undefined}      // with none yet, the empty list below offers them
    />
  );
  const dialog = (
    <>
      <NewLessonDialog open={creating} onClose={() => setCreating(false)} courses={courses} audience={audience} />
      <ImportLessonsDialog
        open={importing} onClose={() => setImporting(false)} onImported={() => { setError(""); load(); }} courses={courses} audience={audience}
      />
    </>
  );

  if (loadError) return <>{header}<p className="error" role="alert">{loadError}</p>{dialog}</>;
  if (!items) return <>{header}<p className="muted">Loading…</p>{dialog}</>;

  return (
    <>
      {header}
      {error && <p className="error" role="alert">{error}</p>}
      {items.length === 0 ? (
        <EmptyState icon={BookOpen} title="No lessons yet" action={<>{newLesson}{importButton}</>}>
          Write your first lesson: start with a title, then add text, code, pictures and knowledge checks. Or import
          lessons exported from another platform.
        </EmptyState>
      ) : (
        <>
          <div className="filters">
            <label>
              Show
              <select value={filter} onChange={(e) => setFilter(e.target.value as Filter)}>
                <option value="all">All lessons ({items.length})</option>
                <option value="everyone">For all students</option>
                {courses.map((c) => <option key={c.id} value={`course-${c.id}`}>{c.name}</option>)}
                <option value="none">Given to nobody</option>
              </select>
            </label>
            <span className="muted">
              {reorder
                ? "Students see these lessons in this order. Use the arrows to change it."
                : "To change the order students see lessons in, show one course, or the lessons for all students."}
            </span>
            {shown.length > 0 && (
              <button
                className="secondary push" disabled={exporting || shown.length > MAX_EXPORT_LESSONS} onClick={exportShown}
                title={`${shown.length === 1 ? "This lesson" : `These ${shown.length} lessons`} as a .zip with pictures and notebooks, to import here or elsewhere. It has the answers: keep it from students.`}
              >
                <Download aria-hidden />{exporting ? "Exporting…" : shown.length === 1 ? "Export" : `Export ${shown.length}`}
              </button>
            )}
          </div>
          {shown.length === 0
            ? <p className="muted">No lessons here yet.</p>
            : (
              <LessonRows
                lessons={shown} order={items.map((lesson) => lesson.id)} courses={courses} reorder={reorder}
                onChanged={load} onError={setError}
              />
            )}
        </>
      )}
      {dialog}
    </>
  );
}
