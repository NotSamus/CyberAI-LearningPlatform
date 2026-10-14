"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Award, Bot, Cpu, ExternalLink, NotebookPen, RotateCcw, Send, UserCheck, Users } from "lucide-react";
import DueDate from "@/components/DueDate";
import PageHeader from "@/components/PageHeader";
import Status, { Label, points, publishLabel } from "@/components/Status";
import SubmissionResult from "@/components/SubmissionResult";
import { courseName } from "@/components/learn/courses";
import { api, type Launch, type MyAssignmentDetail, type Submission } from "@/lib/api";
import { message } from "@/lib/errors";
import { useMe } from "@/lib/useMe";

type Phase = "idle" | "starting" | "open" | "error";

export default function OpenNotebook({ assignmentId }: { assignmentId: string }) {
  const me = useMe();
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
  // Filled in the notebook's bar, where it is the main thing to do; outlined on the page before,
  // where opening the notebook is.
  const submitButton = (main: boolean) => canSubmit && (
    <button className={main ? "" : "secondary"} onClick={submit} disabled={submitting}>
      <Send aria-hidden />{submitting ? "Submitting…" : submission ? "Submit again" : "Submit"}
    </button>
  );
  const environment = (gpu: boolean) => (
    <span className="fact"><Cpu aria-hidden />{gpu ? "GPU environment" : "Standard environment"}</span>
  );

  if (phase === "open" && launch && assignment) {
    return (
      <div className="workspace">
        <div className="workspace-bar">
          <Link href="/" className="back"><ArrowLeft aria-hidden />Home</Link>
          <strong>{assignment.title}</strong>
          {environment(launch.profile === "gpu")}
          <DueDate due_at={assignment.due_at} done={Boolean(submission)} />
          <span className="spacer" />
          {submission && (
            <button className="secondary" onClick={() => setShowResult((shown) => !shown)}>
              <Status assignment={assignment} /> {showResult ? "Hide" : "Details"}
            </button>
          )}
          {submitButton(true)}
          <button className="secondary" onClick={restart}><RotateCcw aria-hidden />Restart environment</button>
          <a href={launch.url} target="_blank" rel="noopener" className="button secondary"><ExternalLink aria-hidden />Open in a new tab</a>
        </div>
        {error && <p className="error bar-message" role="alert">{error}</p>}
        {showResult && submission && <div className="bar-message"><SubmissionResult submission={submission} /></div>}
        {/* No sandbox attribute: JupyterLab needs its own cookies, storage and WebSockets. */}
        <iframe src={launch.url} title="Jupyter notebook" allow="clipboard-read; clipboard-write; fullscreen" />
      </div>
    );
  }

  if (!assignment) {
    return (
      <main className="page assignment">
        <p className="crumbs"><Link href="/">Home</Link></p>
        {error ? <p className="error" role="alert">{error}</p> : <p className="muted">Loading…</p>}
      </main>
    );
  }

  const teacher = Boolean(me?.can_teach);
  return (
    <main className="page assignment">
      <PageHeader
        crumbs={[{ label: "Home", href: "/" }, { label: courseName(assignment.course) }]}
        title={assignment.title}
        status={
          <span className="badges">
            {!assignment.published && <Label standing={publishLabel(assignment)} />}
            {/* A teacher's own progress on an assignment means nothing: students get the status. */}
            {me && !teacher && <Status assignment={assignment} />}
          </span>
        }
        description={assignment.description || undefined}
        actions={teacher && (
          <Link href={`/teach/assignments/${assignment.id}`} className="button secondary"><Users aria-hidden />Progress and grades</Link>
        )}
      />
      <p className="meta">
        <DueDate due_at={assignment.due_at} done={Boolean(submission)} />
        {environment(assignment.requires_gpu)}
        {assignment.points !== null && <span className="fact"><Award aria-hidden />{points(assignment.points)} points</span>}
        {assignment.autograded
          ? <span className="fact"><Bot aria-hidden />Graded automatically</span>
          : <span className="fact"><UserCheck aria-hidden />Graded by your teacher</span>}
      </p>

      <section className="card start" aria-label="How it works">
        <ol className="steps">
          <li>
            <span className="number" aria-hidden>1</span>
            <div>
              <strong>Open the notebook</strong>
              <span className="muted">You get your own copy the first time you open it. Your work is saved in it and is there next time.</span>
            </div>
          </li>
          <li>
            <span className="number" aria-hidden>2</span>
            <div>
              <strong>Work in it, and save</strong>
              <span className="muted">Press Ctrl+S, or File &gt; Save Notebook: only what is saved is handed in.</span>
            </div>
          </li>
          <li>
            <span className="number" aria-hidden>3</span>
            <div>
              <strong>Submit</strong>
              <span className="muted">
                {assignment.autograded
                  ? "It is graded automatically within a minute or so, and you can submit again to improve your score."
                  : "Your teacher grades it. You can submit again, but that replaces your earlier submission and its grade."}
              </span>
            </div>
          </li>
        </ol>
        <div className="start-actions">
          <button onClick={open} disabled={phase === "starting"}>
            <NotebookPen aria-hidden />
            {phase === "starting" ? "Starting your environment (up to a minute)…" : assignment.opened_at ? "Continue working" : "Open the notebook"}
          </button>
          {submitButton(false)}
        </div>
      </section>

      {error && <p className="error" role="alert">{error}</p>}
      {submission && <SubmissionResult submission={submission} />}
    </main>
  );
}
