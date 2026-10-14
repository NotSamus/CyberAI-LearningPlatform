"""Platform API used by the Next.js frontend: who am I, my assignments (with my progress on each)
and announcements, open and stop a notebook, submit it."""
from contextlib import contextmanager
from urllib.parse import quote

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from .. import assignments, config, courses, submissions
from ..db import get_db
from ..models import Assignment
from . import hub_client
from .deps import PlatformUser, get_current_user_optional

router = APIRouter(prefix="/api", tags=["notebooks"])


async def require_user(user: PlatformUser | None = Depends(get_current_user_optional)) -> PlatformUser:
    if user is None:
        raise HTTPException(401, "not logged in")
    return user


def visible_assignment(
    assignment_id: int, user: PlatformUser = Depends(require_user), db: Session = Depends(get_db),
) -> Assignment:
    """The assignment, if this user may see it. A student asking for one that is a draft, or was not
    given to them, gets the same 404 as for one that does not exist."""
    assignment = assignments.get_visible(db, user, assignment_id)
    if assignment is None:
        raise HTTPException(404, "No such assignment.")
    return assignment


def _server_for(assignment: Assignment) -> str:
    return "gpu" if assignment.requires_gpu else "cpu"


@router.get("/me")
async def me(user: PlatformUser = Depends(require_user)):
    return {
        "id": user.id,
        "username": user.username,
        "name": user.display_name,
        "role": user.role,
        "is_admin": user.is_admin,
        "can_teach": user.can_teach,
        "gpu_enabled": "gpu" in user.hub_groups,
        "theme": user.theme,
    }


def _iso(moment) -> str | None:
    return moment.isoformat() if moment else None


@router.get("/assignments")
def list_assignments(user: PlatformUser = Depends(require_user), db: Session = Depends(get_db)):
    """The assignments this person may see, each with their own progress on it."""
    course_names = courses.names(db)
    opened = assignments.opened_by(db, user.id)
    submitted = submissions.of_user(db, user.id)
    return [
        {
            **assignments.summary(a, course_names),
            "opened_at": _iso(opened.get(a.id)),
            "submission": submissions.summary(submitted[a.id]) if a.id in submitted else None,
        }
        for a in assignments.list_visible(db, user)
    ]


def _with_progress(db: Session, assignment: Assignment, user: PlatformUser) -> dict:
    submission = submissions.get(db, assignment.id, user.id)
    return {
        **assignments.summary(assignment, courses.names(db)),
        "opened_at": _iso(assignments.opened_by(db, user.id).get(assignment.id)),
        "submission": submissions.details(submission, for_teacher=False) if submission else None,
    }


@router.get("/assignments/{assignment_id}")
def get_assignment(
    assignment: Assignment = Depends(visible_assignment),
    user: PlatformUser = Depends(require_user),
    db: Session = Depends(get_db),
):
    return _with_progress(db, assignment, user)


@router.get("/announcements")
def list_announcements(user: PlatformUser = Depends(require_user), db: Session = Depends(get_db)):
    course_names = courses.names(db)
    return [courses.announcement(item, course_names) for item in courses.announcements_for(db, user)]


@contextmanager
def hub_errors():
    """Turns what can go wrong while talking to the hub into an answer the person can read."""
    try:
        yield
    except hub_client.HubError as e:
        # e.g. "All GPU slots are in use" from the hub's pre_spawn_hook; shown to the student as-is
        raise HTTPException(503 if e.status >= 500 else e.status, e.detail)
    except httpx.HTTPStatusError as e:
        # The hub answered but refused (config or permissions problem): don't call that "unreachable"
        raise HTTPException(502, f"The notebook service returned an error ({e.response.status_code}).")
    except httpx.HTTPError:
        raise HTTPException(503, "The notebook service is not reachable right now. Try again in a minute.")


async def running_server(user: PlatformUser, server: str) -> None:
    """Makes sure this person's notebook server ("cpu" or "gpu") is running. Use inside hub_errors()."""
    if server == "gpu" and "gpu" not in user.hub_groups:
        raise HTTPException(403, "GPU access is not enabled for your account.")
    await hub_client.ensure_user(user.hub_username, user.hub_groups)
    if not await hub_client.start_server(user.hub_username, server):
        raise HTTPException(503, "Your environment is still starting. Try again in a moment.")


def notebook_url(user: PlatformUser, server: str, path: str) -> str:
    # First load walks: hub login -> /oauth/authorize -> back to the notebook
    return f"{config.HUB_ORIGIN}/user/{user.hub_username}/{server}/lab/tree/{quote(path)}"


def _path(assignment: Assignment) -> str:
    """Where a person's copy of the assignment's notebook is, in their Jupyter home."""
    return f"assignments/{assignment.slug}/{assignment.notebook_name}"


@router.post("/assignments/{assignment_id}/launch")
async def launch(
    assignment: Assignment = Depends(visible_assignment),
    user: PlatformUser = Depends(require_user),
    db: Session = Depends(get_db),
):
    server, path = _server_for(assignment), _path(assignment)
    with hub_errors():
        await running_server(user, server)
        # The student's own copy, made the first time they open the assignment. Never overwritten:
        # from then on the file in their home is their work.
        if not await hub_client.has_file(user.hub_username, server, path):
            notebook = await run_in_threadpool(assignments.notebook_bytes, db, assignment.id)
            await hub_client.put_file(user.hub_username, server, path, notebook)
    await run_in_threadpool(assignments.record_open, db, assignment.id, user.id)
    return {"ready": True, "profile": server, "url": notebook_url(user, server, path)}


@router.post("/assignments/{assignment_id}/submit")
async def submit(
    background: BackgroundTasks,
    assignment: Assignment = Depends(visible_assignment),
    user: PlatformUser = Depends(require_user),
    db: Session = Depends(get_db),
):
    """Hands in the person's notebook as it is saved in their Jupyter home right now. Submitting
    again replaces the earlier submission. Autograded assignments are graded in the background:
    the status goes from "queued" to "graded" (GET /api/assignments/{id} shows it)."""
    if not assignment.published:
        raise HTTPException(400, "This assignment is a draft. Publish it before submitting to it.")
    server = _server_for(assignment)
    megabytes = assignments.MAX_SUBMISSION_BYTES // (1024 * 1024)
    too_large = f"Your notebook is larger than {megabytes} MB. Clear its outputs (Edit > Clear Outputs of All Cells), save it, and submit again."
    with hub_errors():
        await running_server(user, server)
        try:
            notebook = await hub_client.get_file(user.hub_username, server, _path(assignment), assignments.MAX_SUBMISSION_BYTES)
        except hub_client.FileTooLarge:
            raise HTTPException(400, too_large)
    if notebook is None:
        raise HTTPException(400, "There is nothing to submit yet: open the notebook first.")
    try:
        assignments.check_notebook(notebook, assignments.MAX_SUBMISSION_BYTES)
    except assignments.AssignmentError:
        raise HTTPException(400, "Your notebook file could not be read as a notebook. Open it, save it, and submit again.")

    submission = await run_in_threadpool(submissions.record, db, assignment, user.id, notebook)
    if submission.status == "queued":
        background.add_task(submissions.grade_submission, submission.id, submission.attempt)
    return submissions.details(submission, for_teacher=False)


@router.post("/assignments/{assignment_id}/stop")
async def stop(assignment: Assignment = Depends(visible_assignment), user: PlatformUser = Depends(require_user)):
    try:
        await hub_client.stop_server(user.hub_username, _server_for(assignment))
    except httpx.HTTPError:
        raise HTTPException(503, "The notebook service is not reachable right now.")
    return {"stopped": True}
