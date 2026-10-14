"""Lessons: writing and publishing them, who gets them, and knowledge checks that are checked on
the server. On a real (throwaway) Postgres database."""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import lessons
from app.main import app
from app.models import Lesson, LessonAnswer, LessonImage
from conftest import upload

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def text(block_id="text1", body="TLS protects data **in transit**."):
    return {"type": "text", "id": block_id, "text": body}


def choice(block_id="quiz1", options=(("80", False), ("443", True), ("22", False)), explanation="HTTPS listens on 443 unless told otherwise."):
    return {
        "type": "multiple_choice", "id": block_id, "question": "Which port does HTTPS use?", "explanation": explanation,
        "options": [{"id": f"{block_id}-{n}", "text": label, "correct": correct} for n, (label, correct) in enumerate(options)],
    }


def short(block_id="short1", answers=("Transport Layer Security",)):
    return {"type": "short_answer", "id": block_id, "question": "What does TLS stand for?", "answers": list(answers), "explanation": "It replaced SSL."}


def write(teacher, blocks, title="TLS basics", publish=True, **changes) -> int:
    """A lesson with these blocks, given to every student unless `changes` say otherwise."""
    lesson_id = teacher.post("/api/teach/lessons", json={"title": title}).json()["id"]
    r = teacher.patch(f"/api/teach/lessons/{lesson_id}", json={"blocks": blocks, "for_everyone": True, **changes})
    assert r.status_code == 200, r.text
    if publish:
        assert teacher.post(f"/api/teach/lessons/{lesson_id}/publish").status_code == 200
    return lesson_id


def answer(client, block_id, lesson_id=1, **given):
    return client.post(f"/api/lessons/{lesson_id}/answers", json={"block_id": block_id, **given})


def titles(client) -> list[str]:
    return [lesson["title"] for lesson in client.get("/api/lessons").json()]


def test_a_lesson_is_written_as_a_draft_and_then_published(people, db):
    teacher, maria, _ = people
    r = teacher.post("/api/teach/lessons", json={"title": "  TLS basics "})
    assert r.status_code == 201
    assert r.json() == {
        "id": 1, "title": "TLS basics", "summary": "", "published": False, "course_id": None, "course": None,
        "questions": 0, "for_everyone": False, "published_at": None, "changed": False, "blocks_count": 0,
    }

    # The working copy is saved as it is, unfinished questions included...
    unfinished = choice(options=(("80", False), ("443", False)))
    r = teacher.patch("/api/teach/lessons/1", json={"summary": "What TLS is for.", "blocks": [text(), unfinished], "for_everyone": True})
    assert r.status_code == 200 and (r.json()["summary"], r.json()["blocks_count"]) == ("What TLS is for.", 2)
    assert teacher.get("/api/teach/lessons/1").json()["blocks"] == [text(), unfinished]
    assert titles(maria) == [] and maria.get("/api/lessons/1").status_code == 404        # a draft

    # ...but it is only published once every question can be answered.
    r = teacher.post("/api/teach/lessons/1/publish")
    assert r.status_code == 400 and r.json()["detail"] == "Block 2 (multiple choice): mark the correct option."
    assert titles(maria) == []
    teacher.patch("/api/teach/lessons/1", json={"blocks": [text(), choice()]})
    r = teacher.post("/api/teach/lessons/1/publish")
    assert r.status_code == 200 and (r.json()["published"], r.json()["questions"], r.json()["changed"]) == (True, 1, False)
    assert titles(maria) == ["TLS basics"]
    assert [block["type"] for block in maria.get("/api/lessons/1").json()["blocks"]] == ["text", "multiple_choice"]

    # Later edits stay with the teacher until they are published.
    r = teacher.patch("/api/teach/lessons/1", json={"blocks": [text(body="Rewritten."), choice(), short()]})
    assert r.json()["changed"] is True and r.json()["questions"] == 1
    assert maria.get("/api/lessons/1").json()["blocks"][0]["text"] == text()["text"]
    assert teacher.post("/api/teach/lessons/1/publish").json()["questions"] == 2
    seen = maria.get("/api/lessons/1").json()
    assert seen["blocks"][0]["text"] == "Rewritten." and seen["questions"] == 2 and seen["preview"] is False

    assert teacher.post("/api/teach/lessons/1/unpublish").json()["published"] is False
    assert titles(maria) == [] and maria.get("/api/lessons/1").status_code == 404
    assert teacher.delete("/api/teach/lessons/1").json() == {"deleted": True}
    assert teacher.get("/api/teach/lessons").json() == [] and teacher.get("/api/teach/lessons/1").status_code == 404


