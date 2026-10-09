"""Autograding with Otter-Grader (https://otter-grader.readthedocs.io).

A teacher writes one notebook in Otter Assign format: questions, their solutions and tests, some of
them hidden. When it is uploaded, `prepare` has Otter turn it into the version students get (no
solutions, only the public tests) and an autograder package (every test). When a student submits,
`grade` has Otter execute their notebook and run every test.

Nothing is executed in this process, which can reach the database. The work is done by the grading
service (grader/ at the project root), in a throwaway container without network access.
"""
import base64
import json

import httpx

from app import config

GRADER_TIMEOUT = 3600       # seconds: a job runs up to 5 minutes and may wait behind other jobs first


class GradingError(Exception):
    """Otter could not do it. `reason` is safe to show; `log` is the end of what Otter printed."""

    def __init__(self, reason: str, log: str = ""):
        super().__init__(reason)
        self.reason, self.log = reason, log

    def __str__(self) -> str:
        return f"{self.reason}\n\n{self.log[-2000:].strip()}".strip()     # the end of the log is where Otter says what failed


class GraderUnreachable(GradingError):
    pass


def _cell_text(cell: dict) -> str:
    source = cell.get("source", "")
    return "".join(source) if isinstance(source, list) else source


def is_otter_master(notebook: bytes) -> bool:
    """Whether a (valid) notebook is written in Otter Assign format: it has the raw cells Otter
    looks for. Any other notebook is a plain assignment, graded by hand."""
    cells = json.loads(notebook).get("cells", [])
    return any(
        cell.get("cell_type") == "raw" and _cell_text(cell).lstrip().startswith(("# ASSIGNMENT CONFIG", "# BEGIN QUESTION"))
        for cell in cells
    )


def total_points(student_notebook: bytes) -> float | None:
    """The points of all questions together, read from the tests Otter put in the students'
    notebook. None when that cannot be told (it is then known once a submission is graded)."""
    tests = json.loads(student_notebook).get("metadata", {}).get("otter", {}).get("tests") or {}
    total = 0.0
    for test in tests.values():
        points = test.get("points")
        if isinstance(points, list) and all(isinstance(p, (int, float)) for p in points):
            points = sum(points)
        if not isinstance(points, (int, float)) or isinstance(points, bool):
            return None
        total += points
    return total if tests else None


async def _ask_grader(path: str, name: str, gpu: bool, files: dict[str, bytes]) -> dict:
    try:
        async with httpx.AsyncClient(base_url=config.GRADER_URL, timeout=GRADER_TIMEOUT) as grader:
            r = await grader.post(
                path,
                headers={"Authorization": f"Bearer {config.GRADER_TOKEN}"},
                data={"name": name, "image": "gpu" if gpu else "cpu"},
                files=files,
            )
    except httpx.HTTPError:
        raise GraderUnreachable("The grading service is not reachable right now.")
    if r.status_code == 200:
        return r.json()
    try:
        detail = r.json().get("detail")
    except ValueError:
        detail = None
    if isinstance(detail, dict):
        raise GradingError(str(detail.get("reason", "Otter stopped with an error.")), str(detail.get("log", "")))
    raise GradingError(str(detail) if r.status_code == 400 and detail else f"The grading service returned an error ({r.status_code}).")


async def prepare(master: bytes, name: str, gpu: bool) -> tuple[bytes, bytes]:
    """(the notebook for students, the autograder package). Otter runs the notebook's own solutions
    against its tests while preparing, and refuses a notebook whose solutions do not pass."""
    answer = await _ask_grader("/prepare", name, gpu, {"notebook": master})
    return base64.b64decode(answer["student"]), base64.b64decode(answer["autograder"])


async def grade(notebook: bytes, autograder: bytes, name: str, gpu: bool) -> dict:
    """Otter's results for a submitted notebook: {"tests": [{name, score, max_score, visibility, output}, ...]}."""
    return (await _ask_grader("/grade", name, gpu, {"notebook": notebook, "autograder": autograder}))["results"]


def _scored(results: dict) -> list[dict]:
    return [t for t in results.get("tests", []) if isinstance(t.get("max_score"), (int, float))]


def totals(results: dict) -> tuple[float, float]:
    """(score, the most it could have been)."""
    scored = _scored(results)
    return float(sum(t.get("score") or 0 for t in scored)), float(sum(t["max_score"] for t in scored))


def questions(results: dict | None, with_hidden_output: bool) -> list[dict]:
    """A score per question. Otter's output for a question describes its hidden tests too, so only
    teachers get it."""
    return [
        {"name": t.get("name", ""), "score": t.get("score") or 0, "max_score": t["max_score"]}
        | ({"output": t.get("output", "")} if with_hidden_output else {})
        for t in _scored(results or {})
    ]


def public_output(results: dict | None) -> str:
    """What Otter marks as visible to students: the outcome of the public tests."""
    return "\n\n".join(
        t["output"] for t in (results or {}).get("tests", []) if t.get("visibility") == "visible" and t.get("output")
    )
