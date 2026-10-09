"""Database tables. Change them here, then add a migration (see sql/README.md)."""
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, LargeBinary, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

ROLES = ("student", "teacher")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('student', 'teacher')", name="role"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True)      # always stored lowercase
    password_hash: Mapped[str] = mapped_column(String(255))             # argon2id, see app/auth.py
    display_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(16))                       # decides the hub groups
    is_admin: Mapped[bool] = mapped_column(default=False)               # may manage accounts
    gpu_enabled: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LoginSession(Base):
    """One row per logged-in browser. The cookie holds a random token; only its SHA-256 is stored."""
    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Course(Base):
    """A class: a named group of students. Assignments and announcements can be given to a course."""
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)         # e.g. "CS 101, section 2"
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CourseStudent(Base):
    __tablename__ = "course_students"

    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)


class Assignment(Base):
    """A notebook a teacher uploaded. Students get their own copy the first time they open it:
    assignments/<slug>/<notebook_name> in their Jupyter home (see app/jupyter/launch.py)."""
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(60), unique=True)          # folder name in the student's home; never changes or reused
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    requires_gpu: Mapped[bool] = mapped_column(default=False)
    notebook_name: Mapped[str] = mapped_column(String(100))             # a safe file name ending in .ipynb
    # The .ipynb file itself. Loaded only when asked for (deferred), so listing assignments stays cheap.
    notebook: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    # Autograded assignments (the upload was an Otter Assign notebook, see app/grading.py): `notebook`
    # is the version without solutions that Otter made for students, `master` is what the teacher
    # uploaded, and `autograder` is Otter's package with every test, hidden ones included.
    master: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    autograder: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    autograded: Mapped[bool] = mapped_column(default=False)
    points: Mapped[float | None] = mapped_column()                      # the most a submission can score, when known
    published: Mapped[bool] = mapped_column(default=False)              # drafts are visible to teachers only
    # Who gets it: every student (including ones added later), the students of one course, and/or
    # students chosen by name (AssignmentStudent below).
    for_everyone: Mapped[bool] = mapped_column(default=False)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"), index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AssignmentStudent(Base):
    """The students an assignment was given to one by one (used when it is not `for_everyone`)."""
    __tablename__ = "assignment_students"

    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)


class AssignmentOpen(Base):
    """Written the first time someone opens an assignment (and so gets their copy of the notebook)."""
    __tablename__ = "assignment_opens"

    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Announcement(Base):
    """A short message from a teacher, shown on students' home page."""
    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(primary_key=True)
    course_id: Mapped[int | None] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)   # None: for everyone
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


SUBMISSION_STATUSES = ("submitted", "queued", "grading", "graded", "failed")


class Submission(Base):
    """The notebook a student handed in for an assignment, and its grade. One row per student and
    assignment: submitting again replaces the notebook and starts the grading over."""
    __tablename__ = "submissions"
    __table_args__ = (
        UniqueConstraint("assignment_id", "user_id"),
        CheckConstraint("status IN ('submitted', 'queued', 'grading', 'graded', 'failed')", name="status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    notebook: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)     # the student's file as it was when they submitted
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempt: Mapped[int] = mapped_column(default=1)                     # 2 after the first resubmission, and so on
    late: Mapped[bool] = mapped_column(default=False)                   # submitted after the due date
    # submitted: waiting for a teacher to grade it by hand.   queued, grading: with the autograder.
    # graded: has a score.   failed: the autograder could not run it (`error` says why).
    status: Mapped[str] = mapped_column(String(16))
    score: Mapped[float | None] = mapped_column()
    max_score: Mapped[float | None] = mapped_column()
    results: Mapped[dict | None] = mapped_column(JSONB)                 # Otter's results: a score and output per question
    error: Mapped[str | None] = mapped_column(Text)
    feedback: Mapped[str] = mapped_column(Text, default="")             # the teacher's comment
    graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    graded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))   # None: the autograder
