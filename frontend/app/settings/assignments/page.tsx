"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import DueDate from "@/components/DueDate";
import { api, type Course, type ManagedAssignment, type Student } from "@/lib/api";
import { fromLocalInput, toLocalInput } from "@/lib/dates";
import { JSON_HEADERS, message } from "@/lib/errors";

const MAX_NOTEBOOK_BYTES = 10 * 1024 * 1024;    // same as MAX_NOTEBOOK_BYTES in api/app/assignments.py

export default function AssignmentsSettings() {
  // The server decides who may teach: /api/teach answers 403 for students, and this section only
  // shows anything once those requests have succeeded.
  const [items, setItems] = useState<ManagedAssignment[] | null>(null);
  const [students, setStudents] = useState<Student[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [editing, setEditing] = useState<number | null>(null);

  const load = useCallback(() => {
    Promise.all([
      api<ManagedAssignment[]>("/teach/assignments"), api<Student[]>("/teach/students"), api<Course[]>("/teach/courses"),
    ])
      .then(([assignments, people, classes]) => { setItems(assignments); setStudents(people); setCourses(classes); })
      .catch((e) => setLoadError(message(e)));
  }, []);
  useEffect(load, [load]);

  async function change(id: number, changes: Record<string, unknown>) {
    setError("");
    try {
      await api(`/teach/assignments/${id}`, { method: "PATCH", headers: JSON_HEADERS, body: JSON.stringify(changes) });
      load();
      return true;
    } catch (e) {
      setError(message(e));
      return false;
    }
  }

  async function remove(a: ManagedAssignment) {
    const sure = window.confirm(
      `Delete "${a.title}"? Students will no longer see it, and its submissions and grades are deleted too. ` +
      "Copies students already opened stay in their own notebook folders.",
    );
    if (!sure) return;
    setError("");
    try {
      await api(`/teach/assignments/${a.id}`, { method: "DELETE" });
      load();
    } catch (e) {
      setError(message(e));
    }
  }

  if (loadError) return <><h1>Assignments</h1><p className="error" role="alert">{loadError}</p></>;
  if (!items) return <><h1>Assignments</h1><p className="muted">Loading…</p></>;

  return (
    <>
      <h1>Assignments</h1>
      <p className="muted">
        Upload a notebook, choose who gets it, then publish it. Each student gets their own copy the
        first time they open it, and submits it when done.
      </p>

      <h2>New assignment</h2>
      <NewAssignment onCreated={(created) => { load(); setEditing(created.id); }} />

      <h2>Uploaded ({items.length})</h2>
      {error && <p className="error" role="alert">{error}</p>}
      {items.length === 0 && <p className="muted">Nothing uploaded yet.</p>}
      <ul className="assignments">
        {items.map((a) => (
          <li key={a.id} className="card">
            <div className="row">
              <h3>{a.title}</h3>
              <span className={`badge ${a.published ? "live" : "draft"}`}>{a.published ? "Published" : "Draft"}</span>
              <span className="badge">{a.autograded ? "Autograded" : "Graded by hand"}{a.points !== null && `, ${a.points} points`}</span>
              <span className="spacer" />
              <button className="secondary" onClick={() => change(a.id, { published: !a.published })}>
                {a.published ? "Unpublish" : "Publish"}
              </button>
              <button className="secondary" onClick={() => setEditing(editing === a.id ? null : a.id)}>
                {editing === a.id ? "Close" : "Edit"}
              </button>
              <button className="secondary danger" onClick={() => remove(a)}>Delete</button>
            </div>
            <p className="muted facts">
              <span>{givenTo(a, students, courses)}</span>
              {a.requires_gpu && <span className="badge gpu">GPU</span>}
              <DueDate due_at={a.due_at} done />
            </p>
            <p className="facts">
              <Link href={`/settings/assignments/${a.id}`}>Progress and grades</Link>
              <Link href={`/assignments/${a.id}`}>Open as a student would</Link>
              <a href={`/api/teach/assignments/${a.id}/notebook`}>Download {a.notebook_name}</a>
              {a.autograded && <a href={`/api/teach/assignments/${a.id}/master`}>Download with solutions</a>}
            </p>
            {a.published && nobody(a) && (
              <p className="error">Published, but given to nobody: no student can see it. Choose who gets it under Edit.</p>
            )}
            {editing === a.id && (
              <EditAssignment
                assignment={a}
                students={students}
                courses={courses}
                onSave={async (changes) => { if (await change(a.id, changes)) setEditing(null); }}
              />
            )}
          </li>
        ))}
      </ul>
    </>
  );
}

function nobody(a: ManagedAssignment): boolean {
  return !a.for_everyone && a.course_id === null && a.student_ids.length === 0;
}

function givenTo(a: ManagedAssignment, students: Student[], courses: Course[]): string {
  if (a.for_everyone) return `Given to all students (${students.length})`;
  if (nobody(a)) return "Given to nobody yet";
  const names = students.filter((s) => a.student_ids.includes(s.id)).map((s) => s.name);
  const course = courses.find((c) => c.id === a.course_id);
  const parts = [
    course && `${course.name} (${course.student_ids.length} students)`,
    names.length > 0 && (names.length <= 3 ? names.join(", ") : `${names.length} students`),
  ].filter(Boolean);
  return `Given to ${parts.join(" and ")}`;
}

function NewAssignment({ onCreated }: { onCreated: (created: ManagedAssignment) => void }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [due, setDue] = useState("");
  const [gpu, setGpu] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [fileInput, setFileInput] = useState(0);      // changing the key empties the file field
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [created, setCreated] = useState<ManagedAssignment | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setError("");
    setCreated(null);
    if (file.size > MAX_NOTEBOOK_BYTES) {     // a quick answer here; the server enforces the same limit
      setError("The notebook is larger than 10 MB. Clear its outputs and try again.");
      return;
    }
    setBusy(true);
    const form = new FormData();
    form.set("title", title);
    form.set("description", description);
    form.set("requires_gpu", String(gpu));
    const dueAt = fromLocalInput(due);
    if (dueAt) form.set("due_at", dueAt);
    form.set("file", file);
    try {
      // The server checks the file (a real notebook, at most 10 MB) and stores it as a draft. A
      // notebook written for Otter-Grader is prepared by Otter first, which runs it.
      const assignment = await api<ManagedAssignment>("/teach/assignments", { method: "POST", body: form });
      setCreated(assignment);
      setTitle("");
      setDescription("");
      setDue("");
      setGpu(false);
      setFile(null);
      setFileInput((n) => n + 1);
      onCreated(assignment);
    } catch (e) {
      setError(message(e));
    }
    setBusy(false);
  }

  return (
    <>
      <form className="form card" onSubmit={submit}>
        <label>
          Title
          <input required maxLength={120} value={title} onChange={(e) => setTitle(e.target.value)} />
        </label>
        <label>
          Notebook file (.ipynb, up to 10 MB)
          <input key={fileInput} type="file" accept=".ipynb" required onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </label>
        <label className="full">
          Description (what students should do)
          <textarea rows={3} maxLength={2000} value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
        <label>
          Due (optional)
          <input type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} />
        </label>
        <label className="check">
          <input type="checkbox" checked={gpu} onChange={(e) => setGpu(e.target.checked)} />
          Needs a GPU
        </label>
        <p className="muted full">
          For automatic grading, write the notebook in Otter-Grader’s “Otter Assign” format (questions with
          solutions and tests) and upload that one file: students get a version without your solutions, and
          submissions are graded against your tests, hidden ones included. Any other notebook is collected
          when students submit, and you grade it by hand.
        </p>
        <div className="full">
          <button type="submit" disabled={busy}>
            {busy ? "Uploading… (an autograded notebook is run first: up to a few minutes)" : "Upload as a draft"}
          </button>
        </div>
      </form>
      {error && <p className="error log" role="alert">{error}</p>}
      {created && (
        <p className="notice" role="status">
          <strong>{created.title}</strong> was uploaded as a draft
          {created.autograded ? `, and will be graded automatically${created.points !== null ? ` (${created.points} points)` : ""}` : ""}.
          Choose who gets it below, then press Publish.
        </p>
      )}
    </>
  );
}

