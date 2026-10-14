import type { MyAssignment } from "@/lib/api";
import type { MyLesson } from "@/lib/lessons";

// Lessons and assignments that belong to no course are for every student: they are listed under
// this name, on Home and in the "you are here" line of their pages.
export const FOR_EVERYONE = "For all students";

export function courseName(course: string | null): string {
  return course ?? FOR_EVERYONE;
}

export type CourseGroup = { id: number | null; course: string | null; lessons: MyLesson[]; assignments: MyAssignment[] };

// One group per course, with its lessons (in the order the teachers put them in) and its
// assignments (as the server sends them: soonest due date first). Courses come in the order their
// first lesson does; what belongs to no course comes last.
export function byCourse(lessons: MyLesson[], assignments: MyAssignment[]): CourseGroup[] {
  const groups = new Map<number | null, CourseGroup>();
  const group = (item: MyLesson | MyAssignment) => {
    if (!groups.has(item.course_id)) groups.set(item.course_id, { id: item.course_id, course: item.course, lessons: [], assignments: [] });
    return groups.get(item.course_id)!;
  };
  for (const lesson of lessons) if (lesson.course_id !== null) group(lesson).lessons.push(lesson);
  for (const assignment of assignments) if (assignment.course_id !== null) group(assignment).assignments.push(assignment);
  for (const lesson of lessons) if (lesson.course_id === null) group(lesson).lessons.push(lesson);
  for (const assignment of assignments) if (assignment.course_id === null) group(assignment).assignments.push(assignment);
  return [...groups.values()];
}
