"""Lessons: pages teachers write in the platform, made of blocks.

A lesson is a list of blocks: text (Markdown), code, a callout, an image, a video, a link to a
notebook assignment, and knowledge checks (a multiple-choice or a short-answer question).

The teacher's working copy (`Lesson.blocks`) is saved as they type and may be unfinished. Students
get `Lesson.live_blocks`: the working copy as it was the last time the teacher pressed Publish.
A student sees a lesson once it is published and given to every student or to a course they are in.

Knowledge checks are checked here, on the server. What a person is sent (`view` below) never says
which option is correct, which answers are accepted or what the explanation is, until they have
answered correctly or used up their tries. They are practice, not grades: nothing here reaches the
gradebook.

The routes are in app/lesson_routes.py.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, StringConstraints, TypeAdapter, ValidationError
from sqlalchemy import and_, delete, exists, func, or_, select, true, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app import assignments
from app.jupyter.deps import PlatformUser
from app.models import CourseStudent, Lesson, LessonAnswer, LessonImage, LessonProgress, User

MAX_TITLE_LENGTH = 120
MAX_SUMMARY_LENGTH = 300
MAX_BLOCKS = 200
MAX_TEXT_LENGTH = 20_000            # one text, code or callout block
MAX_QUESTION_LENGTH = 2000          # a question, and its explanation
MAX_OPTIONS = 8
MAX_ACCEPTED_ANSWERS = 10
MAX_ANSWER_LENGTH = 200
MAX_LESSON_BYTES = 500_000          # all blocks together, as JSON: well under the 1 MB a request may be
MAX_TRIES = 3                       # per knowledge check; after that the answer is shown
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGES = 100                    # per lesson

CHECKS = ("multiple_choice", "short_answer")


class LessonError(ValueError):
    """Something that cannot be saved, published or answered. The message is safe to show to the person."""


# --- the blocks -----------------------------------------------------------------------------------
# The same shapes are written out for the frontend in frontend/lib/lessons.ts.

Id = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{4,32}$")]    # made by the editor; one of a kind in its lesson


class Text(BaseModel):
    type: Literal["text"]
    id: Id
    text: str = Field("", max_length=MAX_TEXT_LENGTH)                   # Markdown


class Code(BaseModel):
    type: Literal["code"]
    id: Id
    language: str = Field("", max_length=30, pattern=r"^[A-Za-z0-9+#. _-]*$")   # a label, e.g. "python"
    code: str = Field("", max_length=MAX_TEXT_LENGTH)


class Callout(BaseModel):
    type: Literal["callout"]
    id: Id
    tone: Literal["note", "tip", "warning"] = "note"
    text: str = Field("", max_length=MAX_TEXT_LENGTH)                   # Markdown


class Image(BaseModel):
    type: Literal["image"]
    id: Id
    image_id: int | None = None                                         # a LessonImage of this lesson
    alt: str = Field("", max_length=300)                                # says what the picture shows, for people who cannot see it


class Video(BaseModel):
    type: Literal["video"]
    id: Id
    url: str = Field("", max_length=300)                                # a YouTube link, as the teacher pasted it


class AssignmentLink(BaseModel):
    type: Literal["assignment"]
    id: Id
    assignment_id: int | None = None


class Option(BaseModel):
    id: Id
    text: str = Field("", max_length=500)
    correct: bool = False


class MultipleChoice(BaseModel):
    """One correct option: students pick one. Several: they must pick exactly those."""
    type: Literal["multiple_choice"]
    id: Id
    question: str = Field("", max_length=MAX_QUESTION_LENGTH)           # Markdown
    options: list[Option] = Field(default_factory=list, max_length=MAX_OPTIONS)
    explanation: str = Field("", max_length=MAX_QUESTION_LENGTH)        # Markdown; shown once the question is closed


class ShortAnswer(BaseModel):
    """Right when what the student types is one of `answers`, ignoring capitals and extra spaces."""
    type: Literal["short_answer"]
    id: Id
    question: str = Field("", max_length=MAX_QUESTION_LENGTH)
    answers: list[Annotated[str, StringConstraints(max_length=MAX_ANSWER_LENGTH)]] = Field(default_factory=list, max_length=MAX_ACCEPTED_ANSWERS)
    explanation: str = Field("", max_length=MAX_QUESTION_LENGTH)


Block = Annotated[
    Union[Text, Code, Callout, Image, Video, AssignmentLink, MultipleChoice, ShortAnswer],
    Field(discriminator="type"),
]
_blocks = TypeAdapter(list[Block])

_YOUTUBE = re.compile(
    r"^https?://(?:www\.|m\.)?(?:youtube(?:-nocookie)?\.com/(?:watch\?(?:[^#]*&)?v=|embed/|shorts/|live/)|youtu\.be/)"
    r"([A-Za-z0-9_-]{11})(?:[?&#/].*)?$"
)


def video_id(url: str) -> str | None:
    """The id of the YouTube video a link points to. Videos are only ever embedded from YouTube."""
    match = _YOUTUBE.match(url.strip())
    return match.group(1) if match else None


def check_blocks(db: Session, lesson: Lesson, raw: object) -> list[dict]:
    """A working copy as the editor sent it, in the shape it is stored in. It may be unfinished (a
    question with no correct option yet): `problems` decides whether it can be published."""
    if not isinstance(raw, list) or len(raw) > MAX_BLOCKS:
        raise LessonError(f"A lesson has at most {MAX_BLOCKS} blocks.")
    try:
        blocks = [block.model_dump() for block in _blocks.validate_python(raw)]
    except ValidationError as e:
        error = e.errors()[0]
        where = error["loc"]            # e.g. (3, "multiple_choice", "options", 0, "text")
        number = where[0] + 1 if where and isinstance(where[0], int) else "?"
        field = ", ".join(str(part) for part in where[2:]) or "its type"
        raise LessonError(f"Block {number} cannot be saved ({field}): {error['msg']}.")
    ids = [block["id"] for block in blocks]
    for block in blocks:
        if block["type"] == "multiple_choice":
            ids += [f"{block['id']}/{option['id']}" for option in block["options"]]
    if len(set(ids)) != len(ids):
        raise LessonError("Two blocks, or two options of a question, have the same id.")
    if len(json.dumps(blocks)) > MAX_LESSON_BYTES:
        raise LessonError("This lesson is too long to save. Split it into two lessons.")
    pictures = {block["image_id"] for block in blocks if block["type"] == "image" and block["image_id"] is not None}
    if pictures - set(db.scalars(select(LessonImage.id).where(LessonImage.lesson_id == lesson.id))):
        raise LessonError("A picture in this lesson was not uploaded to it. Add the picture again.")
    return blocks


def is_check(block: dict) -> bool:
    return block["type"] in CHECKS


def _is_empty(block: dict) -> bool:
    """Nothing to show: left out of what students get."""
    kind = block["type"]
    if kind in ("text", "callout"):
        return not block["text"].strip()
    if kind == "code":
        return not block["code"].strip()
    if kind == "image":
        return block["image_id"] is None
    if kind == "video":
        return not block["url"].strip()
    if kind == "assignment":
        return block["assignment_id"] is None
    return False


def problems(blocks: list[dict]) -> list[str]:
    """Why this working copy cannot be published yet. Empty when it can."""
    if all(_is_empty(block) for block in blocks):
        return ["The lesson is empty: write something first."]
    found = []
    for number, block in enumerate(blocks, start=1):
        kind = block["type"]
        if kind == "multiple_choice":
            where = f"Block {number} (multiple choice)"
            if not block["question"].strip():
                found.append(f"{where}: write the question.")
            if len(_options(block)) < 2:
                found.append(f"{where}: give at least two options.")
            elif not _correct_ids(block):
                found.append(f"{where}: mark the correct option.")
        elif kind == "short_answer":
            where = f"Block {number} (short answer)"
            if not block["question"].strip():
                found.append(f"{where}: write the question.")
            if not _accepted(block):
                found.append(f"{where}: give at least one accepted answer.")
        elif kind == "video" and block["url"].strip() and video_id(block["url"]) is None:
            found.append(f"Block {number} (video): this is not a link to a YouTube video.")
    return found


# --- who sees what --------------------------------------------------------------------------------

def _visible_to(user: PlatformUser):
    """The condition for the lessons this user may see."""
    if user.can_teach:
        return true()
    in_their_course = exists().where(CourseStudent.course_id == Lesson.course_id, CourseStudent.user_id == user.id)
    return and_(Lesson.published, or_(Lesson.for_everyone, in_their_course))


def list_visible(db: Session, user: PlatformUser) -> list[Lesson]:
    """In the order the teachers put them in."""
    return list(db.scalars(select(Lesson).where(_visible_to(user)).order_by(Lesson.position, Lesson.id)))


def get_visible(db: Session, user: PlatformUser, lesson_id: int) -> Lesson | None:
    return db.scalar(select(Lesson).where(Lesson.id == lesson_id, _visible_to(user)))


def content(lesson: Lesson, user: PlatformUser) -> list[dict]:
    """The blocks this person works with: teachers try out their working copy, students get the
    published one."""
    return lesson.blocks if user.can_teach else lesson.live_blocks


def summary(lesson: Lesson, course_names: dict[int, str]) -> dict:
    """What every logged-in person may know about a lesson they can see."""
    return {
        "id": lesson.id,
        "title": lesson.title,
        "summary": lesson.summary,
        "published": lesson.published,
        "course_id": lesson.course_id,
        "course": course_names.get(lesson.course_id) if lesson.course_id else None,
        "questions": lesson.questions,
    }


def audience(db: Session, lesson: Lesson) -> list[User]:
    """The students this lesson is given to, by name."""
    query = select(User).where(User.role == "student")
    if not lesson.for_everyone:
        query = query.where(User.id.in_(select(CourseStudent.user_id).where(CourseStudent.course_id == lesson.course_id)))
    return list(db.scalars(query.order_by(User.display_name, User.id)))


# --- knowledge checks -----------------------------------------------------------------------------

def _options(block: dict) -> list[dict]:
    """The options of a multiple-choice question that have something written in them. The ones left
    empty in the editor are not shown and cannot be chosen."""
    return [option for option in block["options"] if option["text"].strip()]


def _correct_ids(block: dict) -> list[str]:
    return sorted(option["id"] for option in _options(block) if option["correct"])


def _normal(text: str) -> str:
    return " ".join(text.split()).casefold()


def _accepted(block: dict) -> list[str]:
    return [answer.strip() for answer in block["answers"] if answer.strip()]


def _answer_key(block: dict) -> list:
    """What decides whether an answer to this question is right. When a teacher publishes a change to
    it, the answers given before no longer say anything and are removed (see `publish`)."""
    if block["type"] == "multiple_choice":
        return [sorted(option["id"] for option in _options(block)), _correct_ids(block)]
    return sorted({_normal(answer) for answer in _accepted(block)})


def _is_closed(answer: LessonAnswer) -> bool:
    return answer.correct or answer.attempts >= MAX_TRIES


def _state(block: dict, answer: LessonAnswer | None) -> dict | None:
    """Where this person is with one question. The explanation and the right answer are only added
    once the question is closed: answered correctly, or out of tries."""
    if answer is None:
        return None
    state = {
        **answer.answer,                # their last answer: {"choices": [...]} or {"text": "..."}
        "attempts": answer.attempts,
        "tries_left": max(0, MAX_TRIES - answer.attempts),
        "correct": answer.correct,
        "closed": _is_closed(answer),
    }
    if state["closed"]:
        state["explanation"] = block["explanation"]
        state["solution"] = _correct_ids(block) if block["type"] == "multiple_choice" else (_accepted(block) or [""])[0]
    return state


def answers_of(db: Session, lesson_id: int, user_id: int) -> dict[str, LessonAnswer]:
    """block id -> this person's answer."""
    rows = db.scalars(select(LessonAnswer).where(LessonAnswer.lesson_id == lesson_id, LessonAnswer.user_id == user_id))
    return {row.block_id: row for row in rows}


