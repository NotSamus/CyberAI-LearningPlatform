"""Submitting, autograding and the gradebook, on a real (throwaway) Postgres database.

The hub and the grading service are replaced by stand-ins: `hub` remembers the files in each
person's Jupyter home, and `otter` answers like Otter-Grader does (the real thing runs in Docker
and is tried out by hand, see README.md)."""
import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import grading, submissions
from app.main import app
from app.models import Assignment, Submission
from conftest import notebook_file, upload

MARIA_COPY = ("s-2", "assignments/functions-lab-1/lab.ipynb")
JOSE_COPY = ("s-3", "assignments/functions-lab-1/lab.ipynb")


def otter_master() -> bytes:
    """A teacher's notebook in Otter Assign format: one question with its solution and tests."""
    def raw(source):
        return {"cell_type": "raw", "metadata": {}, "source": source}

    def code(source):
        return {"cell_type": "code", "metadata": {}, "source": source, "outputs": [], "execution_count": None}

    cells = [
        raw("# ASSIGNMENT CONFIG\nname: functions-lab"),
        raw("# BEGIN QUESTION\nname: q1\npoints: 2"),
        raw("# BEGIN SOLUTION"), code("def square(x):\n    return x * x # SOLUTION"), raw("# END SOLUTION"),
        raw("# BEGIN TESTS"), code("square(2) == 4"), code("# HIDDEN\nsquare(-3) == 9"), raw("# END TESTS"),
        raw("# END QUESTION"),
    ]
    return json.dumps({"cells": cells, "metadata": {}, "nbformat": 4, "nbformat_minor": 5}).encode()


def student_version() -> bytes:
    """What Otter makes of it for students: no solution, the public test in the metadata."""
    notebook = json.loads(notebook_file("def square(x):\n    ...", 'grader.check("q1")'))
    notebook["metadata"]["otter"] = {"tests": {"q1": {"name": "q1", "points": 2}, "q2": {"name": "q2", "points": [1, 2]}}}
    return json.dumps(notebook).encode()


def otter_results(q1: float, q2: float) -> dict:
    """In the shape of Otter's results.json."""
    return {"tests": [
        {"name": "Public Tests", "visibility": "visible", "output": "q1 results: All test cases passed!", "status": "passed"},
        {"name": "q1", "score": q1, "max_score": 2.0, "visibility": "hidden", "output": "q1 - 2 result: hidden test square(-3) == 9"},
        {"name": "q2", "score": q2, "max_score": 3.0, "visibility": "hidden", "output": "q2 - 2 result: hidden test total([]) == 0"},
    ]}


def tampered_results() -> dict:
    """What can come back when the student's code works against the autograder (it runs in the same
    process as Otter's tests): a public test fails with a line it read from the hidden tests, and q2
    claims far more points than it has."""
    stolen = "hidden test square(-3) == 9"
    return {"tests": [
        {"name": "Public Tests", "visibility": "visible", "status": "failed", "output": (
            "q1 results: All test cases passed!\n\n"
            "q2 results:\n    q2 - 1 result:\n        Test case failed\n        Expected:\n            0\n"
            f"        Got:\n            '{stolen}'\nq9 results: All test cases passed!"
        )},
        {"name": "q1", "score": 2.0, "max_score": 2.0, "visibility": "hidden", "output": "q1 results: All test cases passed!"},
        {"name": "q2", "score": 99.0, "max_score": 3.0, "visibility": "hidden", "output": f"q2 results:\n    Got: '{stolen}'"},
    ]}


@pytest.fixture
def otter(monkeypatch):
    """Stands in for the grading service. A submission scores full marks when it contains "x * x"."""
    jobs = {"prepared": [], "graded": []}

    async def prepare(master, name, gpu):
        jobs["prepared"].append(name)
        return student_version(), b"the autograder package"

    async def grade(notebook, autograder, name, gpu):
        jobs["graded"].append(name)
        assert autograder == b"the autograder package"
        return otter_results(2.0, 3.0) if b"x * x" in notebook else otter_results(0, 0)

    monkeypatch.setattr(grading, "prepare", prepare)
    monkeypatch.setattr(grading, "grade", grade)
    return jobs


