"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import DueDate from "@/components/DueDate";
import Status from "@/components/Status";
import { api, type Announcement, type MyAssignment } from "@/lib/api";
import { formatWhen } from "@/lib/dates";
import { useMe } from "@/lib/useMe";

export default function Home() {
  const me = useMe();
  const [items, setItems] = useState<MyAssignment[] | null>(null);
  const [news, setNews] = useState<Announcement[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    // The server sends only what this account may see: students get the published assignments
    // given to them, teachers get every assignment, drafts included.
    api<MyAssignment[]>("/assignments").then(setItems).catch((e) => setError(e.message));
    api<Announcement[]>("/announcements").then(setNews).catch(() => {});
  }, []);

  // One group per course, in the order the server sent the assignments (soonest due date first);
  // assignments that belong to no course come last.
  const groups = new Map<string, MyAssignment[]>();
  for (const a of items ?? []) {
    if (a.course) groups.set(a.course, [...(groups.get(a.course) ?? []), a]);
  }
  const noCourse = (items ?? []).filter((a) => !a.course);
  if (noCourse.length > 0) groups.set(groups.size > 0 ? "Other assignments" : "", noCourse);

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

      <h1>{me?.can_teach ? "Assignments" : "My assignments"}</h1>
      {error && <p className="error" role="alert">Could not load assignments: {error}</p>}
      {!items && !error && <p className="muted">Loading…</p>}
      {items?.length === 0 && (
        me?.can_teach
          ? <p className="muted">No assignments yet. Upload a notebook under <Link href="/settings/assignments">Settings</Link>.</p>
          : <p className="muted">Nothing has been assigned to you yet. New assignments will show up here.</p>
      )}
      {[...groups].map(([course, assignments]) => (
        <section key={course}>
          {course && <h2>{course}</h2>}
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
        </section>
      ))}
    </main>
  );
}