def view(db: Session, user: PlatformUser, lesson: Lesson) -> list[dict]:
    """The lesson's blocks as this person may see them: nothing that gives away an answer, and each
    question with where they are with it."""
    blocks = content(lesson, user)
    answers = answers_of(db, lesson.id, user.id)
    linked = {block["assignment_id"] for block in blocks if block["type"] == "assignment"}
    titles = {a.id: a.title for a in assignments.list_visible(db, user) if a.id in linked} if linked else {}
    shown = []
    for block in blocks:
        kind, here = block["type"], {"type": block["type"], "id": block["id"]}
        if _is_empty(block):
            continue
        if kind in ("text", "code", "callout"):     # nothing to hide in these
            shown.append(block)
        elif kind == "image":
            shown.append({**here, "url": f"/api/lessons/{lesson.id}/images/{block['image_id']}", "alt": block["alt"]})
        elif kind == "video":
            if video_id(block["url"]):
                shown.append({**here, "video_id": video_id(block["url"])})
        elif kind == "assignment":
            if block["assignment_id"] in titles:    # left out when this person was not given the assignment
                shown.append({**here, "assignment_id": block["assignment_id"], "title": titles[block["assignment_id"]]})
        elif kind == "multiple_choice":
            shown.append({
                **here,
                "question": block["question"],
                "options": [{"id": option["id"], "text": option["text"]} for option in _options(block)],
                "multiple": len(_correct_ids(block)) > 1,
                "state": _state(block, answers.get(block["id"])),
            })
        elif kind == "short_answer":
            shown.append({**here, "question": block["question"], "state": _state(block, answers.get(block["id"]))})
    return shown


