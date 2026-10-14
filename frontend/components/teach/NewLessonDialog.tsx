"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Dialog from "@/components/Dialog";
import { api, type Course } from "@/lib/api";
import { JSON_HEADERS, message } from "@/lib/errors";
import type { ManagedLesson } from "@/lib/lessons";

// "New lesson": a title and who it is for, then straight to writing it. `audience` is what "For"
// starts at: "none", "everyone", or the id of a course (on a course's page, that course).
export default function NewLessonDialog({ open, onClose, courses, audience: preset = "none" }: {
  open: boolean;
  onClose: () => void;
  courses: Course[];
  audience?: string;
}) {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [audience, setAudience] = useState(preset);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) { setAudience(preset); setError(""); }
  }, [open, preset]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      // A new lesson is a draft given to nobody: who it is for is set right after.
      const lesson = await api<ManagedLesson>("/teach/lessons", { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ title }) });
      if (audience !== "none") {
        const given = { for_everyone: audience === "everyone", course_id: audience === "everyone" ? null : Number(audience) };
        // If this fails the lesson still opens: the editor shows who it is for, and it can be chosen there.
        await api(`/teach/lessons/${lesson.id}`, { method: "PATCH", headers: JSON_HEADERS, body: JSON.stringify(given) }).catch(() => {});
      }
      router.push(`/teach/lessons/${lesson.id}`);      // straight to writing
    } catch (e) {
      setError(message(e));
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} title="New lesson" onClose={onClose}>
      <form onSubmit={create}>
        <div className="dialog-body">
          <label>
            Title
            <input required autoFocus maxLength={120} value={title} onChange={(e) => setTitle(e.target.value)} />
          </label>
          <label>
            For
            <select value={audience} onChange={(e) => setAudience(e.target.value)}>
              <option value="none">Nobody yet</option>
              <option value="everyone">All students</option>
              {courses.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.student_ids.length})</option>)}
            </select>
          </label>
          <p className="muted">Students see it once it is published. You can change who it is for while writing.</p>
          {error && <p className="error" role="alert">{error}</p>}
        </div>
        <div className="dialog-foot">
          <button type="button" className="secondary" onClick={onClose}>Cancel</button>
          <button type="submit" disabled={busy}>{busy ? "Creating…" : "Start writing"}</button>
        </div>
      </form>
    </Dialog>
  );
}
