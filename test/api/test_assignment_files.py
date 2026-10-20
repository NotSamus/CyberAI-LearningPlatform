"""Data files (datasets) beside an assignment's notebook: uploaded with it or later, a copy for each
student who opens it, and handed to Otter with an autograded notebook. On a real (throwaway)
Postgres database; the hub and the grading service are replaced by stand-ins."""
import importlib.util
import io
import json
import sys
import types
import zipfile
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app import assignments, grading
from app.models import AssignmentFile
from conftest import notebook_file, upload

CSV = b"port,service\n22,ssh\n443,https\n"
MARIA = "s-2"


def upload_with(client, data: dict[str, bytes], title="Ports lab", name="lab.ipynb", content=None, **fields):
    files = [("file", (name, notebook_file() if content is None else content)), *(("data", (n, d)) for n, d in data.items())]
    return client.post("/api/teach/assignments", data={"title": title, **fields}, files=files)


def add(client, data: dict[str, bytes], assignment_id=1):
    return client.post(f"/api/teach/assignments/{assignment_id}/data-files", files=[("files", (n, d)) for n, d in data.items()])


def stored(db) -> int:
    return db.scalar(select(func.count()).select_from(AssignmentFile))


def otter_master() -> bytes:
    notebook = json.loads(notebook_file("import pandas as pd\nports = pd.read_csv('ports.csv') # SOLUTION"))
    notebook["cells"].insert(0, {"cell_type": "raw", "metadata": {}, "source": "# ASSIGNMENT CONFIG\nname: ports-lab"})
    return json.dumps(notebook).encode()


@pytest.fixture
def otter(monkeypatch):
    """Stands in for the grading service, and remembers which data files each preparing was given."""
    given = []

    async def prepare(master, name, gpu, data):
        given.append(dict(data))
        return notebook_file("ports = ..."), b"the autograder package"

    async def grade(notebook, autograder, name, gpu):
        return {"tests": [{"name": "q1", "score": 0, "max_score": 1.0}]}

    monkeypatch.setattr(grading, "prepare", prepare)
    monkeypatch.setattr(grading, "grade", grade)
    return given


def test_each_student_gets_a_copy_of_the_data_beside_the_notebook(people, hub, db):
    teacher, maria, _ = people
    r = upload_with(teacher, {"ports.csv": CSV, "my scans.zip": b"PK\x05\x06" + b"\x00" * 18})
    assert r.status_code == 201, r.text
    assert r.json()["data_files"] == [{"name": "my scans.zip", "size": 22}, {"name": "ports.csv", "size": len(CSV)}]
    teacher.patch("/api/teach/assignments/1", json={"for_everyone": True, "published": True})
    r = teacher.get("/api/teach/assignments/1/data-files/ports.csv")
    assert r.content == CSV and r.headers["content-disposition"] == 'attachment; filename="ports.csv"'
    assert maria.get("/api/teach/assignments/1/data-files/ports.csv").status_code == 403

    assert maria.post("/api/assignments/1/launch").status_code == 200
    folder = "assignments/ports-lab-1"
    assert {path for owner, path in hub if owner == MARIA} == {f"{folder}/lab.ipynb", f"{folder}/ports.csv", f"{folder}/my scans.zip"}
    assert hub[(MARIA, f"{folder}/ports.csv")] == CSV

    # Her copy is hers: opening again never overwrites it, but one she deleted comes back.
    hub[(MARIA, f"{folder}/ports.csv")] = b"her own edits"
    del hub[(MARIA, f"{folder}/my scans.zip")]
    maria.post("/api/assignments/1/launch")
    assert hub[(MARIA, f"{folder}/ports.csv")] == b"her own edits" and (MARIA, f"{folder}/my scans.zip") in hub

    # From then on the data files, like the notebook, can no longer be changed.
    assert add(teacher, {"more.csv": CSV}).status_code == 409
    assert teacher.delete("/api/teach/assignments/1/data-files/ports.csv").status_code == 409
    assert teacher.get("/api/teach/assignments/1/progress").json()["assignment"]["notebook_locked"] is True


