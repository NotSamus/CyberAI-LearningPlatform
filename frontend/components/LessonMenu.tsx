"use client";
import { useEffect, useState } from "react";
import LessonList, { type LessonRow } from "@/components/LessonList";
import { api } from "@/lib/api";
import type { MyLesson, Topic } from "@/lib/lessons";

// Kept from one lesson's page to the next, so that the menu is there at once when moving on.
let known: MyLesson[] | null = null;
let teaching = false;

// Every lesson this person may see, in the teachers' order, with their own progress. `live` is the
// lesson on the page as it is right now: the kept list follows it, so that the next page starts
// from what was just done (a lesson completed, a check answered).
export function useMyLessons(live: MyLesson | null): MyLesson[] | null {
  const [lessons, setLessons] = useState(known);
  useEffect(() => {
    api<MyLesson[]>("/lessons").then((all) => { known = all; setLessons(all); }).catch(() => {});
  }, []);
  useEffect(() => {
    if (known && live) known = known.map((lesson) => (lesson.id === live.id ? live : lesson));
  }, [live]);
  return lessons;
}

// The lessons of the same course as `currentId` (`lessons`: as useMyLessons gives them; `live`: the
// one on the page, which wins over its line in the list). For lessons that belong to no course,
// the other lessons for all students.
export function courseLessons(lessons: MyLesson[] | null, live: MyLesson | null, currentId: number): MyLesson[] {
  const all = (lessons ?? (live ? [live] : [])).map((lesson) => (live && lesson.id === live.id ? live : lesson));
  const current = all.find((lesson) => lesson.id === currentId);
  return current ? all.filter((lesson) => lesson.course_id === current.course_id) : [];
}

function row(lesson: MyLesson, asTeacher: boolean): LessonRow {
  const here = { id: lesson.id, title: lesson.title, href: `/lessons/${lesson.id}` };
  // A teacher's own progress in a lesson means nothing: they get where the lesson stands instead.
  if (asTeacher) return lesson.published ? { ...here, dot: "live", note: "Published" } : { ...here, dot: "draft", note: "Draft" };
  if (lesson.completed_at) return { ...here, dot: "live", note: "Completed" };
  if (!lesson.opened_at) return { ...here, dot: "draft", note: "Not started" };
  const checks = lesson.questions > 0 ? ` · ${lesson.answered} of ${lesson.questions} checks` : "";
  return { ...here, dot: "changed", note: `In progress${checks}` };
}

// To the left of a lesson being read: the lessons of the same course (`course`, from courseLessons)
// with how far they are in each, and under this lesson its topics. `asTeacher`: a teacher trying
// out lessons.
export default function LessonMenu({ currentId, course, asTeacher, topics, reading }: {
  currentId: number;
  course: MyLesson[];
  asTeacher: boolean | null;      // null: not known yet, the lesson is still loading
  topics: Topic[];
  reading: string | null;
}) {
  useEffect(() => {
    if (asTeacher !== null) teaching = asTeacher;
  }, [asTeacher]);

  if (course.length === 0) return null;
  const current = course.find((lesson) => lesson.id === currentId);
  return (
    <nav className="lesson-menu" aria-label="Lessons">
      <div className="rail">
        <p className="check-label">{current?.course ?? "For all students"}</p>
        <LessonList rows={course.map((lesson) => row(lesson, asTeacher ?? teaching))} currentId={currentId} topics={topics} reading={reading} />
      </div>
    </nav>
  );
}
