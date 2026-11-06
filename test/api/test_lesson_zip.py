"""Exporting lessons as a .zip and importing them again, here or on another platform: their blocks,
pictures and linked notebooks. On a real (throwaway) Postgres database; the grading service is
replaced by a stand-in."""
import io
import json
import os
import zipfile
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import grading, lesson_zip, lessons
from app.main import app
from app.models import Assignment, Lesson, LessonImage
from conftest import notebook_file, upload

# A picture of 1.5 MB that does not compress: the import request is larger than the 1 MB most requests may be.
PICTURE = b"\x89PNG\r\n\x1a\n" + os.urandom(1_500_000)
TODAY = date.today().isoformat()


def blocks(assignment_id=1, image_id=1):
    return [
        {"type": "text", "id": "text1", "text": "# TLS\nTLS protects data **in transit**."},
        {"type": "image", "id": "pic1", "image_id": image_id, "alt": "A padlock in the address bar"},
        {"type": "image", "id": "pic2", "image_id": None, "alt": ""},          # a picture block not filled in yet
        {"type": "video", "id": "vid1", "url": "https://youtu.be/dQw4w9WgXcQ"},
        {"type": "assignment", "id": "lab1", "assignment_id": assignment_id},
        {"type": "multiple_choice", "id": "quiz1", "question": "Which port does HTTPS use?", "explanation": "443.", "options": [
            {"id": "quiz1-a", "text": "80", "correct": False}, {"id": "quiz1-b", "text": "443", "correct": True},
        ]},
        {"type": "short_answer", "id": "short1", "question": "What does TLS stand for?", "answers": ["Transport Layer Security"], "explanation": ""},
    ]


def write(teacher, title="TLS basics", picture=PICTURE, assignment_id=1) -> int:
    """A published lesson for every student, with a picture and a link to an assignment."""
    lesson_id = teacher.post("/api/teach/lessons", json={"title": title}).json()["id"]
    image_id = teacher.post("/api/teach/lesson-images", data={"lesson_id": lesson_id}, files={"file": ("p.png", picture)}).json()["id"]
    r = teacher.patch(f"/api/teach/lessons/{lesson_id}", json={
        "summary": "What TLS is for.", "tags": ["Cybersecurity", "TLS"], "blocks": blocks(assignment_id, image_id), "for_everyone": True,
    })
    assert r.status_code == 200, r.text
    assert teacher.post(f"/api/teach/lessons/{lesson_id}/publish").status_code == 200
    return lesson_id


def export(client, ids="1"):
    return client.get(f"/api/teach/lessons.zip?ids={ids}")


def bring_in(client, data: bytes, audience="none"):
    return client.post("/api/teach/lesson-imports", data={"for": audience}, files={"file": ("lessons.zip", data, "application/zip")})


def opened(content: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def zipped(files: dict[str, bytes | dict]) -> bytes:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, json.dumps(content) if isinstance(content, dict) else content)
    return out.getvalue()


def stored(db) -> tuple[int, int, int]:
    """How many lessons, pictures and assignments there are."""
    return tuple(db.scalar(select(func.count()).select_from(table)) for table in (Lesson, LessonImage, Assignment))


@pytest.fixture
def otter(monkeypatch):
    """Stands in for the grading service: every notebook Otter prepares has questions of 2 and 3 points."""
    prepared = []

    async def prepare(master, name, gpu, data):
        prepared.append(name)
        return notebook_file("def square(x):\n    ..."), b"the autograder package"

    async def grade(notebook, autograder, name, gpu):
        return {"tests": [{"name": "q1", "score": 0, "max_score": 2.0}, {"name": "q2", "score": 0, "max_score": 3.0}]}

    monkeypatch.setattr(grading, "prepare", prepare)
    monkeypatch.setattr(grading, "grade", grade)
    return prepared


def otter_master() -> bytes:
    notebook = json.loads(notebook_file("def square(x):\n    return x * x # SOLUTION"))
    notebook["cells"].insert(0, {"cell_type": "raw", "metadata": {}, "source": "# ASSIGNMENT CONFIG\nname: functions-lab"})
    return json.dumps(notebook).encode()


