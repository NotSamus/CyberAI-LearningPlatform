"""Assignments: the notebooks teachers upload, and who gets them.

A teacher uploads an .ipynb file and it is stored in the database, as a draft given to nobody.
A student sees an assignment once it is published and given to them: to every student, to a course
they are in, or to them by name. Teachers and admins see all of them.

The teacher API that creates and changes assignments is app/teach.py. Students open them through
app/jupyter/launch.py, which puts a copy of the notebook into their Jupyter home.
"""
import re
import secrets
import warnings
from datetime import datetime, timezone

import nbformat
from sqlalchemy import and_, delete, exists, or_, select, true
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.jupyter.deps import PlatformUser
from app.models import Assignment, AssignmentOpen, AssignmentStudent, CourseStudent, User

MAX_NOTEBOOK_BYTES = 10 * 1024 * 1024      # room for plots and images in the outputs
MAX_SUBMISSION_BYTES = 2 * MAX_NOTEBOOK_BYTES   # a student's copy grows as they run it
MAX_POINTS = 10_000
MAX_TITLE_LENGTH = 120
MAX_DESCRIPTION_LENGTH = 2000


class AssignmentError(ValueError):
    """An upload or a change that cannot be accepted. The message is safe to show to the person."""


# --- who sees what --------------------------------------------------------------------------------

def _visible_to(user: PlatformUser):
    """The condition for the assignments this user may see and open."""
    if user.can_teach:
        return true()
    given_by_name = exists().where(
        AssignmentStudent.assignment_id == Assignment.id, AssignmentStudent.user_id == user.id
    )
    in_their_course = exists().where(
        CourseStudent.course_id == Assignment.course_id, CourseStudent.user_id == user.id
    )
    return and_(Assignment.published, or_(Assignment.for_everyone, given_by_name, in_their_course))


def list_visible(db: Session, user: PlatformUser) -> list[Assignment]:
    """Soonest due date first, then the ones without a due date, oldest first."""
    return list(db.scalars(
        select(Assignment).where(_visible_to(user)).order_by(Assignment.due_at.asc().nulls_last(), Assignment.id)
    ))


def get_visible(db: Session, user: PlatformUser, assignment_id: int) -> Assignment | None:
    return db.scalar(select(Assignment).where(Assignment.id == assignment_id, _visible_to(user)))


def notebook_bytes(db: Session, assignment_id: int) -> bytes:
    return db.scalar(select(Assignment.notebook).where(Assignment.id == assignment_id))


def summary(assignment: Assignment, course_names: dict[int, str]) -> dict:
    """What every logged-in person may know about an assignment they can see."""
    return {
        "id": assignment.id,
        "title": assignment.title,
        "description": assignment.description,
        "requires_gpu": assignment.requires_gpu,
        "due_at": assignment.due_at.isoformat() if assignment.due_at else None,
        "published": assignment.published,
        "course_id": assignment.course_id,
        "course": course_names.get(assignment.course_id) if assignment.course_id else None,
        "autograded": assignment.autograded,
        "points": assignment.points,
    }


def audience(db: Session, assignment: Assignment) -> list[User]:
    """The students this assignment is given to, by name."""
    query = select(User).where(User.role == "student")
    if not assignment.for_everyone:
        by_name = select(AssignmentStudent.user_id).where(AssignmentStudent.assignment_id == assignment.id)
        in_course = select(CourseStudent.user_id).where(CourseStudent.course_id == assignment.course_id)
        query = query.where(or_(User.id.in_(by_name), User.id.in_(in_course)))
    return list(db.scalars(query.order_by(User.display_name, User.id)))


# --- who has opened what --------------------------------------------------------------------------

def record_open(db: Session, assignment_id: int, user_id: int) -> None:
    """Remembers the first time this person opened this assignment."""
    db.execute(insert(AssignmentOpen).values(assignment_id=assignment_id, user_id=user_id).on_conflict_do_nothing())
    db.commit()


def opened_by(db: Session, user_id: int) -> dict[int, datetime]:
    """assignment id -> when this person first opened it."""
    rows = db.execute(select(AssignmentOpen.assignment_id, AssignmentOpen.opened_at).where(AssignmentOpen.user_id == user_id))
    return {row.assignment_id: row.opened_at for row in rows}


def opens_of(db: Session, assignment_id: int) -> dict[int, datetime]:
    """user id -> when they first opened this assignment."""
    rows = db.execute(select(AssignmentOpen.user_id, AssignmentOpen.opened_at).where(AssignmentOpen.assignment_id == assignment_id))
    return {row.user_id: row.opened_at for row in rows}


# --- checks on what a teacher sends ---------------------------------------------------------------

