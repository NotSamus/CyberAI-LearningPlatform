"""Assignments: the notebooks teachers upload, and who gets them.

A teacher uploads an .ipynb file and it is stored in the database, as a draft given to nobody.
A student sees an assignment once it is published and given to them: to every student, to a course
they are in, or to them by name. Teachers and admins see all of them.

An assignment can have data files (datasets) beside its notebook. Each student gets a copy of them
too, in the same folder, so the notebook opens them by name; an autograded assignment's autograder
package carries them as well (Otter's `files`, see grader/main.py), so it grades without a network.

The teacher API that creates and changes assignments is app/teach.py. Students open them through
app/jupyter/launch.py, which puts a copy of the notebook and its data files into their Jupyter home.
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
from app.models import Assignment, AssignmentFile, AssignmentOpen, AssignmentStudent, CourseStudent, Submission, User

MAX_NOTEBOOK_BYTES = 10 * 1024 * 1024      # room for plots and images in the outputs
MAX_SUBMISSION_BYTES = 2 * MAX_NOTEBOOK_BYTES   # a student's copy grows as they run it
MAX_POINTS = 10_000
MAX_TITLE_LENGTH = 120
MAX_DESCRIPTION_LENGTH = 2000
MAX_DATA_FILES = 20
# All of an assignment's data files together. Each student gets a copy, and an autograded assignment's
# autograder package carries them: the grading service reads back at most 64 MB of it
# (MAX_OUTPUT_BYTES in grader/main.py), so this stays well under that.
MAX_DATA_BYTES = 50 * 1024 * 1024


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
    """Remembers the first time this person opened this assignment. Waits while its notebook is
    being replaced (replace_notebook)."""
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


def a_student_has_it(db: Session, assignment_id: int) -> bool:
    """Whether a student has opened this assignment, and so has their own copy of its notebook, or
    has handed one in. From then on its notebook can no longer be changed (replace_notebook).
    Teachers trying it out do not count."""
    students = select(User.id).where(User.role == "student")
    return bool(db.scalar(select(or_(
        exists().where(AssignmentOpen.assignment_id == assignment_id, AssignmentOpen.user_id.in_(students)),
        exists().where(Submission.assignment_id == assignment_id, Submission.user_id.in_(students)),
    ))))


def counts(db: Session) -> dict[int, dict]:
    """assignment id -> how far its students have got: how many it is given to, opened it and
    submitted, and how many submissions wait for a teacher (graded by hand, or the autograder could
    not run them). Only the students it is given to count, as in its gradebook: a teacher trying it
    out, or a student who has since left the course, does not. A few queries for every assignment
    at once, not a few per assignment."""
    everyone = set(db.scalars(select(User.id).where(User.role == "student")))
    by_name: dict[int, set[int]] = {}
    for row in db.execute(select(AssignmentStudent.assignment_id, AssignmentStudent.user_id)):
        by_name.setdefault(row.assignment_id, set()).add(row.user_id)
    in_course: dict[int, set[int]] = {}
    for row in db.execute(select(CourseStudent.course_id, CourseStudent.user_id)):
        in_course.setdefault(row.course_id, set()).add(row.user_id)
    opened: dict[int, set[int]] = {}
    for row in db.execute(select(AssignmentOpen.assignment_id, AssignmentOpen.user_id)):
        opened.setdefault(row.assignment_id, set()).add(row.user_id)
    handed_in: dict[int, list] = {}
    for row in db.execute(select(Submission.assignment_id, Submission.user_id, Submission.status, Submission.late, Submission.submitted_at)):
        handed_in.setdefault(row.assignment_id, []).append(row)

    found = {}
    for assignment in db.execute(select(Assignment.id, Assignment.for_everyone, Assignment.course_id)):
        given = everyone if assignment.for_everyone else (by_name.get(assignment.id, set()) | in_course.get(assignment.course_id, set())) & everyone
        rows = [row for row in handed_in.get(assignment.id, []) if row.user_id in given]
        waiting = [row for row in rows if row.status in ("submitted", "failed")]
        found[assignment.id] = {
            "given": len(given),
            "opened": len(opened.get(assignment.id, set()) & given),
            "submitted": len(rows),
            "graded": sum(row.status == "graded" for row in rows),
            "to_grade": sum(row.status == "submitted" for row in rows),      # waiting for a grade by hand
            "failed": sum(row.status == "failed" for row in rows),           # the autograder could not run them
            "late": sum(row.late for row in rows),
            "oldest_waiting_at": min(row.submitted_at for row in waiting).isoformat() if waiting else None,
        }
    return found


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


# A data file's name: what the notebook opens beside itself, so it is kept as it is, never changed into
# something else. Letters, digits, dots, dashes, underscores and spaces; never a path.
_DATA_NAME = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._ -]{0,98}[A-Za-z0-9._-])?")


def data_file_name(filename: str) -> str:
    """The name an uploaded data file is kept under: the file's own name, without any folders."""
    return re.split(r"[/\\]", filename or "")[-1]


