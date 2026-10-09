"""Courses (classes) and announcements.

A course is a named group of students. An assignment or an announcement given to a course reaches
its students. For now every teacher and admin can manage every course (see app/teach.py).
"""
from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.jupyter.deps import PlatformUser
from app.models import Announcement, Course, CourseStudent, User

MAX_NAME_LENGTH = 120
MAX_ANNOUNCEMENT_LENGTH = 5000


class CourseError(ValueError):
    """A change that cannot be accepted. The message is safe to show to the person."""


def names(db: Session) -> dict[int, str]:
    """course id -> name, for every course."""
    return {row.id: row.name for row in db.execute(select(Course.id, Course.name))}


def student_ids(db: Session) -> dict[int, list[int]]:
    """course id -> the students in it."""
    members: dict[int, list[int]] = {}
    for row in db.execute(select(CourseStudent.course_id, CourseStudent.user_id).order_by(CourseStudent.user_id)):
        members.setdefault(row.course_id, []).append(row.user_id)
    return members


def check_name(name: str) -> str:
    name = name.strip()
    if not 1 <= len(name) <= MAX_NAME_LENGTH:
        raise CourseError(f"Course names are 1 to {MAX_NAME_LENGTH} characters.")
    return name


def save(db: Session, course: Course) -> None:
    """Commits a new or renamed course; two courses cannot have the same name."""
    db.add(course)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise CourseError(f"There is already a course named '{course.name}'.")


def set_students(db: Session, course: Course, user_ids: list[int]) -> None:
    """Replaces who is in the course. Does not commit."""
    wanted = set(user_ids)
    students = set(db.scalars(select(User.id).where(User.id.in_(wanted), User.role == "student")))
    if students != wanted:
        raise CourseError("Only student accounts can be put in a course.")
    db.execute(delete(CourseStudent).where(CourseStudent.course_id == course.id))
    db.add_all(CourseStudent(course_id=course.id, user_id=user_id) for user_id in sorted(wanted))


def check_announcement(title: str, body: str) -> tuple[str, str]:
    title, body = title.strip(), body.strip()
    if not 1 <= len(title) <= MAX_NAME_LENGTH:
        raise CourseError(f"Announcement titles are 1 to {MAX_NAME_LENGTH} characters.")
    if len(body) > MAX_ANNOUNCEMENT_LENGTH:
        raise CourseError(f"Announcements are at most {MAX_ANNOUNCEMENT_LENGTH} characters.")
    return title, body


def announcements_for(db: Session, user: PlatformUser, limit: int = 20) -> list[Announcement]:
    """Newest first. Students get the ones for everyone and for their courses; teachers get all."""
    query = select(Announcement).order_by(Announcement.created_at.desc(), Announcement.id.desc()).limit(limit)
    if not user.can_teach:
        mine = select(CourseStudent.course_id).where(CourseStudent.user_id == user.id)
        query = query.where(or_(Announcement.course_id.is_(None), Announcement.course_id.in_(mine)))
    return list(db.scalars(query))


def announcement(item: Announcement, course_names: dict[int, str]) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "body": item.body,
        "course_id": item.course_id,
        "course": course_names.get(item.course_id) if item.course_id else None,
        "created_at": item.created_at.isoformat(),
    }