def test_a_lesson_goes_out_as_a_zip_and_comes_back_in(people, db):
    teacher, maria, _ = people
    assert upload(teacher, "Loops", description="For loops.").status_code == 201
    teacher.patch("/api/teach/assignments/1", json={"points": 10})
    write(teacher)
    maria.post("/api/lessons/1/answers", json={"block_id": "short1", "text": "Totally Lost Student"})

    r = export(teacher)
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert r.headers["content-disposition"] == f'attachment; filename="tls-basics-{TODAY}.zip"'
    assert r.headers["cache-control"] == "no-store"
    files = opened(r.content)
    assert sorted(files) == [
        "01-tls-basics/images/1.png", "01-tls-basics/lesson.json", "README.txt", "lessons.json", "notebooks/loops-1/lab.ipynb",
    ]
    assert files["01-tls-basics/images/1.png"] == PICTURE and files["notebooks/loops-1/lab.ipynb"] == notebook_file()
    contents = json.loads(files["lessons.json"])
    assert (contents["format"], contents["version"], contents["lessons"]) == ("cyberai-lessons", 1, ["01-tls-basics/lesson.json"])
    assert contents["notebooks"] == [
        {"file": "notebooks/loops-1/lab.ipynb", "title": "Loops", "description": "For loops.", "requires_gpu": False, "points": 10.0, "data": []},
    ]
    lesson = json.loads(files["01-tls-basics/lesson.json"])
    assert (lesson["title"], lesson["summary"], lesson["tags"]) == ("TLS basics", "What TLS is for.", ["Cybersecurity", "TLS"])
    # Pictures and notebooks are named by their file in the .zip, not by an id that means nothing elsewhere.
    picture, empty, link = lesson["blocks"][1], lesson["blocks"][2], lesson["blocks"][4]
    assert picture == {"type": "image", "id": "pic1", "alt": "A padlock in the address bar", "image": "01-tls-basics/images/1.png"}
    assert empty["image"] is None and link == {"type": "assignment", "id": "lab1", "notebook": "notebooks/loops-1/lab.ipynb"}
    # The answers are in it (it is for teachers); what students did is not.
    assert b"Transport Layer Security" in files["01-tls-basics/lesson.json"]
    assert not any(b"Totally Lost Student" in content or b"maria" in content for content in files.values())

    # Imported on the same platform: a new draft after the others, for nobody, linked to the same assignment.
    r = bring_in(teacher, r.content)
    assert r.status_code == 201, r.text
    assert r.json() == {"lessons": [{"id": 2, "title": "TLS basics"}], "notebooks_added": [], "notebooks_linked": ["Loops"], "warnings": []}
    copy = teacher.get("/api/teach/lessons/2").json()
    assert (copy["published"], copy["for_everyone"], copy["course_id"], copy["summary"]) == (False, False, None, "What TLS is for.")
    assert copy["tags"] == ["Cybersecurity", "TLS"]
    assert [lesson["id"] for lesson in teacher.get("/api/teach/lessons").json()] == [1, 2]
    new_picture = copy["blocks"][1]["image_id"]
    assert new_picture != 1 and copy["blocks"] == blocks(assignment_id=1, image_id=new_picture)
    assert teacher.get(f"/api/lessons/2/images/{new_picture}").content == PICTURE
    assert stored(db) == (2, 2, 1)
    assert [lesson["title"] for lesson in maria.get("/api/lessons").json()] == ["TLS basics"]      # only the published one



def test_picture_questions_keep_their_picture(people, db):
    teacher, _, _ = people
    lesson_id = teacher.post("/api/teach/lessons", json={"title": "Phishing"}).json()["id"]
    image_id = teacher.post("/api/teach/lesson-images", data={"lesson_id": lesson_id}, files={"file": ("p.png", PICTURE)}).json()["id"]
    question = {
        "type": "multiple_choice", "id": "tfq1", "question": "This email is phishing.", "explanation": "", "options": [
            {"id": "tfq1-a", "text": "True", "correct": True}, {"id": "tfq1-b", "text": "False", "correct": False},
        ], "picture": {"image_id": image_id, "alt": "An email"},
    }
    assert teacher.patch(f"/api/teach/lessons/{lesson_id}", json={"blocks": [question]}).status_code == 200

    files = opened(export(teacher, str(lesson_id)).content)
    assert files["01-phishing/images/1.png"] == PICTURE
    assert json.loads(files["01-phishing/lesson.json"])["blocks"][0]["picture"] == {"image": "01-phishing/images/1.png", "alt": "An email"}

    r = bring_in(teacher, export(teacher, str(lesson_id)).content)
    assert r.status_code == 201 and r.json()["warnings"] == [], r.text
    copy_id = r.json()["lessons"][0]["id"]
    copy = teacher.get(f"/api/teach/lessons/{copy_id}").json()["blocks"][0]
    new_picture = copy["picture"]["image_id"]
    assert new_picture != image_id and copy == {**question, "picture": {"image_id": new_picture, "alt": "An email"}}
    assert teacher.get(f"/api/lessons/{copy_id}/images/{new_picture}").content == PICTURE