@pytest.fixture
def lab(people, hub, otter):
    """An autograded assignment (id 1), published to every student; maria has opened it."""
    teacher, maria, jose = people
    assert upload(teacher, "Functions lab", content=otter_master()).status_code == 201
    teacher.patch("/api/teach/assignments/1", json={"for_everyone": True, "published": True})
    maria.post("/api/assignments/1/launch")
    return teacher, maria, jose


def solve(hub, copy=MARIA_COPY):
    hub[copy] = notebook_file("def square(x):\n    return x * x")


# --- uploading an autograded assignment -----------------------------------------------------------

def test_an_otter_notebook_becomes_an_autograded_assignment(people, hub, otter, db):
    teacher, maria, _ = people
    master = otter_master()
    created = upload(teacher, "Functions lab", content=master).json()
    assert (created["autograded"], created["points"], created["notebook_name"]) == (True, 5.0, "lab.ipynb")
    assert otter["prepared"] == ["lab.ipynb"]
    teacher.patch("/api/teach/assignments/1", json={"for_everyone": True, "published": True})

    # Students get the version without solutions. The teacher can get both back.
    maria.post("/api/assignments/1/launch")
    assert hub[MARIA_COPY] == student_version() and b"SOLUTION" not in hub[MARIA_COPY]
    assert teacher.get("/api/teach/assignments/1/notebook").content == student_version()
    r = teacher.get("/api/teach/assignments/1/master")
    assert r.content == master and r.headers["content-disposition"] == 'attachment; filename="with-solutions-lab.ipynb"'
    for path in ["/api/teach/assignments/1/master", "/api/teach/assignments/1/notebook"]:
        assert maria.get(path).status_code == 403
    assert "SOLUTION" not in maria.get("/api/assignments/1").text + maria.get("/api/assignments").text

    # A plain notebook is not sent to Otter, and has no version with solutions.
    plain = upload(teacher, "Reading").json()
    assert (plain["autograded"], plain["points"]) == (False, None) and otter["prepared"] == ["lab.ipynb"]
    assert teacher.get("/api/teach/assignments/2/master").status_code == 404
    r = teacher.patch("/api/teach/assignments/1", json={"points": 50})
    assert r.status_code == 400 and "come from its tests" in r.json()["detail"]


def test_a_notebook_otter_cannot_prepare_is_refused(people, db, monkeypatch):
    teacher, _, _ = people

    async def solutions_fail(master, name, gpu):
        raise grading.GradingError("Otter stopped with an error.", "q1 - 1 result:\n    Test case failed")

    monkeypatch.setattr(grading, "prepare", solutions_fail)
    r = upload(teacher, "Functions lab", content=otter_master())
    assert r.status_code == 400
    assert "Otter could not prepare this notebook" in r.json()["detail"] and "Test case failed" in r.json()["detail"]

    async def unreachable(master, name, gpu):
        raise grading.GraderUnreachable("The grading service is not reachable right now.")

    monkeypatch.setattr(grading, "prepare", unreachable)
    r = upload(teacher, "Functions lab", content=otter_master())
    assert r.status_code == 503 and "was not uploaded" in r.json()["detail"]
    assert db.scalar(select(func.count()).select_from(Assignment)) == 0


# --- submitting and the autograder ----------------------------------------------------------------

