"use client";
import { useCallback, useEffect, useState } from "react";
import { api, type Announcement, type Course } from "@/lib/api";
import { formatWhen } from "@/lib/dates";
import { JSON_HEADERS, message } from "@/lib/errors";

// Short messages that students see at the top of their home page.
export default function AnnouncementsSettings() {
  const [items, setItems] = useState<Announcement[] | null>(null);
  const [courses, setCourses] = useState<Course[]>([]);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [courseId, setCourseId] = useState("");       // "": for everyone
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    Promise.all([api<Announcement[]>("/teach/announcements"), api<Course[]>("/teach/courses")])
      .then(([announcements, classes]) => { setItems(announcements); setCourses(classes); })
      .catch((e) => setLoadError(message(e)));
  }, []);
  useEffect(load, [load]);

  async function post(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/teach/announcements", {
        method: "POST", headers: JSON_HEADERS,
        body: JSON.stringify({ title, body, course_id: courseId === "" ? null : Number(courseId) }),
      });
      setTitle("");
      setBody("");
      load();
    } catch (e) {
      setError(message(e));
    }
    setBusy(false);
  }

  async function remove(item: Announcement) {
    if (!window.confirm(`Delete the announcement "${item.title}"?`)) return;
    setError("");
    try {
      await api(`/teach/announcements/${item.id}`, { method: "DELETE" });
      load();
    } catch (e) {
      setError(message(e));
    }
  }

  if (loadError) return <><h1>Announcements</h1><p className="error" role="alert">{loadError}</p></>;
  if (!items) return <><h1>Announcements</h1><p className="muted">Loading…</p></>;

  return (
    <>
      <h1>Announcements</h1>
      <p className="muted">Students see the five newest announcements meant for them at the top of their home page.</p>

      <h2>New announcement</h2>
      <form className="form card" onSubmit={post}>
        <label>
          Title
          <input required maxLength={120} value={title} onChange={(e) => setTitle(e.target.value)} />
        </label>
        <label>
          For
          <select value={courseId} onChange={(e) => setCourseId(e.target.value)}>
            <option value="">Everyone</option>
            {courses.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
        <label className="full">
          Message
          <textarea rows={3} maxLength={5000} value={body} onChange={(e) => setBody(e.target.value)} />
        </label>
        <div className="full">
          <button type="submit" disabled={busy}>{busy ? "Posting…" : "Post"}</button>
        </div>
      </form>
      {error && <p className="error" role="alert">{error}</p>}

      <h2>Posted ({items.length})</h2>
      {items.length === 0 && <p className="muted">Nothing posted yet.</p>}
      <ul className="assignments">
        {items.map((item) => (
          <li key={item.id} className="card">
            <div className="row">
              <h3>{item.title}</h3>
              <span className="badge">{item.course ?? "Everyone"}</span>
              <span className="muted">{formatWhen(item.created_at)}</span>
              <span className="spacer" />
              <button className="secondary danger" onClick={() => remove(item)}>Delete</button>
            </div>
            {item.body && <p className="description">{item.body}</p>}
          </li>
        ))}
      </ul>
    </>
  );
}
