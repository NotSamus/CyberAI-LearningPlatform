"""Courses, announcements and who-opened-what, on a real (throwaway) Postgres database."""
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import auth
from app.main import app
from app.models import Announcement, Course
from conftest import PASSWORD, upload


def titles(client) -> list[str]:
    return [a["title"] for a in client.get("/api/assignments").json()]


def test_a_course_groups_students(people, db):
    teacher, maria, jose = people
    r = teacher.post("/api/teach/courses", json={"name": "  CS 101, section 2 "})
    assert r.status_code == 201 and r.json() == {"id": 1, "name": "CS 101, section 2", "student_ids": []}
    assert teacher.patch("/api/teach/courses/1", json={"student_ids": [2]}).json()["student_ids"] == [2]

    # An assignment given to the course reaches its students, and only them.
    upload(teacher, "Loops")
    r = teacher.patch("/api/teach/assignments/1", json={"course_id": 1, "published": True})
    assert r.status_code == 200 and (r.json()["course_id"], r.json()["course"]) == (1, "CS 101, section 2")
    assert titles(maria) == ["Loops"] and titles(jose) == []
    assert maria.get("/api/assignments").json()[0]["course"] == "CS 101, section 2"
    assert jose.get("/api/assignments/1").status_code == 404

    # Joining the course is enough to get its assignments; leaving it takes them away.
    teacher.patch("/api/teach/courses/1", json={"student_ids": [3]})
    assert titles(maria) == [] and titles(jose) == ["Loops"]

    # Renaming keeps the students.
    assert teacher.patch("/api/teach/courses/1", json={"name": "CS 101"}).json() == {"id": 1, "name": "CS 101", "student_ids": [3]}
    assert teacher.get("/api/teach/courses").json() == [{"id": 1, "name": "CS 101", "student_ids": [3]}]

    # Deleting the course keeps the assignment, given to nobody.
    assert teacher.delete("/api/teach/courses/1").json() == {"deleted": True}
    assert titles(jose) == [] and titles(teacher) == ["Loops"]
    assert teacher.get("/api/teach/assignments").json()[0]["course_id"] is None


def test_course_changes_are_checked(people, db):
    teacher, _, _ = people
    teacher.post("/api/teach/courses", json={"name": "CS 101"})
    for bad, why in [({"name": "CS 101"}, "already a course named"), ({"name": "  "}, "1 to 120"), ({"name": "n" * 121}, "1 to 120")]:
        r = teacher.post("/api/teach/courses", json=bad)
        assert r.status_code == 400 and why in r.json()["detail"]
    for ids in ([1], [2, 999]):                                         # a teacher, an account that does not exist
        r = teacher.patch("/api/teach/courses/1", json={"student_ids": ids, "name": "Changed"})
        assert r.status_code == 400 and "student accounts" in r.json()["detail"]
    assert teacher.get("/api/teach/courses").json() == [{"id": 1, "name": "CS 101", "student_ids": []}]
    assert teacher.patch("/api/teach/courses/9", json={"name": "x"}).status_code == 404
    assert teacher.delete("/api/teach/courses/9").status_code == 404

    upload(teacher)
    r = teacher.patch("/api/teach/assignments/1", json={"course_id": 9})
    assert r.status_code == 400 and "course does not exist" in r.json()["detail"]


def test_announcements_reach_the_right_students(people, db):
    teacher, maria, jose = people
    teacher.post("/api/teach/courses", json={"name": "CS 101"})
    teacher.patch("/api/teach/courses/1", json={"student_ids": [2]})

    r = teacher.post("/api/teach/announcements", json={"title": "Welcome", "body": "Labs start Monday."})
    assert r.status_code == 201 and r.json()["course"] is None
    r = teacher.post("/api/teach/announcements", json={"title": "Quiz on Friday", "body": "", "course_id": 1})
    assert r.status_code == 201 and r.json()["course"] == "CS 101"

    def seen(client):
        return [a["title"] for a in client.get("/api/announcements").json()]

    assert seen(maria) == ["Quiz on Friday", "Welcome"]                 # newest first
    assert seen(jose) == ["Welcome"]                                    # not in the course
    assert seen(teacher) == ["Quiz on Friday", "Welcome"]

    for bad, why in [({"title": " "}, "titles are"), ({"title": "t", "body": "b" * 5001}, "at most 5000")]:
        r = teacher.post("/api/teach/announcements", json=bad)
        assert r.status_code == 400 and why in r.json()["detail"]
    assert teacher.post("/api/teach/announcements", json={"title": "t", "course_id": 9}).status_code == 404

    assert teacher.delete("/api/teach/announcements/2").json() == {"deleted": True}
    assert seen(maria) == ["Welcome"]
    teacher.post("/api/teach/announcements", json={"title": "Room change", "course_id": 1})
    teacher.delete("/api/teach/courses/1")                              # its announcements go with it
    assert seen(maria) == ["Welcome"] and db.scalar(select(func.count()).select_from(Announcement)) == 1


def test_students_cannot_manage_courses_or_announcements(people, db):
    teacher, maria, _ = people
    teacher.post("/api/teach/courses", json={"name": "CS 101"})
    teacher.post("/api/teach/announcements", json={"title": "Welcome"})
    for client, refusal in [(TestClient(app), 401), (maria, 403)]:
        assert client.get("/api/teach/courses").status_code == refusal
        assert client.post("/api/teach/courses", json={"name": "Mine"}).status_code == refusal
        assert client.patch("/api/teach/courses/1", json={"student_ids": [2]}).status_code == refusal
        assert client.delete("/api/teach/courses/1").status_code == refusal
        assert client.get("/api/teach/announcements").status_code == refusal
        assert client.post("/api/teach/announcements", json={"title": "School is cancelled"}).status_code == refusal
        assert client.delete("/api/teach/announcements/1").status_code == refusal
        assert client.get("/api/teach/assignments/1/progress").status_code == refusal
    assert TestClient(app).get("/api/announcements").status_code == 401
    assert db.scalar(select(func.count()).select_from(Course)) == 1 and db.scalar(select(func.count()).select_from(Announcement)) == 1


def test_who_has_opened_an_assignment(people, hub, db):
    teacher, maria, jose = people
    auth.create_user(db, "ana", PASSWORD, display_name="Ana Ruiz")      # id 4, not given the assignment
    upload(teacher, "Loops")
    teacher.patch("/api/teach/assignments/1", json={"student_ids": [2, 3], "published": True})

    assert maria.get("/api/assignments").json()[0]["opened_at"] is None
    assert maria.post("/api/assignments/1/launch").status_code == 200
    first = maria.get("/api/assignments/1").json()["opened_at"]
    assert first is not None
    maria.post("/api/assignments/1/launch")                             # opening again keeps the first time
    assert maria.get("/api/assignments").json()[0]["opened_at"] == first
    assert jose.get("/api/assignments").json()[0]["opened_at"] is None

    progress = teacher.get("/api/teach/assignments/1/progress").json()
    assert progress["assignment"]["title"] == "Loops"
    assert [(s["name"], s["opened_at"]) for s in progress["students"]] == [("Jose Perez", None), ("Maria Lopez", first)]

    # Given to everyone: every student is listed, the teacher who tried it out is not.
    teacher.post("/api/assignments/1/launch")
    teacher.patch("/api/teach/assignments/1", json={"for_everyone": True})
    names = [s["name"] for s in teacher.get("/api/teach/assignments/1/progress").json()["students"]]
    assert names == ["Ana Ruiz", "Jose Perez", "Maria Lopez"]
    assert teacher.get("/api/teach/assignments/9/progress").status_code == 404
