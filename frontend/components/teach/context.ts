"use client";
import { createContext, useContext } from "react";
import type { Course, Progress } from "@/lib/api";

// What the layout of one assignment or one course has loaded, for the tabs under its header: they
// share it rather than each asking the server again.

// An assignment and its gradebook (GET /teach/assignments/{id}/progress). `reload` asks again.
export type AssignmentPage = { progress: Progress; reload: () => Promise<void> };
export const AssignmentContext = createContext<AssignmentPage | null>(null);

export function useAssignmentPage(): AssignmentPage {
  const page = useContext(AssignmentContext);
  if (!page) throw new Error("Only inside the layout of an assignment (app/teach/assignments/[id]/layout.tsx).");
  return page;
}

// A course, with every course (for the lists that say who a lesson is for). `newLesson` opens the
// header's "New lesson" dialog.
export type CoursePage = { course: Course; courses: Course[]; reload: () => Promise<void>; newLesson: () => void };
export const CourseContext = createContext<CoursePage | null>(null);

export function useCoursePage(): CoursePage {
  const page = useContext(CourseContext);
  if (!page) throw new Error("Only inside the layout of a course (app/teach/courses/[id]/layout.tsx).");
  return page;
}
