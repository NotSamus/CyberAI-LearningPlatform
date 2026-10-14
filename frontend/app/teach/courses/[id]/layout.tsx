"use client";
import { LayoutList, Megaphone, Pencil, Plus, Trash2, Upload, Users } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { use, useCallback, useEffect, useState } from "react";
import Dialog from "@/components/Dialog";
import Menu from "@/components/Menu";
import PageHeader from "@/components/PageHeader";
import Tabs from "@/components/Tabs";
import NewLessonDialog from "@/components/teach/NewLessonDialog";
import { CourseContext } from "@/components/teach/context";
import { plural } from "@/components/teach/given";
import { api, type Course } from "@/lib/api";
import { JSON_HEADERS, message } from "@/lib/errors";

// One course: its header (New lesson, Upload notebook, and Rename and Delete under ⋯) above its three
// tabs, Content, Students and Announcements, which get the course from here.
export default function CourseLayout({ children, params }: { children: React.ReactNode; params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const [courses, setCourses] = useState<Course[] | null>(null);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  // On the Students tab, saving the students is the main thing to do: New lesson is outlined there.
  const onStudents = usePathname().endsWith("/students");
  const [renaming, setRenaming] = useState(false);

  // There is no request for one course: it is taken from the list.
  const reload = useCallback(() => api<Course[]>("/teach/courses").then(setCourses), []);
  useEffect(() => { reload().catch((e) => setLoadError(message(e))); }, [reload]);

  const crumbs = [{ label: "Courses", href: "/teach/courses" }];
  const course = courses?.find((c) => c.id === Number(id));
  if (loadError) return <><PageHeader crumbs={crumbs} title="Course" /><p className="error" role="alert">{loadError}</p></>;
  if (!courses) return <><PageHeader crumbs={crumbs} title="Course" /><p className="muted">Loading…</p></>;
  if (!course) return <><PageHeader crumbs={crumbs} title="Course" /><p className="error" role="alert">No such course.</p></>;

  async function remove(course: Course) {
    const sure = window.confirm(
      `Delete "${course.name}"? Its announcements are deleted. Its lessons and assignments stay, but are no longer given to ` +
      "this course: its students lose sight of them until you give them to someone again.",
    );
    if (!sure) return;
    setError("");
    try {
      await api(`/teach/courses/${course.id}`, { method: "DELETE" });
      router.push("/teach/courses");
    } catch (e) {
      setError(message(e));
    }
  }

  return (
    <CourseContext.Provider value={{ course, courses, reload, newLesson: () => setCreating(true) }}>
      <PageHeader
        crumbs={[...crumbs, { label: course.name }]}
        title={course.name}
        meta={<span className="fact"><Users aria-hidden />{plural(course.student_ids.length, "student")}</span>}
        actions={
          <>
            <button className={onStudents ? "secondary" : ""} onClick={() => setCreating(true)}><Plus aria-hidden />New lesson</button>
            <Link href={`/teach/assignments/new?course=${course.id}`} className="button secondary"><Upload aria-hidden />Upload notebook</Link>
            <Menu
              label={`More for ${course.name}`}
              items={[
                { label: "Rename", icon: Pencil, onSelect: () => setRenaming(true) },
                { label: "Delete", icon: Trash2, danger: true, onSelect: () => remove(course) },
              ]}
            />
          </>
        }
        tabs={
          <Tabs
            kind="item" label="Views of this course"
            tabs={[
              { href: `/teach/courses/${course.id}`, label: "Content", icon: LayoutList, exact: true },
              { href: `/teach/courses/${course.id}/students`, label: "Students", icon: Users, count: course.student_ids.length },
              { href: `/teach/courses/${course.id}/announcements`, label: "Announcements", icon: Megaphone },
            ]}
          />
        }
      />
      {error && <p className="error" role="alert">{error}</p>}
      {children}
      <NewLessonDialog open={creating} onClose={() => setCreating(false)} courses={courses} audience={String(course.id)} />
      <RenameDialog open={renaming} course={course} onClose={() => setRenaming(false)} onSaved={async () => { setRenaming(false); await reload(); }} />
    </CourseContext.Provider>
  );
}

function RenameDialog({ open, course, onClose, onSaved }: { open: boolean; course: Course; onClose: () => void; onSaved: () => Promise<void> }) {
  const [name, setName] = useState(course.name);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (open) { setName(course.name); setError(""); }
  }, [open, course.name]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api(`/teach/courses/${course.id}`, { method: "PATCH", headers: JSON_HEADERS, body: JSON.stringify({ name }) });
      await onSaved();
    } catch (e) {
      setError(message(e));
    }
    setBusy(false);
  }

  return (
    <Dialog open={open} title="Rename course" onClose={onClose}>
      <form onSubmit={save}>
        <div className="dialog-body">
          <label>
            Name
            <input required autoFocus maxLength={120} value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          {error && <p className="error" role="alert">{error}</p>}
        </div>
        <div className="dialog-foot">
          <button type="button" className="secondary" onClick={onClose}>Cancel</button>
          <button type="submit" disabled={busy}>{busy ? "Saving…" : "Save"}</button>
        </div>
      </form>
    </Dialog>
  );
}
