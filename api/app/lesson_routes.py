"""Lessons over HTTP (the rules are in app/lessons.py).

`teach_router`: writing, publishing and following up on lessons, for Settings > Lessons. Every
route checks on the server that the account is a teacher or an admin; students get 403.

`router`: reading a lesson and answering its knowledge checks, for everyone who is logged in. A
student asking for a lesson that is a draft, or was not given to them, gets the same 404 as for
one that does not exist.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, undefer
from starlette.datastructures import UploadFile

from app import courses, lessons
from app.db import get_db
from app.jupyter.deps import PlatformUser
from app.jupyter.launch import require_user
from app.models import Course, Lesson
from app.teach import require_teacher

teach_router = APIRouter(prefix="/api/teach", tags=["lessons"])
router = APIRouter(prefix="/api", tags=["lessons"])


def _iso(moment) -> str | None:
    return moment.isoformat() if moment else None


# --- for teachers ---------------------------------------------------------------------------------

def _lesson_or_404(db: Session, lesson_id: int) -> Lesson:
    lesson = db.get(Lesson, lesson_id)
    if lesson is None:
        raise HTTPException(404, "No such lesson.")
    return lesson


def _details(lesson: Lesson, course_names: dict[int, str]) -> dict:
    return {
        **lessons.summary(lesson, course_names),
        "for_everyone": lesson.for_everyone,
        "published_at": _iso(lesson.published_at),
        # Published, and edited since: students still have the version from the last Publish.
        "changed": lesson.published and lesson.blocks != lesson.live_blocks,
        "blocks_count": len(lesson.blocks),
    }


@teach_router.get("/lessons")
def list_lessons(teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    course_names = courses.names(db)
    query = select(Lesson).options(undefer(Lesson.blocks), undefer(Lesson.live_blocks)).order_by(Lesson.position, Lesson.id)
    return [_details(lesson, course_names) for lesson in db.scalars(query)]


class NewLesson(BaseModel):
    title: str


@teach_router.post("/lessons", status_code=201)
def create_lesson(body: NewLesson, teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    """An empty draft given to nobody, ready to be written."""
    try:
        lesson = lessons.create(db, body.title, teacher.id)
    except lessons.LessonError as e:
        raise HTTPException(400, str(e))
    return _details(lesson, courses.names(db))


class Order(BaseModel):
    ids: list[int] = Field(max_length=10_000)


@teach_router.put("/lessons/order")
def order_lessons(body: Order, teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    """The order lessons are listed in, for everyone: the ids, first lesson first."""
    lessons.set_order(db, body.ids)
    return {"ordered": True}


@teach_router.get("/lessons/{lesson_id}")
def get_lesson(lesson_id: int, teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    """The working copy, with the answers to its questions."""
    lesson = _lesson_or_404(db, lesson_id)
    return {**_details(lesson, courses.names(db)), "blocks": lesson.blocks}


class Changes(BaseModel):
    """Only the fields that are sent are changed. `blocks` replaces the whole working copy (students
    keep the published version until the next Publish); the other fields take effect at once.
    `course_id: null` takes the lesson out of its course."""
    title: str | None = None
    summary: str | None = None
    blocks: list | None = None
    for_everyone: bool | None = None
    course_id: int | None = None


@teach_router.patch("/lessons/{lesson_id}")
def change_lesson(lesson_id: int, body: Changes, teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    lesson = _lesson_or_404(db, lesson_id)
    try:
        if body.title is not None:
            lesson.title = lessons.check_title(body.title)
        if body.summary is not None:
            lesson.summary = lessons.check_summary(body.summary)
        if body.blocks is not None:
            lesson.blocks = lessons.check_blocks(db, lesson, body.blocks)
        if "course_id" in body.model_fields_set:
            if body.course_id is not None and db.get(Course, body.course_id) is None:
                raise lessons.LessonError("That course does not exist.")
            lesson.course_id = body.course_id
    except lessons.LessonError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    if body.for_everyone is not None:
        lesson.for_everyone = body.for_everyone
    db.commit()
    return _details(lesson, courses.names(db))


@teach_router.post("/lessons/{lesson_id}/publish")
def publish_lesson(lesson_id: int, teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    """Gives students the working copy as it is now. Refused, with the reasons, while a question in
    it is unfinished."""
    lesson = _lesson_or_404(db, lesson_id)
    try:
        lessons.publish(db, lesson)
    except lessons.LessonError as e:
        raise HTTPException(400, str(e))
    return _details(lesson, courses.names(db))


@teach_router.post("/lessons/{lesson_id}/unpublish")
def unpublish_lesson(lesson_id: int, teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    """Hides the lesson from students. Their answers are kept."""
    lesson = _lesson_or_404(db, lesson_id)
    lesson.published = False
    db.commit()
    return _details(lesson, courses.names(db))


@teach_router.delete("/lessons/{lesson_id}")
def delete_lesson(lesson_id: int, teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    """Removes the lesson with its pictures and what students answered in it."""
    db.delete(_lesson_or_404(db, lesson_id))
    db.commit()
    return {"deleted": True}


@teach_router.get("/lessons/{lesson_id}/progress")
def lesson_progress(lesson_id: int, teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    """Every student the lesson is given to: whether they opened and completed it, and how the
    knowledge checks went."""
    lesson = _lesson_or_404(db, lesson_id)
    return {"lesson": _details(lesson, courses.names(db)), **lessons.progress(db, lesson)}


@teach_router.post("/lesson-images", status_code=201)
async def upload_image(request: Request, teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    """Stores a picture for a lesson; an image block then points to it. A web form with the fields
    `lesson_id` and `file`. The form is read here and not declared as parameters, so that the
    account check above comes first (as for notebooks, see app/teach.py)."""
    async with request.form() as form:
        file = form.get("file")
        if not isinstance(file, UploadFile) or not str(form.get("lesson_id") or "").isdigit():
            raise HTTPException(422, "Send a lesson_id and a picture file.")
        lesson_id = int(str(form["lesson_id"]))
        data = await file.read(lessons.MAX_IMAGE_BYTES + 1)     # one byte more: enough to see it is too big

    def store() -> dict:
        lesson = _lesson_or_404(db, lesson_id)
        try:
            image = lessons.add_image(db, lesson, data)
        except lessons.LessonError as e:
            raise HTTPException(400, str(e))
        return {"id": image.id, "url": f"/api/lessons/{lesson.id}/images/{image.id}"}

    return await run_in_threadpool(store)


# --- for everyone who is logged in ----------------------------------------------------------------

def visible_lesson(lesson_id: int, user: PlatformUser = Depends(require_user), db: Session = Depends(get_db)) -> Lesson:
    lesson = lessons.get_visible(db, user, lesson_id)
    if lesson is None:
        raise HTTPException(404, "No such lesson.")
    return lesson


def _mine(lesson: Lesson, course_names: dict[int, str], progress, closed: int) -> dict:
    """A lesson with the logged-in person's own progress in it."""
    return {
        **lessons.summary(lesson, course_names),
        "opened_at": _iso(progress.opened_at) if progress else None,
        "completed_at": _iso(progress.completed_at) if progress else None,
        "answered": closed,             # knowledge checks they are done with
    }


