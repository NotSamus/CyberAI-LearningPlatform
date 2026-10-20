"""Lessons as a .zip file: to take them to another platform (from a laptop to the server), or to
keep a copy and bring it back.

A teacher exports one lesson or several (Teach > Lessons) and imports the file on any platform,
this one included. It holds each lesson's working copy (what the teacher is writing, which may have
changes students do not have yet), the pictures it shows and the notebook assignments it links to.
Nothing a student did is in it. It does hold the answers to the knowledge checks, and each
autograded notebook as the teacher uploaded it, with its solutions and hidden tests: teachers only.

In the file (format version 1):

    lessons.json                          what is in it: {"format": "cyberai-lessons", "version": 1,
                                          "exported_at", "lessons": [each lesson's file, in order],
                                          "notebooks": [{"file", "title", "description", "requires_gpu", "points"}]}
    01-tls-basics/lesson.json             {"title", "summary", "blocks"}
    01-tls-basics/images/1.png            the lesson's pictures
    notebooks/functions-lab-7/lab.ipynb   the notebooks the lessons link to,
    notebooks/functions-lab-7/ports.csv   and each one's data files beside it
    README.txt                            what this is, for whoever opens the file

The blocks are as they are stored (app/lessons.py), except that pictures and notebooks are named by
their file in the .zip, since ids mean nothing on another platform: a picture block, and the
"picture" of a picture question, have "image" in place of "image_id", a notebook link "notebook" in
place of "assignment_id".

Importing first reads and checks everything (`read`), and the route has Otter prepare the
autograded notebooks; only then is anything stored, all in one go (`store`), so a file that cannot
be taken in leaves nothing behind. The lessons come in as drafts after the ones there are, given to
nobody or to whom the teacher chose. A linked notebook becomes a draft assignment as if it had been
chosen on Upload notebook, unless an assignment with the same title and the same file is here
already: the lesson then links to that one.

The routes are in app/lesson_routes.py.
"""
import io
import json
import re
import zipfile
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone

from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, undefer

from app import assignments, lessons
from app.exports import file_stem
from app.lessons import LessonError
from app.models import Assignment, Lesson, LessonImage

FORMAT, VERSION = "cyberai-lessons", 1
MAX_FILE_BYTES = 100 * 1024 * 1024          # the .zip as uploaded (app/main.py lets an import request be this large)
MAX_UNPACKED_BYTES = 3 * MAX_FILE_BYTES     # all that is read out of it, together
MAX_ENTRIES = 25_000                        # files in it: 200 lessons of 100 pictures, and their notebooks
MAX_LESSONS = 200                           # in one file
MAX_CONTENTS_BYTES = 1024 * 1024            # lessons.json
MAX_LESSON_FILE_BYTES = 2 * lessons.MAX_LESSON_BYTES    # a lesson.json: its blocks, laid out to be read
EXTENSIONS = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/webp": ".webp"}

README = """\
Lessons exported from the cyberAI platform (Teach > Lessons).

To bring them in, open Teach > Lessons on the platform and choose Import. They come in as drafts.

This file holds the answers to the lessons' knowledge checks, and every autograded notebook they
link to with its solutions and hidden tests. Keep it away from students.

lessons.json lists the lessons in order. Each numbered folder holds one lesson (lesson.json) and
its pictures; notebooks/ holds the notebook assignments the lessons link to, with their data files.
"""


def _mb(size: int) -> str:
    return f"{size // (1024 * 1024)} MB"


def _json(value) -> bytes:
    return json.dumps(value, indent=2, ensure_ascii=False).encode()


# --- exporting ------------------------------------------------------------------------------------

def _named(block: dict, pictures: dict[int, str], notebooks: dict[int, str]) -> dict:
    """A block as it goes into the file: its picture or notebook named by its file there, not by its
    id here. One that is gone (an assignment since deleted) is left empty, as in the editor. The
    type and the id come first, for whoever reads the file (the database keeps fields in its own order)."""
    block = {"type": block["type"], "id": block["id"], **block}
    if block["type"] == "image":
        return {**{k: v for k, v in block.items() if k != "image_id"}, "image": pictures.get(block["image_id"])}
    if block["type"] == "multiple_choice" and block.get("picture"):
        picture = block["picture"]
        return {**block, "picture": {"image": pictures.get(picture["image_id"]), "alt": picture["alt"]}}
    if block["type"] == "assignment":
        return {**{k: v for k, v in block.items() if k != "assignment_id"}, "notebook": notebooks.get(block["assignment_id"])}
    return block