def test_what_cannot_be_published(people, db):
    teacher, _, _ = people
    cases = [
        ([], "The lesson is empty"),
        ([text(body="  ")], "The lesson is empty"),
        ([choice(options=(("443", True),))], "give at least two options"),
        ([choice(options=(("443", True), (" ", False)))], "give at least two options"),    # an empty option is no option
        ([choice(options=(("80", False), ("443", False), ("", True)))], "mark the correct option"),
        ([{**choice(), "question": ""}], "write the question"),
        ([short(answers=(" ",))], "give at least one accepted answer"),
        ([text(), {"type": "video", "id": "video1", "url": "https://example.com/watch?v=dQw4w9WgXcQ"}], "not a link to a YouTube video"),
    ]
    for number, (blocks, why) in enumerate(cases, start=1):
        write(teacher, blocks, publish=False)
        r = teacher.post(f"/api/teach/lessons/{number}/publish")
        assert r.status_code == 400 and why in r.json()["detail"], (blocks, r.text)
    assert db.scalar(select(func.count()).select_from(Lesson).where(Lesson.published)) == 0


def test_blocks_are_checked_before_they_are_saved(people, db):
    teacher, _, _ = people
    write(teacher, [text()], publish=False)
    write(teacher, [], title="Another lesson", publish=False)
    other_picture = teacher.post("/api/teach/lesson-images", data={"lesson_id": "2"}, files={"file": ("a.png", PNG)}).json()["id"]
    bad = [
        ([{"type": "script", "id": "block1", "text": "x"}], "Block 1 cannot be saved"),
        ([text(), {"type": "text", "id": "x y", "text": ""}], "Block 2 cannot be saved"),
        ([text(), text()], "the same id"),
        ([{**choice(), "options": [{"id": "same", "text": "a"}, {"id": "same", "text": "b"}]}], "the same id"),
        ([choice(options=[(str(n), n == 0) for n in range(lessons.MAX_OPTIONS + 1)])], "Block 1 cannot be saved (options)"),
        ([text(body="x" * (lessons.MAX_TEXT_LENGTH + 1))], "Block 1 cannot be saved (text)"),
        ([text(f"text{n}") for n in range(lessons.MAX_BLOCKS + 1)], "at most 200 blocks"),
        ([text(f"text{n}", "x" * lessons.MAX_TEXT_LENGTH) for n in range(26)], "too long to save"),
        ([{"type": "image", "id": "image1", "image_id": other_picture, "alt": ""}], "was not uploaded to it"),
        ([{"type": "image", "id": "image1", "image_id": 999, "alt": ""}], "was not uploaded to it"),
    ]
    for blocks, why in bad:
        r = teacher.patch("/api/teach/lessons/1", json={"blocks": blocks, "title": "Changed"})
        assert r.status_code == 400 and why in r.json()["detail"], r.text
    saved = teacher.get("/api/teach/lessons/1").json()
    assert saved["blocks"] == [text()] and saved["title"] == "TLS basics"         # a refused change changes nothing

    # Fields the editor does not know are dropped, and what is missing gets its usual value.
    teacher.patch("/api/teach/lessons/1", json={"blocks": [{"type": "callout", "id": "note1", "text": "Careful.", "onclick": "x"}]})
    assert teacher.get("/api/teach/lessons/1").json()["blocks"] == [{"type": "callout", "id": "note1", "tone": "note", "text": "Careful."}]

    for changes, why in [({"title": " "}, "Titles are"), ({"summary": "s" * 301}, "at most 300"), ({"course_id": 9}, "course does not exist")]:
        r = teacher.patch("/api/teach/lessons/1", json=changes)
        assert r.status_code == 400 and why in r.json()["detail"]
    assert teacher.post("/api/teach/lessons", json={"title": ""}).status_code == 400
    assert teacher.patch("/api/teach/lessons/9", json={"title": "x"}).status_code == 404
    assert teacher.post("/api/teach/lessons/9/publish").status_code == 404


