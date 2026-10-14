"use client";
import { Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import LessonList, { type LessonRow } from "@/components/LessonList";
import { api } from "@/lib/api";
import { JSON_HEADERS, message } from "@/lib/errors";
import type { ManagedLesson, Topic } from "@/lib/lessons";

// The list is kept from one lesson's editor to the next, so that it is there at once when switching.
let known: ManagedLesson[] | null = null;
// The last save of the lesson that was just left: the list is asked for once that has arrived.
let leaving: Promise<unknown> = Promise.resolve();

export function leftLesson(saving: Promise<unknown>) {
  leaving = saving;
}

function row(lesson: ManagedLesson): LessonRow {
  const here = { id: lesson.id, title: lesson.title, href: `/teach/lessons/${lesson.id}` };
  const blocks = lesson.blocks_count === 1 ? "1 block" : `${lesson.blocks_count} blocks`;
  if (!lesson.published) return { ...here, dot: "draft", note: `Draft · ${blocks}` };
  return lesson.changed ? { ...here, dot: "changed", note: "Changes not published" } : { ...here, dot: "live", note: "Published" };
}

// Beside the lesson editor: every lesson, in the order students get them, with where each one
// stands. Under the lesson being written (`live`: as it is on screen right now), its topics.
export default function LessonRail({ currentId, live, topics }: { currentId: number; live: ManagedLesson | null; topics: Topic[] }) {
  const router = useRouter();
  const [lessons, setLessons] = useState(known);
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    await leaving.catch(() => {});
    try {
      known = await api<ManagedLesson[]>("/teach/lessons");
      setLessons(known);
    } catch (e) {
      setError(message(e));
    }
  }, []);

  // Now, and whenever this window is come back to: another teacher may have been writing.
  useEffect(() => {
    load();
    window.addEventListener("focus", load);
    return () => window.removeEventListener("focus", load);
  }, [load]);

  const shown = (lessons ?? []).map((lesson) => (live && lesson.id === live.id ? live : lesson));
  useEffect(() => {
    if (known && live) known = known.map((lesson) => (lesson.id === live.id ? live : lesson));
  }, [live]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const lesson = await api<ManagedLesson>("/teach/lessons", { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ title }) });
      known = [...(known ?? []), lesson];
      setTitle("");
      router.push(`/teach/lessons/${lesson.id}`);      // straight to writing it
    } catch (e) {
      setError(message(e));
    }
    setBusy(false);
  }

  return (
    <aside className="rail" aria-label="Lessons">
      <p className="check-label">Lessons{lessons && ` (${lessons.length})`}</p>
      {!lessons && !error && <p className="muted">Loading…</p>}
      <LessonList rows={shown.map(row)} currentId={currentId} topics={topics} />
      <form onSubmit={create}>
        <input
          required maxLength={120} placeholder="New lesson…" aria-label="Title of a new lesson" disabled={busy}
          value={title} onChange={(e) => setTitle(e.target.value)}
        />
        <button type="submit" className="icon" title="Create this lesson and write it" aria-label="Create this lesson" disabled={busy}><Plus aria-hidden /></button>
      </form>
      {error && <p className="error" role="alert">{error}</p>}
    </aside>
  );
}
