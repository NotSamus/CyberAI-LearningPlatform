"use client";
import { useCallback, useEffect, useState } from "react";
import { api, type Course, type Student } from "@/lib/api";
import { JSON_HEADERS, message } from "@/lib/errors";

// Courses group students, so an assignment or an announcement can be given to a whole class at once.
export default function CoursesSettings() {
  const [courses, setCourses] = useState<Course[] | null>(null);
  const [students, setStudents] = useState<Student[]>([]);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [name, setName] = useState("");
  const [editing, setEditing] = useState<number | null>(null);

  const load = useCallback(() => {
    Promise.all([api<Course[]>("/teach/courses"), api<Student[]>("/teach/students")])
      .then(([classes, people]) => { setCourses(classes); setStudents(people); })
      .catch((e) => setLoadError(message(e)));
  }, []);
  useEffect(load, [load]);

  async function act(action: () => Promise<unknown>) {
    setError("");
    try {
      await action();
      load();
      return true;
    } catch (e) {
      setError(message(e));
      return false;
    }
  }

  async function create(e: React.FormEvent) {
    e.preventDefault();
    const created = await act(async () => {
      const course = await api<Course>("/teach/courses", { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ name }) });
      setEditing(course.id);        // straight on to choosing its students
    });
    if (created) setName("");
  }

  function remove(course: Course) {
    const sure = window.confirm(
      `Delete "${course.name}"? Its announcements are deleted. Its assignments stay, but are no longer given to these students until you give them out again.`,
    );
    if (sure) act(() => api(`/teach/courses/${course.id}`, { method: "DELETE" }));
  }

  if (loadError) return <><h1>Courses</h1><p className="error" role="alert">{loadError}</p></>;
  if (!courses) return <><h1>Courses</h1><p className="muted">Loading…</p></>;

  return (
    <>
      <h1>Courses</h1>
      <p className="muted">
        A course is a group of students. Give an assignment or an announcement to a course and all its
        students get it, including students you add to the course later.
      </p>

      <h2>New course</h2>
      <form className="row" onSubmit={create}>
        <input required maxLength={120} placeholder="CS 101, section 2" aria-label="Course name" value={name} onChange={(e) => setName(e.target.value)} />
        <button type="submit">Create course</button>
      </form>
      {error && <p className="error" role="alert">{error}</p>}

      <h2>Courses ({courses.length})</h2>
      {courses.length === 0 && <p className="muted">No courses yet.</p>}
      <ul className="assignments">
        {courses.map((course) => (
          <li key={course.id} className="card">
            <div className="row">
              <h3>{course.name}</h3>
              <span className="badge">{course.student_ids.length} {course.student_ids.length === 1 ? "student" : "students"}</span>
              <span className="spacer" />
              <button className="secondary" onClick={() => setEditing(editing === course.id ? null : course.id)}>
                {editing === course.id ? "Close" : "Edit"}
              </button>
              <button className="secondary danger" onClick={() => remove(course)}>Delete</button>
            </div>
            {editing === course.id && (
              <EditCourse
                course={course}
                students={students}
                onSave={async (changes) => {
                  const saved = await act(() => api(`/teach/courses/${course.id}`, {
                    method: "PATCH", headers: JSON_HEADERS, body: JSON.stringify(changes),
                  }));
                  if (saved) setEditing(null);
                }}
              />
            )}
          </li>
        ))}
      </ul>
    </>
  );
}

function EditCourse({ course, students, onSave }: {
  course: Course;
  students: Student[];
  onSave: (changes: { name: string; student_ids: number[] }) => Promise<void>;
}) {
  const [name, setName] = useState(course.name);
  const [chosen, setChosen] = useState<number[]>(course.student_ids);
  const [busy, setBusy] = useState(false);

  function toggle(id: number) {
    setChosen((ids) => (ids.includes(id) ? ids.filter((i) => i !== id) : [...ids, id]));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    await onSave({ name, student_ids: chosen });
    setBusy(false);
  }

  return (
    <form className="form edit" onSubmit={submit}>
      <label>
        Name
        <input required maxLength={120} value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <fieldset className="full">
        <legend>Students in this course ({chosen.length})</legend>
        {students.length === 0
          ? <p className="muted">There are no student accounts yet. An admin adds them under Accounts.</p>
          : (
            <>
              <p className="row">
                <button type="button" className="secondary" onClick={() => setChosen(students.map((s) => s.id))}>Select all</button>
                <button type="button" className="secondary" onClick={() => setChosen([])}>Select none</button>
              </p>
              <div className="students">
                {students.map((s) => (
                  <label key={s.id} className="check">
                    <input type="checkbox" checked={chosen.includes(s.id)} onChange={() => toggle(s.id)} />
                    {s.name} <span className="muted">({s.username})</span>
                  </label>
                ))}
              </div>
            </>
          )}
      </fieldset>
      <div className="full">
        <button type="submit" disabled={busy}>{busy ? "Saving…" : "Save"}</button>
      </div>
    </form>
  );
}
