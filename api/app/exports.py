"""Students' progress and grades as a file, for teachers: the students of one course, or every
student on the platform. The file is made here, so who may have it is checked on the server, as on
every teacher route: teachers and admins get it, students get 403.

One row per student, by username (the platform keeps no real names): their course(s), lessons
completed out of those given to them, knowledge checks answered and correct out of the checks in
those lessons, the status and score of each assignment, then totals. Only what is published counts,
as students never see drafts. A course's file has the course's own lessons and assignments and the
ones given to every student. The whole platform's has all of them; an assignment's cells are left
empty for a student it was not given to.

As CSV (UTF-8 with a byte order mark, so Excel reads accents right) or as an Excel workbook: one
sheet for a course; for the whole platform an "All students" sheet, the same as the CSV, then a
sheet per course.
"""
import csv
import io
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.orm import Session, undefer

from app import lessons
from app.db import get_db
from app.jupyter.deps import PlatformUser
from app.models import (
    Assignment, AssignmentOpen, AssignmentStudent, Course, CourseStudent, Lesson, LessonAnswer, LessonProgress,
    Submission, User,
)
from app.submissions import DEFAULT_POINTS
from app.teach import require_teacher

router = APIRouter(prefix="/api/teach", tags=["exports"])

Kind = Literal["csv", "xlsx"]
MEDIA_TYPES = {"csv": "text/csv; charset=utf-8", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}


# --- what the files are made from -----------------------------------------------------------------

@dataclass
class Platform:
    """Everything on the platform the files are made from, read in a few queries for every student
    at once rather than a few per student."""
    students: list[tuple[int, str]]                 # (id, username), by username
    courses: list[Course]                           # by name
    members: dict[int, set[int]]                    # course id -> its students
    lessons: list[Lesson]                           # the published ones
    checks: dict[int, set[str]]                     # lesson id -> the ids of its published knowledge checks
    answers: dict[tuple[int, int], list[bool]]      # (lesson id, user id) -> for each check answered: correct?
    completed: set[tuple[int, int]]                 # (lesson id, user id)
    assignments: list[Assignment]                   # the published ones, soonest due first
    by_name: dict[int, set[int]]                    # assignment id -> the students given it by name
    opened: set[tuple[int, int]]                    # (assignment id, user id)
    handed_in: dict[tuple[int, int], object]        # (assignment id, user id) -> the submission's status and score


def load(db: Session) -> Platform:
    members: dict[int, set[int]] = {}
    for row in db.execute(select(CourseStudent.course_id, CourseStudent.user_id)):
        members.setdefault(row.course_id, set()).add(row.user_id)
    published = list(db.scalars(select(Lesson).options(undefer(Lesson.live_blocks)).where(Lesson.published)))
    checks = {lesson.id: {block["id"] for block in lesson.live_blocks if lessons.is_check(block)} for lesson in published}
    answers: dict[tuple[int, int], list[bool]] = {}
    for row in db.execute(select(LessonAnswer.lesson_id, LessonAnswer.user_id, LessonAnswer.block_id, LessonAnswer.correct)):
        if row.block_id in checks.get(row.lesson_id, ()):        # not an answer to a question since taken out
            answers.setdefault((row.lesson_id, row.user_id), []).append(row.correct)
    by_name: dict[int, set[int]] = {}
    for row in db.execute(select(AssignmentStudent.assignment_id, AssignmentStudent.user_id)):
        by_name.setdefault(row.assignment_id, set()).add(row.user_id)
    handed_in = db.execute(select(Submission.assignment_id, Submission.user_id, Submission.status, Submission.late, Submission.score, Submission.max_score))
    return Platform(
        students=[(row.id, row.username) for row in db.execute(select(User.id, User.username).where(User.role == "student").order_by(User.username))],
        courses=list(db.scalars(select(Course).order_by(Course.name))),
        members=members,
        lessons=published,
        checks=checks,
        answers=answers,
        completed={(row.lesson_id, row.user_id) for row in db.execute(
            select(LessonProgress.lesson_id, LessonProgress.user_id).where(LessonProgress.completed_at.is_not(None))
        )},
        assignments=list(db.scalars(select(Assignment).where(Assignment.published).order_by(Assignment.due_at.asc().nulls_last(), Assignment.id))),
        by_name=by_name,
        opened={(row.assignment_id, row.user_id) for row in db.execute(select(AssignmentOpen.assignment_id, AssignmentOpen.user_id))},
        handed_in={(row.assignment_id, row.user_id): row for row in handed_in},
    )


