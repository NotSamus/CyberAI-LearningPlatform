"use client";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowDown, Check, Clock, ListChecks, Pencil, RotateCcw } from "lucide-react";
import LessonBlocks, { checkAnchor } from "@/components/LessonBlocks";
import LessonMenu, { courseLessons, useMyLessons } from "@/components/LessonMenu";
import { useCurrentTopic } from "@/components/Outline";
import PageHeader, { type Crumb } from "@/components/PageHeader";
import ProgressBar from "@/components/ProgressBar";
import { Label, lessonLabel, publishLabel } from "@/components/Status";
import LessonDone from "@/components/learn/LessonDone";
import { courseName } from "@/components/learn/courses";
import { api } from "@/lib/api";
import { message } from "@/lib/errors";
import { isCheck, outline, readingMinutes, rightFirstTime, type CheckState, type LessonPage, type MyLesson } from "@/lib/lessons";

// The page a lesson is read on. Teachers get their working copy here, to try it out.
export default function LessonReader({ lessonId }: { lessonId: string }) {
  const [lesson, setLesson] = useState<LessonPage | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [justCompleted, setJustCompleted] = useState(false);
  const id = Number(lessonId);

  const load = useCallback(() => {
    return api<LessonPage>(`/lessons/${lessonId}`).then(setLesson).catch((e) => setError(message(e)));
  }, [lessonId]);
  useEffect(() => { load(); }, [load]);

  // The topics of the lesson (its headings), for the menu beside it, with the one being read marked.
  const blocks = lesson?.blocks;
  const topics = useMemo(() => outline(blocks ?? []), [blocks]);
  const reading = useCurrentTopic(topics);

  // This lesson as it stands on the page right now: its line in the menu, and the count of its
  // course, follow what is done here.
  const live = useMemo<MyLesson | null>(() => {
    if (!lesson) return null;
    const checks = lesson.blocks.filter(isCheck);
    return {
      id: lesson.id, title: lesson.title, summary: lesson.summary, published: lesson.published,
      course_id: lesson.course_id, course: lesson.course, opened_at: lesson.opened_at, completed_at: lesson.completed_at,
      questions: checks.length, answered: checks.filter((b) => b.state?.closed).length,
    };
  }, [lesson]);
  const lessons = useMyLessons(live);

  // Coming from Home's "mark it complete" (#end): once the lesson is there, go to its end. Once only.
  const loaded = lesson !== null;
  const wentToEnd = useRef(false);
  useEffect(() => {
    if (!loaded || wentToEnd.current) return;
    wentToEnd.current = true;
    if (window.location.hash === "#end") document.getElementById("end")?.scrollIntoView({ block: "center" });
  }, [loaded]);

  function answered(blockId: string, state: CheckState) {
    setLesson((l) => l && {
      ...l,
      blocks: l.blocks.map((b) => (b.id === blockId && isCheck(b) ? { ...b, state } : b)),
    });
  }

  async function complete() {
    setBusy(true);
    setError("");
    try {
      const { completed_at } = await api<{ completed_at: string | null }>(`/lessons/${lessonId}/complete`, { method: "POST" });
      setLesson((l) => l && { ...l, completed_at: completed_at ?? new Date().toISOString() });
      setJustCompleted(true);
    } catch (e) {
      setError(message(e));
    }
    setBusy(false);
  }

  // For teachers: forget their own answers and go through the lesson again.
  async function startOver() {
    setBusy(true);
    setError("");
    try {
      await api(`/lessons/${lessonId}/start-over`, { method: "POST" });
      setJustCompleted(false);
      setLesson(null);      // read it again from the start: the questions forget what was typed
      await load();
    } catch (e) {
      setError(message(e));
    }
    setBusy(false);
  }

  if (!lesson || !live) {
    return (
      <main className="page lesson">
        <p className="crumbs"><Link href="/">Home</Link></p>
        {error ? <p className="error" role="alert">{error}</p> : <p className="muted">Loading…</p>}
        {!error && <LessonMenu currentId={id} course={courseLessons(lessons, null, id)} asTeacher={null} topics={[]} reading={null} />}
      </main>
    );
  }

  const checks = lesson.blocks.filter(isCheck);
  const done = live.answered;
  const left = checks.length - done;
  const minutes = readingMinutes(lesson.blocks);
  // Its course: the lessons of the list, once it has arrived (before that, only this one is known).
  const course = lessons ? courseLessons(lessons, live, id) : [];
  const place = course.findIndex((other) => other.id === id) + 1;

  const crumbs: Crumb[] = [{ label: "Home", href: "/" }, { label: courseName(lesson.course) }];
  if (place > 0) crumbs.push({ label: `Lesson ${place} of ${course.length}` });

  // "Go to it": the first knowledge check not done yet, brought into view.
  function goToOpenCheck() {
    const open = checks.find((b) => !b.state?.closed);
    const target = open && document.getElementById(checkAnchor(open.id));
    if (!target) return;
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    target.scrollIntoView({ behavior: still ? "auto" : "smooth", block: "start" });
    target.focus({ preventScroll: true });
  }

  return (
    <main className="page lesson">
      {lesson.preview && (
        <p className="notice row">
          <span>
            This is your working copy, as a student would see it.
            {!lesson.published && " The lesson is a draft: students cannot see it yet."}
          </span>
          <span className="spacer" />
          <Link href={`/teach/lessons/${lesson.id}`} className="button secondary"><Pencil aria-hidden />Back to writing</Link>
          <button className="secondary" disabled={busy} onClick={startOver}><RotateCcw aria-hidden />Start over</button>
        </p>
      )}

      <PageHeader
        crumbs={crumbs}
        title={lesson.title}
        status={
          lesson.preview
            ? (lesson.published ? null : <Label standing={publishLabel(lesson)} />)
            : (lesson.completed_at ? <Label standing={lessonLabel(live)} /> : null)
        }
        description={lesson.summary || undefined}
      />
      <div className="lesson-facts">
        {(checks.length > 0 || minutes > 0) && (
          <p className="meta">
            {checks.length > 0 && (
              <span className="fact"><ListChecks aria-hidden />{checks.length === 1 ? "1 knowledge check" : `${checks.length} knowledge checks`}</span>
            )}
            {minutes > 0 && <span className="fact"><Clock aria-hidden />{minutes} min read</span>}
          </p>
        )}
        {checks.length > 0 && <ProgressBar value={done} max={checks.length} label={`${done} of ${checks.length} checks done`} />}
      </div>

      <LessonMenu currentId={lesson.id} course={courseLessons(lessons, live, id)} asTeacher={lesson.preview} topics={topics} reading={reading} />

      <LessonBlocks lessonId={lesson.id} blocks={lesson.blocks} onAnswered={answered} />

      <footer id="end" className="lesson-end">
        {error && <p className="error" role="alert">{error}</p>}
        {lesson.completed_at ? (
          <LessonDone
            lesson={live} course={course} checks={checks.length} firstTry={rightFirstTime(lesson.blocks)}
            next={lesson.next} fresh={justCompleted}
          />
        ) : (
          <>
            <div className="finish">
              {left > 0 && (
                <button className="secondary" onClick={goToOpenCheck}>
                  <ArrowDown aria-hidden />{left === 1 ? "1 check left" : `${left} checks left`}: go to it
                </button>
              )}
              <button disabled={busy || left > 0} onClick={complete}><Check aria-hidden />Mark as complete</button>
            </div>
            {lesson.next && <p><Link href={`/lessons/${lesson.next.id}`}>Next lesson: {lesson.next.title}</Link></p>}
          </>
        )}
      </footer>
    </main>
  );
}