def test_data_files_are_added_and_removed_until_a_student_has_it(people, hub, db):
    teacher, maria, _ = people
    upload(teacher, "Ports lab")
    r = add(teacher, {"ports.csv": b"old", "hosts.csv": CSV})
    assert r.status_code == 200 and [f["name"] for f in r.json()["data_files"]] == ["hosts.csv", "ports.csv"]
    r = add(teacher, {"ports.csv": CSV})                    # the same name: in place of the earlier one
    assert {f["name"]: f["size"] for f in r.json()["data_files"]} == {"hosts.csv": len(CSV), "ports.csv": len(CSV)}
    assert teacher.get("/api/teach/assignments/1/data-files/ports.csv").content == CSV
    r = teacher.delete("/api/teach/assignments/1/data-files/hosts.csv")
    assert r.status_code == 200 and r.json()["data_files"] == [{"name": "ports.csv", "size": len(CSV)}]
    assert teacher.delete("/api/teach/assignments/1/data-files/hosts.csv").status_code == 404
    assert add(teacher, {}).status_code == 422
    assert maria.post("/api/teach/assignments/1/data-files", files=[("files", ("x.csv", CSV))]).status_code == 403

    # Replacing the notebook keeps them.
    r = teacher.put("/api/teach/assignments/1/notebook", files={"file": ("lab.ipynb", notebook_file("print(2)"))})
    assert r.status_code == 200 and r.json()["data_files"] == [{"name": "ports.csv", "size": len(CSV)}]

    # The teacher's editing copy gets them beside it, so that it runs there as it will for students.
    assert teacher.post("/api/teach/assignments/1/editing-copy", json={}).status_code == 200
    assert hub[("t-1", "editing/ports-lab-1/ports.csv")] == CSV


def test_an_autograded_notebook_is_prepared_with_its_data(people, hub, db, otter, monkeypatch):
    teacher, _, _ = people
    r = upload_with(teacher, {"ports.csv": CSV}, content=otter_master())
    assert r.status_code == 201 and r.json()["autograded"] is True
    assert otter == [{"ports.csv": CSV}]

    # Every change of the data files goes through Otter again, with all of them (its autograder carries them).
    add(teacher, {"hosts.csv": b"h"})
    assert otter[-1] == {"ports.csv": CSV, "hosts.csv": b"h"}
    teacher.delete("/api/teach/assignments/1/data-files/ports.csv")
    assert otter[-1] == {"hosts.csv": b"h"}
    # So does a new version of the notebook, with the data files the assignment has.
    teacher.put("/api/teach/assignments/1/notebook", files={"file": ("lab.ipynb", otter_master())})
    assert otter[-1] == {"hosts.csv": b"h"} and len(otter) == 4

    # Otter refusing the notebook with the new data leaves the data files as they were.
    async def solutions_fail(master, name, gpu, data):
        raise grading.GradingError("q1 failed")

    monkeypatch.setattr(grading, "prepare", solutions_fail)
    assert add(teacher, {"broken.csv": b"x"}).status_code == 400
    assert [f["name"] for f in teacher.get("/api/teach/assignments/1/progress").json()["assignment"]["data_files"]] == ["hosts.csv"]


@pytest.mark.parametrize("name, refusal", [
    ("my data (1).csv", "cannot be a data file's name"),
    (".hidden.csv", "cannot be a data file's name"),
    ("other.ipynb", "is a notebook: upload it as an assignment of its own"),
    ("lab.ipynb", "is a notebook"),
    ("tests", "the notebook or the autograder uses it"),
    ("dist", "the notebook or the autograder uses it"),
    ("lab-autograder_2026.zip", "the notebook or the autograder uses it"),
])
def test_data_file_names_that_are_refused(people, db, name, refusal):
    teacher, _, _ = people
    r = upload_with(teacher, {name: CSV})
    assert r.status_code == 400 and refusal in r.json()["detail"], r.text
    assert stored(db) == 0