def status(submission, opened: bool) -> str:
    """Where a student is with an assignment. `late`: handed in after the due date, no grade yet."""
    if submission is None:
        return "opened" if opened else "not started"
    if submission.status == "graded":
        return "graded late" if submission.late else "graded"
    if submission.status == "failed":
        return "could not be graded"
    return "late" if submission.late else "submitted"      # waiting for a teacher, or with the autograder


def _number(value: float | None) -> int | float | None:
    """8.0 as 8: scores are stored as decimals, and most are whole."""
    return int(value) if value is not None and float(value).is_integer() else value


def _out_of(assignment: Assignment) -> float | None:
    """What a submission is graded out of, as the gradebook does (app/submissions.py)."""
    if assignment.points is not None:
        return assignment.points
    return None if assignment.autograded else DEFAULT_POINTS


@dataclass
class Table:
    name: str                   # the sheet's name in the workbook
    header: list[str]
    rows: list[list]            # text, numbers, or None for an empty cell


def table(platform: Platform, course: Course | None = None) -> Table:
    """The students of `course` with its lessons and assignments, or with None every student and
    everything published."""
    if course is None:
        students, given_lessons, given_assignments = platform.students, platform.lessons, platform.assignments
    else:
        students = [s for s in platform.students if s[0] in platform.members.get(course.id, set())]
        given_lessons = [x for x in platform.lessons if x.for_everyone or x.course_id == course.id]
        given_assignments = [a for a in platform.assignments if a.for_everyone or a.course_id == course.id]

    header = ["Username", "Courses" if course is None else "Course",
              "Lessons completed", "Lessons given", "Checks answered", "Checks correct", "Checks given"]
    for assignment in given_assignments:
        out_of = _out_of(assignment)
        header += [f"{assignment.title}: status", f"{assignment.title}: score" + (f" (of {_number(out_of)})" if out_of is not None else "")]
    header += ["Assignments submitted", "Assignments given", "Total score", "Total out of"]

    rows = []
    for user_id, username in students:
        in_courses = {course_id for course_id, ids in platform.members.items() if user_id in ids}
        mine = [x for x in given_lessons if x.for_everyone or x.course_id in in_courses]
        answered = [correct for x in mine for correct in platform.answers.get((x.id, user_id), [])]
        row = [
            username,
            "; ".join(c.name for c in platform.courses if c.id in in_courses) if course is None else course.name,
            sum((x.id, user_id) in platform.completed for x in mine), len(mine),
            len(answered), sum(answered), sum(len(platform.checks[x.id]) for x in mine),
        ]
        submitted = given = 0
        score = out_of = 0.0
        for assignment in given_assignments:
            if not (assignment.for_everyone or assignment.course_id in in_courses or user_id in platform.by_name.get(assignment.id, set())):
                row += [None, None]         # not given to this student
                continue
            submission = platform.handed_in.get((assignment.id, user_id))
            graded = submission is not None and submission.status == "graded"
            row += [status(submission, (assignment.id, user_id) in platform.opened), _number(submission.score) if graded else None]
            given += 1
            submitted += submission is not None
            if graded:
                score += submission.score or 0
                out_of += submission.max_score or _out_of(assignment) or 0
        rows.append(row + [submitted, given, _number(score), _number(out_of)])
    return Table(name="All students" if course is None else course.name, header=header, rows=rows)