def test_students_are_never_sent_the_answers(people, db):
    teacher, maria, _ = people
    write(teacher, [text(), choice(), short()])
    sent = maria.get("/api/lessons/1")
    question, written = sent.json()["blocks"][1], sent.json()["blocks"][2]
    assert question == {
        "type": "multiple_choice", "id": "quiz1", "question": "Which port does HTTPS use?", "multiple": False, "state": None,
        "options": [{"id": "quiz1-0", "text": "80"}, {"id": "quiz1-1", "text": "443"}, {"id": "quiz1-2", "text": "22"}],
    }
    assert written == {"type": "short_answer", "id": "short1", "question": "What does TLS stand for?", "state": None}
    for secret in ('"correct"', "explanation", "listens on 443", "Transport Layer Security", "It replaced SSL", '"answers"'):
        assert secret not in sent.text and secret not in maria.get("/api/lessons").text

    # Options left empty in the editor are not shown, and cannot be chosen.
    teacher.patch("/api/teach/lessons/1", json={"blocks": [text(), choice(options=(("80", False), ("443", True), ("22", False), ("", False))), short()]})
    teacher.post("/api/teach/lessons/1/publish")
    assert maria.get("/api/lessons/1").json()["blocks"][1] == question
    assert answer(maria, "quiz1", choices=["quiz1-3"]).status_code == 400

    # A wrong answer is told to be wrong, and nothing more.
    r = answer(maria, "quiz1", choices=["quiz1-0"])
    assert r.status_code == 200
    assert r.json() == {"choices": ["quiz1-0"], "attempts": 1, "tries_left": 2, "correct": False, "closed": False}
    assert "listens on 443" not in maria.get("/api/lessons/1").text

    # The explanation comes with the right answer.
    r = answer(maria, "quiz1", choices=["quiz1-1"])
    assert r.json() == {
        "choices": ["quiz1-1"], "attempts": 2, "tries_left": 1, "correct": True, "closed": True,
        "explanation": "HTTPS listens on 443 unless told otherwise.", "solution": ["quiz1-1"],
    }
    assert maria.get("/api/lessons/1").json()["blocks"][1]["state"] == r.json()

    # Answered correctly, it stays that way whatever is sent next.
    assert answer(maria, "quiz1", choices=["quiz1-0"]).json() == r.json()
    assert db.scalar(select(LessonAnswer.attempts).where(LessonAnswer.block_id == "quiz1")) == 2


def test_knowledge_checks_are_checked_on_the_server(people, db):
    teacher, maria, jose = people
    several = choice("quiz2", options=(("Encryption", True), ("Speed", False), ("Authentication", True)))
    write(teacher, [choice(), several, short(answers=("Transport Layer Security", "transport-layer security"))])
    assert maria.get("/api/lessons/1").json()["blocks"][1]["multiple"] is True

    # Several correct options: exactly those, in any order.
    assert answer(maria, "quiz2", choices=["quiz2-0"]).json()["correct"] is False
    assert answer(maria, "quiz2", choices=["quiz2-0", "quiz2-1", "quiz2-2"]).json()["correct"] is False
    r = answer(maria, "quiz2", choices=["quiz2-2", "quiz2-0", "quiz2-0"]).json()
    assert (r["correct"], r["attempts"], r["solution"]) == (True, 3, ["quiz2-0", "quiz2-2"])

    # Typed answers: capitals and extra spaces do not matter, other differences do.
    assert answer(maria, "short1", text="transport security").json()["correct"] is False
    r = answer(maria, "short1", text="  transport   LAYER security ").json()
    assert (r["correct"], r["text"], r["solution"]) == (True, "transport   LAYER security", "Transport Layer Security")

    # Out of tries: the question closes and shows the right answer.
    for attempt in (1, 2):
        r = answer(jose, "quiz1", choices=["quiz1-0"]).json()
        assert (r["attempts"], r["closed"], "solution" in r) == (attempt, False, False)
    r = answer(jose, "quiz1", choices=["quiz1-2"]).json()
    assert (r["attempts"], r["tries_left"], r["correct"], r["closed"], r["solution"]) == (3, 0, False, True, ["quiz1-1"])
    r = answer(jose, "quiz1", choices=["quiz1-1"]).json()                           # too late
    assert (r["attempts"], r["correct"], r["choices"]) == (3, False, ["quiz1-2"])

    # What is not an answer to a question of this lesson is refused and does not count as a try.
    for given, why in [
        ({"block_id": "quiz2", "choices": ["quiz1-1"]}, "Choose one of the options"),      # an option of another question
        ({"block_id": "quiz2", "choices": []}, "Choose one of the options"),
        ({"block_id": "quiz2", "text": "Encryption"}, "Choose one of the options"),
        ({"block_id": "short1"}, "Write an answer"),
        ({"block_id": "short1", "text": "x" * 201}, "Write an answer"),
        ({"block_id": "nope"}, "no longer part of this lesson"),
    ]:
        r = jose.post("/api/lessons/1/answers", json=given)
        assert r.status_code == 400 and why in r.json()["detail"], r.text
    assert db.scalar(select(func.count()).select_from(LessonAnswer).where(LessonAnswer.user_id == 3)) == 1
    assert jose.post("/api/lessons/9/answers", json={"block_id": "quiz1", "choices": ["quiz1-1"]}).status_code == 404


