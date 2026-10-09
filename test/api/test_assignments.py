"""Uploading notebooks as assignments and giving them to students, on a real (throwaway) Postgres
database. The hub is replaced by a stand-in that remembers which files were put into whose home."""
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app import assignments, auth
from app.jupyter import hub_client
from app.main import MAX_REQUEST_BYTES, LimitRequestSize, app
from app.models import Assignment
from conftest import API_DIR, PASSWORD, browser, notebook_file, upload

def titles(client) -> list[str]:
    return [a["title"] for a in client.get("/api/assignments").json()]


# --- the normal path ------------------------------------------------------------------------------

def test_teacher_uploads_assigns_and_publishes(people, db):
    teacher, maria, jose = people
    r = upload(teacher, "Loops and lists", description="Practice with for loops.", due_at="2026-11-01T06:59:00Z")
    assert r.status_code == 201
    created = r.json()
    assert (created["slug"], created["notebook_name"], created["published"], created["for_everyone"]) == \
        ("loops-and-lists-1", "lab.ipynb", False, False)
    assert created["due_at"].startswith("2026-11-01T06:59:00")
    url = f"/api/teach/assignments/{created['id']}"

    # A draft: the teacher sees it, students do not.
    assert titles(teacher) == ["Loops and lists"] and titles(maria) == [] and titles(jose) == []

    # Published and given to maria by name: only she gets it.
    r = teacher.patch(url, json={"student_ids": [2], "published": True})
    assert r.status_code == 200 and r.json()["student_ids"] == [2]
    assert titles(maria) == ["Loops and lists"] and titles(jose) == []
    assert maria.get("/api/assignments/1").json()["description"] == "Practice with for loops."

    # Given to everyone: jose gets it too, and so does a student whose account is created later.
    assert teacher.patch(url, json={"for_everyone": True}).status_code == 200
    assert titles(jose) == ["Loops and lists"]
    auth.create_user(db, "ana", PASSWORD)
    assert titles(browser("ana")) == ["Loops and lists"]

    # Unpublished again: gone for students at once.
    assert teacher.patch(url, json={"published": False}).status_code == 200
    assert titles(maria) == [] and maria.get("/api/assignments/1").status_code == 404


def test_teacher_edits_an_assignment(people):
    teacher, maria, _ = people
    upload(teacher, "Loops", due_at="2026-11-01T06:59:00Z")
    assert upload(teacher, "Loops").json()["slug"] == "loops-2"           # same title, its own folder
    url = "/api/teach/assignments/1"

    r = teacher.patch(url, json={"title": "  Loops, part 1 ", "description": "New text.", "requires_gpu": True, "due_at": None})
    changed = r.json()
    assert (changed["title"], changed["description"], changed["requires_gpu"], changed["due_at"]) == ("Loops, part 1", "New text.", True, None)
    assert changed["slug"] == "loops-1"              # the folder students already have keeps its name

    for bad, why in [({"title": "   "}, "Titles are"), ({"title": "t" * 121}, "Titles are"), ({"description": "d" * 2001}, "Descriptions are")]:
        refused = teacher.patch(url, json=bad)
        assert refused.status_code == 400 and why in refused.json()["detail"]
    assert teacher.patch(url, json={"due_at": "next friday"}).status_code == 422
    assert teacher.patch("/api/teach/assignments/99", json={"published": True}).status_code == 404
    assert [a["title"] for a in teacher.get("/api/teach/assignments").json()] == ["Loops", "Loops, part 1"]   # newest first


def test_opening_gives_each_student_their_own_copy_once(people, hub):
    teacher, maria, jose = people
    original = notebook_file("# Exercise 1", "print('fill me in')")
    upload(teacher, "Loops", content=original)
    teacher.patch("/api/teach/assignments/1", json={"for_everyone": True, "published": True})

    r = maria.post("/api/assignments/1/launch")
    assert r.status_code == 200
    assert r.json()["url"] == "http://localhost:8081/user/s-2/cpu/lab/tree/assignments/loops-1/lab.ipynb"
    assert hub == {("s-2", "assignments/loops-1/lab.ipynb"): original}    # exactly the uploaded bytes, in her home only

    # She works on it. Opening it again never replaces her work.
    hub[("s-2", "assignments/loops-1/lab.ipynb")] = b"maria's answers"
    assert maria.post("/api/assignments/1/launch").status_code == 200
    assert hub[("s-2", "assignments/loops-1/lab.ipynb")] == b"maria's answers"

    # The teacher can open it too, in the teacher's own home.
    assert teacher.post("/api/assignments/1/launch").json()["url"].startswith("http://localhost:8081/user/t-1/cpu/")
    assert hub[("t-1", "assignments/loops-1/lab.ipynb")] == original
    assert ("s-3", "assignments/loops-1/lab.ipynb") not in hub             # jose has not opened it