def test_submit_is_graded_and_shown_to_the_student(lab, hub, otter):
    teacher, maria, jose = lab
    assert maria.get("/api/assignments/1").json()["submission"] is None
    r = jose.post("/api/assignments/1/submit")                   # he never opened it
    assert r.status_code == 400 and "open the notebook first" in r.json()["detail"]

    # She submits it unsolved, sees the score, fixes it and submits again.
    first = maria.post("/api/assignments/1/submit")
    assert first.status_code == 200 and first.json()["attempt"] == 1
    mine = maria.get("/api/assignments/1").json()["submission"]
    assert (mine["status"], mine["score"], mine["max_score"], mine["late"]) == ("graded", 0.0, 5.0, False)
    solve(hub)
    assert maria.post("/api/assignments/1/submit").json()["attempt"] == 2
    mine = maria.get("/api/assignments/1").json()["submission"]
    assert (mine["status"], mine["score"], mine["max_score"]) == ("graded", 5.0, 5.0)
    assert mine["questions"] == [{"name": "q1", "score": 2.0, "max_score": 2.0}, {"name": "q2", "score": 3.0, "max_score": 3.0}]
    assert mine["public_tests"] == [{"name": "q1", "passed": True}, {"name": "q2", "passed": True}]
    assert "public_output" not in mine                          # Otter's text about the tests is for teachers
    assert otter["graded"] == ["lab.ipynb", "lab.ipynb"]

    # Students never receive what the hidden tests are, nor the autograder's log.
    everything_maria_can_ask = maria.get("/api/assignments/1").text + maria.get("/api/assignments").text
    assert "hidden test" not in everything_maria_can_ask and mine["error"] is None
    listed = maria.get("/api/assignments").json()[0]["submission"]
    assert (listed["status"], listed["score"], listed["max_score"]) == ("graded", 5.0, 5.0)

    # The teacher's gradebook has every student, and the hidden tests' output.
    rows = teacher.get("/api/teach/assignments/1/progress").json()["students"]
    assert [(r["name"], r["opened_at"] is not None, r["submission"] and r["submission"]["score"]) for r in rows] == \
        [("Jose Perez", False, None), ("Maria Lopez", True, 5.0)]
    assert "hidden test square(-3)" in rows[1]["submission"]["questions"][0]["output"]
    assert rows[1]["submission"]["public_output"] == "q1 results: All test cases passed!"
    assert jose.get("/api/assignments/1").json()["submission"] is None      # he sees nothing of hers


def test_what_the_students_code_makes_otter_say_does_not_reach_them(lab, hub, monkeypatch):
    teacher, maria, _ = lab

    async def tampered(notebook, autograder, name, gpu):
        return tampered_results()

    monkeypatch.setattr(grading, "grade", tampered)
    answer = maria.post("/api/assignments/1/submit").text
    mine = maria.get("/api/assignments/1").json()["submission"]
    # Each question counts for at most its points: 2 + 3, not 2 + 99.
    assert (mine["status"], mine["score"], mine["max_score"]) == ("graded", 5.0, 5.0)
    assert mine["questions"] == [{"name": "q1", "score": 2.0, "max_score": 2.0}, {"name": "q2", "score": 3.0, "max_score": 3.0}]
    # Whether each question's public tests passed, and not one word of what they reported.
    assert mine["public_tests"] == [{"name": "q1", "passed": True}, {"name": "q2", "passed": False}]
    everything_maria_can_ask = answer + maria.get("/api/assignments/1").text + maria.get("/api/assignments").text
    for told in ("hidden test", "square(-3)", "Test case failed", "Got:", "q9"):
        assert told not in everything_maria_can_ask

    # The teacher sees all of it, with the capped score.
    row = teacher.get("/api/teach/assignments/1/progress").json()["students"][1]["submission"]
    assert "hidden test square(-3)" in row["public_output"] and "hidden test square(-3)" in row["questions"][1]["output"]
    assert (row["score"], row["questions"][1]["score"]) == (5.0, 3.0)


def test_late_submissions_are_marked(lab, hub, db):
    teacher, maria, _ = lab
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    teacher.patch("/api/teach/assignments/1", json={"due_at": yesterday})
    assert maria.post("/api/assignments/1/submit").json()["late"] is True
    teacher.patch("/api/teach/assignments/1", json={"due_at": None})
    assert maria.post("/api/assignments/1/submit").json()["late"] is False


