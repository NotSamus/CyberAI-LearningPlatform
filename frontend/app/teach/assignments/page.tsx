"use client";
import { Bot, ClipboardList, Cpu, Eye, NotebookPen, PencilLine, Send, Settings, Trash2, Undo2, Upload, Users } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import DueDate from "@/components/DueDate";
import EmptyState from "@/components/EmptyState";
import Menu from "@/components/Menu";
import PageHeader from "@/components/PageHeader";
import { Label, publishLabel, points } from "@/components/Status";
import { Waiting } from "@/components/teach/AssignmentRows";
import { GIVEN_TO_NOBODY, assignmentFor, givenToNobody } from "@/components/teach/given";
import { api, type Course, type ManagedAssignment, type Student } from "@/lib/api";
import { dueText } from "@/lib/dates";
import { JSON_HEADERS, message } from "@/lib/errors";

// Every notebook assignment, in a table: who it is for, when it is due, and how far its students
// have got, with a chip by the title only when something is not right yet (a draft, or published to
// nobody). Each opens on its gradebook; uploading is on a page of its own. On an iPad, who it is for
// and when it is due go under the title instead of into columns (app/styles/teach.css).
export default function AssignmentsPage() {
  // The server decides who may teach: /api/teach answers 403 for students.
  const [items, setItems] = useState<ManagedAssignment[] | null>(null);
  const [students, setStudents] = useState<Student[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(() => {
    Promise.all([
      api<ManagedAssignment[]>("/teach/assignments"), api<Student[]>("/teach/students"), api<Course[]>("/teach/courses"),
    ])
      .then(([assignments, people, classes]) => { setItems(assignments); setStudents(people); setCourses(classes); })
      .catch((e) => setLoadError(message(e)));
  }, []);
  useEffect(load, [load]);

  async function act(request: () => Promise<unknown>) {
    setError("");
    try {
      await request();
    } catch (e) {
      setError(message(e));
    }
    load();
  }

  function publish(a: ManagedAssignment, published: boolean) {
    act(() => api(`/teach/assignments/${a.id}`, { method: "PATCH", headers: JSON_HEADERS, body: JSON.stringify({ published }) }));
  }

  function remove(a: ManagedAssignment) {
    const sure = window.confirm(
      `Delete "${a.title}"? Students will no longer see it, and its submissions and grades are deleted too. ` +
      "Copies students already opened stay in their own notebook folders.",
    );
    if (sure) act(() => api(`/teach/assignments/${a.id}`, { method: "DELETE" }));
  }

  const upload = <Link href="/teach/assignments/new" className="button"><Upload aria-hidden />Upload notebook</Link>;
  const header = (
    <PageHeader
      title="Assignments"
      description="Upload a notebook, choose who gets it, then publish it. Each student gets their own copy the first time they open it, and submits it when done."
      actions={items && items.length > 0 ? upload : undefined}      // with none yet, the empty list below offers it
    />
  );

  if (loadError) return <>{header}<p className="error" role="alert">{loadError}</p></>;
  if (!items) return <>{header}<p className="muted">Loading…</p></>;

  return (
    <>
      {header}
      {error && <p className="error" role="alert">{error}</p>}
      {items.length === 0 ? (
        <EmptyState icon={NotebookPen} title="No assignments yet" action={upload}>
          Upload a Jupyter notebook. A notebook written for Otter-Grader is graded automatically; any other is graded by you.
        </EmptyState>
      ) : (
        <div className="table-box">
          <table>
            <thead>
              <tr>
                <th>Title</th><th className="wide">For</th><th className="wide">Due</th>
                <th className="num">Submitted</th><th className="num">To grade</th><th><span className="visually-hidden">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {items.map((a) => {
                const nobody = givenToNobody(a);
                const forWhom = assignmentFor(a, students, courses);
                const counts = a.counts;
                return (
                  <tr key={a.id}>
                    <td className="wrap">
                      <span className="title-line">
                        <Link className="title" href={`/teach/assignments/${a.id}`}>{a.title}</Link>
                        {!a.published && <Label standing={publishLabel(a)} />}
                        {a.published && nobody && <Label standing={GIVEN_TO_NOBODY} />}
                      </span>
                      <span className="meta">
                        <span className="fact">
                          {a.autograded ? <Bot aria-hidden /> : <PencilLine aria-hidden />}
                          {a.autograded ? "Autograded" : "Graded by hand"}{a.points !== null && `, ${points(a.points)} points`}
                        </span>
                        {a.requires_gpu && <span className="fact"><Cpu aria-hidden />GPU</span>}
                        <span className="narrow">
                          <span className="fact"><Users aria-hidden />{forWhom}</span>
                          <DueDate due_at={a.due_at} done />
                        </span>
                      </span>
                    </td>
                    <td className="wrap wide">{nobody ? <span className="muted">{forWhom}</span> : forWhom}</td>
                    <td className="wide">{a.due_at ? dueText(a.due_at) : <span className="muted">—</span>}</td>
                    <td className="num">{counts ? `${counts.submitted} / ${counts.given}` : "—"}</td>
                    <td className="num">
                      {counts && counts.to_grade + counts.failed > 0
                        ? <span className="waiting"><Waiting assignment={a} /></span>
                        : <span className="muted">—</span>}
                    </td>
                    <td className="more">
                      <Menu
                        label={`More for ${a.title}`}
                        items={[
                          { label: "Gradebook", icon: ClipboardList, href: `/teach/assignments/${a.id}` },
                          { label: "Settings", icon: Settings, href: `/teach/assignments/${a.id}/settings` },
                          { label: "Open as a student would", icon: Eye, href: `/assignments/${a.id}` },
                          a.published
                            ? { label: "Unpublish", icon: Undo2, onSelect: () => publish(a, false) }
                            : { label: "Publish", icon: Send, onSelect: () => publish(a, true) },
                          { label: "Delete", icon: Trash2, danger: true, onSelect: () => remove(a) },
                        ]}
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
