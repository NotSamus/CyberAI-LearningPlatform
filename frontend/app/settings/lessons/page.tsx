"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, type Course } from "@/lib/api";
import { JSON_HEADERS, message } from "@/lib/errors";
import type { ManagedLesson } from "@/lib/lessons";

// Lessons are written here, in the platform: text, code, pictures, videos and knowledge checks.
export default function LessonsSettings() {
  const router = useRouter();
  const [items, setItems] = useState<ManagedLesson[] | null>(null);
  const [courses, setCourses] = useState<Course[]>([]);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    Promise.all([api<ManagedLesson[]>("/teach/lessons"), api<Course[]>("/teach/courses")])
      .then(([lessons, classes]) => { setItems(lessons); setCourses(classes); })
      .catch((e) => setLoadError(message(e)));
  }, []);
  useEffect(load, [load]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const lesson = await api<ManagedLesson>("/teach/lessons", { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ title }) });
      router.push(`/settings/lessons/${lesson.id}`);      // straight to writing
    } catch (e) {
      setError(message(e));
      setBusy(false);
    }
  }

  async function act(request: () => Promise<unknown>) {
    setError("");
    try {
      await request();
      load();
    } catch (e) {
      setError(message(e));
    }
  }

  function move(index: number, by: -1 | 1) {
    const ids = (items ?? []).map((lesson) => lesson.id);
    [ids[index], ids[index + by]] = [ids[index + by], ids[index]];
    act(() => api("/teach/lessons/order", { method: "PUT", headers: JSON_HEADERS, body: JSON.stringify({ ids }) }));
  }

  function remove(lesson: ManagedLesson) {
    const sure = window.confirm(`Delete "${lesson.title}"? Its pictures and what students answered in it are deleted too.`);
    if (sure) act(() => api(`/teach/lessons/${lesson.id}`, { method: "DELETE" }));
  }

  function givenTo(lesson: ManagedLesson): string {
    if (lesson.for_everyone) return "For all students";
    const course = courses.find((c) => c.id === lesson.course_id);
    return course ? `For ${course.name} (${course.student_ids.length} students)` : "Given to nobody yet";
  }

  if (loadError) return <><h1>Lessons</h1><p className="error" role="alert">{loadError}</p></>;
  if (!items) return <><h1>Lessons</h1><p className="muted">Loading…</p></>;

  return (
    <>
      <h1>Lessons</h1>
      <p className="muted">
        Write lessons here, block by block: text, code, pictures, videos, and knowledge checks that are
        checked as students answer. Students see a lesson once it is published and given to them.
      </p>

      <h2>New lesson</h2>
      <form className="row" onSubmit={create}>
        <input required maxLength={120} placeholder="Title" aria-label="Title of the new lesson" value={title} onChange={(e) => setTitle(e.target.value)} />
        <button type="submit" disabled={busy}>{busy ? "Creating…" : "Start writing"}</button>
      </form>
      {error && <p className="error" role="alert">{error}</p>}

      <h2>Written ({items.length})</h2>
      {items.length === 0 && <p className="muted">No lessons yet.</p>}
      {items.length > 1 && <p className="muted">Students see their lessons in this order. Use the arrows to change it.</p>}
      <ul className="assignments">
        {items.map((lesson, index) => (
          <li key={lesson.id} className="card">
            <div className="row">
              <h3><Link href={`/settings/lessons/${lesson.id}`}>{lesson.title}</Link></h3>
              <span className={`badge ${lesson.published ? "live" : "draft"}`}>{lesson.published ? "Published" : "Draft"}</span>
              {lesson.changed && <span className="badge draft">Changes not published</span>}
              <span className="spacer" />
              <button className="icon" title="Move up" aria-label={`Move ${lesson.title} up`} disabled={index === 0} onClick={() => move(index, -1)}>↑</button>
              <button className="icon" title="Move down" aria-label={`Move ${lesson.title} down`} disabled={index === items.length - 1} onClick={() => move(index, 1)}>↓</button>
              <Link href={`/settings/lessons/${lesson.id}`} className="button secondary">Write</Link>
              <button className="secondary danger" onClick={() => remove(lesson)}>Delete</button>
            </div>
            {lesson.summary && <p className="muted">{lesson.summary}</p>}
            <p className="muted facts">
              <span>{givenTo(lesson)}</span>
              <span>{lesson.blocks_count === 1 ? "1 block" : `${lesson.blocks_count} blocks`}</span>
              {lesson.published && <span>{lesson.questions === 1 ? "1 knowledge check" : `${lesson.questions} knowledge checks`}</span>}
            </p>
            <p className="facts">
              <Link href={`/settings/lessons/${lesson.id}/progress`}>Who has done it</Link>
              <Link href={`/lessons/${lesson.id}`}>Open as a student would</Link>
            </p>
            {lesson.published && !lesson.for_everyone && lesson.course_id === null && (
              <p className="error">Published, but given to nobody: no student can see it. Open it and choose who it is for.</p>
            )}
          </li>
        ))}
      </ul>
    </>
  );
}
