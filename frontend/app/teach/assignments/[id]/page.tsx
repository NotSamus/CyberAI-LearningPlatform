"use client";
import { Circle, CircleCheck, CircleDashed, Clock, Info, Users } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import Chip from "@/components/Chip";
import EmptyState from "@/components/EmptyState";
import { Label, points, submissionLabel, type Standing } from "@/components/Status";
import { useAssignmentPage } from "@/components/teach/context";
import { api, type Launch, type StudentProgress, type Submission } from "@/lib/api";
import { formatWhen } from "@/lib/dates";
import { JSON_HEADERS, message } from "@/lib/errors";

// The gradebook of one assignment: every student it is given to, whether they opened it, what they
// submitted and their grade. The assignment and its rows come from the layout above, which asks
// the server again after every change. Teachers and admins only: the server refuses everyone else.
export default function Gradebook() {
  const { progress, reload } = useAssignmentPage();
  const [error, setError] = useState("");
  const [grading, setGrading] = useState<number | null>(null);    // the student whose row is open
  const { assignment, students } = progress;
  const id = assignment.id;

  // While the autograder is working on something, ask again every three seconds.
  const waiting = students.some((s) => s.submission && ["queued", "grading"].includes(s.submission.status));
  useEffect(() => {
    if (!waiting) return;
    const timer = setInterval(() => { reload().catch(() => {}); }, 3000);
    return () => clearInterval(timer);
  }, [waiting, reload]);

  async function act(action: () => Promise<unknown>) {
    setError("");
    try {
      await action();
      await reload();
      return true;
    } catch (e) {
      setError(message(e));
      return false;
    }
  }

  async function open(student: StudentProgress) {
    // A copy of the submission goes into the teacher's own notebook environment and opens in a new
    // tab. The tab is opened first, before anything is awaited: otherwise browsers block it as a pop-up.
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

  // Waiting for the teacher: handed in and not graded yet, or the autograder could not run it.
  const toGrade = (s: StudentProgress) => s.submission !== null && ["submitted", "failed"].includes(s.submission.status);
  // The one to grade after this student: the next one down the table waiting for a grade, or else
  // the first one above it.
  function nextToGrade(after: number): number | null {
    const here = students.findIndex((s) => s.id === after);
    const order = [...students.slice(here + 1), ...students.slice(0, Math.max(here, 0))];
    return order.find(toGrade)?.id ?? null;
  }

  const submitted = students.filter((s) => s.submission);
  const graded = submitted.filter((s) => s.submission?.status === "graded" && s.submission.score !== null);
  const average = graded.length > 0 ? graded.reduce((sum, s) => sum + (s.submission?.score ?? 0), 0) / graded.length : null;

  if (students.length === 0) {
    return (
      <EmptyState
        icon={Users} title="Not given to any student yet"
        action={<Link href={`/teach/assignments/${id}/settings`} className="button secondary">Choose who gets it</Link>}
      >
        Once it is given to students and published, each of them shows up here with what they handed in.
      </EmptyState>
    );
  }

  return (
    <>
      {error && <p className="error log" role="alert">{error}</p>}
      <p className="meta gradebook-facts">
        <span>{students.length} {students.length === 1 ? "student" : "students"}</span>
        <span>{students.filter((s) => s.opened_at).length} opened</span>
        <span>{submitted.length} submitted</span>
        <span>{graded.length} graded</span>
        {average !== null && <span>average {points(average)}</span>}
      </p>
      <p className="safety">
        <Info aria-hidden />
        <span>
          “Open” puts a copy of a submission in your own notebook environment. Read it there, but do not run it:
          it is a student’s code, and it would run with your files in reach.
          {assignment.autograded && " The autograder has already run it, safely, in a box of its own."}
          {assignment.autograded && " It runs the student’s own notebook, so the student’s code can influence the score: open the notebook when a score looks wrong."}
        </span>
      </p>

      <div className="table-scroll gradebook">
        <table>
          <thead>
            <tr><th>Student</th><th>Submitted</th><th>Status</th><th className="num">Score</th><th><span className="visually-hidden">Actions</span></th></tr>
          </thead>
          <tbody>
            {students.map((s) => (
              <Row
                key={s.id}
                student={s}
                autograded={assignment.autograded}
                outOf={assignment.points}
                next={nextToGrade(s.id)}
                open={grading === s.id}
                onToggle={() => setGrading(grading === s.id ? null : s.id)}
                onOpen={() => open(s)}
                downloadHref={`/api/teach/assignments/${id}/submissions/${s.id}/notebook`}
                onRegrade={() => act(() => api(`/teach/assignments/${id}/submissions/${s.id}/regrade`, { method: "POST" }))}
                onGrade={async (grade, andNext) => {
                  // Where to go next is worked out before the save: after it, this student is no
                  // longer waiting and the list has moved on.
                  const next = andNext ? nextToGrade(s.id) : null;
                  const saved = await act(() => api(`/teach/assignments/${id}/submissions/${s.id}`, {
                    method: "PATCH", headers: JSON_HEADERS, body: JSON.stringify(grade),
                  }));
                  if (saved && andNext) setGrading(next);
                  return saved;
                }}
              />
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function statusOf(student: StudentProgress): Standing {
  if (student.submission) {
    const standing = submissionLabel(student.submission);
    return student.submission.status === "graded" ? { ...standing, text: "Graded", icon: CircleCheck } : standing;
  }
  return student.opened_at ? { text: "Opened", tone: "info", icon: CircleDashed } : { text: "Not started", tone: "neutral", icon: Circle };
}

type Grade = { score?: number; feedback: string };

function Row({ student, autograded, outOf, next, open, onToggle, onOpen, downloadHref, onRegrade, onGrade }: {
  student: StudentProgress;
  autograded: boolean;
  outOf: number | null;           // the assignment's points, if the teacher set them
  next: number | null;            // the student to grade after this one, if any
  open: boolean;
  onToggle: () => void;
  onOpen: () => void;
  downloadHref: string;
  onRegrade: () => Promise<boolean>;
  onGrade: (grade: Grade, andNext: boolean) => Promise<boolean>;
}) {
  const submission = student.submission;
  const status = statusOf(student);
  return (
    <>
      <tr>
        <td><span className="person"><strong>{student.name}</strong><span className="muted">{student.username}</span></span></td>
        {/* When it was handed in; before that, when it was opened (one column less, so that the
            buttons at the end fit on an iPad held upright) */}
        <td className="when">
          {submission ? formatWhen(submission.submitted_at)
            : student.opened_at ? <span className="muted">Opened {formatWhen(student.opened_at)}</span>
            : <span className="muted">—</span>}
          {submission?.late && <> <Chip tone="bad" icon={Clock}>Late</Chip></>}
        </td>
        <td><Label standing={status} /></td>
        <td className="num">
          {submission?.score != null && `${points(submission.score)} / ${points(submission.max_score)}`}
          {submission?.graded_by_teacher && <span className="muted"> (by hand)</span>}
        </td>
        <td className="end">
          {submission && (
            <span className="cell-actions">
              <button className="secondary" aria-expanded={open} onClick={onToggle}>{open ? "Close" : "Grade"}</button>
              <button className="secondary" onClick={onOpen}>Open</button>
              <a className="button secondary" href={downloadHref}>Download</a>
            </span>
          )}
        </td>
      </tr>
      {open && submission && (
        <tr className="detail">
          <td colSpan={5}>
            <GradeForm submission={submission} autograded={autograded} outOf={outOf} hasNext={next !== null} onRegrade={onRegrade} onGrade={onGrade} />
          </td>
        </tr>
      )}
    </>
  );
}

// What the server grades out of when nothing else says (DEFAULT_POINTS in api/app/submissions.py)
const DEFAULT_POINTS = 100;

function GradeForm({ submission, autograded, outOf, hasNext, onRegrade, onGrade }: {
  submission: Submission;
  autograded: boolean;
  outOf: number | null;
  hasNext: boolean;
  onRegrade: () => Promise<boolean>;
  onGrade: (grade: Grade, andNext: boolean) => Promise<boolean>;
}) {
  const [score, setScore] = useState(submission.score === null ? "" : String(submission.score));
  const [feedback, setFeedback] = useState(submission.feedback);
  const [busy, setBusy] = useState(false);
  const field = useRef<HTMLInputElement | null>(null);
  // As the server works it out: the autograder's maximum, else the assignment's points, else 100.
  const maximum = submission.max_score ?? outOf ?? DEFAULT_POINTS;

  // Opened by Grade or by "Save and next": straight to the score, in view.
  useEffect(() => {
    field.current?.focus({ preventScroll: true });
    field.current?.closest("tr")?.scrollIntoView({ block: "nearest" });
  }, []);

  async function save(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    // Which button sent the form: "Save and next" goes on to the next submission to grade.
    const andNext = (e.nativeEvent as SubmitEvent).submitter?.getAttribute("data-next") === "yes";
    setBusy(true);
    // An untouched score is not sent, so the autograder's score stays the autograder's.
    const changed = score !== "" && Number(score) !== submission.score;
    await onGrade({ ...(changed ? { score: Number(score) } : {}), feedback }, andNext);
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
          Score
          <span className="score-field">
            <input ref={field} type="number" min="0" max={maximum} step="any" value={score} onChange={(e) => setScore(e.target.value)} />
            <span className="muted">out of {points(maximum)}</span>
          </span>
        </label>
        <label className="full">
          Comment for the student
          <textarea rows={2} maxLength={5000} value={feedback} onChange={(e) => setFeedback(e.target.value)} />
        </label>
        <div className="full row">
          {hasNext ? (
            <>
              <button type="submit" data-next="yes" disabled={busy}>{busy ? "Saving…" : "Save and next"}</button>
              <button type="submit" className="secondary" disabled={busy}>Save</button>
            </>
          ) : (
            <button type="submit" disabled={busy}>{busy ? "Saving…" : "Save grade"}</button>
          )}
          {autograded && (
            <button type="button" className="secondary" disabled={busy} onClick={onRegrade}>Run the autograder again</button>
          )}
        </div>
      </form>
    </div>
  );
}