def answer(db: Session, lesson: Lesson, user: PlatformUser, block_id: str, choices: list[str] | None, text: str | None) -> dict:
    """Checks one answer and remembers it. Returns where the person now is with the question."""
    block = next((b for b in content(lesson, user) if b["id"] == block_id and is_check(b)), None)
    if block is None:
        raise LessonError("That question is no longer part of this lesson. Reload the page.")
    if block["type"] == "multiple_choice":
        chosen = sorted(set(choices or []))
        if not chosen or not set(chosen) <= {option["id"] for option in _options(block)}:
            raise LessonError("Choose one of the options.")
        given, correct = {"choices": chosen}, chosen == _correct_ids(block)
    else:
        written = (text or "").strip()
        if not written or len(written) > MAX_ANSWER_LENGTH:
            raise LessonError(f"Write an answer of at most {MAX_ANSWER_LENGTH} characters.")
        given, correct = {"text": written}, _normal(written) in _answer_key(block)

    first = insert(LessonAnswer).values(
        lesson_id=lesson.id, user_id=user.id, block_id=block_id, answer=given, correct=correct, first_try=correct, attempts=1,
    )
    # A question that is closed stays as it is: the row is only changed while tries are left.
    db.execute(first.on_conflict_do_update(
        index_elements=[LessonAnswer.lesson_id, LessonAnswer.user_id, LessonAnswer.block_id],
        set_={"answer": given, "correct": correct, "attempts": LessonAnswer.attempts + 1, "answered_at": func.now()},
        where=and_(LessonAnswer.correct.is_(False), LessonAnswer.attempts < MAX_TRIES),
    ))
    db.commit()
    return _state(block, answers_of(db, lesson.id, user.id)[block_id])


