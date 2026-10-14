"use client";
import Link from "next/link";
import { useEffect, useRef } from "react";
import { Circle, CircleCheck, CircleDashed } from "lucide-react";
import Outline from "@/components/Outline";
import type { Topic } from "@/lib/lessons";

// One line of the list of lessons shown to the left of a lesson, in the editor and on the page it
// is read on: where the lesson stands, as an icon (an empty ring, a dashed blue ring, a green tick)
// and in words.
export type LessonRow = { id: number; title: string; href: string; dot: "draft" | "changed" | "live"; note: string };

const MARKS = { draft: Circle, changed: CircleDashed, live: CircleCheck };

// The lessons, with the topics of the current one under it (`reading`: the topic in view, if known).
export default function LessonList({ rows, currentId, topics, reading }: {
  rows: LessonRow[];
  currentId: number;
  topics: Topic[];
  reading?: string | null;
}) {
  const list = useRef<HTMLOListElement | null>(null);

  // In a long list, bring the current lesson into view: by scrolling the list's own box, never the page.
  useEffect(() => {
    const row = list.current?.querySelector<HTMLElement>(".active");
    const box = row?.closest<HTMLElement>(".rail");
    if (!row || !box) return;
    const here = row.getBoundingClientRect(), frame = box.getBoundingClientRect();
    if (here.top < frame.top || here.bottom > frame.bottom) box.scrollTop += here.top - frame.top - 8;
  }, [currentId, rows.length]);

  return (
    <ol ref={list}>
      {rows.map((row) => {
        const current = row.id === currentId;
        const Mark = MARKS[row.dot];
        return (
          <li key={row.id}>
            <Link href={row.href} className={`rail-lesson ${current ? "active" : ""}`} aria-current={current ? "page" : undefined}>
              <Mark className={`mark ${row.dot}`} aria-hidden />
              <span className="name">{row.title}</span>
              <span className="muted">{row.note}</span>
            </Link>
            {current && topics.length > 0 && <Outline topics={topics} current={reading} label="Topics of this lesson" />}
          </li>
        );
      })}
    </ol>
  );
}