# --- the files ------------------------------------------------------------------------------------

def plain_text(text: str) -> str:
    """Spreadsheet programs run a cell that starts with one of these as a formula ("=HYPERLINK(...)"),
    and course names and assignment titles are typed by people. A quote in front keeps it text."""
    return "'" + text if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text


def to_csv(sheet: Table) -> bytes:
    out = io.StringIO()
    out.write("\ufeff")         # tells Excel the file is UTF-8
    writer = csv.writer(out)
    for values in [sheet.header, *sheet.rows]:
        writer.writerow(["" if v is None else plain_text(v) if isinstance(v, str) else v for v in values])
    return out.getvalue().encode("utf-8")


def _sheet_name(name: str, used: set[str]) -> str:
    """Excel's rules for a sheet's name: at most 31 characters, none of []:*?/\\, not starting or
    ending with a quote, no two alike (capitals aside), and not "History", which Excel keeps."""
    base = re.sub(r"[\[\]:*?/\\]", " ", ILLEGAL_CHARACTERS_RE.sub("", name)).strip(" '")[:31].strip(" '") or "Course"
    if base.lower() == "history":
        base = "History course"
    candidate, n = base, 2
    while candidate.lower() in used:
        suffix = f" ({n})"
        candidate, n = base[: 31 - len(suffix)].rstrip(" '") + suffix, n + 1
    used.add(candidate.lower())
    return candidate


def to_xlsx(sheets: list[Table]) -> bytes:
    book = Workbook()
    book.remove(book.active)
    used: set[str] = set()
    for sheet in sheets:
        page = book.create_sheet(_sheet_name(sheet.name, used))
        for r, values in enumerate([sheet.header, *sheet.rows], start=1):
            for c, value in enumerate(values, start=1):
                cell = page.cell(r, c, ILLEGAL_CHARACTERS_RE.sub("", value) if isinstance(value, str) else value)
                if isinstance(value, str):
                    cell.data_type = "s"        # text stays text, even "=HYPERLINK(...)": never a formula
                if r == 1:
                    cell.font = Font(bold=True)
        for c, title in enumerate(sheet.header, start=1):
            page.column_dimensions[get_column_letter(c)].width = min(max(len(title), 8) + 2, 40)
        page.freeze_panes = "B2"            # the header and the usernames stay in view
        page.auto_filter.ref = f"A1:{get_column_letter(len(sheet.header))}{len(sheet.rows) + 1}"
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def file_stem(name: str, fallback: str = "course") -> str:
    """A name as part of a file name: "Programación 1, sección 2" -> "programacion-1-seccion-2"."""
    letters = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", letters.lower()).strip("-")[:40].strip("-") or fallback


def _download(content: bytes, stem: str, kind: Kind) -> Response:
    """A download, kept out of the browser's cache: it is students' records."""
    return Response(content, media_type=MEDIA_TYPES[kind], headers={
        "Content-Disposition": f'attachment; filename="{stem}-students-{date.today().isoformat()}.{kind}"',
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "no-store",
    })


@router.get("/students.{kind}")
def export_everyone(kind: Kind, teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    """Every student on the platform. As a workbook: an "All students" sheet, then one per course."""
    platform = load(db)
    everyone = table(platform)
    content = to_csv(everyone) if kind == "csv" else to_xlsx([everyone, *(table(platform, c) for c in platform.courses)])
    return _download(content, "all", kind)


@router.get("/courses/{course_id}/students.{kind}")
def export_course(course_id: int, kind: Kind, teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    """The students of one course, with the course's lessons and assignments and those for everyone."""
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(404, "No such course.")
    sheet = table(load(db), course)
    return _download(to_csv(sheet) if kind == "csv" else to_xlsx([sheet]), file_stem(course.name), kind)
