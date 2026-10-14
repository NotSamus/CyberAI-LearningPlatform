"""Submissions: the notebook a student hands in for an assignment, and its grade.

Submitting copies the student's notebook, as it is saved in their Jupyter home at that moment, into
the database. Autograded assignments are then graded by Otter (app/grading.py) in the background;
the others wait for a teacher to give a score. A teacher can also change any score and add a comment.
"""
from datetime import datetime, timezone

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import grading
from app.db import SessionLocal
from app.models import Assignment, Submission

DEFAULT_POINTS = 100.0              # what a hand-graded assignment is out of, unless the teacher set its points

# Grading runs after the request that started it has been answered, so it opens its own database
# sessions. The tests point this at their throwaway database.
session_factory = SessionLocal


def _iso(moment: datetime | None) -> str | None:
    return moment.isoformat() if moment else None


def summary(submission: Submission) -> dict:
    return {
        "submitted_at": _iso(submission.submitted_at),
        "late": submission.late,
        "status": submission.status,
        "attempt": submission.attempt,
        "score": submission.score,
        "max_score": submission.max_score,
    }


def details(submission: Submission, for_teacher: bool) -> dict:
    """A submission and its grade. Students get no text from Otter (app/grading.py says why):
    their score per question and whether each question's public tests passed."""
    return {
        **summary(submission),
        "feedback": submission.feedback,
        "graded_at": _iso(submission.graded_at),
        "graded_by_teacher": submission.graded_by is not None,
        "questions": grading.questions(submission.results, with_hidden_output=for_teacher),
        "public_tests": grading.public_tests(submission.results),
        # Why the autograder could not run it. For the student: only that it failed.
        "error": submission.error if for_teacher else None,
    } | ({"public_output": grading.public_output(submission.results)} if for_teacher else {})


def of_user(db: Session, user_id: int) -> dict[int, Submission]:
    """assignment id -> this person's submission."""
    return {s.assignment_id: s for s in db.scalars(select(Submission).where(Submission.user_id == user_id))}


def of_assignment(db: Session, assignment_id: int) -> dict[int, Submission]:
    """user id -> their submission for this assignment."""
    return {s.user_id: s for s in db.scalars(select(Submission).where(Submission.assignment_id == assignment_id))}


def get(db: Session, assignment_id: int, user_id: int) -> Submission | None:
    return db.scalar(select(Submission).where(Submission.assignment_id == assignment_id, Submission.user_id == user_id))


def notebook_bytes(db: Session, submission_id: int) -> bytes:
    return db.scalar(select(Submission.notebook).where(Submission.id == submission_id))


def record(db: Session, assignment: Assignment, user_id: int, notebook: bytes) -> Submission:
    """Stores a submission, replacing this student's earlier one for the assignment (and its grade:
    that was for the earlier notebook)."""
    now = datetime.now(timezone.utc)
    submission = get(db, assignment.id, user_id)
    if submission is None:
        submission = Submission(assignment_id=assignment.id, user_id=user_id, attempt=0)
        db.add(submission)
    submission.notebook = notebook
    submission.submitted_at = now
    submission.attempt += 1
    submission.late = assignment.due_at is not None and now > assignment.due_at
    submission.status = "queued" if assignment.autograded else "submitted"
    submission.score = submission.max_score = submission.results = submission.error = None
    submission.feedback = ""
    submission.graded_at = submission.graded_by = None
    db.commit()
    return submission


def queue_again(db: Session, submission: Submission) -> None:
    """Back to the autograder, e.g. after it failed for a reason that has been fixed."""
    submission.status = "queued"
    submission.error = None
    db.commit()


def grade_by_hand(db: Session, submission: Submission, assignment: Assignment, teacher_id: int,
                  score: float | None, feedback: str | None) -> None:
    if score is not None:
        max_score = submission.max_score or assignment.points or DEFAULT_POINTS
        if not 0 <= score <= max_score:
            raise ValueError(f"The score must be between 0 and {max_score:g}.")
        submission.score, submission.max_score = score, max_score
        submission.status, submission.error = "graded", None
        submission.graded_at, submission.graded_by = datetime.now(timezone.utc), teacher_id
    if feedback is not None:
        submission.feedback = feedback.strip()
    db.commit()


async def grade_submission(submission_id: int, attempt: int) -> None:
    """Has Otter grade one submission and stores the outcome. Does nothing when the student has
    submitted again in the meantime (`attempt` no longer matches): that newer notebook has its own
    grading on the way."""
    current = (Submission.id == submission_id, Submission.attempt == attempt)

    def start():
        with session_factory() as db:
            job = db.execute(
                select(Submission.notebook, Assignment.autograder, Assignment.notebook_name, Assignment.requires_gpu)
                .join(Assignment, Assignment.id == Submission.assignment_id)
                .where(*current, Submission.status.in_(("queued", "grading")))
            ).first()
            if job is not None:
                db.get(Submission, submission_id).status = "grading"
                db.commit()
            return job

    job = await run_in_threadpool(start)
    if job is None:
        return
    try:
        results = await grading.grade(*job)
        score, max_score = grading.totals(results)
        outcome = dict(status="graded", results=results, score=score, max_score=max_score, error=None)
    except grading.GradingError as e:
        outcome = dict(status="failed", results=None, score=None, max_score=None, error=str(e))

    def finish():
        with session_factory() as db:
            submission = db.scalar(select(Submission).where(*current))
            if submission is None:
                return
            for field, value in outcome.items():
                setattr(submission, field, value)
            submission.graded_at, submission.graded_by = datetime.now(timezone.utc), None
            db.commit()

    await run_in_threadpool(finish)


def waiting_for_the_autograder() -> list[tuple[int, int]]:
    """(submission id, attempt) of everything that was queued or being graded, for picking the
    work up again after the backend was restarted."""
    with session_factory() as db:
        rows = db.execute(select(Submission.id, Submission.attempt).where(Submission.status.in_(("queued", "grading"))))
        return [(row.id, row.attempt) for row in rows]