def test_a_copy_that_cannot_be_made_is_reported(people, hub, monkeypatch):
    teacher, maria, _ = people
    upload(teacher)
    teacher.patch("/api/teach/assignments/1", json={"for_everyone": True, "published": True})

    async def refused(username, server, path, content):
        import httpx
        request = httpx.Request("PUT", "http://hub/user/s-2/cpu/api/contents/x")
        raise httpx.HTTPStatusError("403", request=request, response=httpx.Response(403, request=request))

    monkeypatch.setattr(hub_client, "put_file", refused)
    r = maria.post("/api/assignments/1/launch")
    assert r.status_code == 502 and "returned an error (403)" in r.json()["detail"]


def test_download_and_delete(people, hub):
    teacher, maria, _ = people
    original = notebook_file("print('teacher copy')")
    upload(teacher, content=original, name="Week 1 (final).ipynb")
    teacher.patch("/api/teach/assignments/1", json={"for_everyone": True, "published": True})
    maria.post("/api/assignments/1/launch")

    r = teacher.get("/api/teach/assignments/1/notebook")
    assert r.status_code == 200 and r.content == original
    assert r.headers["content-disposition"] == 'attachment; filename="Week_1_final.ipynb"'    # a download, never shown in the page
    assert r.headers["x-content-type-options"] == "nosniff"

    assert teacher.delete("/api/teach/assignments/1").json() == {"deleted": True}
    assert titles(maria) == [] and maria.post("/api/assignments/1/launch").status_code == 404
    assert teacher.delete("/api/teach/assignments/1").status_code == 404
    assert ("s-2", "assignments/loops-1/Week_1_final.ipynb") in hub      # her copy is hers: deleting does not reach into homes


def test_a_corrected_notebook_under_the_same_title_reaches_students(people, hub):
    # The teacher finds a mistake after students opened the notebook, deletes the assignment and
    # uploads the corrected file with the same title. Students must get the new file, not find the
    # old one still sitting in a folder of the same name.
    teacher, maria, _ = people
    upload(teacher, "Loops", content=notebook_file("print('with a mistake')"))
    teacher.patch("/api/teach/assignments/1", json={"for_everyone": True, "published": True})
    maria.post("/api/assignments/1/launch")
    teacher.delete("/api/teach/assignments/1")

    corrected = notebook_file("print('corrected')")
    assert upload(teacher, "Loops", content=corrected).json()["slug"] == "loops-2"
    teacher.patch("/api/teach/assignments/2", json={"for_everyone": True, "published": True})
    assert maria.post("/api/assignments/2/launch").json()["url"].endswith("/assignments/loops-2/lab.ipynb")
    assert hub[("s-2", "assignments/loops-2/lab.ipynb")] == corrected
    assert ("s-2", "assignments/loops-1/lab.ipynb") in hub              # her first attempt is still hers


# --- what students must not be able to do ---------------------------------------------------------

def test_teacher_api_is_enforced_on_the_server(people, db):
    teacher, maria, _ = people
    upload(teacher, "Secret draft")
    stranger = TestClient(app)

    for client, refusal in [(stranger, 401), (maria, 403)]:
        assert client.get("/api/teach/assignments").status_code == refusal
        assert client.get("/api/teach/students").status_code == refusal
        assert upload(client, "Mine").status_code == refusal
        assert client.patch("/api/teach/assignments/1", json={"published": True, "student_ids": [2]}).status_code == refusal
        assert client.delete("/api/teach/assignments/1").status_code == refusal
        assert client.get("/api/teach/assignments/1/notebook").status_code == refusal
    assert "Secret draft" not in maria.get("/api/teach/assignments").text
    # Pretending in the request changes nothing: the role is read from the database.
    assert maria.get("/api/teach/assignments", headers={"X-Role": "teacher"}, params={"role": "teacher"}).status_code == 403
    assert maria.get("/api/me").json()["can_teach"] is False

    stored = db.scalars(select(Assignment)).all()
    assert [(a.title, a.published) for a in stored] == [("Secret draft", False)]     # nothing was added or changed

    assert [s["username"] for s in teacher.get("/api/teach/students").json()] == ["jose", "maria"]
    assert "argon2" not in teacher.get("/api/teach/students").text