def test_completing_a_lesson(people, db):
    teacher, maria, jose = people
    write(teacher, [text(), choice(), short()])
    write(teacher, [text()], title="Reading only")

    assert maria.get("/api/lessons").json()[0] == {
        "id": 1, "title": "TLS basics", "summary": "", "published": True, "course_id": None, "course": None,
        "questions": 2, "opened_at": None, "completed_at": None, "answered": 0,
    }
    opened = maria.get("/api/lessons/1").json()
    assert opened["opened_at"] is not None and (opened["questions"], opened["answered"], opened["completed_at"]) == (2, 0, None)
    assert maria.get("/api/lessons/1").json()["opened_at"] == opened["opened_at"]         # the first time is kept

    r = maria.post("/api/lessons/1/complete")
    assert r.status_code == 400 and "Answer every knowledge check" in r.json()["detail"]
    answer(maria, "quiz1", choices=["quiz1-1"])
    answer(maria, "short1", text="no idea")
    assert maria.post("/api/lessons/1/complete").status_code == 400                       # one question still open
    assert maria.get("/api/lessons").json()[0]["answered"] == 1
    answer(maria, "short1", text="still no idea")
    answer(maria, "short1", text="really none")                                           # out of tries: that counts as done
    done = maria.post("/api/lessons/1/complete")
    assert done.status_code == 200 and done.json()["completed_at"] is not None
    assert maria.post("/api/lessons/1/complete").json() == done.json()                    # the first time is kept
    mine = maria.get("/api/lessons").json()[0]
    assert (mine["answered"], mine["completed_at"]) == (2, done.json()["completed_at"])

    # A lesson without questions can be completed right away, without having been opened.
    assert jose.post("/api/lessons/2/complete").status_code == 200
    assert [lesson["completed_at"] is not None for lesson in jose.get("/api/lessons").json()] == [False, True]


def test_the_teacher_sees_how_a_lesson_went(people, db):
    teacher, maria, jose = people
    teacher.post("/api/teach/courses", json={"name": "CS 101"})
    teacher.patch("/api/teach/courses/1", json={"student_ids": [2, 3]})
    write(teacher, [text(), choice(), short()], for_everyone=False, course_id=1)

    maria.get("/api/lessons/1")
    answer(maria, "quiz1", choices=["quiz1-1"])                                           # right at once
    answer(maria, "short1", text="?")
    answer(maria, "short1", text="transport layer security")                              # right at the second try
    maria.post("/api/lessons/1/complete")
    for _ in range(3):
        answer(jose, "quiz1", choices=["quiz1-0"])                                        # never right
    teacher.get("/api/lessons/1")                                                         # a teacher trying it is not a student
    answer(teacher, "quiz1", choices=["quiz1-1"])

    progress = teacher.get("/api/teach/lessons/1/progress").json()
    assert progress["lesson"]["title"] == "TLS basics" and progress["lesson"]["course"] == "CS 101"
    assert progress["questions"] == [
        {"id": "quiz1", "question": "Which port does HTTPS use?", "answered": 2, "correct": 1, "first_try": 1, "missed": 1},
        {"id": "short1", "question": "What does TLS stand for?", "answered": 1, "correct": 1, "first_try": 0, "missed": 0},
    ]
    jose_row, maria_row = progress["students"]
    assert jose_row == {
        "id": 3, "username": "jose", "name": "Jose Perez", "opened_at": None, "completed_at": None,
        "answered": 1, "correct": 0, "first_try": 0, "missed": 1,
    }
    assert (maria_row["name"], maria_row["answered"], maria_row["correct"], maria_row["first_try"], maria_row["missed"]) == ("Maria Lopez", 2, 2, 1, 0)
    assert maria_row["opened_at"] is not None and maria_row["completed_at"] is not None
    assert teacher.get("/api/teach/lessons/9/progress").status_code == 404