def export(db: Session, chosen: list[Lesson]) -> bytes:
    """These lessons as a .zip, in this order. Refused when the file would be too large to import
    again: better to find out now than on the day it is needed."""
    linked = {block["assignment_id"] for lesson in chosen for block in lesson.blocks if block["type"] == "assignment"} - {None}
    query = select(Assignment).where(Assignment.id.in_(linked)).options(undefer(Assignment.notebook), undefer(Assignment.master))
    notebooks = list(db.scalars(query.order_by(Assignment.id)))
    files = {a.id: f"notebooks/{a.slug}/{a.notebook_name}" for a in notebooks}

    out, unpacked = io.BytesIO(), 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        def put(path: str, data: bytes, compression: int = zipfile.ZIP_DEFLATED) -> None:
            nonlocal unpacked
            unpacked += len(data)
            archive.writestr(path, data, compress_type=compression)

        put("README.txt", README.encode())
        lesson_files = []
        for n, lesson in enumerate(chosen, start=1):
            folder = f"{n:02d}-{file_stem(lesson.title, 'lesson')}"
            used = lessons.picture_ids(lesson.blocks)
            pictures: dict[int, str] = {}
            rows = db.execute(
                select(LessonImage.id, LessonImage.content_type, LessonImage.data)
                .where(LessonImage.lesson_id == lesson.id, LessonImage.id.in_(used)).order_by(LessonImage.id)
            )
            for image in rows:
                pictures[image.id] = f"{folder}/images/{len(pictures) + 1}{EXTENSIONS.get(image.content_type, '')}"
                put(pictures[image.id], image.data, zipfile.ZIP_STORED)        # pictures are compressed already
            blocks = [_named(block, pictures, files) for block in lesson.blocks]
            put(f"{folder}/lesson.json", _json({"title": lesson.title, "summary": lesson.summary, "blocks": blocks}))
            lesson_files.append(f"{folder}/lesson.json")
        data_files: dict[int, list[str]] = {}
        for a in notebooks:
            put(files[a.id], a.master if a.autograded else a.notebook)     # what the teacher uploaded
            folder = files[a.id].rsplit("/", 1)[0]
            data_files[a.id] = []
            for name, content in assignments.data_bytes(db, a.id).items():
                data_files[a.id].append(f"{folder}/{name}")
                put(f"{folder}/{name}", content)
        put("lessons.json", _json({
            "format": FORMAT,
            "version": VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "lessons": lesson_files,
            "notebooks": [
                {
                    "file": files[a.id], "title": a.title, "description": a.description, "requires_gpu": a.requires_gpu,
                    "points": None if a.autograded else a.points,       # an autograded one's come from its tests
                    "data": data_files[a.id],                           # its data files, beside it
                }
                for a in notebooks
            ],
        }))
    content = out.getvalue()
    if len(content) > MAX_FILE_BYTES or unpacked > MAX_UNPACKED_BYTES:
        raise LessonError(
            f"These lessons make a file larger than the {_mb(MAX_FILE_BYTES)} an import takes. Export fewer lessons at a time."
        )
    return content


# --- importing ------------------------------------------------------------------------------------

class _Notebook(BaseModel):
    file: str
    title: str
    description: str = ""
    requires_gpu: bool = False
    points: float | None = None
    data: list[str] = Field(default_factory=list, max_length=assignments.MAX_DATA_FILES)     # its data files' paths in the .zip


class _Contents(BaseModel):
    format: str
    version: int
    lessons: list[str] = Field(max_length=MAX_LESSONS)
    notebooks: list[_Notebook] = Field(default_factory=list, max_length=MAX_ENTRIES)