def test_a_submission_the_autograder_cannot_run(lab, hub, monkeypatch):
    teacher, maria, _ = lab

    async def never_ends(notebook, autograder, name, gpu):
        raise grading.GradingError("It ran for more than 5 minutes and was stopped.", "Traceback: KeyboardInterrupt")

    monkeypatch.setattr(grading, "grade", never_ends)
    maria.post("/api/assignments/1/submit")
    mine = maria.get("/api/assignments/1").json()["submission"]
    assert (mine["status"], mine["score"], mine["error"]) == ("failed", None, None)      # she is told it failed, not the log
    row = teacher.get("/api/teach/assignments/1/progress").json()["students"][1]
    assert "more than 5 minutes" in row["submission"]["error"] and "KeyboardInterrupt" in row["submission"]["error"]

    # The teacher sends it to the autograder again once the cause is fixed.
    async def works_now(notebook, autograder, name, gpu):
        return otter_results(2.0, 0)

    monkeypatch.setattr(grading, "grade", works_now)
    assert teacher.post("/api/teach/assignments/1/submissions/2/regrade").status_code == 200
    mine = maria.get("/api/assignments/1").json()["submission"]
    assert (mine["status"], mine["score"], mine["max_score"]) == ("graded", 2.0, 5.0)
    assert teacher.post("/api/teach/assignments/1/submissions/3/regrade").status_code == 404     # jose submitted nothing


def test_what_cannot_be_submitted(lab, hub, monkeypatch):
    teacher, maria, _ = lab
    hub[MARIA_COPY] = b"she replaced the file with something else"
    r = maria.post("/api/assignments/1/submit")
    assert r.status_code == 400 and "could not be read as a notebook" in r.json()["detail"]

    monkeypatch.setattr("app.assignments.MAX_SUBMISSION_BYTES", 100_000)     # the real limit is 20 MB: slow to test with
    hub[MARIA_COPY] = notebook_file("x" * 100_000)
    r = maria.post("/api/assignments/1/submit")
    assert r.status_code == 400 and "Clear its outputs" in r.json()["detail"]
    assert maria.get("/api/assignments/1").json()["submission"] is None

    upload(teacher, "Draft")                                     # a teacher trying out a draft
    teacher.post("/api/assignments/2/launch")
    assert teacher.post("/api/assignments/2/submit").status_code == 400
    assert maria.post("/api/assignments/2/submit").status_code == 404
    assert TestClient(app).post("/api/assignments/1/submit").status_code == 401


def test_a_grade_for_an_earlier_notebook_is_dropped(lab, hub, db, otter):
    # The student submits again while the first submission is still with the autograder: the result
    # that then arrives for the first one must not be written over the second.
    teacher, maria, _ = lab
    assignment = db.get(Assignment, 1)
    first = submissions.record(db, assignment, 2, notebook_file("first try"))
    assert (first.status, first.attempt) == ("queued", 1)
    second = submissions.record(db, assignment, 2, notebook_file("def square(x):\n    return x * x"))
    assert (second.id, second.attempt) == (first.id, 2)

    asyncio.run(submissions.grade_submission(first.id, attempt=1))
    assert otter["graded"] == [] and maria.get("/api/assignments/1").json()["submission"]["status"] == "queued"

    # After a restart of the backend, what was still waiting is found again and graded.
    assert submissions.waiting_for_the_autograder() == [(first.id, 2)]
    asyncio.run(submissions.grade_submission(first.id, attempt=2))
    assert maria.get("/api/assignments/1").json()["submission"]["score"] == 5.0
    assert submissions.waiting_for_the_autograder() == []


# --- grading by hand ------------------------------------------------------------------------------

