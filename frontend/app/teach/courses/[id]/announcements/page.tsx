"use client";
import { Megaphone, Plus } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import EmptyState from "@/components/EmptyState";
import AnnouncementRows from "@/components/teach/AnnouncementRows";
import NewAnnouncementDialog from "@/components/teach/NewAnnouncementDialog";
import { useCoursePage } from "@/components/teach/context";
import { plural } from "@/components/teach/given";
import { api, type Announcement } from "@/lib/api";
import { message } from "@/lib/errors";

// A course's announcements, and a new one for it. There is no request for one course's
// announcements: they are picked out of the list of all of them. Its students also see those for
// everyone, which are kept under Teach > Announcements.
export default function CourseAnnouncements() {
  const { course, courses } = useCoursePage();
  const [items, setItems] = useState<Announcement[] | null>(null);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [posting, setPosting] = useState(false);

  const load = useCallback(() => {
    api<Announcement[]>("/teach/announcements").then(setItems).catch((e) => setLoadError(message(e)));
  }, []);
  useEffect(load, [load]);

  // Outlined: the header's New lesson is the course page's main action, on every tab.
  const newAnnouncement = <button className="secondary" onClick={() => setPosting(true)}><Plus aria-hidden />New announcement</button>;
  const dialog = (
    <NewAnnouncementDialog
      open={posting} courses={courses} preset={String(course.id)}
      onClose={() => setPosting(false)} onPosted={() => { setPosting(false); load(); }}
    />
  );
  if (loadError) return <p className="error" role="alert">{loadError}</p>;
  if (!items) return <p className="muted">Loading…</p>;

  const own = items.filter((item) => item.course_id === course.id);
  const forEveryone = items.filter((item) => item.course_id === null).length;

  return (
    <>
      {error && <p className="error" role="alert">{error}</p>}
      {own.length === 0 ? (
        <EmptyState icon={Megaphone} title="No announcements for this course yet" action={newAnnouncement}>
          Post a short message for its students: a change of plan, a reminder, a new lesson.
        </EmptyState>
      ) : (
        <>
          <div className="filters">
            {newAnnouncement}
            <span className="muted">Its students see the five newest announcements meant for them at the top of their home page.</span>
          </div>
          <AnnouncementRows items={own} withinCourse onChanged={load} onError={setError} />
        </>
      )}
      {forEveryone > 0 && (
        <p className="muted hint">
          Its students also see {forEveryone === 1 ? "the announcement" : `the ${plural(forEveryone, "announcement")}`} for
          everyone, under <Link href="/teach/announcements">Announcements</Link>.
        </p>
      )}
      {dialog}
    </>
  );
}