class _LessonFile(BaseModel):
    title: str
    summary: str = ""
    blocks: list = Field(default_factory=list)          # checked by lessons.check_shape


@dataclass
class NewLesson:
    title: str
    summary: str
    blocks: list[dict]                  # checked, with no picture or notebook linked yet
    pictures: dict[str, str]            # block id -> its picture's file in the .zip
    notebooks: dict[str, str]           # block id -> its notebook's file in the .zip


@dataclass
class NewNotebook:
    file: str                           # in the .zip
    title: str
    description: str
    requires_gpu: bool
    points: float | None                # what a hand-graded one is out of
    name: str                           # its file name in students' homes
    data: bytes                         # as the teacher uploaded it
    existing: int | None                # the id of the same assignment, when it is here already
    data_files: dict[str, bytes] = field(default_factory=dict)      # name -> contents: datasets beside the notebook
    otter: dict = field(default_factory=dict)       # for an autograded one: grading.autograded_fields, filled in by the route


@dataclass
class Found:
    """What an exported file holds, checked, with nothing stored yet."""
    lessons: list[NewLesson] = field(default_factory=list)
    pictures: dict[str, tuple[str, bytes]] = field(default_factory=dict)    # file in the .zip -> (kind, data)
    notebooks: dict[str, NewNotebook] = field(default_factory=dict)         # file in the .zip -> the notebook
    warnings: list[str] = field(default_factory=list)


# A file name inside the .zip: folders and names of letters, digits and . _ - and spaces, never
# starting with a dot (so never "..") nor with "/". Nothing is unpacked to disk, but names are kept plain anyway.
_PATH = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._ -]*(?:/[A-Za-z0-9_][A-Za-z0-9._ -]*)*")


class _Files:
    """The files in an uploaded .zip, read one at a time, with a limit on each and on all of them.
    Only the files lessons.json leads to are ever read."""

    def __init__(self, archive: zipfile.ZipFile):
        self.archive, self.total = archive, 0

    def read(self, path: str, limit: int) -> bytes | None:
        """The file's contents, or None when the .zip has no such file."""
        if len(path) > 255 or not _PATH.fullmatch(path):
            raise LessonError(f'"{path[:100]}" is not the name of a file in a lessons export.')
        try:
            info = self.archive.getinfo(path)
        except KeyError:
            return None
        too_large = LessonError(f"{path} is larger than {_mb(limit)}.")
        if info.file_size > limit:
            raise too_large
        try:
            with self.archive.open(info) as file:
                data = file.read(limit + 1)     # the size the .zip gives can be wrong: one byte past the limit says enough
        except (zipfile.BadZipFile, zlib.error, EOFError, RuntimeError, NotImplementedError, OSError):
            raise LessonError(f"{path} could not be read: the file is damaged, or protected by a password.")
        if len(data) > limit:
            raise too_large
        self.total += len(data)
        if self.total > MAX_UNPACKED_BYTES:
            raise LessonError(f"This file unpacks to more than {_mb(MAX_UNPACKED_BYTES)}. Export fewer lessons at a time.")
        return data


def _parse(model: type[BaseModel], data: bytes, where: str):
    try:
        return model.model_validate_json(data)
    except ValidationError as e:
        error = e.errors()[0]
        place = ", ".join(str(part) for part in error["loc"])
        raise LessonError(f"{where} cannot be read{f' ({place})' if place else ''}: {error['msg']}.")


def _unlinked(block: object) -> object:
    """A block from the file without its picture or notebook: those are linked once they are stored here."""
    if isinstance(block, dict) and block.get("type") == "image":
        return {**block, "image_id": None}
    if isinstance(block, dict) and block.get("type") == "multiple_choice" and isinstance(block.get("picture"), dict):
        return {**block, "picture": {**block["picture"], "image_id": None}}
    if isinstance(block, dict) and block.get("type") == "assignment":
        return {**block, "assignment_id": None}
    return block