def check_data_files(files: dict[str, bytes], notebook_name: str) -> dict[str, bytes]:
    """An assignment's data files (name -> contents), refused when they cannot go beside its notebook:
    names that are not plain file names, a notebook (Otter grades the one .ipynb beside the tests), a
    name Otter uses there, or more than the limits."""
    if len(files) > MAX_DATA_FILES:
        raise AssignmentError(f"An assignment has at most {MAX_DATA_FILES} data files. Put many small files in one .zip.")
    stem = notebook_name.lower().removesuffix(".ipynb")
    for name in files:
        lowered = name.lower()
        if not _DATA_NAME.fullmatch(name):
            raise AssignmentError(
                f'"{name[:100]}" cannot be a data file\'s name: rename it with letters, digits, dots, dashes, underscores and '
                "spaces only, starting with a letter or digit (and change the name in the notebook too)."
            )
        if lowered.endswith(".ipynb"):
            raise AssignmentError(f"{name} is a notebook: upload it as an assignment of its own, not as a data file.")
        if lowered in (notebook_name.lower(), "tests", "dist") or lowered.startswith(f"{stem}-autograder_"):
            raise AssignmentError(f"{name} cannot be a data file's name here: the notebook or the autograder uses it. Rename the file.")
    if sum(len(data) for data in files.values()) > MAX_DATA_BYTES:
        raise AssignmentError(
            f"The data files come to more than {MAX_DATA_BYTES // (1024 * 1024)} MB together. Each student gets a copy: "
            "make them smaller, or leave some out."
        )
    return files


def data_files(db: Session, assignment_id: int) -> list[dict]:
    """The assignment's data files, by name, with their sizes (not their contents)."""
    rows = db.execute(
        select(AssignmentFile.name, AssignmentFile.size).where(AssignmentFile.assignment_id == assignment_id).order_by(AssignmentFile.name)
    )
    return [{"name": row.name, "size": row.size} for row in rows]


def data_bytes(db: Session, assignment_id: int, names: list[str] | None = None) -> dict[str, bytes]:
    """name -> contents of the assignment's data files (only `names`, when given)."""
    query = select(AssignmentFile.name, AssignmentFile.data).where(AssignmentFile.assignment_id == assignment_id)
    if names is not None:
        query = query.where(AssignmentFile.name.in_(names))
    return {row.name: row.data for row in db.execute(query.order_by(AssignmentFile.name))}


def _store_data(db: Session, assignment_id: int, files: dict[str, bytes]) -> None:
    """Replaces the assignment's data files with these. Does not commit."""
    db.execute(delete(AssignmentFile).where(AssignmentFile.assignment_id == assignment_id))
    db.add_all(AssignmentFile(assignment_id=assignment_id, name=name, size=len(data), data=data) for name, data in sorted(files.items()))


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
    question_points: dict[str, float] | None = None,
    data_files: dict[str, bytes] | None = None,
    commit: bool = True,
) -> Assignment:
    """`master`, `autograder` and `question_points` are given for an autograded assignment (see
    app/grading.py); `notebook` is then the version Otter made for students. `commit=False` leaves
    the commit to the caller, which is adding more in the same go (app/lesson_zip.py). `data_files`
    (name -> contents) go beside the notebook; Otter must have had them too for an autograded one."""
    title = check_title(title)
    notebook_name = safe_notebook_name(filename)
    check_notebook(notebook)
    check_data_files(data_files or {}, notebook_name)
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
        question_points=question_points,
        published=published,
        for_everyone=for_everyone,
        due_at=check_due_at(due_at),
        created_by=created_by,
    )
    db.add(assignment)
    db.flush()
    assignment.slug = _folder_name(title, assignment.id)
    _store_data(db, assignment.id, data_files or {})
    if commit:
        db.commit()
    return assignment


class NotebookLocked(AssignmentError):
    def __init__(self):
        super().__init__(
            "A student has opened this assignment and has their own copy of its notebook, so the notebook can "
            "no longer be changed. To hand out a corrected notebook, upload it as a new assignment."
        )


def replace_notebook(
    db: Session,
    assignment_id: int,
    *,
    filename: str,
    notebook: bytes,
    master: bytes | None = None,
    autograder: bytes | None = None,
    points: float | None = None,
    question_points: dict[str, float] | None = None,
    data_files: dict[str, bytes] | None = None,
) -> Assignment:
    """Puts a new notebook in place of the assignment's own, taken in as `create` takes it: autograded
    when `autograder` is given, otherwise graded by hand. Only while no student has it
    (a_student_has_it): a student's copy is never changed, and would no longer match the tests.
    `data_files`, when given, replace the assignment's data files the same way (None keeps them).

    The assignment's row stays locked until the commit, and recording a student's open waits for
    that (it refers to the row). app/jupyter/launch.py records the open before it copies the
    notebook, so a student either stops the replacing or gets the new notebook, never the old one
    after it was replaced."""
    assignment = db.scalar(
        select(Assignment).where(Assignment.id == assignment_id).with_for_update().execution_options(populate_existing=True)
    )
    if assignment is None:
        raise AssignmentError("This assignment was deleted.")
    if a_student_has_it(db, assignment_id):
        raise NotebookLocked()
    check_notebook(notebook)
    if data_files is not None:
        _store_data(db, assignment_id, check_data_files(data_files, safe_notebook_name(filename)))
    if autograder is None:
        # Graded by hand: out of what the teacher set, or out of the default when the tests had set it
        points = None if assignment.autograded else assignment.points
    assignment.notebook_name = safe_notebook_name(filename)
    assignment.notebook, assignment.master, assignment.autograder = notebook, master, autograder
    assignment.autograded = autograder is not None
    assignment.points, assignment.question_points = points, question_points
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