def test_a_plain_notebook_is_graded_by_the_teacher(people, hub, db):
    teacher, maria, _ = people
    upload(teacher, "Essay")
    teacher.patch("/api/teach/assignments/1", json={"for_everyone": True, "published": True, "points": 10})
    maria.post("/api/assignments/1/launch")
    hub[("s-2", "assignments/essay-1/lab.ipynb")] = notebook_file("# my essay")

    assert maria.post("/api/assignments/1/submit").json()["status"] == "submitted"        # waiting for the teacher
    url = "/api/teach/assignments/1/submissions/2"
    for bad in (11, -1):
        r = teacher.patch(url, json={"score": bad})
        assert r.status_code == 400 and "between 0 and 10" in r.json()["detail"]
    graded = teacher.patch(url, json={"score": 8.5, "feedback": "  Good structure. Cite your sources.  "}).json()
    assert (graded["status"], graded["score"], graded["max_score"], graded["graded_by_teacher"]) == ("graded", 8.5, 10.0, True)

    mine = maria.get("/api/assignments/1").json()["submission"]
    assert (mine["score"], mine["max_score"], mine["feedback"]) == (8.5, 10.0, "Good structure. Cite your sources.")
    assert teacher.patch(url, json={"feedback": "Sources added: thanks."}).json()["score"] == 8.5     # a comment alone keeps the score
    assert teacher.post(f"{url}/regrade").status_code == 400     # there is no autograder for it

    # Submitting again starts over: the old grade was for the old notebook.
    again = maria.post("/api/assignments/1/submit").json()
    assert (again["status"], again["score"], again["feedback"], again["attempt"]) == ("submitted", None, "", 2)


def test_a_teacher_can_overrule_the_autograder(lab, hub):
    teacher, maria, _ = lab
    maria.post("/api/assignments/1/submit")                      # 0 of 5
    graded = teacher.patch("/api/teach/assignments/1/submissions/2", json={"score": 4, "feedback": "Partial credit."}).json()
    assert (graded["score"], graded["max_score"], graded["graded_by_teacher"]) == (4.0, 5.0, True)
    assert teacher.patch("/api/teach/assignments/1/submissions/2", json={"score": 6}).status_code == 400


# --- looking at submissions -----------------------------------------------------------------------

def test_teacher_opens_downloads_and_exports(lab, hub, db):
    teacher, maria, jose = lab
    solve(hub)
    maria.post("/api/assignments/1/submit")
    submitted = hub[MARIA_COPY]
    hub[MARIA_COPY] = notebook_file("she keeps working after submitting")

    r = teacher.get("/api/teach/assignments/1/submissions/2/notebook")
    assert r.content == submitted and r.headers["content-disposition"] == 'attachment; filename="maria-lab.ipynb"'

    opened = teacher.post("/api/teach/assignments/1/submissions/2/open").json()
    assert opened["url"] == "http://localhost:8081/user/t-1/cpu/lab/tree/submissions/functions-lab-1/maria/lab.ipynb"
    assert hub[("t-1", "submissions/functions-lab-1/maria/lab.ipynb")] == submitted      # a copy, in the teacher's home
    assert hub[MARIA_COPY] != submitted                                                  # hers is left alone

    lines = teacher.get("/api/teach/assignments/1/grades.csv").text.splitlines()
    assert lines[0] == "Name,Username,Opened,Submitted,Late,Status,Score,Out of"
    assert lines[1].startswith("Jose Perez,jose,,,,not started,,")
    assert lines[2].startswith("Maria Lopez,maria,2") and lines[2].endswith(",graded,5.0,5.0")

    for path in ["/api/teach/assignments/1/submissions/3/notebook", "/api/teach/assignments/9/submissions/2/notebook"]:
        assert teacher.get(path).status_code == 404
    assert teacher.post("/api/teach/assignments/1/submissions/3/open").status_code == 404


def test_students_cannot_reach_submissions_or_grades(lab, hub, db):
    teacher, maria, jose = lab
    solve(hub)
    maria.post("/api/assignments/1/submit")
    url = "/api/teach/assignments/1/submissions/2"
    for client, refusal in [(TestClient(app), 401), (jose, 403), (maria, 403)]:
        assert client.get(f"{url}/notebook").status_code == refusal
        assert client.post(f"{url}/open").status_code == refusal
        assert client.post(f"{url}/regrade").status_code == refusal
        assert client.patch(url, json={"score": 5}).status_code == refusal       # nobody grades themselves
        assert client.get("/api/teach/assignments/1/progress").status_code == refusal
        assert client.get("/api/teach/assignments/1/grades.csv").status_code == refusal
    assert ("s-3", "submissions/functions-lab-1/maria/lab.ipynb") not in hub
    stored = db.scalars(select(Submission)).all()
    assert [(s.user_id, s.score, s.graded_by) for s in stored] == [(2, 5.0, None)]

    # Removing the assignment removes its submissions.
    teacher.delete("/api/teach/assignments/1")
    assert db.scalar(select(func.count()).select_from(Submission)) == 0


