import { CircleCheck, CircleX, Clock, MessageSquareText, Send } from "lucide-react";
import Chip from "@/components/Chip";
import { Label, points, submissionLabel } from "@/components/Status";
import type { Submission } from "@/lib/api";
import { formatWhen } from "@/lib/dates";

// What a student sees of their own submission: when, the score per question, whether each
// question's public tests passed, and the teacher's comment. What the tests reported is not sent
// to students at all (it could carry what their code read from the hidden tests): they see it in
// their notebook, where grader.check runs the same public tests.
export default function SubmissionResult({ submission }: { submission: Submission }) {
  const waiting = submission.status === "queued" || submission.status === "grading";
  const tested = new Map(submission.public_tests.map((t) => [t.name, t.passed]));
  return (
    <section className="card result" aria-live="polite">
      <p className="badges">
        <Label standing={submissionLabel(submission)} />
        {submission.late && <Chip tone="bad" icon={Clock}>Late</Chip>}
        <span className="fact">
          <Send aria-hidden />
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
          <thead>
            <tr><th>Question</th>{tested.size > 0 && <th>Public tests</th>}<th className="num">Score</th></tr>
          </thead>
          <tbody>
            {submission.questions.map((q) => (
              <tr key={q.name}>
                <td>{q.name}</td>
                {tested.size > 0 && (
                  <td>
                    {!tested.has(q.name) ? <span className="muted">—</span>
                      : tested.get(q.name) ? <Chip tone="good" icon={CircleCheck}>Passed</Chip>
                      : <Chip tone="bad" icon={CircleX}>Failed</Chip>}
                  </td>
                )}
                <td className="num">{points(q.score)} / {points(q.max_score)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {tested.size > 0 && (
        <p className="muted">
          To see what a public test reported, run its check in your notebook, for
          example <code>grader.check(&quot;{submission.public_tests[0].name}&quot;)</code>.
        </p>
      )}
      {submission.feedback && (
        <>
          <h3><MessageSquareText aria-hidden />From your teacher</h3>
          <p className="description">{submission.feedback}</p>
        </>
      )}
    </section>
  );
}
