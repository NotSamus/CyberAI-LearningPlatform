import { points, submissionLabel } from "@/components/Status";
import type { Submission } from "@/lib/api";
import { formatWhen } from "@/lib/dates";

// What a student sees of their own submission: when, the score per question, the public tests'
// report, and the teacher's comment. The hidden tests' details are not sent to students at all.
export default function SubmissionResult({ submission }: { submission: Submission }) {
  const { text, tone } = submissionLabel(submission);
  const waiting = submission.status === "queued" || submission.status === "grading";
  return (
    <section className="card result" aria-live="polite">
      <p className="badges">
        <span className={`badge ${tone}`}>{text}</span>
        {submission.late && <span className="badge late">Late</span>}
        <span className="muted">
          Submitted {formatWhen(submission.submitted_at)}
          {submission.attempt > 1 && ` (submission ${submission.attempt})`}
        </span>
      </p>
      {waiting && <p className="muted">The autograder is running your notebook. This usually takes under a minute.</p>}
      {submission.status === "submitted" && <p className="muted">Your teacher will grade this one.</p>}
      {submission.status === "failed" && (
        <p className="error">
          The autograder could not run your notebook. Check that it runs from top to bottom (Kernel &gt; Restart
          Kernel and Run All Cells), save it, and submit again. Your teacher can see what went wrong.
        </p>
      )}
      {submission.questions.length > 0 && (
        <table className="compact">
          <thead><tr><th>Question</th><th>Score</th></tr></thead>
          <tbody>
            {submission.questions.map((q) => (
              <tr key={q.name}><td>{q.name}</td><td>{points(q.score)} / {points(q.max_score)}</td></tr>
            ))}
          </tbody>
        </table>
      )}
      {submission.public_output && (
        <details>
          <summary>What the public tests reported</summary>
          <pre>{submission.public_output}</pre>
        </details>
      )}
      {submission.feedback && (
        <>
          <h3>From your teacher</h3>
          <p className="description">{submission.feedback}</p>
        </>
      )}
    </section>
  );
}