# --- reading Otter's files ------------------------------------------------------------------------

def test_reading_otter_notebooks_and_results():
    assert grading.is_otter_master(otter_master()) and not grading.is_otter_master(notebook_file("# ASSIGNMENT CONFIG in a code cell"))
    assert grading.total_points(student_version()) == 5.0
    assert grading.total_points(notebook_file()) is None

    results = otter_results(2.0, 0)
    assert grading.totals(results) == (2.0, 5.0)
    assert grading.questions(results, with_hidden_output=False) == [
        {"name": "q1", "score": 2.0, "max_score": 2.0}, {"name": "q2", "score": 0, "max_score": 3.0},
    ]
    assert "hidden test" in grading.questions(results, with_hidden_output=True)[0]["output"]
    assert grading.public_output(results) == "q1 results: All test cases passed!"
    assert grading.public_tests(results) == [{"name": "q1", "passed": True}, {"name": "q2", "passed": True}]
    assert grading.totals({}) == (0.0, 0.0) and grading.questions(None, True) == [] and grading.public_output(None) == ""
    assert grading.public_tests(None) == [] and grading.public_tests({"tests": [{"name": "q1", "score": 1, "max_score": 1}]}) == []

    # Results are checked, not believed: a score is a number between 0 and the question's points.
    assert grading.totals(tampered_results()) == (5.0, 5.0)
    odd = {"tests": [
        {"name": "q1", "score": "2", "max_score": 2.0}, {"name": "q2", "score": -1, "max_score": 3.0},
        {"name": "q3", "score": 1, "max_score": True}, {"name": "q4", "score": 1, "max_score": -1}, "not a test",
    ]}
    assert grading.totals(odd) == (0.0, 5.0)
    assert [q["score"] for q in grading.questions(odd, with_hidden_output=False)] == [0.0, 0.0]



def test_the_list_of_assignments_counts_where_students_are(people, hub, db):
    teacher, maria, jose = people
    upload(teacher, "Essay")
    teacher.patch("/api/teach/assignments/1", json={"for_everyone": True, "published": True, "points": 10})
    upload(teacher, "Given to nobody yet")
    teacher.post("/api/teach/courses", json={"name": "CS 101"})
    teacher.patch("/api/teach/courses/1", json={"student_ids": [3]})
    upload(teacher, "For the course")
    teacher.patch("/api/teach/assignments/3", json={"course_id": 1, "student_ids": [2], "published": True})

    for student in (maria, jose):
        student.post("/api/assignments/1/launch")
    teacher.post("/api/assignments/1/launch")                   # a teacher trying it out does not count
    hub[("s-2", "assignments/essay-1/lab.ipynb")] = notebook_file("# my essay")
    maria.post("/api/assignments/1/submit")

    def counted():
        return {a["title"]: a["counts"] for a in teacher.get("/api/teach/assignments").json()}

    essay = counted()["Essay"]
    assert essay.pop("oldest_waiting_at") is not None
    assert essay == {"given": 2, "opened": 2, "submitted": 1, "graded": 0, "to_grade": 1, "failed": 0, "late": 0}
    assert counted()["Given to nobody yet"] == {
        "given": 0, "opened": 0, "submitted": 0, "graded": 0, "to_grade": 0, "failed": 0, "late": 0, "oldest_waiting_at": None,
    }
    assert counted()["For the course"]["given"] == 2              # jose through the course, maria by name

    teacher.patch("/api/teach/assignments/1/submissions/2", json={"score": 9})
    essay = counted()["Essay"]
    assert (essay["to_grade"], essay["graded"], essay["oldest_waiting_at"]) == (0, 1, None)
    assert maria.get("/api/teach/assignments").status_code == 403
