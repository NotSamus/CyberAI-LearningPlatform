"use client";
import { Megaphone, Plus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import EmptyState from "@/components/EmptyState";
import PageHeader from "@/components/PageHeader";
import AnnouncementRows from "@/components/teach/AnnouncementRows";
import NewAnnouncementDialog from "@/components/teach/NewAnnouncementDialog";
import { api, type Announcement, type Course } from "@/lib/api";
import { message } from "@/lib/errors";

// Short messages that students see at the top of their home page.
export default function AnnouncementsPage() {
  const [items, setItems] = useState<Announcement[] | null>(null);
  const [courses, setCourses] = useState<Course[]>([]);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("all");          // "all", "everyone" (no course), or the id of a course
  const [posting, setPosting] = useState(false);

  const load = useCallback(() => {
    Promise.all([api<Announcement[]>("/teach/announcements"), api<Course[]>("/teach/courses")])
      .then(([announcements, classes]) => { setItems(announcements); setCourses(classes); })
      .catch((e) => setLoadError(message(e)));
  }, []);
  useEffect(load, [load]);

  const newAnnouncement = <button onClick={() => setPosting(true)}><Plus aria-hidden />New announcement</button>;
  const header = (
    <PageHeader
      title="Announcements"
      description="Students see the five newest announcements meant for them at the top of their home page."
      actions={items && items.length > 0 ? newAnnouncement : undefined}      // with none yet, the empty list below offers it
    />
  );

  const dialog = (
    <NewAnnouncementDialog
      open={posting} courses={courses} preset={filter === "all" || filter === "everyone" ? "" : filter}
      onClose={() => setPosting(false)} onPosted={() => { setPosting(false); load(); }}
    />
  );
  if (loadError) return <>{header}<p className="error" role="alert">{loadError}</p>{dialog}</>;
  if (!items) return <>{header}<p className="muted">Loading…</p>{dialog}</>;

  const shown = items.filter((item) =>
    filter === "all" ? true : filter === "everyone" ? item.course_id === null : item.course_id === Number(filter));

  return (
    <>
      {header}
      {error && <p className="error" role="alert">{error}</p>}
      {items.length === 0 ? (
        <EmptyState icon={Megaphone} title="No announcements yet" action={newAnnouncement}>
          Post a short message for everyone or for one course: a change of plan, a reminder, a new lesson.
        </EmptyState>
      ) : (
        <>
          <div className="filters">
            <label>
              Show
              <select value={filter} onChange={(e) => setFilter(e.target.value)}>
                <option value="all">All announcements ({items.length})</option>
                <option value="everyone">For everyone</option>
                {courses.map((c) => <option key={c.id} value={String(c.id)}>{c.name}</option>)}
              </select>
            </label>
          </div>
          {shown.length === 0
            ? <p className="muted">No announcements here yet.</p>
            : <AnnouncementRows items={shown} onChanged={load} onError={setError} />}
        </>
      )}
      {dialog}
    </>
  );
}