def test_an_admin_can_teach_whatever_their_role(db):
    auth.create_user(db, "boss", PASSWORD, role="student", is_admin=True)
    boss = browser("boss")
    assert boss.get("/api/me").json()["can_teach"] is True
    assert upload(boss).status_code == 201 and titles(boss) == ["Loops"]


def test_students_cannot_open_what_was_not_given_to_them(people, hub):
    teacher, maria, jose = people
    upload(teacher, "For maria")
    upload(teacher, "Draft")
    teacher.patch("/api/teach/assignments/1", json={"student_ids": [2], "published": True})
    teacher.patch("/api/teach/assignments/2", json={"for_everyone": True})         # given to everyone, but not published

    assert maria.post("/api/assignments/1/launch").status_code == 200
    # jose guesses the ids. Same answer as for an assignment that does not exist.
    for path in ["/api/assignments/1", "/api/assignments/2"]:
        assert jose.get(path).status_code == 404
        assert jose.post(f"{path}/launch").json() == {"detail": "No such assignment."}
        assert jose.post(f"{path}/stop").status_code == 404
    assert maria.post("/api/assignments/2/launch").status_code == 404
    assert [who for who, _ in hub] == ["s-2"]                           # nothing reached jose's home


def test_only_student_accounts_can_be_given_an_assignment(people, db):
    teacher, maria, _ = people
    upload(teacher)
    url = "/api/teach/assignments/1"
    teacher.patch(url, json={"student_ids": [2]})
    for ids in ([1], [2, 999], [-1]):                                   # a teacher, an account that does not exist
        r = teacher.patch(url, json={"student_ids": ids, "title": "Changed"})
        assert r.status_code == 400 and "student accounts" in r.json()["detail"]
    assert teacher.patch(url, json={"student_ids": ["2; DROP TABLE users"]}).status_code == 422
    listed = teacher.get("/api/teach/assignments").json()[0]
    assert listed["student_ids"] == [2] and listed["title"] == "Loops"   # a refused change changes nothing


# --- hostile uploads ------------------------------------------------------------------------------

def test_upload_refuses_what_is_not_a_notebook(people, db, monkeypatch):
    teacher, _, _ = people
    monkeypatch.setattr(assignments, "MAX_NOTEBOOK_BYTES", 300_000)     # the real limit is 10 MB: slow to test with
    old_format = b'{"worksheets": [], "metadata": {}, "nbformat": 3, "nbformat_minor": 0}'
    for kwargs, why in [
        (dict(name="lab.py", content=b"print('hi')"), "ending in .ipynb"),
        (dict(name="lab.ipynb.exe"), "ending in .ipynb"),
        (dict(name=""), None),                                          # no file at all
        (dict(content=b"not json"), "not a valid Jupyter notebook"),
        (dict(content=b"\xff\xfe\x00binary"), "not a valid Jupyter notebook"),
        (dict(content=b'{"cells": "no"}'), "not a valid Jupyter notebook"),
        (dict(content=b"[" * 200_000), "not a valid Jupyter notebook"),   # nested deeper than any real notebook
        (dict(content=old_format), "old format"),
        (dict(content=notebook_file("x" * 300_000)), "Clear its outputs"),
        (dict(title="   "), "Titles are"),
        (dict(description="d" * 2001), "Descriptions are"),
    ]:
        r = upload(teacher, **kwargs)
        assert r.status_code in (400, 422), kwargs.get("name")
        if why:
            assert r.status_code == 400 and why in r.json()["detail"]
    assert teacher.post("/api/teach/assignments", json={"title": "No file"}).status_code == 422
    assert db.scalar(select(func.count()).select_from(Assignment)) == 0


@pytest.mark.parametrize("name, stored", [
    ("../../../etc/cron.d/evil.ipynb", "evil.ipynb"),
    ("..\\..\\windows\\evil.ipynb", "evil.ipynb"),
    ("/etc/passwd.ipynb", "passwd.ipynb"),
    ("x; rm -rf ~ #$(id).ipynb", "x_rm_-rf_id.ipynb"),
    ("....ipynb", "notebook.ipynb"),
    ("a" * 300 + ".ipynb", "a" * 80 + ".ipynb"),
    ("Tarea Número 1.IPYNB", "Tarea_N_mero_1.ipynb"),
])
def test_uploaded_file_names_cannot_leave_the_assignment_folder(people, hub, name, stored):
    teacher, _, _ = people
    r = upload(teacher, "../../Escape <b>", name=name)
    assert r.status_code == 201
    assert (r.json()["slug"], r.json()["notebook_name"]) == ("escape-b-1", stored)
    teacher.post("/api/assignments/1/launch")
    assert list(hub) == [("t-1", f"assignments/escape-b-1/{stored}")]