def test_what_is_too_much_data(people, db, monkeypatch):
    teacher, _, _ = people
    # Folders are taken off a file's name: only the name itself is kept.
    assert upload_with(teacher, {"../../etc/ports.csv": CSV}).json()["data_files"] == [{"name": "ports.csv", "size": len(CSV)}]
    r = teacher.post("/api/teach/assignments", data={"title": "Twice"}, files=[
        ("file", ("lab.ipynb", notebook_file())), ("data", ("a.csv", CSV)), ("data", ("a.csv", CSV)),
    ])
    assert r.status_code == 400 and r.json()["detail"] == "Two data files are named a.csv."
    monkeypatch.setattr(assignments, "MAX_DATA_FILES", 2)
    r = upload_with(teacher, {"a.csv": CSV, "b.csv": CSV, "c.csv": CSV})
    assert r.status_code == 400 and "at most 2 data files" in r.json()["detail"]
    monkeypatch.setattr(assignments, "MAX_DATA_BYTES", 1024 * 1024)
    r = upload_with(teacher, {"a.csv": b"x" * 600_000, "b.csv": b"x" * 600_000})
    assert r.status_code == 400 and "more than 1 MB together. Each student gets a copy" in r.json()["detail"]
    r = add(teacher, {"big.csv": b"x" * 1_100_000})
    assert r.status_code == 400 and stored(db) == 1        # only the first upload's
    assert [f["name"] for f in teacher.get("/api/teach/assignments/1/progress").json()["assignment"]["data_files"]] == ["ports.csv"]


def test_data_files_travel_with_their_notebook_in_a_lesson_zip(people, db):
    teacher, _, _ = people
    upload_with(teacher, {"ports.csv": CSV})
    lesson_id = teacher.post("/api/teach/lessons", json={"title": "Ports"}).json()["id"]
    teacher.patch(f"/api/teach/lessons/{lesson_id}", json={"blocks": [{"type": "assignment", "id": "lab1", "assignment_id": 1}]})
    content = teacher.get(f"/api/teach/lessons.zip?ids={lesson_id}").content
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        assert archive.read("notebooks/ports-lab-1/ports.csv") == CSV
        assert json.loads(archive.read("lessons.json"))["notebooks"][0]["data"] == ["notebooks/ports-lab-1/ports.csv"]

    def bring_in():
        return teacher.post("/api/teach/lesson-imports", data={"for": "none"}, files={"file": ("lessons.zip", content, "application/zip")})

    # On the same platform, with the same data files: linked to the assignment that is there.
    assert bring_in().json()["notebooks_linked"] == ["Ports lab"]
    # Elsewhere (the assignment is not there): it comes with its data files.
    for path in ["/api/teach/lessons/1", "/api/teach/lessons/2", "/api/teach/assignments/1"]:
        teacher.delete(path)
    assert bring_in().json()["notebooks_added"] == ["Ports lab"]
    assert teacher.get("/api/teach/assignments/2/progress").json()["assignment"]["data_files"] == [{"name": "ports.csv", "size": len(CSV)}]
    assert teacher.get("/api/teach/assignments/2/data-files/ports.csv").content == CSV
    # The same notebook with other data files is another assignment.
    add(teacher, {"ports.csv": b"changed"}, assignment_id=2)
    assert bring_in().json()["notebooks_added"] == ["Ports lab"]


def test_the_grader_lists_the_data_files_in_otters_config(monkeypatch):
    """grader/main.py adds `files:` to the ASSIGNMENT CONFIG cell, so that Otter puts the data files into
    the autograder package and beside every submission it grades; one the teacher wrote is kept."""
    monkeypatch.setitem(sys.modules, "docker", types.ModuleType("docker"))     # not installed here; only used to run jobs
    monkeypatch.setenv("GRADER_TOKEN", "test")
    spec = importlib.util.spec_from_file_location("grader_main", Path(__file__).resolve().parents[2] / "grader" / "main.py")
    grader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(grader)

    def config(master: bytes) -> str:
        return json.loads(master)["cells"][0]["source"]

    assert config(grader._with_autograder_package(otter_master(), ["2024.csv", "ports.csv"])) == (
        '# ASSIGNMENT CONFIG\nname: ports-lab\ngenerate: true\nfiles:\n  - "2024.csv"\n  - "ports.csv"'
    )
    assert config(grader._with_autograder_package(otter_master(), [])) == "# ASSIGNMENT CONFIG\nname: ports-lab\ngenerate: true"
    own = json.loads(otter_master())
    own["cells"][0]["source"] = "# ASSIGNMENT CONFIG\nfiles:\n  - ports.csv"
    assert config(grader._with_autograder_package(json.dumps(own).encode(), ["ports.csv"])) == (
        "# ASSIGNMENT CONFIG\nfiles:\n  - ports.csv\ngenerate: true"
    )