type Audience = "course" | "everyone" | "chosen";

function EditAssignment({ assignment, students, courses, onSave }: {
  assignment: ManagedAssignment;
  students: Student[];
  courses: Course[];
  onSave: (changes: Record<string, unknown>) => Promise<void>;
}) {
  const [title, setTitle] = useState(assignment.title);
  const [description, setDescription] = useState(assignment.description);
  const [due, setDue] = useState(toLocalInput(assignment.due_at));
  const [gpu, setGpu] = useState(assignment.requires_gpu);
  const [pointsText, setPointsText] = useState(assignment.points === null ? "" : String(assignment.points));
  const [audience, setAudience] = useState<Audience>(
    assignment.for_everyone ? "everyone" : assignment.course_id !== null ? "course" : "chosen",
  );
  const [courseId, setCourseId] = useState<number | null>(assignment.course_id ?? courses[0]?.id ?? null);
  const [chosen, setChosen] = useState<number[]>(assignment.student_ids);
  const [busy, setBusy] = useState(false);
  const who = `who-${assignment.id}`;

  function toggle(id: number) {
    setChosen((ids) => (ids.includes(id) ? ids.filter((i) => i !== id) : [...ids, id]));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    await onSave({
      title, description, requires_gpu: gpu, due_at: fromLocalInput(due),
      // One way of giving it out at a time: a course, everyone, or chosen students.
      for_everyone: audience === "everyone",
      course_id: audience === "course" ? courseId : null,
      student_ids: audience === "chosen" ? chosen : [],
      ...(assignment.autograded ? {} : { points: pointsText === "" ? null : Number(pointsText) }),
    });
    setBusy(false);
  }

  return (
    <form className="form edit" onSubmit={submit}>
      <label>
        Title
        <input required maxLength={120} value={title} onChange={(e) => setTitle(e.target.value)} />
      </label>
      <label>
        Due (optional)
        <input type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} />
      </label>
      <label className="full">
        Description
        <textarea rows={3} maxLength={2000} value={description} onChange={(e) => setDescription(e.target.value)} />
      </label>
      {!assignment.autograded && (
        <label>
          Points (what you grade it out of; 100 if left empty)
          <input type="number" min="0.5" max="10000" step="0.5" value={pointsText} onChange={(e) => setPointsText(e.target.value)} />
        </label>
      )}
      <label className="check">
        <input type="checkbox" checked={gpu} onChange={(e) => setGpu(e.target.checked)} />
        Needs a GPU
      </label>

      <fieldset className="full">
        <legend>Who gets it</legend>
        <label className="check">
          <input type="radio" name={who} checked={audience === "course"} disabled={courses.length === 0} onChange={() => setAudience("course")} />
          The students of a course
          {courses.length === 0
            ? <span className="muted">(create one under Courses first)</span>
            : (
              <select value={courseId ?? ""} disabled={audience !== "course"} onChange={(e) => setCourseId(Number(e.target.value))}>
                {courses.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.student_ids.length} students)</option>)}
              </select>
            )}
        </label>
        <label className="check">
          <input type="radio" name={who} checked={audience === "everyone"} onChange={() => setAudience("everyone")} />
          All students, including accounts added later
        </label>
        <label className="check">
          <input type="radio" name={who} checked={audience === "chosen"} onChange={() => setAudience("chosen")} />
          Only the students I choose
        </label>
        {audience === "chosen" && (
          students.length === 0
            ? <p className="muted">There are no student accounts yet. An admin adds them under Accounts.</p>
            : (
              <div className="students">
                {students.map((s) => (
                  <label key={s.id} className="check">
                    <input type="checkbox" checked={chosen.includes(s.id)} onChange={() => toggle(s.id)} />
                    {s.name} <span className="muted">({s.username})</span>
                  </label>
                ))}
              </div>
            )
        )}
      </fieldset>

      <p className="muted full">
        The notebook file itself cannot be replaced here: students who already opened it keep their
        copy. To hand out a corrected notebook, upload it as a new assignment.
      </p>
      <div className="full">
        <button type="submit" disabled={busy}>{busy ? "Saving…" : "Save"}</button>
      </div>
    </form>
  );
}