def test_oversized_requests_are_cut_off(people):
    teacher, _, _ = people
    too_big = b"x" * (MAX_REQUEST_BYTES + 1)
    json_headers = {"Content-Type": "application/json"}
    for client in (TestClient(app), teacher):                           # logged in or not
        r = client.post("/api/auth/login", content=too_big, headers=json_headers)
        assert r.status_code == 413 and "larger than 1 MB" in r.json()["detail"]

    def in_pieces():                                                    # no Content-Length header to check up front
        for _ in range(MAX_REQUEST_BYTES // 65536 + 2):
            yield b"x" * 65536

    assert TestClient(app).post("/api/auth/login", content=in_pieces(), headers=json_headers).status_code == 413
    # Only the upload itself may be larger than that.
    assert upload(teacher, content=notebook_file("x" * (2 * MAX_REQUEST_BYTES))).status_code == 201
    assert teacher.patch("/api/teach/assignments/1", content=too_big, headers=json_headers).status_code == 413


def test_size_limits_by_route():
    async def count_bytes(scope, receive, send):                        # a tiny app that reads the whole request
        size, more = 0, True
        while more:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size, more = size + len(message.get("body", b"")), message.get("more_body", False)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": str(size).encode()})

    client = TestClient(LimitRequestSize(count_bytes, max_bytes=100, larger={("POST", "/upload"): 1000}))

    def pieces(total):
        for _ in range(total // 10):
            yield b"x" * 10

    assert client.post("/anything", content=b"x" * 100).text == "100"
    assert client.post("/anything", content=b"x" * 101).status_code == 413
    assert client.post("/anything", content=pieces(110)).status_code == 413     # without a Content-Length header
    assert client.post("/upload", content=b"x" * 1000).text == "1000"
    assert client.post("/upload", content=pieces(1000)).text == "1000"
    assert client.post("/upload", content=b"x" * 1001).status_code == 413
    assert client.post("/upload", content=pieces(1010)).status_code == 413
    assert client.put("/upload", content=b"x" * 101).status_code == 413          # the larger limit is for POST only
    assert client.post("/upload/more", content=b"x" * 101).status_code == 413


def test_an_upload_from_someone_who_may_not_teach_is_refused_unread(people):
    _, maria, _ = people
    sent = []

    def large_upload():
        boundary = b"--frontier\r\n"
        yield boundary + b'Content-Disposition: form-data; name="title"\r\n\r\nMine\r\n'
        yield boundary + b'Content-Disposition: form-data; name="file"; filename="lab.ipynb"\r\n\r\n'
        for _ in range(200):
            sent.append(1)
            yield b"x" * 65536

    headers = {"Content-Type": "multipart/form-data; boundary=frontier"}
    assert maria.post("/api/teach/assignments", content=large_upload(), headers=headers).status_code == 403
    assert TestClient(app).post("/api/teach/assignments", content=large_upload(), headers=headers).status_code == 401
    assert sent == []               # the account was checked first: none of the file was taken in


# --- the command line -----------------------------------------------------------------------------

def test_import_assignment_from_the_command_line(people, migrated_db_url, tmp_path):
    _, maria, _ = people
    notebook = tmp_path / "lab1.ipynb"
    notebook.write_bytes(notebook_file())

    def manage(*args):
        return subprocess.run(
            [sys.executable, "-m", "app.manage", "import-assignment", *args],
            cwd=API_DIR, env={**os.environ, "DATABASE_URL": migrated_db_url}, capture_output=True, text=True,
        )

    draft = manage(str(notebook), "--title", "Python basics")
    assert draft.returncode == 0 and "a draft" in draft.stdout and titles(maria) == []
    published = manage(str(notebook), "--title", "Hello GPU", "--gpu", "--publish")
    assert published.returncode == 0 and titles(maria) == ["Hello GPU"]
    (tmp_path / "notes.ipynb").write_text("not a notebook")
    bad = manage(str(tmp_path / "notes.ipynb"), "--title", "Bad")
    assert bad.returncode != 0 and "not a valid Jupyter notebook" in bad.stderr
    missing = manage(str(tmp_path / "nope.ipynb"), "--title", "Missing")
    assert missing.returncode != 0 and "Cannot read" in missing.stderr
