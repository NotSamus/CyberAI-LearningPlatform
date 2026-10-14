"""Teacher API, used by the Settings sections for teachers: assignments (upload, give to students,
publish), each assignment's progress and grades, courses and announcements.

Every route checks on the server, for each request, that the account is a teacher or an admin.
Students get 403 here whatever the frontend shows or hides.
"""
import csv
import io
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from app import assignments, courses, grading, submissions
from app.db import get_db
from app.jupyter import hub_client
from app.jupyter.deps import PlatformUser, get_current_user_optional
from app.jupyter.launch import hub_errors, notebook_url, running_server
from app.models import Announcement, Assignment, Course, Submission, User

router = APIRouter(prefix="/api/teach", tags=["teach"])


def require_teacher(user: PlatformUser | None = Depends(get_current_user_optional)) -> PlatformUser:
    if user is None:
        raise HTTPException(401, "not logged in")
    if not user.can_teach:
        raise HTTPException(403, "This page is for teachers only.")
    return user


def _assignment_or_404(db: Session, assignment_id: int) -> Assignment:
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(404, "No such assignment.")
    return assignment


def _details(db: Session, assignment: Assignment) -> dict:
    return {
        **assignments.summary(assignment, courses.names(db)),
        "slug": assignment.slug,
        "notebook_name": assignment.notebook_name,
        "for_everyone": assignment.for_everyone,
        "student_ids": assignments.student_ids(db).get(assignment.id, []),
        "created_at": assignment.created_at.isoformat(),
    }


def _student(user: User) -> dict:
    return {"id": user.id, "username": user.username, "name": user.display_name}


def _download(content: bytes, filename: str, media_type: str = "application/x-ipynb+json") -> Response:
    """Always a download, never shown in the page: notebooks can contain HTML and scripts, which must
    not run on this site's address."""
    return Response(
        content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "X-Content-Type-Options": "nosniff"},
    )