@router.get("/lessons")
def my_lessons(user: PlatformUser = Depends(require_user), db: Session = Depends(get_db)):
    """The lessons this person may see, in order, each with their own progress."""
    course_names, progress, closed = courses.names(db), lessons.progress_of(db, user.id), lessons.closed_counts(db, user.id)
    return [_mine(lesson, course_names, progress.get(lesson.id), closed.get(lesson.id, 0)) for lesson in lessons.list_visible(db, user)]


@router.get("/lessons/{lesson_id}")
def read_lesson(lesson: Lesson = Depends(visible_lesson), user: PlatformUser = Depends(require_user), db: Session = Depends(get_db)):
    """The lesson to read, without anything that gives away an answer. Teachers get their working
    copy (`preview`), to try it out before publishing. Opening it is remembered."""
    lessons.record_open(db, lesson.id, user.id)
    blocks = lessons.view(db, user, lesson)
    checks = [block for block in blocks if lessons.is_check(block)]
    after = [
        other for other in lessons.list_visible(db, user)
        if other.course_id == lesson.course_id and (other.position, other.id) > (lesson.position, lesson.id)
    ]
    return {
        **_mine(lesson, courses.names(db), lessons.progress_of(db, user.id).get(lesson.id), 0),
        "questions": len(checks),
        "answered": sum(1 for block in checks if block["state"] and block["state"]["closed"]),
        "preview": user.can_teach,
        "max_tries": lessons.MAX_TRIES,
        "blocks": blocks,
        "next": {"id": after[0].id, "title": after[0].title} if after else None,
    }


class Answer(BaseModel):
    block_id: str = Field(max_length=32)
    choices: list[str] | None = Field(None, max_length=lessons.MAX_OPTIONS)    # multiple choice: the ids of the chosen options
    text: str | None = Field(None, max_length=1000)                            # short answer


@router.post("/lessons/{lesson_id}/answers")
def answer_question(
    body: Answer, lesson: Lesson = Depends(visible_lesson), user: PlatformUser = Depends(require_user), db: Session = Depends(get_db),
):
    """Checks an answer to a knowledge check, here on the server, and counts the try. Says whether
    it was right; the explanation and the right answer come once the question is closed."""
    try:
        return lessons.answer(db, lesson, user, body.block_id, body.choices, body.text)
    except lessons.LessonError as e:
        raise HTTPException(400, str(e))


@router.post("/lessons/{lesson_id}/complete")
def complete_lesson(lesson: Lesson = Depends(visible_lesson), user: PlatformUser = Depends(require_user), db: Session = Depends(get_db)):
    try:
        lessons.complete(db, lesson, user)
    except lessons.LessonError as e:
        raise HTTPException(400, str(e))
    return {"completed_at": _iso(lessons.progress_of(db, user.id)[lesson.id].completed_at)}


@router.post("/lessons/{lesson_id}/start-over")
def start_over(lesson: Lesson = Depends(visible_lesson), teacher: PlatformUser = Depends(require_teacher), db: Session = Depends(get_db)):
    """For a teacher trying out a lesson: forgets their own answers, so they can go through it again."""
    lessons.start_over(db, lesson.id, teacher.id)
    return {"started_over": True}


@router.get("/lessons/{lesson_id}/images/{image_id}")
def lesson_image(
    image_id: int, lesson: Lesson = Depends(visible_lesson), user: PlatformUser = Depends(require_user), db: Session = Depends(get_db),
):
    """A picture of a lesson, for the people who may see that lesson. Students only get the pictures
    of the published version: not one that is only in the teacher's working copy yet, or was uploaded
    and never used."""
    shown = {block["image_id"] for block in lesson.live_blocks if block["type"] == "image"}
    image = lessons.get_image(db, lesson.id, image_id) if user.can_teach or image_id in shown else None
    if image is None:
        raise HTTPException(404, "No such picture.")
    content_type, data = image
    return Response(
        data,
        media_type=content_type,        # one of the four picture kinds, found from the file when it was uploaded
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Cache-Control": "private, max-age=86400",
        },
    )
