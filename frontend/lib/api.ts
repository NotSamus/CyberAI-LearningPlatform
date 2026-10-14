// A student's handed-in notebook and its grade. "submitted": waiting for a teacher to grade it by
// hand. "queued" and "grading": with the autograder. "failed": the autograder could not run it.
export type SubmissionSummary = {
  submitted_at: string;
  late: boolean;
  status: "submitted" | "queued" | "grading" | "graded" | "failed";
  attempt: number;            // 2 after the first resubmission, and so on
  score: number | null;
  max_score: number | null;
};

// Teachers also get `output` (it describes the hidden tests) and `error` (the autograder's log).
export type Question = { name: string; score: number; max_score: number; output?: string };

// Whether a question's public tests passed. Students get no text from Otter: the student's code runs
// with the tests, so that text could carry what it read from the hidden ones (api/app/grading.py).
export type PublicTest = { name: string; passed: boolean };

export type Submission = SubmissionSummary & {
  feedback: string;           // the teacher's comment
  graded_at: string | null;
  graded_by_teacher: boolean;
  questions: Question[];
  public_tests: PublicTest[];
  public_output?: string;     // teachers only: what the public tests reported
  error: string | null;
};

export type Assignment = {
  id: number;
  title: string;
  description: string;
  requires_gpu: boolean;
  due_at: string | null;      // ISO date and time, or null when there is no due date
  published: boolean;         // false only for teachers looking at a draft: students never receive drafts
  course_id: number | null;
  course: string | null;      // the course's name
  autograded: boolean;        // graded by Otter-Grader when submitted; otherwise by the teacher
  points: number | null;      // the most a submission can score, when known
};

// With the logged-in person's own progress: in the list, and in full for one assignment.
export type MyAssignment = Assignment & { opened_at: string | null; submission: SubmissionSummary | null };
export type MyAssignmentDetail = Assignment & { opened_at: string | null; submission: Submission | null };

// What Teach > Assignments works with (teachers and admins only, see api/app/teach.py).
// How far an assignment's students have got. Only the students it is given to count, as in its gradebook.
export type AssignmentCounts = {
  given: number;
  opened: number;
  submitted: number;
  graded: number;
  to_grade: number;           // waiting for the teacher to grade them by hand
  failed: number;             // the autograder could not run them: the teacher looks at why
  late: number;
  oldest_waiting_at: string | null;
};

export type ManagedAssignment = Assignment & {
  slug: string;               // the folder name in each student's notebooks: assignments/<slug>/
  notebook_name: string;
  for_everyone: boolean;      // every student, including accounts created later
  student_ids: number[];      // the students it is given to by name
  created_at: string;
  counts?: AssignmentCounts;  // in the list of assignments (GET /teach/assignments) only
};

// One row of an assignment's gradebook.
export type StudentProgress = Student & { opened_at: string | null; submission: Submission | null };
export type Progress = { assignment: ManagedAssignment; students: StudentProgress[] };

export type Course = { id: number; name: string; student_ids: number[] };

export type Announcement = {
  id: number;
  title: string;
  body: string;
  course_id: number | null;   // null: for everyone
  course: string | null;
  created_at: string;
};

export type Student = { id: number; username: string; name: string };

export type Launch = { ready: boolean; profile: "cpu" | "gpu"; url: string };
export type Me = {
  id: number;
  username: string;
  name: string;
  role: string;
  is_admin: boolean;
  can_teach: boolean;         // teacher or admin. Only decides which links are shown: the server checks every request.
  gpu_enabled: boolean;
  theme: string;              // how the site looks for this account (lib/themes.ts)
};

export type Account = {
  id: number;
  username: string;
  name: string;
  role: string;
  is_admin: boolean;
  gpu_enabled: boolean;
  hub_username: string;
  created_at: string;
};

export type NewAccount = Account & { password: string };    // the password is sent once, at creation

export const HUB_ORIGIN = process.env.NEXT_PUBLIC_HUB_ORIGIN ?? "http://localhost:8081";

// JupyterHub keeps its own login cookie, separate from the platform's. It is cleared whenever the
// platform account in this browser changes (log out, and log in), so the hub can never stay signed
// in as the previous person; it signs in again as the current account when a notebook opens.
// Best effort: the hub may be down.
export async function endHubSession(): Promise<void> {
  await fetch(`${HUB_ORIGIN}/hub/logout`, { mode: "no-cors", credentials: "include" }).catch(() => {});
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, { credentials: "same-origin", ...init });
  if (res.status === 401 && window.location.pathname !== "/login") {
    // Not logged in, or the session ended: log in, then come back to this page.
    const here = window.location.pathname + window.location.search;
    window.location.assign(`/login?next=${encodeURIComponent(here)}`);
    return new Promise<T>(() => {});   // the page is leaving; nothing more to show
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail ?? `Request failed (${res.status})`);
  return body as T;
}
