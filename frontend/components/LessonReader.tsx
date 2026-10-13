"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import LessonBlocks from "@/components/LessonBlocks";
import { api } from "@/lib/api";
import { formatWhen } from "@/lib/dates";
import { message } from "@/lib/errors";
import type { CheckState, LessonPage } from "@/lib/lessons";

// The page a lesson is read on. Teachers get their working copy here, to try it out.
export default function LessonReader({ lessonId }: { lessonId: string }) {
  const [lesson, setLesson] = useState<LessonPage | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    return api<LessonPage>(`/lessons/${lessonId}`).then(setLesson).catch((e) => setError(message(e)));
  }, [lessonId]);
  useEffect(() => { load(); }, [load]);

  function answered(blockId: string, state: CheckState) {
    setLesson((l) => l && {
      ...l,
      blocks: l.blocks.map((b) => (b.id === blockId && (b.type === "multiple_choice" || b.type === "short_answer") ? { ...b, state } : b)),
    });
  }

  async function act(path: string) {
    setBusy(true);
    setError("");
    try {
      await api(`/lessons/${lessonId}/${path}`, { method: "POST" });
      setLesson(null);      // read it again from the start: the questions forget what was typed
      await load();
    } catch (e) {
      setError(message(e));
    }
    setBusy(false);
  }

  if (!lesson) {
    return (
      <main className="page lesson">
        <p><Link href="/">← Home</Link></p>
        {error ? <p className="error" role="alert">{error}</p> : <p className="muted">Loading…</p>}
      </main>
    );
  }

  const checks = lesson.blocks.filter((b) => b.type === "multiple_choice" || b.type === "short_answer");
  const done = checks.filter((b) => b.state?.closed).length;

  return (
    <main className="page lesson">
      <p><Link href="/">← Home</Link></p>
      {lesson.preview && (
        <p className="notice row">
          <span>
            This is your working copy, as a student would see it.
            {!lesson.published && " The lesson is a draft: students cannot see it yet."}
          </span>
          <span className="spacer" />
          <Link href={`/settings/lessons/${lesson.id}`} className="button secondary">Back to writing</Link>
          <button className="secondary" disabled={busy} onClick={() => act("start-over")}>Start over</button>
        </p>
      )}
      <h1>{lesson.title}</h1>
      <p className="badges">
        {lesson.course && <span className="badge">{lesson.course}</span>}
        {checks.length > 0 && <span className="badge">{checks.length === 1 ? "1 knowledge check" : `${checks.length} knowledge checks`}</span>}
        {lesson.completed_at && <span className="badge live">Completed</span>}
      </p>

      <LessonBlocks lessonId={lesson.id} blocks={lesson.blocks} onAnswered={answered} />

      <footer className="lesson-end">
        {error && <p className="error" role="alert">{error}</p>}
        {lesson.completed_at ? (
          <p><strong>Completed</strong> <span className="muted">on {formatWhen(lesson.completed_at)}</span></p>
        ) : (
          <p className="row">
            <button disabled={busy || done < checks.length} onClick={() => act("complete")}>Mark as complete</button>
            {checks.length > 0 && <span className="muted">{done} of {checks.length} knowledge checks done</span>}
          </p>
        )}
        {lesson.next && <p><Link href={`/lessons/${lesson.next.id}`}>Next lesson: {lesson.next.title} →</Link></p>}
      </footer>
    </main>
  );
}
