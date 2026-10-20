"""Exporting students' progress and grades as CSV or Excel, for one course or the whole platform.
On a real (throwaway) Postgres database."""
import csv
import io
from datetime import date, datetime, timezone

import openpyxl
from fastapi.testclient import TestClient

from app import auth, exports
from app.main import app
from app.models import AssignmentOpen, Submission
from conftest import PASSWORD, browser, upload

URLS = ["/api/teach/students.csv", "/api/teach/students.xlsx", "/api/teach/courses/1/students.csv", "/api/teach/courses/1/students.xlsx"]
FORMULA = '=HYPERLINK("http://example.com","Click")'


def rows(response) -> list[list[str]]:
    assert response.status_code == 200, response.text
    assert response.content.startswith(b"\xef\xbb\xbf")         # the byte order mark Excel needs for UTF-8
    return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))


def sheet(workbook, name: str) -> list[list]:
    return [list(row) for row in workbook[name].iter_rows(values_only=True)]


def handed_in(db, assignment_id, user_id, status, late=False, score=None, max_score=None):
    db.add(Submission(
        assignment_id=assignment_id, user_id=user_id, notebook=b"{}", submitted_at=datetime.now(timezone.utc),
        status=status, late=late, score=score, max_score=max_score,
    ))
    db.commit()


def lesson(teacher, title, blocks, **audience) -> int:
    lesson_id = teacher.post("/api/teach/lessons", json={"title": title}).json()["id"]
    assert teacher.patch(f"/api/teach/lessons/{lesson_id}", json={"blocks": blocks, **audience}).status_code == 200
    assert teacher.post(f"/api/teach/lessons/{lesson_id}/publish").status_code == 200
    return lesson_id


def quiz(block_id):
    return {"type": "multiple_choice", "id": block_id, "question": "Which port does HTTPS use?", "options": [
        {"id": f"{block_id}-a", "text": "80", "correct": False}, {"id": f"{block_id}-b", "text": "443", "correct": True},
    ]}


def school(people, db):
    """Two courses: CS 101 with maria, "@risk lab" with jose, and ana in none. Assignments for CS 101
    (one of them a draft), for everyone (titled like a formula), for the other course, and one
    given to ana by name; a lesson with two checks for CS 101 and one for everyone."""
    teacher, maria, jose = people
    auth.create_user(db, "ana", PASSWORD)
    ana = browser("ana")
    teacher.post("/api/teach/courses", json={"name": "CS 101"})
    teacher.post("/api/teach/courses", json={"name": "@risk lab"})
    teacher.patch("/api/teach/courses/1", json={"student_ids": [2]})
    teacher.patch("/api/teach/courses/2", json={"student_ids": [3]})

    for title, changes in [
        ("Loops", {"course_id": 1, "points": 10, "due_at": "2026-10-01T12:00:00Z", "published": True}),
        (FORMULA, {"for_everyone": True, "published": True}),
        ("Draft lab", {"course_id": 1}),
        ("Ports", {"course_id": 2, "points": 5, "published": True}),
        ("Extra", {"student_ids": [4], "published": True}),
    ]:
        assert upload(teacher, title).status_code == 201
        assert teacher.patch(f"/api/teach/assignments/{len(teacher.get('/api/teach/assignments').json())}", json=changes).status_code == 200

    lesson(teacher, "TLS basics", [quiz("quiz1"), quiz("quiz2")], course_id=1)
    lesson(teacher, "Welcome", [{"type": "text", "id": "text1", "text": "Hello."}], for_everyone=True)
    assert maria.post("/api/lessons/1/answers", json={"block_id": "quiz1", "choices": ["quiz1-b"]}).json()["correct"] is True
    assert maria.post("/api/lessons/1/answers", json={"block_id": "quiz2", "choices": ["quiz2-a"]}).json()["correct"] is False
    assert maria.post("/api/lessons/2/complete").status_code == 200

    handed_in(db, 1, 2, "graded", late=True, score=8.0, max_score=10.0)      # maria: Loops, graded after the due date
    db.add(AssignmentOpen(assignment_id=2, user_id=2))                       # maria opened the one for everyone
    db.commit()
    handed_in(db, 4, 3, "submitted", late=True)                              # jose: Ports, late, no grade yet
    handed_in(db, 5, 4, "failed")                                            # ana: Extra, the autograder could not run it
    return teacher, maria, jose, ana


def test_only_teachers_and_admins_export(people, db):
    teacher, maria, jose = people
    auth.create_user(db, "boss", PASSWORD, role="teacher", is_admin=True)
    teacher.post("/api/teach/courses", json={"name": "CS 101"})
    for url in URLS:
        assert TestClient(app).get(url).status_code == 401
        assert maria.get(url).status_code == 403 and jose.get(url).status_code == 403
        assert teacher.get(url).status_code == 200 and browser("boss").get(url).status_code == 200
    assert teacher.get("/api/teach/courses/9/students.csv").status_code == 404
    assert teacher.get("/api/teach/students.pdf").status_code == 422
    assert maria.get("/api/teach/students.pdf").status_code == 403             # refused before anything else is looked at