@router.get("/students")
def list_students(teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    """The accounts an assignment can be given to."""
    students = db.scalars(select(User).where(User.role == "student").order_by(User.display_name, User.id))
    return [_student(s) for s in students]


# --- assignments ----------------------------------------------------------------------------------


@router.get("/assignments")
def list_assignments(teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    """Every assignment, each with how far its students have got (`counts`, see assignments.counts)."""
    course_names, given, counted = courses.names(db), assignments.student_ids(db), assignments.counts(db)
    return [
        {
            **assignments.summary(a, course_names),
            "slug": a.slug,
            "notebook_name": a.notebook_name,
            "for_everyone": a.for_everyone,
            "student_ids": given.get(a.id, []),
            "created_at": a.created_at.isoformat(),
            "counts": counted[a.id],
        }
        for a in db.scalars(select(Assignment).order_by(Assignment.id.desc()))
    ]


@router.post("/assignments", status_code=201)
async def create_assignment(request: Request, teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    """Stores an uploaded notebook as a new assignment. It starts as a draft given to nobody: the
    teacher then chooses who gets it and publishes it (PATCH below).

    A notebook written in Otter Assign format becomes an autograded assignment: Otter makes the
    version students get (solutions removed) and the autograder package, in the grading service.
    That takes as long as running the notebook takes. Any other notebook is stored as it is.

    A web form with the fields `title`, `file` and optionally `description`, `requires_gpu`, `due_at`.
    The form is read here and not declared as parameters, so that the account check above comes
    first: someone who is not a teacher is refused before the server takes in the file."""
    async with request.form() as form:
        file = form.get("file")
        title = form.get("title")
        if not isinstance(file, UploadFile) or not isinstance(title, str):
            raise HTTPException(422, "Send a title and a notebook file.")
        try:
            due_at = datetime.fromisoformat(form["due_at"]) if form.get("due_at") else None
        except (TypeError, ValueError):
            raise HTTPException(422, "The due date is not a valid date and time.")
        fields = dict(
            title=title,
            description=str(form.get("description") or ""),
            requires_gpu=str(form.get("requires_gpu") or "").lower() in ("true", "1", "on"),
            due_at=due_at,
            filename=file.filename or "",
            notebook=await file.read(assignments.MAX_NOTEBOOK_BYTES + 1),   # one byte more: enough to see it is too big
            created_by=teacher.id,
        )
    try:
        name = assignments.safe_notebook_name(fields["filename"])
        assignments.check_title(fields["title"])
        assignments.check_notebook(fields["notebook"])
        if grading.is_otter_master(fields["notebook"]):
            master = fields["notebook"]
            student, autograder = await grading.prepare(master, name, fields["requires_gpu"])
            fields.update(notebook=student, master=master, autograder=autograder, points=grading.total_points(student))
        assignment = await run_in_threadpool(lambda: assignments.create(db, **fields))
    except assignments.AssignmentError as e:
        raise HTTPException(400, str(e))
    except grading.GraderUnreachable:
        raise HTTPException(503, "The grading service is not reachable right now, so this autograded notebook was not uploaded. Try again in a minute.")
    except grading.GradingError as e:
        raise HTTPException(400, f"Otter could not prepare this notebook. {e}")
    return _details(db, assignment)


class Changes(BaseModel):
    """Only the fields that are sent are changed. `due_at: null` removes the due date, and
    `course_id: null` takes the assignment out of its course."""
    title: str | None = None
    description: str | None = None
    requires_gpu: bool | None = None
    due_at: datetime | None = None
    published: bool | None = None
    for_everyone: bool | None = None
    course_id: int | None = None
    student_ids: list[int] | None = Field(None, max_length=10_000)
    points: float | None = None         # what a hand-graded assignment is out of


@router.patch("/assignments/{assignment_id}")
def change_assignment(
    assignment_id: int, body: Changes, teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db),
):
    assignment = _assignment_or_404(db, assignment_id)
    sent = body.model_fields_set
    try:
        if body.title is not None:
            assignment.title = assignments.check_title(body.title)
        if body.description is not None:
            assignment.description = assignments.check_description(body.description)
        if "due_at" in sent:
            assignment.due_at = assignments.check_due_at(body.due_at)
        if "course_id" in sent:
            if body.course_id is not None and db.get(Course, body.course_id) is None:
                raise assignments.AssignmentError("That course does not exist.")
            assignment.course_id = body.course_id
        if body.student_ids is not None:
            assignments.set_students(db, assignment, body.student_ids)
        if "points" in sent and body.points != assignment.points:
            if assignment.autograded:
                raise assignments.AssignmentError("The points of an autograded assignment come from its tests.")
            assignment.points = assignments.check_points(body.points)
    except assignments.AssignmentError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    for flag in ("requires_gpu", "published", "for_everyone"):
        if getattr(body, flag) is not None:
            setattr(assignment, flag, getattr(body, flag))
    db.commit()
    return _details(db, assignment)


@router.delete("/assignments/{assignment_id}")
def delete_assignment(assignment_id: int, teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    """Removes the assignment from the platform, with its submissions and grades. Copies students
    already opened stay in their own notebook folders: their work there is never deleted from here."""
    db.delete(_assignment_or_404(db, assignment_id))
    db.commit()
    return {"deleted": True}


@router.get("/assignments/{assignment_id}/notebook")
def download_notebook(assignment_id: int, teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    """The notebook students get."""
    assignment = _assignment_or_404(db, assignment_id)
    return _download(assignments.notebook_bytes(db, assignment.id), assignment.notebook_name)


@router.get("/assignments/{assignment_id}/master")
def download_master(assignment_id: int, teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    """An autograded assignment as the teacher uploaded it: with solutions and hidden tests."""
    assignment = _assignment_or_404(db, assignment_id)
    master = db.scalar(select(Assignment.master).where(Assignment.id == assignment.id))
    if master is None:
        raise HTTPException(404, "This assignment has no separate version with solutions.")
    return _download(master, f"with-solutions-{assignment.notebook_name}")


# --- progress and grades --------------------------------------------------------------------------

def _progress(db: Session, assignment: Assignment) -> list[dict]:
    """A row for every student the assignment is given to."""
    opened = assignments.opens_of(db, assignment.id)
    submitted = submissions.of_assignment(db, assignment.id)
    return [
        {
            **_student(student),
            "opened_at": opened[student.id].isoformat() if student.id in opened else None,
            "submission": submissions.details(submitted[student.id], for_teacher=True) if student.id in submitted else None,
        }
        for student in assignments.audience(db, assignment)
    ]


@router.get("/assignments/{assignment_id}/progress")
def assignment_progress(assignment_id: int, teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    """Every student the assignment is given to: whether they opened it, their submission, their grade."""
    assignment = _assignment_or_404(db, assignment_id)
    return {"assignment": _details(db, assignment), "students": _progress(db, assignment)}


def _spreadsheet_safe(text: str) -> str:
    """Spreadsheet programs run a cell that starts with one of these as a formula."""
    return "'" + text if text.startswith(("=", "+", "-", "@")) else text


@router.get("/assignments/{assignment_id}/grades.csv")
def download_grades(assignment_id: int, teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    assignment = _assignment_or_404(db, assignment_id)
    out = io.StringIO()
    table = csv.writer(out)
    table.writerow(["Name", "Username", "Opened", "Submitted", "Late", "Status", "Score", "Out of"])
    for row in _progress(db, assignment):
        submission = row["submission"] or {}
        table.writerow([
            _spreadsheet_safe(row["name"]), row["username"], row["opened_at"] or "",
            submission.get("submitted_at") or "", "late" if submission.get("late") else "",
            submission.get("status") or ("opened" if row["opened_at"] else "not started"),
            "" if submission.get("score") is None else submission["score"],
            "" if submission.get("max_score") is None else submission["max_score"],
        ])
    return _download(out.getvalue().encode(), f"{assignment.slug}-grades.csv", "text/csv; charset=utf-8")


def _submission_or_404(db: Session, assignment_id: int, user_id: int) -> tuple[Assignment, Submission, User]:
    assignment = _assignment_or_404(db, assignment_id)
    submission, student = submissions.get(db, assignment.id, user_id), db.get(User, user_id)
    if submission is None or student is None:
        raise HTTPException(404, "This student has not submitted this assignment.")
    return assignment, submission, student


@router.get("/assignments/{assignment_id}/submissions/{user_id}/notebook")
def download_submission(assignment_id: int, user_id: int, teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    assignment, submission, student = _submission_or_404(db, assignment_id, user_id)
    return _download(submissions.notebook_bytes(db, submission.id), f"{student.username}-{assignment.notebook_name}")


@router.post("/assignments/{assignment_id}/submissions/{user_id}/open")
async def open_submission(assignment_id: int, user_id: int, teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    """Puts a copy of what the student submitted into the teacher's own Jupyter home, replacing the
    copy of an earlier submission, and says where to open it. The student's files are not touched."""
    assignment, submission, student = await run_in_threadpool(_submission_or_404, db, assignment_id, user_id)
    notebook = await run_in_threadpool(submissions.notebook_bytes, db, submission.id)
    # Under its original file name: an autograded notebook looks for its tests by that name.
    path = f"submissions/{assignment.slug}/{student.username}/{assignment.notebook_name}"
    with hub_errors():
        await running_server(teacher, "cpu")
        await hub_client.put_file(teacher.hub_username, "cpu", path, notebook)
    return {"ready": True, "profile": "cpu", "url": notebook_url(teacher, "cpu", path)}


@router.post("/assignments/{assignment_id}/submissions/{user_id}/regrade")
def regrade_submission(
    assignment_id: int, user_id: int, background: BackgroundTasks,
    teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db),
):
    """Sends a submission to the autograder again."""
    assignment, submission, _ = _submission_or_404(db, assignment_id, user_id)
    if not assignment.autograded:
        raise HTTPException(400, "This assignment has no autograder: give the score by hand.")
    submissions.queue_again(db, submission)
    background.add_task(submissions.grade_submission, submission.id, submission.attempt)
    return submissions.details(submission, for_teacher=True)


class Grade(BaseModel):
    """A teacher's own score (replacing the autograder's, if any) and/or a comment for the student."""
    score: float | None = None
    feedback: str | None = Field(None, max_length=5000)


@router.patch("/assignments/{assignment_id}/submissions/{user_id}")
def grade_submission(
    assignment_id: int, user_id: int, body: Grade,
    teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db),
):
    assignment, submission, _ = _submission_or_404(db, assignment_id, user_id)
    try:
        submissions.grade_by_hand(db, submission, assignment, teacher.id, body.score, body.feedback)
    except ValueError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    return submissions.details(submission, for_teacher=True)


# --- courses --------------------------------------------------------------------------------------

def _course_or_404(db: Session, course_id: int) -> Course:
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(404, "No such course.")
    return course


def _course(db: Session, course: Course) -> dict:
    return {"id": course.id, "name": course.name, "student_ids": courses.student_ids(db).get(course.id, [])}


@router.get("/courses")
def list_courses(teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    members = courses.student_ids(db)
    return [
        {"id": course.id, "name": course.name, "student_ids": members.get(course.id, [])}
        for course in db.scalars(select(Course).order_by(Course.name))
    ]


class NewCourse(BaseModel):
    name: str


@router.post("/courses", status_code=201)
def create_course(body: NewCourse, teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    try:
        course = Course(name=courses.check_name(body.name), created_by=teacher.id)
        courses.save(db, course)
    except courses.CourseError as e:
        raise HTTPException(400, str(e))
    return _course(db, course)


class CourseChanges(BaseModel):
    name: str | None = None
    student_ids: list[int] | None = Field(None, max_length=10_000)


@router.patch("/courses/{course_id}")
def change_course(
    course_id: int, body: CourseChanges, teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db),
):
    course = _course_or_404(db, course_id)
    try:
        if body.student_ids is not None:
            courses.set_students(db, course, body.student_ids)
        if body.name is not None:
            course.name = courses.check_name(body.name)
        courses.save(db, course)
    except courses.CourseError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    return _course(db, course)


@router.delete("/courses/{course_id}")
def delete_course(course_id: int, teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    """Removes the course and its announcements. Its assignments stay, no longer given to a course:
    students lose sight of them until a teacher gives them to someone again."""
    db.delete(_course_or_404(db, course_id))
    db.commit()
    return {"deleted": True}


# --- announcements --------------------------------------------------------------------------------

@router.get("/announcements")
def list_announcements(teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    course_names = courses.names(db)
    return [courses.announcement(item, course_names) for item in courses.announcements_for(db, teacher, limit=200)]


class NewAnnouncement(BaseModel):
    title: str
    body: str = ""
    course_id: int | None = None        # None: for everyone


@router.post("/announcements", status_code=201)
def create_announcement(body: NewAnnouncement, teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    if body.course_id is not None:
        _course_or_404(db, body.course_id)
    try:
        title, text = courses.check_announcement(body.title, body.body)
    except courses.CourseError as e:
        raise HTTPException(400, str(e))
    item = Announcement(title=title, body=text, course_id=body.course_id, created_by=teacher.id)
    db.add(item)
    db.commit()
    return courses.announcement(item, courses.names(db))


@router.delete("/announcements/{announcement_id}")
def delete_announcement(announcement_id: int, teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    item = db.get(Announcement, announcement_id)
    if item is None:
        raise HTTPException(404, "No such announcement.")
    db.delete(item)
    db.commit()
    return {"deleted": True}