def check_title(title: str) -> str:
    title = title.strip()
    if not 1 <= len(title) <= MAX_TITLE_LENGTH:
        raise AssignmentError(f"Titles are 1 to {MAX_TITLE_LENGTH} characters.")
    return title


def check_description(description: str) -> str:
    description = description.strip()
    if len(description) > MAX_DESCRIPTION_LENGTH:
        raise AssignmentError(f"Descriptions are at most {MAX_DESCRIPTION_LENGTH} characters.")
    return description


def check_points(points: float | None) -> float | None:
    if points is not None and not 0 < points <= MAX_POINTS:
        raise AssignmentError(f"Points are a number above 0, up to {MAX_POINTS}.")
    return points


def check_due_at(due_at: datetime | None) -> datetime | None:
    if due_at is not None and due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=timezone.utc)
    return due_at


def safe_notebook_name(filename: str) -> str:
    """The uploaded file's name, reduced to a plain file name: never a path, no odd characters."""
    name = re.split(r"[/\\]", filename or "")[-1]
    if not name.lower().endswith(".ipynb"):
        raise AssignmentError("Choose a Jupyter notebook: a file ending in .ipynb.")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", name[: -len(".ipynb")]).strip("._-")[:80]
    return f"{stem or 'notebook'}.ipynb"


def check_notebook(data: bytes, max_bytes: int | None = None) -> None:
    """Refuses anything that is not a notebook JupyterLab can open."""
    max_bytes = max_bytes or MAX_NOTEBOOK_BYTES
    if len(data) > max_bytes:
        megabytes = max_bytes // (1024 * 1024)
        raise AssignmentError(f"The notebook is larger than {megabytes} MB. Clear its outputs and try again.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")     # e.g. cells without ids, which older Jupyter versions write
            notebook = nbformat.reads(data.decode("utf-8"), as_version=nbformat.NO_CONVERT)
            version = notebook.nbformat
            nbformat.validate(notebook)
    except Exception:       # many kinds, for the many ways a file can be wrong (not text, not JSON, not a notebook...)
        raise AssignmentError("This file is not a valid Jupyter notebook.")
    if version != 4:
        raise AssignmentError("This notebook is in an old format. Open it in Jupyter, save it, and upload it again.")


def _folder_name(title: str, assignment_id: int) -> str:
    """The assignment's folder in students' homes, e.g. "Python basics", id 7 -> "python-basics-7".
    The id makes it one of a kind for good: a folder name is never used again after its assignment
    is deleted, so a student who opened the old one cannot be left with its file under a new one."""
    words = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40].strip("-") or "assignment"
    return f"{words}-{assignment_id}"


# --- changes --------------------------------------------------------------------------------------

def create(
    db: Session,
    *,
    title: str,
    filename: str,
    notebook: bytes,
    description: str = "",
    requires_gpu: bool = False,
    due_at: datetime | None = None,
    published: bool = False,
    for_everyone: bool = False,
    created_by: int | None = None,
    master: bytes | None = None,
    autograder: bytes | None = None,
    points: float | None = None,
) -> Assignment:
    """`master` and `autograder` are given for an autograded assignment (see app/grading.py);
    `notebook` is then the version Otter made for students."""
    title = check_title(title)
    notebook_name = safe_notebook_name(filename)
    check_notebook(notebook)
    assignment = Assignment(
        slug=secrets.token_hex(16),         # placeholder: the real one needs the id, known after the insert
        title=title,
        description=check_description(description),
        requires_gpu=requires_gpu,
        notebook_name=notebook_name,
        notebook=notebook,
        master=master,
        autograder=autograder,
        autograded=autograder is not None,
        points=points,
        published=published,
        for_everyone=for_everyone,
        due_at=check_due_at(due_at),
        created_by=created_by,
    )
    db.add(assignment)
    db.flush()
    assignment.slug = _folder_name(title, assignment.id)
    db.commit()
    return assignment


def student_ids(db: Session) -> dict[int, list[int]]:
    """assignment id -> the students it was given to by name."""
    given: dict[int, list[int]] = {}
    for row in db.execute(select(AssignmentStudent.assignment_id, AssignmentStudent.user_id).order_by(AssignmentStudent.user_id)):
        given.setdefault(row.assignment_id, []).append(row.user_id)
    return given


def set_students(db: Session, assignment: Assignment, user_ids: list[int]) -> None:
    """Replaces the list of students this assignment is given to by name. Does not commit."""
    wanted = set(user_ids)
    students = set(db.scalars(select(User.id).where(User.id.in_(wanted), User.role == "student")))
    if students != wanted:
        raise AssignmentError("Assignments can only be given to student accounts.")
    db.execute(delete(AssignmentStudent).where(AssignmentStudent.assignment_id == assignment.id))
    db.add_all(AssignmentStudent(assignment_id=assignment.id, user_id=user_id) for user_id in sorted(wanted))
