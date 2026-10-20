"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import Dialog from "@/components/Dialog";
import FileDrop from "@/components/teach/FileDrop";
import { plural } from "@/components/teach/given";
import { api, type Course } from "@/lib/api";
import { message } from "@/lib/errors";
import { MAX_IMPORT_BYTES, type LessonImport } from "@/lib/lessons";

// "Import": lessons from a .zip that Export made, on this platform or another one, with their
// pictures and the notebooks they link to (api/app/lesson_zip.py). They come in as drafts, given
// to whom "For" says; `audience` is what it starts at, as in NewLessonDialog. `onImported` reloads
// the list behind the dialog, which then says what was made.
export default function ImportLessonsDialog({ open, onClose, onImported, courses, audience: preset = "none" }: {
  open: boolean;
  onClose: () => void;
  onImported: () => void;
  courses: Course[];
  audience?: string;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [audience, setAudience] = useState(preset);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState<LessonImport | null>(null);

  useEffect(() => {
    if (open) { setFile(null); setAudience(preset); setError(""); setDone(null); }
  }, [open, preset]);

  async function bringIn(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    if (file.size > MAX_IMPORT_BYTES) {
      setError(`The file is larger than ${MAX_IMPORT_BYTES / (1024 * 1024)} MB. Export fewer lessons at a time.`);
      return;
    }
    setBusy(true);
    setError("");
    const form = new FormData();
    form.append("file", file);
    form.append("for", audience);
    try {
      setDone(await api<LessonImport>("/teach/lesson-imports", { method: "POST", body: form }));
      onImported();
    } catch (e) {
      setError(message(e));
    }
    setBusy(false);
  }

  const forWhom = audience === "everyone" ? "all students" : courses.find((c) => String(c.id) === audience)?.name;
  const added = done?.notebooks_added ?? [], linked = done?.notebooks_linked ?? [];
  return (
    <Dialog open={open} title="Import lessons" onClose={onClose} dismissible={!busy}>
      {done ? (
        <form onSubmit={(e) => { e.preventDefault(); onClose(); }}>
          <div className="dialog-body">
            <p>
              {plural(done.lessons.length, "lesson")} imported as {done.lessons.length === 1 ? "a draft" : "drafts"}
              {forWhom ? `, for ${forWhom}` : ", given to nobody yet"}. Students see {done.lessons.length === 1 ? "it" : "them"} once
              you publish.
            </p>
            <ul className="import-list">
              {done.lessons.map((lesson) => <li key={lesson.id}><Link href={`/teach/lessons/${lesson.id}`}>{lesson.title}</Link></li>)}
            </ul>
            {added.length > 0 && (
              <p>
                {added.length === 1 ? "A notebook came in as a draft assignment" : `${added.length} notebooks came in as draft assignments`}:{" "}
                {added.join(", ")}. Publish {added.length === 1 ? "it" : "them"} under <Link href="/teach/assignments">Assignments</Link>,
                so that students can open {added.length === 1 ? "it" : "them"} from the lessons.
              </p>
            )}
            {linked.length > 0 && (
              <p className="muted">Linked to {linked.length === 1 ? "an assignment" : "assignments"} already here: {linked.join(", ")}.</p>
            )}
            {done.warnings.length > 0 && (
              <ul className="import-list error">{done.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>
            )}
          </div>
          <div className="dialog-foot">
            <button type="submit">Done</button>
          </div>
        </form>
      ) : (
        <form onSubmit={bringIn}>
          <div className="dialog-body">
            <FileDrop
              accept=".zip" what="a .zip file" file={file} busy={busy} required onFile={(f) => { setFile(f); setError(""); }}
              hint={`Made with Export on Teach > Lessons, here or on another platform. At most ${MAX_IMPORT_BYTES / (1024 * 1024)} MB.`}
            />
            <label>
              For
              <select value={audience} disabled={busy} onChange={(e) => setAudience(e.target.value)}>
                <option value="none">Nobody yet</option>
                <option value="everyone">All students</option>
                {courses.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.student_ids.length})</option>)}
              </select>
            </label>
            <p className="muted">
              The lessons come in as drafts with their pictures, after the lessons here. The notebooks they link to come in as
              draft assignments, unless the same one is here already. Autograded notebooks go through Otter again, which can
              take a few minutes.
            </p>
            {error && <p className="error" role="alert">{error}</p>}
          </div>
          <div className="dialog-foot">
            <button type="button" className="secondary" disabled={busy} onClick={onClose}>Cancel</button>
            <button type="submit" disabled={busy || !file}>{busy ? "Importing…" : "Import"}</button>
          </div>
        </form>
      )}
    </Dialog>
  );
}