def _lesson(raw: bytes, path: str) -> NewLesson:
    content = _parse(_LessonFile, raw, path)
    try:
        title = lessons.check_title(content.title)
        summary = lessons.check_summary(content.summary)
        blocks = lessons.check_shape([_unlinked(block) for block in content.blocks])
    except LessonError as e:
        raise LessonError(f"{path}: {e}")
    pictures, notebooks = {}, {}
    for original, block in zip(content.blocks, blocks, strict=True):     # check_shape keeps them in order, one for one
        key = {"image": "image", "assignment": "notebook"}.get(block["type"])
        file = original.get(key) if key else None
        if block["type"] == "multiple_choice" and block.get("picture"):     # a picture question: its file is in its "picture"
            key, file = "image", original["picture"].get("image")
        if file is None:
            continue
        if not isinstance(file, str):
            raise LessonError(f'{path}: a block\'s "{key}" is not the name of a file.')
        (pictures if key == "image" else notebooks)[block["id"]] = file
    if len(set(pictures.values())) > lessons.MAX_IMAGES:
        raise LessonError(f'"{title}" has more than {lessons.MAX_IMAGES} pictures.')
    return NewLesson(title, summary, blocks, pictures, notebooks)


def _notebook(db: Session, entry: _Notebook, data: bytes, data_files: dict[str, bytes]) -> NewNotebook:
    try:
        title = assignments.check_title(entry.title)
        description = assignments.check_description(entry.description)
        points = assignments.check_points(entry.points)
        name = assignments.safe_notebook_name(entry.file.rsplit("/", 1)[-1])
        assignments.check_notebook(data)
        assignments.check_data_files(data_files, name)
    except assignments.AssignmentError as e:
        raise LessonError(f"The notebook {entry.file}: {e}")
    # The same assignment here already (imported before, or this is where the file came from): the
    # same title, the same file as the teacher uploaded it (for an autograded one that is `master`)
    # and the same data files.
    same = db.scalars(
        select(Assignment).where(Assignment.title == title, Assignment.notebook_name == name)
        .options(undefer(Assignment.notebook), undefer(Assignment.master)).order_by(Assignment.id)
    )
    existing = next(
        (a.id for a in same if (a.master if a.autograded else a.notebook) == data and assignments.data_bytes(db, a.id) == data_files), None,
    )
    return NewNotebook(entry.file, title, description, entry.requires_gpu, points, name, data, existing, data_files)


def read(db: Session, data: bytes) -> Found:
    """Everything in an exported file, checked as if it were typed and uploaded here, with nothing
    stored. A picture or a notebook the file leaves out only leaves its block empty, with a warning;
    anything wrong with what is in it refuses the whole file (LessonError, said for the teacher)."""
    # Python reads the list of every file in a .zip as it opens it. Each one has a header that starts
    # with these four bytes, so counting them first keeps a file of millions of empty entries out.
    if data.count(b"PK\x01\x02") > MAX_ENTRIES:
        raise LessonError(f"This file holds more than {MAX_ENTRIES:,} files. Export fewer lessons at a time.")
    try:
        files = _Files(zipfile.ZipFile(io.BytesIO(data)))
    except (zipfile.BadZipFile, ValueError, OSError):
        raise LessonError("This is not a .zip file. Choose a file exported from Teach > Lessons.")
    raw = files.read("lessons.json", MAX_CONTENTS_BYTES)
    if raw is None:
        raise LessonError("This .zip is not a lessons export: there is no lessons.json in it.")
    contents = _parse(_Contents, raw, "lessons.json")
    if contents.format != FORMAT:
        raise LessonError("This .zip is not a lessons export from this platform.")
    if contents.version > VERSION:
        raise LessonError("This file comes from a newer version of the platform. Update this one, then import it.")
    if not contents.lessons:
        raise LessonError("There are no lessons in this file.")

    found = Found()
    for path in contents.lessons:
        raw = files.read(path, MAX_LESSON_FILE_BYTES)
        if raw is None:
            raise LessonError(f"lessons.json lists {path}, but the file has no {path} in it.")
        found.lessons.append(_lesson(raw, path))

    settings = {entry.file: entry for entry in contents.notebooks}
    missing: set[str] = set()
    for lesson in found.lessons:
        for block_id, path in list(lesson.pictures.items()):
            if path in found.pictures:
                continue
            picture = None if path in missing else files.read(path, lessons.MAX_IMAGE_BYTES)
            if picture is None:
                del lesson.pictures[block_id]
                if path not in missing:
                    missing.add(path)
                    found.warnings.append(f'"{lesson.title}": the picture {path} is not in the file, so its block is empty.')
                continue
            kind = lessons.image_type(picture)          # from the file itself, never from its name
            if kind is None:
                raise LessonError(f"{path} is not a PNG, JPEG, GIF or WebP picture.")
            found.pictures[path] = (kind, picture)
        for block_id, path in list(lesson.notebooks.items()):
            if path in found.notebooks:
                continue
            notebook = None if path in missing or path not in settings else files.read(path, assignments.MAX_NOTEBOOK_BYTES)
            if notebook is None:
                del lesson.notebooks[block_id]
                if path not in missing:
                    missing.add(path)
                    found.warnings.append(f'"{lesson.title}": the notebook {path} is not in the file, so its link is empty.')
                continue
            data_files = {}
            for data_path in settings[path].data:
                content = files.read(data_path, assignments.MAX_DATA_BYTES)
                if content is None:
                    found.warnings.append(f'"{settings[path].title}": its data file {data_path} is not in the file, so it is left out.')
                    continue
                data_files[assignments.data_file_name(data_path)] = content
            found.notebooks[path] = _notebook(db, settings[path], notebook, data_files)
    return found


