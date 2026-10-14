"use client";
import { Search } from "lucide-react";
import { useState } from "react";
import type { Student } from "@/lib/api";

// Choosing students: the members of a course, or who gets an assignment. A search narrows the list
// by name or username; "Select all" and "Select none" act on the students the list shows.
export default function StudentPicker({ students, chosen, onChange }: {
  students: Student[];
  chosen: number[];
  onChange: (ids: number[]) => void;
}) {
  const [search, setSearch] = useState("");

  if (students.length === 0) {
    return <p className="muted">There are no student accounts yet. An admin adds them under Admin, Accounts.</p>;
  }

  const words = search.trim().toLowerCase();
  const shown = words ? students.filter((s) => `${s.name} ${s.username}`.toLowerCase().includes(words)) : students;
  const shownIds = shown.map((s) => s.id);

  function toggle(id: number) {
    onChange(chosen.includes(id) ? chosen.filter((i) => i !== id) : [...chosen, id]);
  }

  return (
    <div className="picker">
      <div className="picker-bar">
        <label className="search">
          <Search aria-hidden />
          <input type="search" placeholder="Find a student" aria-label="Find a student" value={search} onChange={(e) => setSearch(e.target.value)} />
        </label>
        <button type="button" className="secondary" onClick={() => onChange([...new Set([...chosen, ...shownIds])])}>Select all</button>
        <button type="button" className="secondary" onClick={() => onChange(chosen.filter((id) => !shownIds.includes(id)))}>Select none</button>
        <span className="muted">{chosen.length} of {students.length} chosen</span>
      </div>
      {shown.length === 0
        ? <p className="muted">No student matches “{search.trim()}”.</p>
        : (
          <div className="students">
            {shown.map((s) => (
              <label key={s.id} className="check">
                <input type="checkbox" checked={chosen.includes(s.id)} onChange={() => toggle(s.id)} />
                <span>{s.name} <span className="muted">({s.username})</span></span>
              </label>
            ))}
          </div>
        )}
    </div>
  );
}
