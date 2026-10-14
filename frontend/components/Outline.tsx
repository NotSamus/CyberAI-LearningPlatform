"use client";
import { useEffect, useState } from "react";
import type { Topic } from "@/lib/lessons";

// Where a topic is on the page: its heading, or, while its text is being edited (a text field, with
// no headings in it), the block it is written in.
function find(topic: Topic): HTMLElement | null {
  return document.getElementById(topic.id)
    ?? document.querySelector<HTMLElement>(`[data-focus="${topic.block}"]`)
    ?? document.getElementById(`text-${topic.block}`);
}

function goTo(topic: Topic) {
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  find(topic)?.scrollIntoView({ behavior: still ? "auto" : "smooth", block: "start" });
}

// The topic being read: the last heading that has reached the top part of the window.
export function useCurrentTopic(topics: Topic[]): string | null {
  const [current, setCurrent] = useState<string | null>(null);
  useEffect(() => {
    if (topics.length === 0) return;
    let frame = 0;
    const look = () => {
      frame = 0;
      const atTheEnd = window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4;
      let reached: string | null = null;
      for (const topic of topics) {
        const heading = document.getElementById(topic.id);
        if (heading && (atTheEnd || heading.getBoundingClientRect().top <= 140)) reached = topic.id;
      }
      setCurrent(reached);
    };
    const onScroll = () => { if (!frame) frame = requestAnimationFrame(look); };
    look();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, [topics]);
  return current;
}

// The index of a lesson: its headings, indented by level. Choosing one scrolls to it.
export default function Outline({ topics, current, label }: { topics: Topic[]; current?: string | null; label: string }) {
  const top = Math.min(...topics.map((topic) => topic.level));
  const indent = ["var(--s3)", "var(--s5)", "var(--s6)"];      // by how deep the heading is: steps of the spacing scale (globals.css)
  return (
    <ul className="outline" aria-label={label}>
      {topics.map((topic) => (
        <li key={topic.id}>
          <a
            href={`#${topic.id}`} className={topic.id === current ? "active" : ""} aria-current={topic.id === current ? "location" : undefined}
            style={{ paddingLeft: indent[topic.level - top] }}
            onClick={(e) => { e.preventDefault(); goTo(topic); }}
          >
            {topic.text}
          </a>
        </li>
      ))}
    </ul>
  );
}
