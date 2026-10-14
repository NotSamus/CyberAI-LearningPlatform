import { CircleAlert } from "lucide-react";
import type { Standing } from "@/components/Status";
import type { Course, ManagedAssignment, Student } from "@/lib/api";
import type { ManagedLesson } from "@/lib/lessons";

// Who a lesson or an assignment is given to, in a few words, for the lists of the Teach area.

// Published, but no student can see it: the one case where who it is for is a problem.
export const GIVEN_TO_NOBODY: Standing = { text: "Given to nobody", tone: "bad", icon: CircleAlert };

// An assignment is given to a course, to everyone, or to students chosen by name; nobody until one of these is set.
export function givenToNobody(a: ManagedAssignment): boolean {
  return !a.for_everyone && a.course_id === null && a.student_ids.length === 0;
}

// A lesson is for a course or for everyone; there is no choosing students by name.
export function lessonForNobody(lesson: ManagedLesson): boolean {
  return !lesson.for_everyone && lesson.course_id === null;
}

export function assignmentFor(a: ManagedAssignment, students: Student[], courses: Course[]): string {
  if (a.for_everyone) return "All students";
  if (givenToNobody(a)) return "Given to nobody yet";
  const names = students.filter((s) => a.student_ids.includes(s.id)).map((s) => s.name);
  const chosen = names.length === 0 ? "" : names.length <= 3 ? names.join(", ") : `${names.length} students`;
  const course = courses.find((c) => c.id === a.course_id)?.name ?? a.course;
  return [course, chosen].filter(Boolean).join(" and ");
}

// Whom a lesson is for ("All students", a course and how many are in it), or null: nobody yet.
export function lessonFor(lesson: ManagedLesson, courses: Course[]): string | null {
  if (lesson.for_everyone) return "All students";
  const course = courses.find((c) => c.id === lesson.course_id);
  return course ? `${course.name} (${plural(course.student_ids.length, "student")})` : null;
}

export function plural(n: number, word: string): string {
  return `${n} ${n === 1 ? word : `${word}s`}`;
}
