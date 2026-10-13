"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import DueDate from "@/components/DueDate";
import Status from "@/components/Status";
import SubmissionResult from "@/components/SubmissionResult";
import { api, type Launch, type MyAssignmentDetail, type Submission } from "@/lib/api";
import { message } from "@/lib/errors";

type Phase = "idle" | "starting" | "open" | "error";

export default function OpenNotebook({ assignmentId }: { assignmentId: string }) {
  const [assignment, setAssignment] = useState<MyAssignmentDetail | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [launch, setLaunch] = useState<Launch | null>(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [showResult, setShowResult] = useState(false);

  const load = useCallback(() => {
    return api<MyAssignmentDetail>(`/assignments/${assignmentId}`).then(setAssignment);
  }, [assignmentId]);

  useEffect(() => {
    load().catch((e) => { setError(message(e)); setPhase("error"); });
  }, [load]);

  // While the autograder is working on the submission, ask again every two seconds.
  const status = assignment?.submission?.status;
  useEffect(() => {
    if (status !== "queued" && status !== "grading") return;
    const timer = setInterval(() => { load().catch(() => {}); }, 2000);
    return () => clearInterval(timer);
  }, [status, load]);

  async function open() {
    setPhase("starting");
    setError("");
    try {
      setLaunch(await api<Launch>(`/assignments/${assignmentId}/launch`, { method: "POST" }));
      setPhase("open");
      load().catch(() => {});
    } catch (e) {
      setError(message(e));
      setPhase("error");
    }
  }

  async function restart() {
    setPhase("starting");
    setLaunch(null);
    try {
      await api(`/assignments/${assignmentId}/stop`, { method: "POST" });
    } catch { /* not running is fine */ }
    await open();
  }

  async function submit() {
    // The server takes the notebook as it is saved in the student's files: what is on screen but
    // not saved yet would be left out.
    const sure = window.confirm(
      "Submit your notebook as it is saved right now?\n\n" +
      "Save it first (Ctrl+S, or File > Save Notebook). You can submit again later: the newest submission is the one that counts.",
    );
    if (!sure) return;
    setSubmitting(true);
    setError("");
    try {
      const submission = await api<Submission>(`/assignments/${assignmentId}/submit`, { method: "POST" });
      setAssignment((a) => (a ? { ...a, submission } : a));
      setShowResult(true);
    } catch (e) {
      setError(message(e));
    }
    setSubmitting(false);
  }

  const submission = assignment?.submission ?? null;
  const canSubmit = assignment?.published && assignment.opened_at;
  const submitButton = canSubmit && (
    <button onClick={submit} disabled={submitting}>
      {submitting ? "Submitting…" : submission ? "Submit again" : "Submit"}
    </button>
  );

  if (phase === "open" && launch && assignment) {
    return (
      <div className="workspace">
        <div className="workspace-bar">
          <Link href="/">← Home</Link>
          <strong>{assignment.title}</strong>
          <span className={`badge ${launch.profile === "gpu" ? "gpu" : ""}`}>
            {launch.profile === "gpu" ? "GPU environment" : "Standard environment"}
          </span>
          <DueDate due_at={assignment.due_at} done={Boolean(submission)} />
          <span className="spacer" />
          {submission && (
            <button className="secondary" onClick={() => setShowResult((shown) => !shown)}>
              <Status assignment={assignment} /> {showResult ? "Hide" : "Details"}
            </button>
          )}
          {submitButton}
          <button className="secondary" onClick={restart}>Restart environment</button>
          <a href={launch.url} target="_blank" rel="noopener">Open in a new tab</a>
        </div>
        {error && <p className="error bar-message" role="alert">{error}</p>}
        {showResult && submission && <div className="bar-message"><SubmissionResult submission={submission} /></div>}
        {/* No sandbox attribute: JupyterLab needs its own cookies, storage and WebSockets. */}
        <iframe src={launch.url} title="Jupyter notebook" allow="clipboard-read; clipboard-write; fullscreen" />
      </div>
    );
  }

  return (
    <main className="page">
      <p><Link href="/">← Home</Link></p>
      <h1>{assignment?.title ?? "Assignment"}</h1>
      {assignment && (
        <p className="badges">
          {!assignment.published && <span className="badge draft">Draft: students cannot see this yet</span>}
          {assignment.course && <span className="badge">{assignment.course}</span>}
          <span className={`badge ${assignment.requires_gpu ? "gpu" : ""}`}>
            {assignment.requires_gpu ? "GPU environment" : "Standard environment"}
          </span>
          <DueDate due_at={assignment.due_at} done={Boolean(submission)} />
          {assignment.points !== null && <span className="badge">{assignment.points} points</span>}
        </p>
      )}
      {assignment?.description && <p className="description">{assignment.description}</p>}
      {assignment && (
        <p className="muted">
          You get your own copy of the notebook the first time you open it. Your work is saved in it
          and is there next time. When you are done, save the notebook and press Submit.
          {assignment.autograded && " It is graded automatically within a minute or so, and you can submit again to improve your score."}
        </p>
      )}
      {assignment && (
        <p className="row">
          <button onClick={open} disabled={phase === "starting"}>
            {phase === "starting" ? "Starting your environment (up to a minute)…" : "Open Notebook"}
          </button>
          {submitButton}
        </p>
      )}
      {error && <p className="error" role="alert">{error}</p>}
      {submission && <SubmissionResult submission={submission} />}
    </main>
  );
}
