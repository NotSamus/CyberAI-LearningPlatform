"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import DueDate from "@/components/DueDate";
import Status from "@/components/Status";
import { api, type Announcement, type MyAssignment } from "@/lib/api";
import { formatWhen } from "@/lib/dates";
import type { MyLesson } from "@/lib/lessons";
import { useMe } from "@/lib/useMe";

type Group = { lessons: MyLesson[]; assignments: MyAssignment[] };

export default function Home() {
  const me = useMe();
  const [lessons, setLessons] = useState<MyLesson[] | null>(null);
  const [items, setItems] = useState<MyAssignment[] | null>(null);
  const [news, setNews] = useState<Announcement[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    // The server sends only what this account may see: students get what is published and given
    // to them, teachers get everything, drafts included.
    api<MyLesson[]>("/lessons").then(setLessons).catch((e) => setError(e.message));
    api<MyAssignment[]>("/assignments").then(setItems).catch((e) => setError(e.message));
    api<Announcement[]>("/announcements").then(setNews).catch(() => {});
  }, []);

  // One group per course, with its lessons (in the order the teachers put them in) and its
  // assignments (soonest due date first). What belongs to no course comes last.
  const groups = new Map<string, Group>();
  const group = (course: string | null) => {
    if (!groups.has(course ?? "")) groups.set(course ?? "", { lessons: [], assignments: [] });
    return groups.get(course ?? "")!;
  };
  for (const lesson of lessons ?? []) if (lesson.course) group(lesson.course).lessons.push(lesson);
  for (const a of items ?? []) if (a.course) group(a.course).assignments.push(a);
  const inCourses = groups.size > 0;
  for (const lesson of lessons ?? []) if (!lesson.course) group(null).lessons.push(lesson);
  for (const a of items ?? []) if (!a.course) group(null).assignments.push(a);

  const loaded = lessons !== null && items !== null;
  return (
    <main className="page">
      {news.length > 0 && (
        <section className="announcements" aria-label="Announcements">
          {news.slice(0, 5).map((n) => (
            <article key={n.id} className="card">
              <p className="badges">
                <strong>{n.title}</strong>
                {n.course && <span className="badge">{n.course}</span>}
                <span className="muted">{formatWhen(n.created_at)}</span>
              </p>
              {n.body && <p className="description">{n.body}</p>}
            </article>
          ))}
        </section>
      )}

      <h1>{me?.can_teach ? "Lessons and assignments" : "My lessons and assignments"}</h1>
      {error && <p className="error" role="alert">Could not load this page: {error}</p>}
      {!loaded && !error && <p className="muted">Loading…</p>}
      {loaded && groups.size === 0 && (
        me?.can_teach
          ? (
            <p className="muted">
              Nothing here yet. Write a lesson or upload a notebook under <Link href="/settings">Settings</Link>.
            </p>
          )
          : <p className="muted">Nothing has been given to you yet. New lessons and assignments will show up here.</p>
      )}
      {loaded && [...groups].map(([course, { lessons, assignments }]) => (
        <section key={course}>
          {(course || inCourses) && <h2>{course || "Other"}</h2>}
          {lessons.length > 0 && (
            <>
              <p className="check-label group-label">Lessons</p>
              <ul className="grid">
                {lessons.map((lesson) => (
                  <li key={lesson.id}>
                    <Link href={`/lessons/${lesson.id}`} className="card">
                      <h3>{lesson.title}</h3>
                      <p className="muted clamp">{lesson.summary}</p>
                      <span className="badges">
                        {!lesson.published && <span className="badge draft">Draft</span>}
                        {/* A teacher's own progress in a lesson means nothing: students get the status. */}
                        {me && !me.can_teach && <LessonStatus lesson={lesson} />}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </>
          )}
          {assignments.length > 0 && (
            <>
              <p className="check-label group-label">Assignments</p>
              <ul className="grid">
                {assignments.map((a) => (
                  <li key={a.id}>
                    <Link href={`/assignments/${a.id}`} className="card">
                      <h3>{a.title}</h3>
                      <p className="muted clamp">{a.description}</p>
                      <span className="badges">
                        {!a.published && <span className="badge draft">Draft</span>}
                        {/* A teacher's own progress on an assignment means nothing: students get the status. */}
                        {me && !me.can_teach && <Status assignment={a} />}
                        <DueDate due_at={a.due_at} done={Boolean(a.submission)} />
                        {a.requires_gpu && <span className="badge gpu">GPU</span>}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      ))}
    </main>
  );
}

// Where a student is with a lesson: not started, in progress (with the knowledge checks done), completed.
function LessonStatus({ lesson }: { lesson: MyLesson }) {
  if (lesson.completed_at) return <span className="badge live">Completed</span>;
  if (!lesson.opened_at) return <span className="badge">Not started</span>;
  return (
    <>
      <span className="badge">In progress</span>
      {lesson.questions > 0 && <span className="muted">{lesson.answered} of {lesson.questions} checks done</span>}
    </>
  );
}
