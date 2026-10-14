"use client";
import { ArrowDown, ArrowUp, BookOpen, ChartColumn, CircleAlert, CircleHelp, Eye, LayoutList, Trash2, Users } from "lucide-react";
import Link from "next/link";
import Menu from "@/components/Menu";
import { Label, publishLabel } from "@/components/Status";
import { lessonFor, lessonForNobody, plural } from "@/components/teach/given";
import { api, type Course } from "@/lib/api";
import { JSON_HEADERS, message } from "@/lib/errors";
import type { ManagedLesson } from "@/lib/lessons";

// Lessons as rows of one list: on Teach > Lessons, and on a course's page. `lessons` are the ones
// shown, in the order students get them; `order` is every lesson's id in that order, which is what
// the server is sent when one is moved (lessons have one order for everyone). `reorder` offers the
// arrows: only where the rows shown are what one group of students sees. `withinCourse`: the rows
// are on their course's own page, so who they are for goes without saying.
export default function LessonRows({ lessons, order, courses, reorder, withinCourse = false, onChanged, onError }: {
  lessons: ManagedLesson[];
  order: number[];
  courses: Course[];
  reorder: boolean;
  withinCourse?: boolean;
  onChanged: () => void;
  onError: (message: string) => void;
}) {
  async function act(request: () => Promise<unknown>) {
    onError("");
    try {
      await request();
    } catch (e) {
      onError(message(e));
    }
    onChanged();
  }

  // Swaps the lesson with the one shown above or below it, where both are in the whole order.
  function move(index: number, by: -1 | 1) {
    const ids = [...order];
    const here = ids.indexOf(lessons[index].id), there = ids.indexOf(lessons[index + by].id);
    [ids[here], ids[there]] = [ids[there], ids[here]];
    act(() => api("/teach/lessons/order", { method: "PUT", headers: JSON_HEADERS, body: JSON.stringify({ ids }) }));
  }

  function remove(lesson: ManagedLesson) {
    const sure = window.confirm(`Delete "${lesson.title}"? Its pictures and what students answered in it are deleted too.`);
    if (sure) act(() => api(`/teach/lessons/${lesson.id}`, { method: "DELETE" }));
  }

  return (
    <ul className="list">
      {lessons.map((lesson, index) => {
        const nobody = lesson.published && lessonForNobody(lesson);
        const forWhom = lessonFor(lesson, courses);
        return (
          <li key={lesson.id}>
            <span className="tile"><BookOpen aria-hidden /></span>
            <div className="grow">
              <div className="title-line">
                <Link className="title" href={`/teach/lessons/${lesson.id}`}>{lesson.title}</Link>
                <Label standing={publishLabel(lesson)} />
              </div>
              {lesson.summary && <p className="summary">{lesson.summary}</p>}
              <p className="meta">
                {!withinCourse && (
                  <span className={`fact ${nobody ? "bad" : ""}`}>
                    {nobody ? <CircleAlert aria-hidden /> : <Users aria-hidden />}
                    {nobody ? "Published, but given to nobody: no student can see it" : forWhom ? `For ${forWhom}` : "Given to nobody yet"}
                  </span>
                )}
                <span className="fact"><LayoutList aria-hidden />{plural(lesson.blocks_count, "block")}</span>
                {lesson.published && <span className="fact"><CircleHelp aria-hidden />{plural(lesson.questions, "knowledge check")}</span>}
              </p>
            </div>
            <div className="row-actions">
              {reorder && (
                <>
                  <button className="icon" title="Move up" aria-label={`Move ${lesson.title} up`} disabled={index === 0} onClick={() => move(index, -1)}>
                    <ArrowUp aria-hidden />
                  </button>
                  <button className="icon" title="Move down" aria-label={`Move ${lesson.title} down`} disabled={index === lessons.length - 1} onClick={() => move(index, 1)}>
                    <ArrowDown aria-hidden />
                  </button>
                </>
              )}
              <Menu
                label={`More for ${lesson.title}`}
                items={[
                  { label: "Progress", icon: ChartColumn, href: `/teach/lessons/${lesson.id}/progress` },
                  { label: "Open as a student would", icon: Eye, href: `/lessons/${lesson.id}` },
                  { label: "Delete", icon: Trash2, danger: true, onSelect: () => remove(lesson) },
                ]}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