def test_publishing_a_changed_question_asks_it_again(people, db):
    teacher, maria, _ = people
    write(teacher, [choice(), choice("quiz2"), short()])
    for block_id in ("quiz1", "quiz2"):
        answer(maria, block_id, choices=[f"{block_id}-1"])
    answer(maria, "short1", text="Transport Layer Security")

    def states():
        return {block["id"]: block["state"] is not None for block in maria.get("/api/lessons/1").json()["blocks"]}

    # A typo fixed in an option or in the question: the answers still stand.
    reworded = choice()
    reworded["options"][0]["text"], reworded["question"] = "eighty", "Which port is for HTTPS?"
    teacher.patch("/api/teach/lessons/1", json={"blocks": [reworded, choice("quiz2"), short()]})
    assert states() == {"quiz1": True, "quiz2": True, "short1": True}                     # not published yet
    teacher.post("/api/teach/lessons/1/publish")
    assert states() == {"quiz1": True, "quiz2": True, "short1": True}

    # Another correct option, another accepted answer, or the question taken out: asked again, or gone.
    teacher.patch("/api/teach/lessons/1", json={"blocks": [choice(options=(("80", True), ("443", False))), short(answers=("TLS",))]})
    teacher.post("/api/teach/lessons/1/publish")
    assert states() == {"quiz1": False, "short1": False}
    assert db.scalar(select(func.count()).select_from(LessonAnswer)) == 0


def test_lessons_reach_the_right_students_in_order(people, db):
    teacher, maria, jose = people
    teacher.post("/api/teach/courses", json={"name": "CS 101"})
    teacher.patch("/api/teach/courses/1", json={"student_ids": [2]})
    write(teacher, [text()], title="For the course 1", for_everyone=False, course_id=1)
    write(teacher, [text()], title="For everyone")
    write(teacher, [text()], title="For the course 2", for_everyone=False, course_id=1)
    write(teacher, [text()], title="A draft", publish=False)
    write(teacher, [text()], title="For nobody yet", for_everyone=False)

    assert titles(maria) == ["For the course 1", "For everyone", "For the course 2"]
    assert titles(jose) == ["For everyone"]
    assert titles(teacher) == ["For the course 1", "For everyone", "For the course 2", "A draft", "For nobody yet"]
    assert maria.get("/api/lessons")  .json()[0]["course"] == "CS 101"
    assert jose.get("/api/lessons/1").status_code == 404 and jose.get("/api/lessons/5").status_code == 404
    assert jose.post("/api/lessons/1/answers", json={"block_id": "quiz1", "choices": ["quiz1-1"]}).status_code == 404
    assert jose.post("/api/lessons/1/complete").status_code == 404

    # The next lesson is the next one of the same course.
    assert maria.get("/api/lessons/1").json()["next"] == {"id": 3, "title": "For the course 2"}
    assert maria.get("/api/lessons/3").json()["next"] is None and maria.get("/api/lessons/2").json()["next"] is None

    assert teacher.put("/api/teach/lessons/order", json={"ids": [3, 2, 1, 5, 4]}).json() == {"ordered": True}
    assert titles(maria) == ["For the course 2", "For everyone", "For the course 1"]
    assert [lesson["id"] for lesson in teacher.get("/api/teach/lessons").json()] == [3, 2, 1, 5, 4]
    assert maria.get("/api/lessons/3").json()["next"] == {"id": 1, "title": "For the course 1"}

    # Leaving the course, or the course being deleted, takes its lessons away.
    teacher.delete("/api/teach/courses/1")
    assert titles(maria) == ["For everyone"] and teacher.get("/api/teach/lessons/1").json()["course_id"] is None


