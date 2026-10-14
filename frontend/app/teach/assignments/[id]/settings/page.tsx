"use client";
import { Download, FileCheck, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";
import { points } from "@/components/Status";
import StudentPicker from "@/components/teach/StudentPicker";
import { useAssignmentPage } from "@/components/teach/context";
import { api, type Course, type ManagedAssignment, type Student } from "@/lib/api";
import { fromLocalInput, toLocalInput } from "@/lib/dates";
import { JSON_HEADERS, message } from "@/lib/errors";

// An assignment's settings: what it is, who gets it and when it is due, its files, and deleting it.
// `?new=1`: it was just uploaded, and still has to be given to students and published.
export default function AssignmentSettings({ searchParams }: { searchParams: Promise<{ new?: string }> }) {
  const { new: justUploaded } = use(searchParams);
  const router = useRouter();
  const { progress, reload } = useAssignmentPage();
  const assignment = progress.assignment;
  const [students, setStudents] = useState<Student[] | null>(null);
  const [courses, setCourses] = useState<Course[]>([]);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    Promise.all([api<Student[]>("/teach/students"), api<Course[]>("/teach/courses")])
      .then(([people, classes]) => { setStudents(people); setCourses(classes); })
      .catch((e) => setLoadError(message(e)));
  }, []);

  async function save(changes: Record<string, unknown>) {
    setError("");
    setSaved(false);
    try {
      await api(`/teach/assignments/${assignment.id}`, { method: "PATCH", headers: JSON_HEADERS, body: JSON.stringify(changes) });
      await reload();
      setSaved(true);
    } catch (e) {
      setError(message(e));
    }
  }

  async function remove() {
    const sure = window.confirm(
      `Delete "${assignment.title}"? Students will no longer see it, and its submissions and grades are deleted too. ` +
      "Copies students already opened stay in their own notebook folders.",
    );
    if (!sure) return;
    setError("");
    try {
      await api(`/teach/assignments/${assignment.id}`, { method: "DELETE" });
      router.push("/teach/assignments");
    } catch (e) {
      setError(message(e));
    }
  }

  return (
    <>
      {justUploaded === "1" && !assignment.published && (
        <p className="notice" role="status">
          <strong>{assignment.title}</strong> was uploaded as a draft
          {assignment.autograded ? `, and will be graded automatically${assignment.points !== null ? ` (${points(assignment.points)} points)` : ""}` : ""}.
          {" "}{assignment.course ? `It is for ${assignment.course}: check` : "Choose"} who gets it below, then press Publish.
        </p>
      )}
      {error && <p className="error" role="alert">{error}</p>}
      {saved && <p className="notice" role="status">Saved.</p>}
      {loadError && <p className="error" role="alert">{loadError}</p>}

      <section>
        <h2>Details and who gets it</h2>
        {students
          ? <EditAssignment assignment={assignment} students={students} courses={courses} onSave={save} outcome={error ? "Not saved: see above." : saved ? "Saved." : ""} />
          : !loadError && <p className="muted">Loading…</p>}
      </section>

      <section>
        <h2>Files</h2>
        <ul className="list">
          <li>
            <span className="tile"><Download aria-hidden /></span>
            <div className="grow">
              <a className="title" href={`/api/teach/assignments/${assignment.id}/notebook`}>Download {assignment.notebook_name}</a>
              <span className="muted">The notebook as students get it.</span>
            </div>
          </li>
          {assignment.autograded && (
            <li>
              <span className="tile"><FileCheck aria-hidden /></span>
              <div className="grow">
                <a className="title" href={`/api/teach/assignments/${assignment.id}/master`}>Download with solutions</a>
                <span className="muted">The notebook you uploaded, with your solutions and tests.</span>
              </div>
            </li>
          )}
        </ul>
        <p className="muted hint">
          The notebook file itself cannot be replaced: students who already opened it keep their copy. To hand
          out a corrected notebook, upload it as a new assignment.
        </p>
      </section>

      <section className="danger-zone">
        <h2>Delete this assignment</h2>
        <p className="muted">Its submissions and grades are deleted too. Copies students already opened stay in their own notebook folders.</p>
        <button className="secondary danger" onClick={remove}><Trash2 aria-hidden />Delete assignment</button>
      </section>
    </>
  );
}

type Audience = "course" | "everyone" | "chosen";

function EditAssignment({ assignment, students, courses, onSave, outcome }: {
  assignment: ManagedAssignment;
  students: Student[];
  courses: Course[];
  onSave: (changes: Record<string, unknown>) => Promise<void>;
  outcome: string;            // how the last save went, repeated by the button (the message itself is at the top)
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
    <form className="form card" onSubmit={submit}>
      <label>
        Title
        <input required maxLength={120} value={title} onChange={(e) => setTitle(e.target.value)} />
      </label>
      <label>
        Due (optional)
        <input type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} />
      </label>
      <label className="full">
        Description (what students should do)
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
              <select value={courseId ?? ""} disabled={audience !== "course"} aria-label="Course" onChange={(e) => setCourseId(Number(e.target.value))}>
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
        {audience === "chosen" && <StudentPicker students={students} chosen={chosen} onChange={setChosen} />}
      </fieldset>

      <div className="full row">
        <button type="submit" disabled={busy}>{busy ? "Saving…" : "Save"}</button>
        {!busy && outcome && <span className="muted">{outcome}</span>}
      </div>
    </form>
  );
}
