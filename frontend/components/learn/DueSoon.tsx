import Link from "next/link";
import { GraduationCap } from "lucide-react";
import DueDate from "@/components/DueDate";
import Status, { Label, publishLabel } from "@/components/Status";
import type { MyAssignment } from "@/lib/api";
import { hoursUntil, isPast } from "@/lib/dates";

const TWO_WEEKS = 14 * 24;      // hours

// What is due: for a student, what is past its due date or due in the next two weeks and not
// handed in yet, leaving out what Up next shows above it (`shown`: those assignments' ids). For a
// teacher (`asTeacher`), what is due in the next two weeks, drafts marked.
export default function DueSoon({ assignments, asTeacher, shown = [] }: { assignments: MyAssignment[]; asTeacher: boolean; shown?: number[] }) {
  const due = assignments
    .filter((a) => asTeacher || (!a.submission && !shown.includes(a.id)))
    .filter((a) => a.due_at !== null && (isPast(a.due_at) ? !asTeacher : hoursUntil(a.due_at) <= TWO_WEEKS))
    .sort((a, b) => new Date(a.due_at!).getTime() - new Date(b.due_at!).getTime());

  return (
    <section aria-labelledby="due-soon">
      <h2 id="due-soon">Due soon</h2>
      {due.length === 0 ? (
        <p className="muted">{asTeacher || shown.length === 0 ? "Nothing is due in the next two weeks." : "Nothing else is due in the next two weeks."}</p>
      ) : (
        <ul className="list compact">
          {due.map((a) => (
            <li key={a.id}>
              <div className="grow">
                <Link href={`/assignments/${a.id}`} className="title">{a.title}</Link>
                <p className="meta">
                  <DueDate due_at={a.due_at} done={Boolean(a.submission)} />
                  {a.course && <span className="fact"><GraduationCap aria-hidden />{a.course}</span>}
                </p>
              </div>
              <span className="badges">
                {asTeacher ? !a.published && <Label standing={publishLabel(a)} /> : <Status assignment={a} />}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
