"use client";
import { Bot, ClipboardList, Cpu, Download, Eye, PencilLine, Send, Settings, Trash2, Undo2, Users } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { use, useCallback, useEffect, useState } from "react";
import DueDate from "@/components/DueDate";
import Menu, { type MenuItem } from "@/components/Menu";
import PageHeader from "@/components/PageHeader";
import { Label, points, publishLabel } from "@/components/Status";
import Tabs from "@/components/Tabs";
import { AssignmentContext } from "@/components/teach/context";
import { givenToNobody, plural } from "@/components/teach/given";
import { api, type Progress } from "@/lib/api";
import { JSON_HEADERS, message } from "@/lib/errors";

// One assignment: its header above its two tabs, the Gradebook and its Settings. The header has Open
// as a student would, Publish while it is a draft, and under ⋯ Download grades, Unpublish and Delete.
// Both tabs get the assignment from here, from its gradebook request (there is no request for the
// assignment alone). Teachers and admins only: the server refuses everyone else.
export default function AssignmentLayout({ children, params }: { children: React.ReactNode; params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  // On the Settings tab, saving the form is the main thing to do: Publish is outlined there.
  const onSettings = usePathname().endsWith("/settings");
  const [progress, setProgress] = useState<Progress | null>(null);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const reload = useCallback(() => api<Progress>(`/teach/assignments/${id}/progress`).then(setProgress), [id]);
  useEffect(() => { reload().catch((e) => setLoadError(message(e))); }, [reload]);

  const crumbs = [{ label: "Assignments", href: "/teach/assignments" }];
  if (loadError) return <><PageHeader crumbs={crumbs} title="Assignment" /><p className="error" role="alert">{loadError}</p></>;
  if (!progress) return <><PageHeader crumbs={crumbs} title="Assignment" /><p className="muted">Loading…</p></>;

  const { assignment, students } = progress;
  const forWhom = assignment.for_everyone ? "For all students"
    : givenToNobody(assignment) ? "Given to nobody yet"
      : assignment.course ? `For ${assignment.course}${assignment.student_ids.length > 0 ? " and chosen students" : ""}`
        : "For chosen students";
  const waiting = students.filter((s) => s.submission && ["submitted", "failed"].includes(s.submission.status)).length;
  const outOf = assignment.points !== null ? `, ${points(assignment.points)} points` : "";

  async function publish(published: boolean) {
    setBusy(true);
    setError("");
    try {
      await api(`/teach/assignments/${id}`, { method: "PATCH", headers: JSON_HEADERS, body: JSON.stringify({ published }) });
      await reload();
    } catch (e) {
      setError(message(e));
    }
    setBusy(false);
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

  // What is rare or cannot be undone goes under ⋯. A plain link for the grades: the server sends a file.
  const more: MenuItem[] = [
    { label: "Download grades (CSV)", icon: Download, href: `/api/teach/assignments/${assignment.id}/grades.csv`, download: true },
    ...(assignment.published ? [{ label: "Unpublish", icon: Undo2, disabled: busy, onSelect: () => publish(false) }] : []),
    { label: "Delete", icon: Trash2, danger: true, onSelect: remove },
  ];

  return (
    <AssignmentContext.Provider value={{ progress, reload }}>
      <PageHeader
        crumbs={[...crumbs, { label: assignment.title }]}
        title={assignment.title}
        status={<Label standing={publishLabel(assignment)} />}
        meta={
          <>
            <span className="fact"><Users aria-hidden />{forWhom} ({plural(students.length, "student")})</span>
            <DueDate due_at={assignment.due_at} done />
            {assignment.autograded
              ? <span className="fact"><Bot aria-hidden />Autograded{outOf}</span>
              : <span className="fact"><PencilLine aria-hidden />Graded by hand{outOf}</span>}
            {assignment.requires_gpu && <span className="fact"><Cpu aria-hidden />GPU</span>}
          </>
        }
        actions={
          <>
            <Link href={`/assignments/${assignment.id}`} className="button secondary"><Eye aria-hidden />Open as a student would</Link>
            {!assignment.published && (
              <button className={onSettings ? "secondary" : ""} disabled={busy} onClick={() => publish(true)}><Send aria-hidden />Publish</button>
            )}
            <Menu label={`More for ${assignment.title}`} items={more} />
          </>
        }
        tabs={
          <Tabs
            kind="item" label="Views of this assignment"
            tabs={[
              { href: `/teach/assignments/${assignment.id}`, label: "Gradebook", icon: ClipboardList, exact: true, count: waiting },
              { href: `/teach/assignments/${assignment.id}/settings`, label: "Settings", icon: Settings },
            ]}
          />
        }
      />
      {error && <p className="error" role="alert">{error}</p>}
      {assignment.published && givenToNobody(assignment) && (
        <p className="error">
          Published, but given to nobody: no student can see it.{" "}
          <Link href={`/teach/assignments/${assignment.id}/settings`}>Choose who gets it</Link>.
        </p>
      )}
      {children}
    </AssignmentContext.Provider>
  );
}
