"use client";
import { useEffect, useState } from "react";
import ExportMenu from "@/components/teach/ExportMenu";
import StudentPicker from "@/components/teach/StudentPicker";
import { useCoursePage } from "@/components/teach/context";
import { api, type Student } from "@/lib/api";
import { JSON_HEADERS, message } from "@/lib/errors";

// Who is in a course. Everything given to the course reaches these students, including what was
// given before they were added. Export: their progress and grades in this course, as a file.
export default function CourseStudents() {
  const { course, reload } = useCoursePage();
  const [students, setStudents] = useState<Student[] | null>(null);
  const [chosen, setChosen] = useState<number[]>(course.student_ids);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<Student[]>("/teach/students").then(setStudents).catch((e) => setLoadError(message(e)));
  }, []);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      await api(`/teach/courses/${course.id}`, { method: "PATCH", headers: JSON_HEADERS, body: JSON.stringify({ student_ids: chosen }) });
      await reload();
      setSaved(true);
    } catch (e) {
      setError(message(e));
    }
    setBusy(false);
  }

  if (loadError) return <p className="error" role="alert">{loadError}</p>;
  if (!students) return <p className="muted">Loading…</p>;

  const unsaved = [...chosen].sort().join() !== [...course.student_ids].sort().join();
  return (
    <form className="card members" onSubmit={save}>
      <div className="row members-head">
        <p className="muted">
          Its students get every lesson, assignment and announcement given to this course, including those given
          before they were added.
        </p>
        <ExportMenu path={`/teach/courses/${course.id}/students`} label={`Export the students of ${course.name}`} />
      </div>
      <StudentPicker students={students} chosen={chosen} onChange={(ids) => { setChosen(ids); setSaved(false); }} />
      <div className="row">
        <button type="submit" disabled={busy || !unsaved}>{busy ? "Saving…" : "Save students"}</button>
        {unsaved && <span className="muted">Not saved yet.</span>}
        {saved && !unsaved && <span className="muted" role="status">Saved.</span>}
      </div>
      {error && <p className="error" role="alert">{error}</p>}
    </form>
  );
}
