"use client";
import { CalendarClock, Globe, Megaphone, School, Trash2 } from "lucide-react";
import Menu from "@/components/Menu";
import { api, type Announcement } from "@/lib/api";
import { formatWhen } from "@/lib/dates";
import { message } from "@/lib/errors";

// Announcements as rows of one list, newest first: on Teach > Announcements, and on a course's
// Announcements tab (`withinCourse`: who each is for goes without saying there). Each can be deleted.
export default function AnnouncementRows({ items, withinCourse = false, onChanged, onError }: {
  items: Announcement[];
  withinCourse?: boolean;
  onChanged: () => void;
  onError: (message: string) => void;
}) {
  async function remove(item: Announcement) {
    if (!window.confirm(`Delete the announcement "${item.title}"?`)) return;
    onError("");
    try {
      await api(`/teach/announcements/${item.id}`, { method: "DELETE" });
      onChanged();
    } catch (e) {
      onError(message(e));
    }
  }

  return (
    <ul className="list">
      {items.map((item) => (
        <li key={item.id}>
          <span className="tile"><Megaphone aria-hidden /></span>
          <div className="grow">
            <strong>{item.title}</strong>
            <p className="meta">
              {!withinCourse && <span className="fact">{item.course ? <School aria-hidden /> : <Globe aria-hidden />}{item.course ?? "Everyone"}</span>}
              <span className="fact"><CalendarClock aria-hidden />{formatWhen(item.created_at)}</span>
            </p>
            {item.body && <p className="description body">{item.body}</p>}
          </div>
          <div className="row-actions">
            <Menu
              label={`More for ${item.title}`}
              items={[{ label: "Delete", icon: Trash2, danger: true, onSelect: () => remove(item) }]}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
