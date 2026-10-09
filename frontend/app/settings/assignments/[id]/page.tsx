"use client";
import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import DueDate from "@/components/DueDate";
import { points, submissionLabel } from "@/components/Status";
import { api, type Launch, type Progress, type StudentProgress, type Submission } from "@/lib/api";
import { formatWhen } from "@/lib/dates";
import { JSON_HEADERS, message } from "@/lib/errors";

// The gradebook of one assignment: every student it is given to, whether they opened it, what they
// submitted and their grade. Teachers and admins only: the server refuses everyone else.
export default function AssignmentProgress({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [grading, setGrading] = useState<number | null>(null);    // the student whose row is open

  const load = useCallback(() => {
    return api<Progress>(`/teach/assignments/${id}/progress`).then(setProgress);
  }, [id]);
  useEffect(() => { load().catch((e) => setLoadError(message(e))); }, [load]);

  // While the autograder is working on something, ask again every three seconds.
  const waiting = progress?.students.some((s) => s.submission && ["queued", "grading"].includes(s.submission.status));
  useEffect(() => {
    if (!waiting) return;
    const timer = setInterval(() => { load().catch(() => {}); }, 3000);
    return () => clearInterval(timer);
  }, [waiting, load]);

  async function act(action: () => Promise<unknown>) {
    setError("");
    try {
      await action();
      await load();
      return true;
    } catch (e) {
      setError(message(e));
      return false;
    }
  }

  async function open(student: StudentProgress) {
    // A copy of the submission goes into the teacher's own notebook environment and opens in a new tab.
    const tab = window.open("", "_blank");
    setError("");
    try {
      const launch = await api<Launch>(`/teach/assignments/${id}/submissions/${student.id}/open`, { method: "POST" });
      if (tab) tab.location.href = launch.url; else window.location.assign(launch.url);
    } catch (e) {
      tab?.close();
      setError(message(e));
    }
  }

  if (loadError) return <><h1>Progress and grades</h1><p className="error" role="alert">{loadError}</p></>;
  if (!progress) return <><h1>Progress and grades</h1><p className="muted">Loading…</p></>;

  const { assignment, students } = progress;
  const submitted = students.filter((s) => s.submission);
  const graded = submitted.filter((s) => s.submission?.status === "graded" && s.submission.score !== null);
  const average = graded.length > 0 ? graded.reduce((sum, s) => sum + (s.submission?.score ?? 0), 0) / graded.length : null;

  return (
    <>
      <p><Link href="/settings/assignments">← Assignments</Link></p>
      <h1>{assignment.title}</h1>
      <p className="badges">
        <span className={`badge ${assignment.published ? "live" : "draft"}`}>{assignment.published ? "Published" : "Draft"}</span>
        <span className="badge">{assignment.autograded ? "Autograded" : "Graded by hand"}{assignment.points !== null && `, ${assignment.points} points`}</span>
        {assignment.course && <span className="badge">{assignment.course}</span>}
        <DueDate due_at={assignment.due_at} done />
      </p>
      <p className="facts">
        <span>
          {students.length} {students.length === 1 ? "student" : "students"} · {students.filter((s) => s.opened_at).length} opened · {submitted.length} submitted · {graded.length} graded
          {average !== null && ` · average ${points(average)}`}
        </span>
        <a href={`/api/teach/assignments/${id}/grades.csv`}>Download grades (CSV)</a>
      </p>
      <p className="muted">
        “Open” puts a copy of a submission in your own notebook environment. Read it there, but do not run it:
        it is a student’s code, and it would run with your files in reach. The autograder has already run it safely.
      </p>
      {error && <p className="error log" role="alert">{error}</p>}
      {students.length === 0 && (
        <p className="muted">This assignment is not given to any student yet. Choose who gets it under Assignments &gt; Edit.</p>
      )}

      {students.length > 0 && (
        <div className="table-scroll">
          <table>
            <thead>
              <tr><th>Student</th><th>Opened</th><th>Submitted</th><th>Status</th><th>Score</th><th></th></tr>
            </thead>
            <tbody>
              {students.map((s) => (
                <Row
                  key={s.id}
                  student={s}
                  autograded={assignment.autograded}
                  open={grading === s.id}
                  onToggle={() => setGrading(grading === s.id ? null : s.id)}
                  onOpen={() => open(s)}
                  downloadHref={`/api/teach/assignments/${id}/submissions/${s.id}/notebook`}
                  onRegrade={() => act(() => api(`/teach/assignments/${id}/submissions/${s.id}/regrade`, { method: "POST" }))}
                  onGrade={(grade) => act(() => api(`/teach/assignments/${id}/submissions/${s.id}`, {
                    method: "PATCH", headers: JSON_HEADERS, body: JSON.stringify(grade),
                  }))}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function statusOf(student: StudentProgress): { text: string; tone: string } {
  if (student.submission) {
    const { text, tone } = submissionLabel(student.submission);
    return { text: student.submission.status === "graded" ? "Graded" : text, tone };
  }
  return { text: student.opened_at ? "Opened" : "Not started", tone: "" };
}

function Row({ student, autograded, open, onToggle, onOpen, downloadHref, onRegrade, onGrade }: {
  student: StudentProgress;
  autograded: boolean;
  open: boolean;
  onToggle: () => void;
  onOpen: () => void;
  downloadHref: string;
  onRegrade: () => Promise<boolean>;
  onGrade: (grade: { score?: number; feedback: string }) => Promise<boolean>;
}) {
  const submission = student.submission;
  const status = statusOf(student);
  return (
    <>
      <tr>
        <td>{student.name} <span className="muted">({student.username})</span></td>
        <td>{formatWhen(student.opened_at)}</td>
        <td>
          {submission && formatWhen(submission.submitted_at)}
          {submission?.late && <> <span className="badge late">Late</span></>}
        </td>
        <td><span className={`badge ${status.tone}`}>{status.text}</span></td>
        <td>
          {submission?.score != null && `${points(submission.score)} / ${points(submission.max_score)}`}
          {submission?.graded_by_teacher && <span className="muted"> (by hand)</span>}
        </td>
        <td className="actions">
          {submission && (
            <>
              <button className="secondary" onClick={onToggle}>{open ? "Close" : "Grade"}</button>
              <button className="secondary" onClick={onOpen}>Open</button>
              <a className="button secondary" href={downloadHref}>Download</a>
            </>
          )}
        </td>
      </tr>
      {open && submission && (
        <tr className="detail">
          <td colSpan={6}>
            <GradeForm submission={submission} autograded={autograded} onRegrade={onRegrade} onGrade={onGrade} />
          </td>
        </tr>
      )}
    </>
  );
}

function GradeForm({ submission, autograded, onRegrade, onGrade }: {
  submission: Submission;
  autograded: boolean;
  onRegrade: () => Promise<boolean>;
  onGrade: (grade: { score?: number; feedback: string }) => Promise<boolean>;
}) {
  const [score, setScore] = useState(submission.score === null ? "" : String(submission.score));
  const [feedback, setFeedback] = useState(submission.feedback);
  const [busy, setBusy] = useState(false);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    // An untouched score is not sent, so the autograder's score stays the autograder's.
    const changed = score !== "" && Number(score) !== submission.score;
    await onGrade({ ...(changed ? { score: Number(score) } : {}), feedback });
    setBusy(false);
  }

  return (
    <div className="grade">
      {submission.status === "failed" && (
        <>
          <p className="error">The autograder could not run this notebook:</p>
          <pre>{submission.error}</pre>
        </>
      )}
      {submission.questions.map((q) => (
        <details key={q.name}>
          <summary>{q.name}: {points(q.score)} / {points(q.max_score)}</summary>
          <pre>{q.output}</pre>
        </details>
      ))}
      <form className="form" onSubmit={save}>
        <label>
          Score{submission.max_score !== null && ` (out of ${points(submission.max_score)})`}
          <input type="number" min="0" step="any" value={score} onChange={(e) => setScore(e.target.value)} />
        </label>
        <label className="full">
          Comment for the student
          <textarea rows={2} maxLength={5000} value={feedback} onChange={(e) => setFeedback(e.target.value)} />
        </label>
        <div className="full row">
          <button type="submit" disabled={busy}>{busy ? "Saving…" : "Save grade"}</button>
          {autograded && (
            <button type="button" className="secondary" disabled={busy} onClick={onRegrade}>Run the autograder again</button>
          )}
        </div>
      </form>
    </div>
  );
}