def closed_counts(db: Session, user_id: int) -> dict[int, int]:
    """lesson id -> how many of its knowledge checks this person is done with."""
    rows = db.execute(
        select(LessonAnswer.lesson_id, func.count())
        .where(LessonAnswer.user_id == user_id, or_(LessonAnswer.correct, LessonAnswer.attempts >= MAX_TRIES))
        .group_by(LessonAnswer.lesson_id)
    )
    return {row[0]: row[1] for row in rows}


# --- opening and completing -----------------------------------------------------------------------

def record_open(db: Session, lesson_id: int, user_id: int) -> None:
    """Remembers the first time this person opened this lesson."""
    db.execute(insert(LessonProgress).values(lesson_id=lesson_id, user_id=user_id).on_conflict_do_nothing())
    db.commit()


def progress_of(db: Session, user_id: int) -> dict[int, LessonProgress]:
    """lesson id -> when this person opened and completed it."""
    return {row.lesson_id: row for row in db.scalars(select(LessonProgress).where(LessonProgress.user_id == user_id))}


def complete(db: Session, lesson: Lesson, user: PlatformUser) -> None:
    answers = answers_of(db, lesson.id, user.id)
    checks = [block for block in content(lesson, user) if is_check(block)]
    if any(block["id"] not in answers or not _is_closed(answers[block["id"]]) for block in checks):
        raise LessonError("Answer every knowledge check in the lesson first.")
    record_open(db, lesson.id, user.id)
    db.execute(
        update(LessonProgress)
        .where(LessonProgress.lesson_id == lesson.id, LessonProgress.user_id == user.id, LessonProgress.completed_at.is_(None))
        .values(completed_at=func.now())
    )
    db.commit()


def start_over(db: Session, lesson_id: int, user_id: int) -> None:
    """Forgets this person's answers and that they completed the lesson."""
    db.execute(delete(LessonAnswer).where(LessonAnswer.lesson_id == lesson_id, LessonAnswer.user_id == user_id))
    db.execute(
        update(LessonProgress).where(LessonProgress.lesson_id == lesson_id, LessonProgress.user_id == user_id).values(completed_at=None)
    )
    db.commit()


def progress(db: Session, lesson: Lesson) -> dict:
    """For the teacher: every student the lesson is given to, and how each published question went."""
    students = audience(db, lesson)
    checks = [block for block in lesson.live_blocks if is_check(block)]
    opened = {row.user_id: row for row in db.scalars(select(LessonProgress).where(LessonProgress.lesson_id == lesson.id))}
    answers = list(db.scalars(select(LessonAnswer).where(
        LessonAnswer.lesson_id == lesson.id,
        LessonAnswer.block_id.in_([block["id"] for block in checks]),
        LessonAnswer.user_id.in_([student.id for student in students]),
    )))

    def tally(rows: list[LessonAnswer]) -> dict:
        return {
            "answered": len(rows),
            "correct": sum(row.correct for row in rows),
            "first_try": sum(row.first_try for row in rows),
            "missed": sum(not row.correct and _is_closed(row) for row in rows),     # out of tries
        }

    return {
        "questions": [
            {"id": block["id"], "question": block["question"], **tally([row for row in answers if row.block_id == block["id"]])}
            for block in checks
        ],
        "students": [
            {
                "id": student.id,
                "username": student.username,
                "name": student.display_name,
                "opened_at": opened[student.id].opened_at.isoformat() if student.id in opened else None,
                "completed_at": opened[student.id].completed_at.isoformat() if student.id in opened and opened[student.id].completed_at else None,
                **tally([row for row in answers if row.user_id == student.id]),
            }
            for student in students
        ],
    }


