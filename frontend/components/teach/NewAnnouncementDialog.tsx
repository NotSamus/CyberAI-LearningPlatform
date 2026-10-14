"use client";
import { useEffect, useState } from "react";
import Dialog from "@/components/Dialog";
import { api, type Course } from "@/lib/api";
import { JSON_HEADERS, message } from "@/lib/errors";

// "New announcement": a title, who it is for, and the message. On Teach > Announcements and on a
// course's Announcements tab, where "For" starts at that course.
export default function NewAnnouncementDialog({ open, courses, preset, onClose, onPosted }: {
  open: boolean;
  courses: Course[];
  preset: string;           // the course it starts at, as an id, or "" for everyone
  onClose: () => void;
  onPosted: () => void;
}) {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [courseId, setCourseId] = useState("");       // "": for everyone
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) { setCourseId(preset); setError(""); }
  }, [open, preset]);

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
      onPosted();
    } catch (e) {
      setError(message(e));
    }
    setBusy(false);
  }

  return (
    <Dialog open={open} title="New announcement" onClose={onClose}>
      <form onSubmit={post}>
        <div className="dialog-body">
          <label>
            Title
            <input required autoFocus maxLength={120} value={title} onChange={(e) => setTitle(e.target.value)} />
          </label>
          <label>
            For
            <select value={courseId} onChange={(e) => setCourseId(e.target.value)}>
              <option value="">Everyone</option>
              {courses.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <label>
            Message
            <textarea rows={4} maxLength={5000} value={body} onChange={(e) => setBody(e.target.value)} />
          </label>
          {error && <p className="error" role="alert">{error}</p>}
        </div>
        <div className="dialog-foot">
          <button type="button" className="secondary" onClick={onClose}>Cancel</button>
          <button type="submit" disabled={busy}>{busy ? "Posting…" : "Post"}</button>
        </div>
      </form>
    </Dialog>
  );
}
