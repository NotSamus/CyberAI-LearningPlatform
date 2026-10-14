"use client";
import { School, Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";
import PageHeader from "@/components/PageHeader";
import FileDrop from "@/components/teach/FileDrop";
import { api, type Course, type ManagedAssignment } from "@/lib/api";
import { fromLocalInput } from "@/lib/dates";
import { JSON_HEADERS, message } from "@/lib/errors";

const MAX_NOTEBOOK_BYTES = 10 * 1024 * 1024;    // same as MAX_NOTEBOOK_BYTES in api/app/assignments.py

// Uploading a notebook as a new assignment. It is stored as a draft; its Settings tab comes next,
// to choose who gets it and publish it. `?course=ID` (from a course's page) gives it to that course
// right after the upload.
export default function NewAssignmentPage({ searchParams }: { searchParams: Promise<{ course?: string }> }) {
  const { course: courseParam } = use(searchParams);
  const courseId = courseParam && /^\d+$/.test(courseParam) ? Number(courseParam) : null;
  const router = useRouter();
  const [course, setCourse] = useState<Course | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [due, setDue] = useState("");
  const [gpu, setGpu] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (courseId === null) return;
    api<Course[]>("/teach/courses").then((all) => setCourse(all.find((c) => c.id === courseId) ?? null)).catch(() => {});
  }, [courseId]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setError("");
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
      if (courseId !== null) {
        // If this fails the assignment is still there: its Settings tab, next, shows who gets it.
        await api(`/teach/assignments/${assignment.id}`, {
          method: "PATCH", headers: JSON_HEADERS, body: JSON.stringify({ course_id: courseId }),
        }).catch(() => {});
      }
      router.push(`/teach/assignments/${assignment.id}/settings?new=1`);
    } catch (e) {
      setError(message(e));
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        crumbs={[{ label: "Assignments", href: "/teach/assignments" }]}
        title="Upload notebook"
        description="The notebook is stored as a draft. Next you choose who gets it, then publish it."
      />
      {error && <p className="error log" role="alert">{error}</p>}
      <form className="form card" onSubmit={submit}>
        {courseId !== null && (
          <p className="full meta"><span className="fact"><School aria-hidden />For {course ? course.name : "the course you came from"}</span></p>
        )}
        <div className="full">
          <FileDrop accept=".ipynb" what="a .ipynb file" hint="A Jupyter notebook, up to 10 MB." file={file} required onFile={setFile} />
        </div>
        <label>
          Title
          <input required maxLength={120} value={title} onChange={(e) => setTitle(e.target.value)} />
        </label>
        <label>
          Due (optional)
          <input type="datetime-local" value={due} onChange={(e) => setDue(e.target.value)} />
        </label>
        <label className="check">
          <input type="checkbox" checked={gpu} onChange={(e) => setGpu(e.target.checked)} />
          Needs a GPU
        </label>
        <label className="full">
          Description (what students should do)
          <textarea rows={3} maxLength={2000} value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
        <p className="muted full">
          For automatic grading, write the notebook in Otter-Grader’s “Otter Assign” format (questions with
          solutions and tests) and upload that one file: students get a version without your solutions, and
          submissions are graded against your tests, hidden ones included. Any other notebook is collected
          when students submit, and you grade it by hand.
        </p>
        <div className="full">
          <button type="submit" disabled={busy}>
            <Upload aria-hidden />
            {busy ? "Uploading… (an autograded notebook is run first: up to a few minutes)" : "Upload as a draft"}
          </button>
        </div>
      </form>
    </>
  );
}
