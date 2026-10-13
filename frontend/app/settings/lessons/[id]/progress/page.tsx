"use client";
import Link from "next/link";
import { use, useEffect, useState } from "react";
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

  if (error) return <><p><Link href="/settings/lessons">← Lessons</Link></p><p className="error" role="alert">{error}</p></>;
  if (!progress) return <p className="muted">Loading…</p>;

  const { lesson, questions, students } = progress;
  const opened = students.filter((s) => s.opened_at).length;
  const completed = students.filter((s) => s.completed_at).length;

  return (
    <>
      <p><Link href="/settings/lessons">← Lessons</Link></p>
      <h1>{lesson.title}</h1>
      <p className="badges">
        <span className={`badge ${lesson.published ? "live" : "draft"}`}>{lesson.published ? "Published" : "Draft"}</span>
        {lesson.changed && <span className="badge draft">Changes not published</span>}
        <span className="muted">
          {students.length === 0
            ? "Given to no students yet."
            : `${opened} of ${students.length} students opened it, ${completed} completed it.`}
        </span>
        <Link href={`/settings/lessons/${lesson.id}`}>Write</Link>
      </p>
      <p className="muted">
        Knowledge checks are practice: each allows three tries, and nothing here counts towards a grade.
      </p>

      <h2>Knowledge checks ({questions.length})</h2>
      {questions.length === 0 && <p className="muted">The published lesson has no knowledge checks.</p>}
      {questions.length > 0 && (
        <div className="table-scroll">
          <table>
            <thead>
              <tr><th>Question</th><th>Answered</th><th>Right at the first try</th><th>Right in the end</th><th>Out of tries</th></tr>
            </thead>
            <tbody>
              {questions.map((q, index) => (
                <tr key={q.id}>
                  <td className="wrap">{index + 1}. {q.question}</td>
                  <td>{q.answered} of {students.length}</td>
                  <td>{q.first_try}</td>
                  <td>{q.correct}</td>
                  <td>{q.missed}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2>Students ({students.length})</h2>
      {students.length > 0 && (
        <div className="table-scroll">
          <table>
            <thead>
              <tr><th>Name</th><th>Username</th><th>Opened</th><th>Completed</th><th>Checks answered</th><th>Right at the first try</th><th>Right in the end</th></tr>
            </thead>
            <tbody>
              {students.map((s) => (
                <tr key={s.id}>
                  <td>{s.name}</td>
                  <td className="muted">{s.username}</td>
                  <td>{s.opened_at ? formatWhen(s.opened_at) : <span className="muted">Not yet</span>}</td>
                  <td>{s.completed_at ? formatWhen(s.completed_at) : <span className="muted">Not yet</span>}</td>
                  <td>{s.answered} of {questions.length}</td>
                  <td>{s.first_try}</td>
                  <td>{s.correct}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