def test_on_another_platform_the_notebooks_come_too(people, db, otter):
    teacher, maria, _ = people
    teacher.post("/api/teach/courses", json={"name": "CS 101"})
    upload(teacher, "Loops")
    teacher.patch("/api/teach/assignments/1", json={"points": 10})
    upload(teacher, "Functions lab", content=otter_master())
    assert otter == ["lab.ipynb"]
    write(teacher, "First", assignment_id=1)
    write(teacher, "Second", assignment_id=2)

    r = export(teacher, "2,1")
    assert r.headers["content-disposition"] == f'attachment; filename="2-lessons-{TODAY}.zip"'
    files = opened(r.content)
    assert json.loads(files["lessons.json"])["lessons"] == ["01-second/lesson.json", "02-first/lesson.json"]
    # An autograded notebook goes out as the teacher uploaded it, with its solutions.
    assert files["notebooks/functions-lab-2/lab.ipynb"] == otter_master()
    assert json.loads(files["lessons.json"])["notebooks"][1]["points"] is None       # its points come from its tests

    # Another platform: none of these lessons or assignments are there.
    for path in ["/api/teach/lessons/1", "/api/teach/lessons/2", "/api/teach/assignments/1", "/api/teach/assignments/2"]:
        assert teacher.delete(path).status_code == 200
    r = bring_in(teacher, r.content, audience="1")
    assert r.status_code == 201, r.text
    assert r.json()["lessons"] == [{"id": 3, "title": "Second"}, {"id": 4, "title": "First"}]
    assert r.json()["notebooks_added"] == ["Functions lab", "Loops"] and r.json()["notebooks_linked"] == []
    assert otter == ["lab.ipynb", "lab.ipynb"]        # prepared again by Otter, as on Upload notebook

    lab, loops = db.scalars(select(Assignment).order_by(Assignment.id)).all()
    assert (loops.id, loops.title, loops.points, loops.autograded, loops.notebook) == (4, "Loops", 10.0, False, notebook_file())
    assert (lab.title, lab.autograded, lab.master, lab.points, lab.question_points) == ("Functions lab", True, otter_master(), 5.0, {"q1": 2.0, "q2": 3.0})
    assert lab.notebook == notebook_file("def square(x):\n    ...")      # students get Otter's version
    # Lessons and new assignments: drafts, for the course chosen.
    assert all((a.published, a.course_id, a.slug) == (False, 1, f"{a.title.lower().replace(' ', '-')}-{a.id}") for a in (loops, lab))
    for lesson_id, assignment_id in [(3, 3), (4, 4)]:
        copy = teacher.get(f"/api/teach/lessons/{lesson_id}").json()
        assert (copy["published"], copy["course_id"], copy["blocks"][4]["assignment_id"]) == (False, 1, assignment_id)
    assert maria.get("/api/lessons").json() == []


def test_nothing_is_imported_when_the_grading_service_is_down(people, db, otter, monkeypatch):
    teacher, _, _ = people
    upload(teacher, "Functions lab", content=otter_master())
    write(teacher)
    content = export(teacher).content
    teacher.delete("/api/teach/assignments/1")

    async def unreachable(master, name, gpu, data):
        raise grading.GraderUnreachable("down")

    monkeypatch.setattr(grading, "prepare", unreachable)
    r = bring_in(teacher, content)
    assert r.status_code == 503 and "Nothing was imported" in r.json()["detail"]
    assert stored(db) == (1, 1, 0)


def test_only_teachers_export_and_import(people, db):
    teacher, maria, _ = people
    write(teacher, assignment_id=None)
    content = export(teacher).content
    assert export(maria).status_code == 403 and bring_in(maria, content).status_code == 403
    nobody = TestClient(app)
    assert export(nobody).status_code == 401 and bring_in(nobody, content).status_code == 401
    assert export(teacher, "1,99").status_code == 404
    assert export(teacher, "one").status_code == 422 and export(teacher, "").status_code == 422
    assert bring_in(teacher, content, audience="99").json()["detail"] == "That course does not exist."
    assert bring_in(teacher, content, audience="9" * 20).status_code == 422       # not a course id the database can hold
    assert stored(db) == (1, 1, 0)