def _linked(block: dict, lesson: NewLesson, picture_ids: dict[str, int], assignment_ids: dict[str, int]) -> dict:
    if block["type"] == "image":
        return {**block, "image_id": picture_ids.get(lesson.pictures.get(block["id"], ""))}
    if block["type"] == "multiple_choice" and block.get("picture"):
        return {**block, "picture": {**block["picture"], "image_id": picture_ids.get(lesson.pictures.get(block["id"], ""))}}
    if block["type"] == "assignment":
        return {**block, "assignment_id": assignment_ids.get(lesson.notebooks.get(block["id"], ""))}
    return block


def store(db: Session, found: Found, created_by: int | None, for_everyone: bool, course_id: int | None) -> dict:
    """Stores what `read` found, all of it or (on any error) none of it. The lessons and the new
    assignments are drafts, given to whom the teacher chose."""
    try:
        assignment_ids, added, linked = {}, [], []
        for path, notebook in found.notebooks.items():
            if notebook.existing is not None:
                assignment_ids[path] = notebook.existing
                linked.append(notebook.title)
                continue
            assignment = assignments.create(
                db, title=notebook.title, filename=notebook.name, description=notebook.description, requires_gpu=notebook.requires_gpu,
                for_everyone=for_everyone, created_by=created_by, data_files=notebook.data_files, commit=False,
                **{"notebook": notebook.data, "points": notebook.points, **notebook.otter},     # Otter's version and points, when autograded
            )
            assignment.course_id = course_id
            assignment_ids[path] = assignment.id
            added.append(notebook.title)

        last = db.scalar(select(func.max(Lesson.position))) or 0
        made = []
        for n, new in enumerate(found.lessons, start=1):
            lesson = Lesson(
                title=new.title, summary=new.summary, blocks=[], live_blocks=[], position=last + n,
                for_everyone=for_everyone, course_id=course_id, created_by=created_by,
            )
            db.add(lesson)
            db.flush()
            picture_ids = {}
            for path in dict.fromkeys(new.pictures.values()):      # each picture once, in the order the lesson shows them
                kind, data = found.pictures[path]
                image = LessonImage(lesson_id=lesson.id, content_type=kind, data=data)
                db.add(image)
                db.flush()
                picture_ids[path] = image.id
            lesson.blocks = lessons.check_blocks(db, lesson, [_linked(block, new, picture_ids, assignment_ids) for block in new.blocks])
            made.append({"id": lesson.id, "title": lesson.title})
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"lessons": made, "notebooks_added": added, "notebooks_linked": linked, "warnings": found.warnings}