def test_a_course_export_has_only_its_students_and_what_they_were_given(people, db):
    teacher, *_ = school(people, db)
    r = teacher.get("/api/teach/courses/1/students.csv")
    assert r.headers["content-type"] == "text/csv; charset=utf-8" and r.headers["cache-control"] == "no-store"
    assert r.headers["content-disposition"] == f'attachment; filename="cs-101-students-{date.today().isoformat()}.csv"'
    assert rows(r) == [
        ["Username", "Course", "Lessons completed", "Lessons given", "Checks answered", "Checks correct", "Checks given",
         "Loops: status", "Loops: score (of 10)", f"'{FORMULA}: status", f"'{FORMULA}: score (of 100)",
         "Assignments submitted", "Assignments given", "Total score", "Total out of"],
        ["maria", "CS 101", "1", "2", "2", "1", "2", "graded late", "8", "opened", "", "1", "2", "8", "10"],
    ]

    # The other course: its own assignment and the one for everyone, not CS 101's lesson.
    assert rows(teacher.get("/api/teach/courses/2/students.csv"))[1:] == [
        ["jose", "'@risk lab", "0", "1", "0", "0", "0", "not started", "", "late", "", "1", "2", "0", "0"],
    ]


def test_the_whole_platform_as_csv_leaves_out_what_a_student_was_not_given(people, db):
    teacher, *_ = school(people, db)
    r = teacher.get("/api/teach/students.csv")
    assert r.headers["content-disposition"] == f'attachment; filename="all-students-{date.today().isoformat()}.csv"'
    table = rows(r)
    assert table[0][1] == "Courses" and table[0][7:15] == [
        "Loops: status", "Loops: score (of 10)", f"'{FORMULA}: status", f"'{FORMULA}: score (of 100)",
        "Ports: status", "Ports: score (of 5)", "Extra: status", "Extra: score (of 100)",
    ]
    assert table[1:] == [
        ["ana", "", "0", "1", "0", "0", "0", "", "", "not started", "", "", "", "could not be graded", "", "1", "2", "0", "0"],
        ["jose", "'@risk lab", "0", "1", "0", "0", "0", "", "", "not started", "", "late", "", "", "", "1", "2", "0", "0"],
        ["maria", "CS 101", "1", "2", "2", "1", "2", "graded late", "8", "opened", "", "", "", "", "", "1", "2", "8", "10"],
    ]


def test_the_whole_platform_as_a_workbook_has_a_sheet_per_course(people, db):
    teacher, *_ = school(people, db)
    r = teacher.get("/api/teach/students.xlsx")
    assert r.status_code == 200 and r.headers["content-type"] == exports.MEDIA_TYPES["xlsx"]
    assert r.headers["content-disposition"] == f'attachment; filename="all-students-{date.today().isoformat()}.xlsx"'
    book = openpyxl.load_workbook(io.BytesIO(r.content))
    assert book.sheetnames[0] == "All students" and sorted(book.sheetnames[1:]) == ["@risk lab", "CS 101"]     # courses in the site's order

    everyone = sheet(book, "All students")
    assert [row[0] for row in everyone] == ["Username", "ana", "jose", "maria"]
    assert everyone[3] == ["maria", "CS 101", 1, 2, 2, 1, 2, "graded late", 8, "opened", None, None, None, None, None, 1, 2, 8, 10]
    # Text that looks like a formula stays text, without a quote added in front.
    header = book["All students"]["J1"]
    assert (header.value, header.data_type) == (f"{FORMULA}: status", "s")
    assert book["@risk lab"]["B2"].value == "@risk lab" and book["@risk lab"]["B2"].data_type == "s"

    assert sheet(book, "CS 101")[1:] == [["maria", "CS 101", 1, 2, 2, 1, 2, "graded late", 8, "opened", None, 1, 2, 8, 10]]
    assert [row[0] for row in sheet(book, "@risk lab")] == ["Username", "jose"]

    course = teacher.get("/api/teach/courses/1/students.xlsx")
    assert course.headers["content-disposition"] == f'attachment; filename="cs-101-students-{date.today().isoformat()}.xlsx"'
    assert openpyxl.load_workbook(io.BytesIO(course.content)).sheetnames == ["CS 101"]


def test_cells_that_would_run_as_formulas_are_kept_as_text():
    for text in ["=1+1", "+1", "-1", "@SUM(A1)", "\tx", "\rx"]:
        assert exports.plain_text(text) == "'" + text
    assert exports.plain_text("Loops") == "Loops" and exports.plain_text("a=b") == "a=b"
    assert exports.to_csv(exports.Table("x", ["=A", "B"], [["-2+3", 4.5], [None, 0]])) == "\ufeff'=A,B\r\n'-2+3,4.5\r\n,0\r\n".encode()


def test_sheet_names_follow_excels_rules():
    used: set[str] = set()
    long = "A course with a very long name: section 2 [fall]"
    assert exports._sheet_name(long, used) == "A course with a very long name"
    assert exports._sheet_name(long, used) == "A course with a very long n (2)"
    assert exports._sheet_name("History", used) == "History course"
    assert exports._sheet_name("'?*'", used) == "Course"
    assert exports.file_stem("Programación 1, sección 2") == "programacion-1-seccion-2"
    assert exports.file_stem("¿?") == "course"
