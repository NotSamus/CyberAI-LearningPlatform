"use client";
import { useEffect, useRef, useState } from "react";
import { GraduationCap, Megaphone } from "lucide-react";
import type { Announcement } from "@/lib/api";
import { formatWhen } from "@/lib/dates";

// One announcement: its text cut to two lines, with "More" when there is more of it.
function Row({ item }: { item: Announcement }) {
  const body = useRef<HTMLParagraphElement | null>(null);
  const [long, setLong] = useState(false);
  const [open, setOpen] = useState(false);

  // Whether the two lines hide anything, measured once it is on screen (and again when the window changes size).
  useEffect(() => {
    const measure = () => {
      const text = body.current;
      if (text && !open) setLong(text.scrollHeight > text.clientHeight + 1);
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [open, item.body]);

  return (
    <li>
      <span className="tile"><Megaphone aria-hidden /></span>
      <div className="grow">
        <p className="head">
          <strong>{item.title}</strong>
          <span className="meta">
            <span>{formatWhen(item.created_at)}</span>
            {item.course && <span className="fact"><GraduationCap aria-hidden />{item.course}</span>}
          </span>
        </p>
        {item.body && <p ref={body} className={`body ${open ? "" : "clamp-2"}`}>{item.body}</p>}
        {(long || open) && (
          <button type="button" className="text-button" aria-expanded={open} onClick={() => setOpen((shown) => !shown)}>
            {open ? "Less" : "More"}
          </button>
        )}
      </div>
    </li>
  );
}

// The newest announcements, for everyone and for the reader's courses.
export default function Announcements({ items }: { items: Announcement[] }) {
  if (items.length === 0) return null;
  return (
    <section aria-labelledby="announcements">
      <h2 id="announcements">Announcements</h2>
      <ul className="list news">
        {items.slice(0, 5).map((item) => <Row key={item.id} item={item} />)}
      </ul>
    </section>
  );
}