def test_what_a_file_leaves_out_only_leaves_its_block_empty(people, db):
    teacher, _, _ = people
    lesson = {"title": "Ports", "blocks": [
        {"type": "text", "id": "text1", "text": "Hello"},
        {"type": "image", "id": "pic1", "image": "01-ports/images/1.png", "alt": ""},
        {"type": "assignment", "id": "lab1", "notebook": "notebooks/lab/lab.ipynb"},
        {"type": "assignment", "id": "lab2", "notebook": "notebooks/lab/lab.ipynb"},
    ]}
    r = bring_in(teacher, zipped({
        "lessons.json": {"format": "cyberai-lessons", "version": 1, "lessons": ["01-ports/lesson.json"]},
        "01-ports/lesson.json": lesson,
    }))
    assert r.status_code == 201, r.text
    assert r.json()["warnings"] == [
        '"Ports": the picture 01-ports/images/1.png is not in the file, so its block is empty.',
        '"Ports": the notebook notebooks/lab/lab.ipynb is not in the file, so its link is empty.',
    ]
    assert [block.get("image_id", block.get("assignment_id")) for block in teacher.get("/api/teach/lessons/1").json()["blocks"][1:]] == [None] * 3


@pytest.mark.parametrize("files, refusal", [
    ({"notes.txt": b"hello"}, "This .zip is not a lessons export: there is no lessons.json in it."),
    ({"lessons.json": b"{not json"}, "lessons.json cannot be read"),
    ({"lessons.json": {"format": "other", "version": 1, "lessons": ["a.json"]}}, "not a lessons export from this platform"),
    ({"lessons.json": {"format": "cyberai-lessons", "version": 2, "lessons": ["a.json"]}}, "newer version of the platform"),
    ({"lessons.json": {"format": "cyberai-lessons", "version": 1, "lessons": []}}, "There are no lessons in this file."),
    ({"lessons.json": {"format": "cyberai-lessons", "version": 1, "lessons": ["../../etc/passwd"]}}, "is not the name of a file in a lessons export"),
    ({"lessons.json": {"format": "cyberai-lessons", "version": 1, "lessons": ["/a.json"]}}, "is not the name of a file in a lessons export"),
    ({"lessons.json": {"format": "cyberai-lessons", "version": 1, "lessons": ["a.json"]}}, "lessons.json lists a.json, but the file has no a.json in it."),
    ({"lessons.json": {"format": "cyberai-lessons", "version": 1, "lessons": ["a.json"]}, "a.json": {"title": "", "blocks": []}}, "a.json: Titles are 1 to 120"),
    ({"lessons.json": {"format": "cyberai-lessons", "version": 1, "lessons": ["a.json"]}, "a.json": {"title": "A", "blocks": [{"type": "script"}]}},
     "a.json: Block 1 cannot be saved"),
    ({"lessons.json": {"format": "cyberai-lessons", "version": 1, "lessons": ["a.json"]},
      "a.json": {"title": "A", "blocks": [{"type": "image", "id": "pic1", "image": "a.svg"}]}, "a.svg": b"<svg onload='alert(1)'/>"},
     "a.svg is not a PNG, JPEG, GIF or WebP picture."),
    ({"lessons.json": {"format": "cyberai-lessons", "version": 1, "lessons": ["a.json"], "notebooks": [{"file": "n/lab.ipynb", "title": "Lab"}]},
      "a.json": {"title": "A", "blocks": [{"type": "assignment", "id": "lab1", "notebook": "n/lab.ipynb"}]}, "n/lab.ipynb": b"{}"},
     "The notebook n/lab.ipynb: This file is not a valid Jupyter notebook."),
])
def test_files_that_are_refused_leave_nothing_behind(people, db, files, refusal):
    teacher, _, _ = people
    r = bring_in(teacher, zipped(files))
    assert r.status_code == 400 and refusal in r.json()["detail"], r.text
    assert stored(db) == (0, 0, 0)


def test_what_is_too_large(people, db, monkeypatch):
    teacher, _, _ = people
    write(teacher, assignment_id=None)
    content = export(teacher).content
    assert bring_in(teacher, b"not a zip").json()["detail"] == "This is not a .zip file. Choose a file exported from Teach > Lessons."

    monkeypatch.setattr(lessons, "MAX_IMAGE_BYTES", 1024 * 1024)
    assert bring_in(teacher, content).json()["detail"] == "01-tls-basics/images/1.png is larger than 1 MB."
    monkeypatch.setattr(lesson_zip, "MAX_ENTRIES", 3)
    assert bring_in(teacher, content).json()["detail"] == "This file holds more than 3 files. Export fewer lessons at a time."
    # Never a file that could not be imported again.
    monkeypatch.setattr(lesson_zip, "MAX_FILE_BYTES", 1024 * 1024)
    r = export(teacher)
    assert r.status_code == 400 and "Export fewer lessons at a time" in r.json()["detail"]
    assert stored(db) == (1, 1, 0)
