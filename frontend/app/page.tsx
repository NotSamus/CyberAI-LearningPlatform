"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { BookOpen } from "lucide-react";
import EmptyState from "@/components/EmptyState";
import PageHeader from "@/components/PageHeader";
import Announcements from "@/components/learn/Announcements";
import CourseSection from "@/components/learn/CourseSection";
import DueSoon from "@/components/learn/DueSoon";
import TeachStrip from "@/components/learn/TeachStrip";
import UpNext, { SHOWN, whatIsNext } from "@/components/learn/UpNext";
import { byCourse } from "@/components/learn/courses";
import { api, type Announcement, type MyAssignment } from "@/lib/api";
import type { MyLesson } from "@/lib/lessons";
import { useMe } from "@/lib/useMe";

// Home. For a student: what to do next, what is due, the announcements, and then every lesson and
// assignment they have, course by course. For a teacher: the same lists as their students see
// them, drafts included, under a line about what waits for them in Teach.
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

  const teacher = Boolean(me?.can_teach);
  // Until the account is known, nothing that depends on whose it is: a teacher must not see a
  // student's "Up next" for a moment, made of their own progress.
  const known = me !== null;
  const loaded = lessons !== null && items !== null;
  const empty = loaded && lessons.length === 0 && items.length === 0;

  // One line on where the student stands, over everything they have.
  const standing: string[] = [];
  if (lessons && lessons.length > 0) {
    const completed = lessons.filter((lesson) => lesson.completed_at).length;
    standing.push(`${completed} of ${lessons.length} ${lessons.length === 1 ? "lesson" : "lessons"} completed`);
  }
  if (items && items.length > 0) {
    const open = items.filter((a) => !a.submission).length;
    standing.push(open === 0 ? "every assignment handed in" : `${open} ${open === 1 ? "assignment" : "assignments"} to hand in`);
  }
  // The assignments Up next shows, so that Due soon does not list them a second time.
  const upNext = !teacher && lessons && items
    ? whatIsNext(lessons, items).slice(0, SHOWN).flatMap((item) => (item.key.startsWith("assignment-") ? [Number(item.key.slice(11))] : []))
    : [];

  const summary = teacher
    ? "What your students see, drafts included. Your own progress is not shown here."
    : loaded && standing.length > 0 ? standing.join(" · ") : undefined;

  return (
    <main className="page home">
      {teacher && <TeachStrip />}
      <PageHeader title={teacher ? "Lessons and assignments" : "My lessons and assignments"} description={known ? summary : undefined} />
      {error && <p className="error" role="alert">Could not load this page: {error}</p>}
      {(!loaded || !known) && !error && <p className="muted">Loading…</p>}

      {loaded && known && empty && (
        teacher ? (
          <EmptyState
            icon={BookOpen} title="Nothing here yet"
            action={<>
              <Link href="/teach/lessons" className="button">Write a lesson</Link>
              <Link href="/teach/assignments/new" className="button secondary">Upload a notebook</Link>
            </>}
          >
            Lessons you write and notebooks you upload show up here, the way your students will see them.
          </EmptyState>
        ) : (
          <EmptyState icon={BookOpen} title="Nothing here yet">
            Nothing has been given to you yet. New lessons and assignments will show up here.
          </EmptyState>
        )
      )}

      {loaded && known && !empty && !teacher && <UpNext lessons={lessons} assignments={items} />}
      {loaded && known && !empty && <DueSoon assignments={items} asTeacher={teacher} shown={upNext} />}
      <Announcements items={news} />
      {loaded && known && byCourse(lessons, items).map((group) => (
        <CourseSection key={group.id ?? "everyone"} group={group} asTeacher={teacher} />
      ))}
    </main>
  );
}