# --- changes by teachers --------------------------------------------------------------------------

def check_title(title: str) -> str:
    title = title.strip()
    if not 1 <= len(title) <= MAX_TITLE_LENGTH:
        raise LessonError(f"Titles are 1 to {MAX_TITLE_LENGTH} characters.")
    return title


def check_summary(text: str) -> str:
    text = text.strip()
    if len(text) > MAX_SUMMARY_LENGTH:
        raise LessonError(f"Summaries are at most {MAX_SUMMARY_LENGTH} characters.")
    return text


def create(db: Session, title: str, created_by: int | None) -> Lesson:
    """A new draft with nothing in it, placed after the lessons there already are."""
    last = db.scalar(select(func.max(Lesson.position)))
    lesson = Lesson(title=check_title(title), blocks=[], live_blocks=[], position=(last or 0) + 1, created_by=created_by)
    db.add(lesson)
    db.commit()
    return lesson


def set_order(db: Session, lesson_ids: list[int]) -> None:
    """Lists lessons in this order from now on."""
    for position, lesson_id in enumerate(lesson_ids, start=1):
        db.execute(update(Lesson).where(Lesson.id == lesson_id).values(position=position))
    db.commit()


def publish(db: Session, lesson: Lesson) -> None:
    """Gives students the working copy as it is now."""
    found = problems(lesson.blocks)
    if found:
        raise LessonError("\n".join(found))
    before = {block["id"]: _answer_key(block) for block in lesson.live_blocks if is_check(block)}
    after = {block["id"]: _answer_key(block) for block in lesson.blocks if is_check(block)}
    changed = [block_id for block_id, key in before.items() if after.get(block_id) != key]
    if changed:     # removed, or with other options or answers: what students answered says nothing now
        db.execute(delete(LessonAnswer).where(LessonAnswer.lesson_id == lesson.id, LessonAnswer.block_id.in_(changed)))
    lesson.live_blocks = lesson.blocks
    lesson.questions = len(after)
    lesson.published = True
    lesson.published_at = datetime.now(timezone.utc)
    # Pictures that were uploaded and then taken out again. Not the newest ones: the editor may be
    # about to save the block one of them goes with.
    used = {block["image_id"] for block in lesson.blocks if block["type"] == "image" and block["image_id"] is not None}
    db.execute(delete(LessonImage).where(
        LessonImage.lesson_id == lesson.id,
        LessonImage.id.not_in(used),
        LessonImage.created_at < datetime.now(timezone.utc) - timedelta(hours=1),
    ))
    db.commit()


# --- pictures -------------------------------------------------------------------------------------

def image_type(data: bytes) -> str | None:
    """The kind of picture this file is, going by how it starts and never by its name. Only these
    kinds are stored: none of them can carry scripts (SVG can, so it is refused)."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def add_image(db: Session, lesson: Lesson, data: bytes) -> LessonImage:
    if len(data) > MAX_IMAGE_BYTES:
        raise LessonError(f"The picture is larger than {MAX_IMAGE_BYTES // (1024 * 1024)} MB. Make it smaller and try again.")
    kind = image_type(data)
    if kind is None:
        raise LessonError("Choose a PNG, JPEG, GIF or WebP picture.")
    if db.scalar(select(func.count()).select_from(LessonImage).where(LessonImage.lesson_id == lesson.id)) >= MAX_IMAGES:
        raise LessonError(f"A lesson has at most {MAX_IMAGES} pictures.")
    image = LessonImage(lesson_id=lesson.id, content_type=kind, data=data)
    db.add(image)
    db.commit()
    return image


def get_image(db: Session, lesson_id: int, image_id: int) -> tuple[str, bytes] | None:
    row = db.execute(
        select(LessonImage.content_type, LessonImage.data).where(LessonImage.id == image_id, LessonImage.lesson_id == lesson_id)
    ).first()
    return (row.content_type, row.data) if row else None
