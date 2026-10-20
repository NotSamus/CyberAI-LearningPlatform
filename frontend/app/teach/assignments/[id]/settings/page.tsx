"use client";
import { Database, Download, FileCheck, Plus, RotateCcw, SquarePen, Trash2, Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";
import { points } from "@/components/Status";
import FileDrop, { fileSize } from "@/components/teach/FileDrop";
import StudentPicker from "@/components/teach/StudentPicker";
import { useAssignmentPage } from "@/components/teach/context";
import { api, dataProblem, MAX_DATA_BYTES, MAX_DATA_FILES, type Course, type Launch, type ManagedAssignment, type Student } from "@/lib/api";
import { fromLocalInput, toLocalInput } from "@/lib/dates";
import { JSON_HEADERS, message } from "@/lib/errors";
import { useMe } from "@/lib/useMe";

const MAX_NOTEBOOK_BYTES = 10 * 1024 * 1024;    // same as MAX_NOTEBOOK_BYTES in api/app/assignments.py

// An assignment's settings: what it is, who gets it and when it is due, its files (the notebook and
// its data files), changing them (until a student has opened it), and deleting it.
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
  const [replaced, setReplaced] = useState("");      // what a new notebook or new data files made of the assignment
  const [version, setVersion] = useState(0);         // a new notebook can change the points: the form starts over

  useEffect(() => {
    Promise.all([api<Student[]>("/teach/students"), api<Course[]>("/teach/courses")])
      .then(([people, classes]) => { setStudents(people); setCourses(classes); })
      .catch((e) => setLoadError(message(e)));
  }, []);

  async function save(changes: Record<string, unknown>) {
    setError("");
    setSaved(false);
    setReplaced("");
    try {
      await api(`/teach/assignments/${assignment.id}`, { method: "PATCH", headers: JSON_HEADERS, body: JSON.stringify(changes) });
      await reload();
      setSaved(true);
    } catch (e) {
      setError(message(e));
    }
  }

  const [changingData, setChangingData] = useState(false);
  const [dataNote, setDataNote] = useState<{ error: boolean; text: string } | null>(null);   // shown under the files, where the change was made
  // Adds or removes data files. An autograded assignment goes through Otter again first.
  async function changeData(done: string, request: () => Promise<ManagedAssignment>): Promise<boolean> {
    setChangingData(true);
    setDataNote(null);
    try {
      await request();
      await reload();
      setDataNote({ error: false, text: done });
      return true;
    } catch (e) {
      setDataNote({ error: true, text: message(e) });
      return false;
    } finally {
      setChangingData(false);
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
      {replaced && <p className="notice" role="status">{replaced}</p>}
      {loadError && <p className="error" role="alert">{loadError}</p>}

      <section>
        <h2>Details and who gets it</h2>
        {students
          ? <EditAssignment key={version} assignment={assignment} students={students} courses={courses} onSave={save} outcome={error ? "Not saved: see above." : saved ? "Saved." : ""} />
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
          {(assignment.data_files ?? []).map((data) => (
            <li key={data.name}>
              <span className="tile"><Database aria-hidden /></span>
              <div className="grow">
                <a className="title" href={`/api/teach/assignments/${assignment.id}/data-files/${encodeURIComponent(data.name)}`}>{data.name}</a>
                <span className="muted">Data file, {fileSize(data.size)}. Each student gets a copy beside the notebook.</span>
              </div>
              {assignment.notebook_locked === false && (
                <div className="row-actions">
                  <button
                    className="icon danger" title="Remove" aria-label={`Remove ${data.name}`} disabled={changingData}
                    onClick={() => window.confirm(`Remove ${data.name}? Students will not get it. Keep a copy if you may need it again.`)
                      && changeData(`${data.name} removed.`, () => api<ManagedAssignment>(
                        `/teach/assignments/${assignment.id}/data-files/${encodeURIComponent(data.name)}`, { method: "DELETE" },
                      ))}
                  >
                    <Trash2 aria-hidden />
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
        {dataNote && <p className={dataNote.error ? "error log" : "notice"} role={dataNote.error ? "alert" : "status"}>{dataNote.text}</p>}
        {assignment.notebook_locked === false && (
          <AddDataFiles assignment={assignment} busy={changingData} onAdd={(files) => changeData(
            files.length === 1 ? `${files[0].name} added.` : `${files.length} data files added.`,
            () => {
              const form = new FormData();
              files.forEach((f) => form.append("files", f));
              return api<ManagedAssignment>(`/teach/assignments/${assignment.id}/data-files`, { method: "POST", body: form });
            },
          )} onError={(text) => setDataNote({ error: true, text })} />
        )}
        {assignment.notebook_locked && (
          <p className="muted hint">
            A student has opened it and has their own copy, so the notebook and its data files can no longer be
            changed. To hand out a corrected notebook, upload it as a new assignment.
          </p>
        )}
      </section>

      {assignment.notebook_locked === false && (
        <ChangeNotebook
          assignment={assignment}
          onError={(text) => { setReplaced(""); setSaved(false); setError(text); }}
          onReplaced={async (now) => {
            await reload();
            setVersion((v) => v + 1);
            setError("");
            setSaved(false);
            setReplaced(
              `Notebook replaced. ${now.autograded ? `It is graded automatically now (${points(now.points ?? 0)} points).` : "It is graded by hand now."}` +
              " If you opened it to try it out before, your copy is the earlier version: delete it in JupyterLab to get this one.",
            );
          }}
        />
      )}

      <section className="danger-zone">
        <h2>Delete this assignment</h2>
        <p className="muted">Its submissions and grades are deleted too. Copies students already opened stay in their own notebook folders.</p>
        <button className="secondary danger" onClick={remove}><Trash2 aria-hidden />Delete assignment</button>
      </section>
    </>
  );
}

// Choosing data files to add, while no student has the assignment yet.
function AddDataFiles({ assignment, busy, onAdd, onError }: {
  assignment: ManagedAssignment;
  busy: boolean;
  onAdd: (files: File[]) => Promise<boolean>;
  onError: (text: string) => void;
}) {
  const [files, setFiles] = useState<File[]>([]);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    // Those with the same name as one already there take its place.
    const kept = (assignment.data_files ?? []).filter((d) => !files.some((f) => f.name === d.name));
    const problem = dataProblem(files, kept);
    if (problem) return onError(problem);
    if (await onAdd(files)) setFiles([]);
  }

  return (
    <form className="add-data" onSubmit={add}>
      <FileDrop
        multiple what="data files" files={files} busy={busy} required onFiles={setFiles}
        hint={`Datasets the notebook opens by name (CSV, JSON, images, a .zip…), beside it in each student's folder. Up to ${MAX_DATA_FILES} files, ${MAX_DATA_BYTES / (1024 * 1024)} MB in all. A file with the name of one already here takes its place.`}
      />
      <div className="row">
        <button type="submit" className="secondary" disabled={busy || files.length === 0}>
          <Plus aria-hidden />{busy ? (assignment.autograded ? "Adding… (Otter runs the notebook again first: up to a few minutes)" : "Adding…") : "Add data files"}
        </button>
      </div>
      {assignment.autograded && (
        <p className="muted hint">
          Otter runs your notebook with them before they are kept, and its autograder carries them, so submissions are graded
          with them. If your ASSIGNMENT CONFIG lists <code>files:</code> itself, list every data file there.
        </p>
      )}
    </form>
  );
}

// Changing the notebook while no student has it yet: for instance to add Otter's cells so that it
// is graded automatically. Edited in the teacher's own JupyterLab and taken back from there, or
// replaced by uploading another file. Either way Otter prepares it first, as for an upload.
function ChangeNotebook({ assignment, onError, onReplaced }: {
  assignment: ManagedAssignment;
  onError: (text: string) => void;
  onReplaced: (now: ManagedAssignment) => Promise<void>;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState<"" | "editing" | "using" | "uploading">("");
  const checking = "Checking… (an autograded notebook is run first: up to a few minutes)";

  async function edit(startOver: boolean) {
    if (startOver && !window.confirm(
      "Start over? Your editing copy is replaced with the assignment's notebook as it is now, and the edits in it are lost.",
    )) return;
    // Opened first, before anything is awaited: otherwise browsers block it as a pop-up.
    const tab = window.open("", "_blank");
    setBusy("editing");
    try {
      const launch = await api<Launch>(`/teach/assignments/${assignment.id}/editing-copy`, {
        method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ start_over: startOver }),
      });
      if (tab) tab.location.href = launch.url; else window.location.assign(launch.url);
    } catch (e) {
      tab?.close();
      onError(message(e));
    }
    setBusy("");
  }

  async function replace(kind: "using" | "uploading", request: () => Promise<ManagedAssignment>) {
    setBusy(kind);
    try {
      await onReplaced(await request());
      if (kind === "uploading") setFile(null);
    } catch (e) {
      onError(message(e));
    }
    setBusy("");
  }

  function useEdits() {
    return replace("using", () => api<ManagedAssignment>(`/teach/assignments/${assignment.id}/editing-copy/use`, { method: "POST" }));
  }

  function upload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    if (file.size > MAX_NOTEBOOK_BYTES) {     // a quick answer here; the server enforces the same limit
      onError("The notebook is larger than 10 MB. Clear its outputs and try again.");
      return;
    }
    const form = new FormData();
    form.set("file", file);
    return replace("uploading", () => api<ManagedAssignment>(`/teach/assignments/${assignment.id}/notebook`, { method: "PUT", body: form }));
  }

  return (
    <section>
      <h2>Change the notebook</h2>
      <p className="muted hint">
        Until the first student opens this assignment, its notebook can still be changed. To have it graded
        automatically, add Otter-Grader’s cells (questions with solutions and tests, as in the platform’s
        example <code>assignments/otter-example/functions.ipynb</code>); without them it is graded by hand. Otter checks your solutions
        against your tests before the change is made.
      </p>
      <div className="card change-notebook">
        <div>
          <h3>Edit it in JupyterLab</h3>
          <p className="muted">
            A copy{assignment.autograded ? ", with your solutions and tests," : ""} goes into your own notebook
            files, at <code>editing/{assignment.slug}/{assignment.notebook_name}</code>. Edit it there, run the
            test cells, save it, then come back here and press Use my edits. Your edits stay in that copy until
            you start over.
          </p>
          <div className="row">
            <button type="button" className="secondary" disabled={busy !== ""} onClick={() => edit(false)}>
              <SquarePen aria-hidden />{busy === "editing" ? "Opening…" : "Edit in JupyterLab"}
            </button>
            <button type="button" disabled={busy !== ""} onClick={useEdits}>
              <FileCheck aria-hidden />{busy === "using" ? checking : "Use my edits"}
            </button>
            <span className="spacer" />
            <button type="button" className="secondary" disabled={busy !== ""} onClick={() => edit(true)}>
              <RotateCcw aria-hidden />Start over
            </button>
          </div>
        </div>
        <form onSubmit={upload}>
          <h3>Or upload a new version</h3>
          <FileDrop accept=".ipynb" what="a .ipynb file" hint="A Jupyter notebook, up to 10 MB. It takes the place of the current one." file={file} busy={busy !== ""} required onFile={setFile} />
          <div className="row">
            <button type="submit" disabled={busy !== "" || !file}>
              <Upload aria-hidden />{busy === "uploading" ? checking : "Replace notebook"}
            </button>
          </div>
        </form>
      </div>
    </section>
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
  const gpuOff = useMe()?.gpu_notebooks === false;       // GPU notebooks turned off for the platform
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
        Needs a GPU{gpuOff && <span className="muted"> (turned off for now: it opens in the standard environment)</span>}
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