def test_teachers_try_out_their_working_copy(people, db):
    teacher, maria, _ = people
    write(teacher, [text(), choice()])
    teacher.patch("/api/teach/lessons/1", json={"blocks": [text(body="Not published yet."), choice(), short()]})

    trying = teacher.get("/api/lessons/1").json()
    assert trying["preview"] is True and trying["questions"] == 2 and trying["blocks"][0]["text"] == "Not published yet."
    assert '"correct": true' not in json.dumps(trying)                                   # as a student would get it
    assert answer(teacher, "short1", text="transport layer security").json()["correct"] is True
    assert answer(maria, "short1", text="transport layer security").status_code == 400    # not published: no such question for her
    answer(teacher, "quiz1", choices=["quiz1-1"])
    assert teacher.post("/api/lessons/1/complete").status_code == 200

    assert maria.post("/api/lessons/1/start-over").status_code == 403
    assert teacher.post("/api/lessons/1/start-over").json() == {"started_over": True}
    again = teacher.get("/api/lessons/1").json()
    assert (again["answered"], again["completed_at"]) == (0, None) and again["opened_at"] is not None


def test_other_blocks(people, hub, db):
    teacher, maria, jose = people
    upload(teacher, "Wireshark lab")
    teacher.patch("/api/teach/assignments/1", json={"student_ids": [2], "published": True})
    blocks = [
        {"type": "code", "id": "code1", "language": "python", "code": "print('hi')"},
        {"type": "callout", "id": "note1", "tone": "warning", "text": "Never reuse a nonce."},
        {"type": "video", "id": "video1", "url": " https://youtu.be/dQw4w9WgXcQ?t=42 "},
        {"type": "video", "id": "video2", "url": ""},                                    # nothing chosen yet: left out
        {"type": "assignment", "id": "lab1", "assignment_id": 1},
        {"type": "assignment", "id": "lab2", "assignment_id": 999},                      # deleted since: left out
        {"type": "code", "id": "code2", "language": "", "code": "\n"},
    ]
    write(teacher, blocks)
    assert maria.get("/api/lessons/1").json()["blocks"] == [
        blocks[0], blocks[1],
        {"type": "video", "id": "video1", "video_id": "dQw4w9WgXcQ"},
        {"type": "assignment", "id": "lab1", "assignment_id": 1, "title": "Wireshark lab"},
    ]
    # The link to the notebook is only there for the students the assignment was given to.
    assert [block["type"] for block in jose.get("/api/lessons/1").json()["blocks"]] == ["code", "callout", "video"]


