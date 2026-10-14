import { CircleAlert, Inbox, NotebookPen } from "lucide-react";
import Link from "next/link";
import Chip from "@/components/Chip";
import DueDate from "@/components/DueDate";
import ProgressBar from "@/components/ProgressBar";
import { Label, publishLabel } from "@/components/Status";
import type { ManagedAssignment } from "@/lib/api";

// What waits for the teacher in an assignment: submissions to grade by hand, and those the
// autograder could not run. Nothing when nothing waits.
export function Waiting({ assignment }: { assignment: ManagedAssignment }) {
  const counts = assignment.counts;
  if (!counts) return null;
  return (
    <>
      {counts.to_grade > 0 && <Chip tone="warn" icon={Inbox}>{counts.to_grade} to grade</Chip>}
      {counts.failed > 0 && <Chip tone="bad" icon={CircleAlert}>{counts.failed} could not be graded</Chip>}
    </>
  );
}

// Assignments as rows of one list (a course's page): each links to its gradebook.
export default function AssignmentRows({ assignments }: { assignments: ManagedAssignment[] }) {
  return (
    <ul className="list">
      {assignments.map((a) => (
        <li key={a.id}>
          <span className="tile"><NotebookPen aria-hidden /></span>
          <div className="grow">
            <div className="title-line">
              <Link className="title" href={`/teach/assignments/${a.id}`}>{a.title}</Link>
              <Label standing={publishLabel(a)} />
              <Waiting assignment={a} />
            </div>
            <p className="meta">
              <DueDate due_at={a.due_at} done />
              {a.counts && a.counts.given > 0 && (
                <ProgressBar value={a.counts.submitted} max={a.counts.given} label={`${a.counts.submitted} of ${a.counts.given} submitted`} />
              )}
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}
