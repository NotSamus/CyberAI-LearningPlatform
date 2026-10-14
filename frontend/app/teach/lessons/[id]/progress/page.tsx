"use client";
import { Eye, Users } from "lucide-react";
import Link from "next/link";
import { use, useEffect, useState } from "react";
import EmptyState from "@/components/EmptyState";
import PageHeader from "@/components/PageHeader";
import ProgressBar from "@/components/ProgressBar";
import { Label, publishLabel } from "@/components/Status";
import LessonTabs from "@/components/teach/LessonTabs";
import { api } from "@/lib/api";
import { formatWhen } from "@/lib/dates";
import { message } from "@/lib/errors";
import type { LessonProgress } from "@/lib/lessons";

// How a lesson went: who opened and completed it, and which knowledge checks were hard.
export default function LessonProgressPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [progress, setProgress] = useState<LessonProgress | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<LessonProgress>(`/teach/lessons/${id}/progress`).then(setProgress).catch((e) => setError(message(e)));
  }, [id]);

  const crumbs = [{ label: "Lessons", href: "/teach/lessons" }];
  if (error) return <><PageHeader crumbs={crumbs} title="Progress" tabs={<LessonTabs id={id} />} /><p className="error" role="alert">{error}</p></>;
  if (!progress) return <><PageHeader crumbs={crumbs} title="Progress" tabs={<LessonTabs id={id} />} /><p className="muted">Loading…</p></>;

  const { lesson, questions, students } = progress;
  const opened = students.filter((s) => s.opened_at).length;
  const completed = students.filter((s) => s.completed_at).length;

  return (
    <>
      <PageHeader
        crumbs={[...crumbs, { label: lesson.title }]}
        title={lesson.title}
        status={<Label standing={publishLabel(lesson)} />}
        description={
          students.length === 0
            ? "Given to no students yet."
            : <span className="meta">
              <ProgressBar value={completed} max={students.length} label={`${completed} of ${students.length} completed it`} />
              <span>{opened} opened it</span>
            </span>
        }
        actions={<Link href={`/lessons/${lesson.id}`} className="button secondary"><Eye aria-hidden />Open as a student would</Link>}
        tabs={<LessonTabs id={id} />}
      />
      <p className="muted hint">Knowledge checks are practice: each allows three tries, and nothing here counts towards a grade.</p>

      <h2>Knowledge checks ({questions.length})</h2>
      {questions.length === 0 && <p className="muted">The published lesson has no knowledge checks.</p>}
      {questions.length > 0 && (
        <div className="table-scroll">
          <table>
            <thead>
              <tr><th>Question</th><th className="num">Answered</th><th className="num">Right at the first try</th><th className="num">Right in the end</th><th className="num">Out of tries</th></tr>
            </thead>
            <tbody>
              {questions.map((q, index) => (
                <tr key={q.id}>
                  <td className="wrap">{index + 1}. {q.question}</td>
                  <td className="num">{q.answered} of {students.length}</td>
                  <td className="num">{q.first_try}</td>
                  <td className="num">{q.correct}</td>
                  <td className="num">{q.missed}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2>Students ({students.length})</h2>
      {students.length === 0 && (
        <EmptyState icon={Users} title="No students yet" action={<Link href={`/teach/lessons/${lesson.id}`} className="button secondary">Choose who it is for</Link>}>
          This lesson is not given to any student. Choose a course, or all students, while writing it.
        </EmptyState>
      )}
      {students.length > 0 && (
        <div className="table-scroll">
          <table>
            <thead>
              <tr><th>Student</th><th>Opened</th><th>Completed</th><th className="num">Checks answered</th><th className="num">Right at the first try</th><th className="num">Right in the end</th></tr>
            </thead>
            <tbody>
              {students.map((s) => (
                <tr key={s.id}>
                  <td><span className="person"><strong>{s.name}</strong><span className="muted">{s.username}</span></span></td>
                  <td>{s.opened_at ? formatWhen(s.opened_at) : <span className="muted">Not yet</span>}</td>
                  <td>{s.completed_at ? formatWhen(s.completed_at) : <span className="muted">Not yet</span>}</td>
                  <td className="num">{s.answered} of {questions.length}</td>
                  <td className="num">{s.first_try}</td>
                  <td className="num">{s.correct}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