@pytest.mark.parametrize("url, found", [
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://youtube.com/watch?list=PL1&v=dQw4w9WgXcQ&t=3s", "dQw4w9WgXcQ"),
    ("https://m.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("http://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/watch?v=short", None),
    ("https://evil.example/https://youtu.be/dQw4w9WgXcQ", None),
    ("https://youtube.com.evil.example/watch?v=dQw4w9WgXcQ", None),
    ("javascript:alert(1)//youtu.be/dQw4w9WgXcQ", None),
    ("dQw4w9WgXcQ", None),
])
def test_only_youtube_links_become_videos(url, found):
    assert lessons.video_id(url) == found


def test_pictures(people, db):
    teacher, maria, jose = people
    teacher.post("/api/teach/courses", json={"name": "CS 101"})
    teacher.patch("/api/teach/courses/1", json={"student_ids": [2]})
    write(teacher, [text()], for_everyone=False, course_id=1, publish=False)

    def send(data, name="diagram.png", lesson_id="1", client=teacher):
        return client.post("/api/teach/lesson-images", data={"lesson_id": lesson_id}, files={"file": (name, data)})

    r = send(PNG)
    assert r.status_code == 201 and r.json() == {"id": 1, "url": "/api/lessons/1/images/1"}
    assert send(b"\xff\xd8\xff\xe0" + b"\x00" * 32, "photo.png").status_code == 201      # a JPEG, whatever its name says
    for data, name, why in [
        (b"<svg xmlns='http://www.w3.org/2000/svg' onload='alert(1)'/>", "drawing.svg", "PNG, JPEG, GIF or WebP"),
        (b"<html><script>alert(1)</script></html>", "page.png", "PNG, JPEG, GIF or WebP"),
        (b"", "empty.png", "PNG, JPEG, GIF or WebP"),
        (PNG + b"\x00" * lessons.MAX_IMAGE_BYTES, "huge.png", "larger than 5 MB"),
    ]:
        r = send(data, name)
        assert r.status_code == 400 and why in r.json()["detail"], r.text
    assert send(PNG, lesson_id="9").status_code == 404 and send(PNG, lesson_id="x").status_code == 422
    assert send(PNG + b"\x00" * (lessons.MAX_IMAGE_BYTES + 2 * 1024 * 1024)).status_code == 413     # cut off while it arrives

    teacher.patch("/api/teach/lessons/1", json={"blocks": [text(), {"type": "image", "id": "image1", "image_id": 1, "alt": "A TLS handshake"}]})
    teacher.post("/api/teach/lessons/1/publish")
    assert maria.get("/api/lessons/1").json()["blocks"][1] == {
        "type": "image", "id": "image1", "url": "/api/lessons/1/images/1", "alt": "A TLS handshake",
    }
    r = maria.get("/api/lessons/1/images/1")
    assert r.status_code == 200 and r.content == PNG
    assert (r.headers["content-type"], r.headers["x-content-type-options"]) == ("image/png", "nosniff")
    # Picture 2 was uploaded but is in no block: the teacher can see it, students cannot.
    assert teacher.get("/api/lessons/1/images/2").headers["content-type"] == "image/jpeg"
    assert maria.get("/api/lessons/1/images/2").status_code == 404
    # Nor before the block it is in is published: until then it is in the teacher's working copy only.
    teacher.patch("/api/teach/lessons/1", json={"blocks": [
        text(), {"type": "image", "id": "image1", "image_id": 1, "alt": "A TLS handshake"},
        {"type": "image", "id": "image2", "image_id": 2, "alt": "Photo"},
    ]})
    assert maria.get("/api/lessons/1/images/2").status_code == 404 and teacher.get("/api/lessons/1/images/2").status_code == 200
    teacher.post("/api/teach/lessons/1/publish")
    assert maria.get("/api/lessons/1/images/2").status_code == 200
    # Only for the people who may see the lesson, and only that lesson's pictures.
    assert jose.get("/api/lessons/1/images/1").status_code == 404
    assert TestClient(app).get("/api/lessons/1/images/1").status_code == 401
    write(teacher, [text()], title="Another lesson")
    assert maria.get("/api/lessons/2/images/1").status_code == 404 and maria.get("/api/lessons/1/images/9").status_code == 404

    teacher.delete("/api/teach/lessons/1")                                               # its pictures go with it
    assert db.scalar(select(func.count()).select_from(LessonImage)) == 0


def test_students_cannot_write_lessons(people, db):
    teacher, maria, _ = people
    write(teacher, [text(), choice()])
    for client, refusal in [(TestClient(app), 401), (maria, 403)]:
        assert client.get("/api/teach/lessons").status_code == refusal
        assert client.post("/api/teach/lessons", json={"title": "Mine"}).status_code == refusal
        assert client.get("/api/teach/lessons/1").status_code == refusal                 # the working copy has the answers
        assert client.patch("/api/teach/lessons/1", json={"title": "Mine", "blocks": []}).status_code == refusal
        assert client.put("/api/teach/lessons/order", json={"ids": [1]}).status_code == refusal
        assert client.post("/api/teach/lessons/1/publish").status_code == refusal
        assert client.post("/api/teach/lessons/1/unpublish").status_code == refusal
        assert client.get("/api/teach/lessons/1/progress").status_code == refusal
        assert client.delete("/api/teach/lessons/1").status_code == refusal
        assert client.post("/api/teach/lesson-images", data={"lesson_id": "1"}, files={"file": ("a.png", PNG)}).status_code == refusal
    for path in ("/api/lessons", "/api/lessons/1"):
        assert TestClient(app).get(path).status_code == 401
    assert TestClient(app).post("/api/lessons/1/answers", json={"block_id": "quiz1", "choices": ["quiz1-1"]}).status_code == 401
    lesson = teacher.get("/api/teach/lessons/1").json()
    assert (lesson["title"], lesson["published"], len(lesson["blocks"])) == ("TLS basics", True, 2)
    assert db.scalar(select(func.count()).select_from(LessonImage)) == 0
