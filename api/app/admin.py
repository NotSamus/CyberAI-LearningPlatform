"""Admin-only API, used by the Accounts section of the Settings page.

Every route checks the account's admin flag here, on the server, for each request. What the
frontend shows or hides is only a convenience and is never what protects this data.
"""
import logging
import secrets

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import auth
from app.db import get_db
from app.jupyter import hub_client
from app.jupyter.deps import PlatformUser, get_current_user_optional
from app.models import User

router = APIRouter(prefix="/api/admin", tags=["admin"])
log = logging.getLogger(__name__)


def require_admin(user: PlatformUser | None = Depends(get_current_user_optional)) -> PlatformUser:
    if user is None:
        raise HTTPException(401, "not logged in")
    if not user.is_admin:
        raise HTTPException(403, "This page is for admins only.")
    return user


def _new_password() -> str:
    return secrets.token_urlsafe(9)             # 12 characters, 72 bits


def _user_or_404(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "No such account.")
    return user


def _account(user: User) -> dict:
    # Built field by field: the password hash must never leave the server.
    return {
        "id": user.id,
        "username": user.username,
        "name": user.display_name,
        "role": user.role,
        "is_admin": user.is_admin,
        "gpu_enabled": user.gpu_enabled,
        "hub_username": PlatformUser.from_db(user).hub_username,    # the name JupyterHub shows
        "created_at": user.created_at.isoformat(),
    }


@router.get("/users")
def list_users(admin: PlatformUser = Depends(require_admin), db: Session = Depends(get_db)):
    return [_account(user) for user in db.scalars(select(User).order_by(User.username))]


class NewAccount(BaseModel):
    username: str = Field(max_length=64)
    name: str = Field("", max_length=100)
    role: str = "student"
    gpu_enabled: bool = False


@router.post("/users", status_code=201)
def create_user(body: NewAccount, admin: PlatformUser = Depends(require_admin), db: Session = Depends(get_db)):
    """Creates a student or teacher account. The password is generated here and returned once, for the
    admin to hand over; only its hash is stored. Admin rights are not given here: a teacher gets them
    afterwards, from `set_admin` below."""
    password = _new_password()
    try:
        user = auth.create_user(
            db, body.username, password, display_name=body.name, role=body.role, gpu_enabled=body.gpu_enabled,
        )
    except auth.AccountError as e:
        raise HTTPException(400, str(e))
    return {**_account(user), "password": password}


class AccountChanges(BaseModel):
    """Only the fields that are sent are changed. The username and the role stay as they are: the
    account's notebook files are stored under a name made from its role and number."""
    name: str | None = Field(None, min_length=1, max_length=100)
    gpu_enabled: bool | None = None


@router.patch("/users/{user_id}")
def change_user(user_id: int, body: AccountChanges, admin: PlatformUser = Depends(require_admin), db: Session = Depends(get_db)):
    user = _user_or_404(db, user_id)
    if body.name is not None:
        user.display_name = body.name.strip() or user.username
    if body.gpu_enabled is not None:
        user.gpu_enabled = body.gpu_enabled
    db.commit()
    return _account(user)


class PasswordReset(BaseModel):
    your_password: str = ""     # the acting admin's own password: asked for when the account is another admin's


@router.post("/users/{user_id}/reset-password")
async def reset_password(
    user_id: int, request: Request, body: PasswordReset | None = None,
    admin: PlatformUser = Depends(require_admin), db: Session = Depends(get_db),
):
    """For someone who forgot their password: a new one is generated and returned once, and the
    account is logged out everywhere: its platform sessions, and its notebook servers and hub login
    (its files stay; the hub account is made again when a notebook is next opened). Another admin's
    account too, but only once the acting admin has typed their own password again, so that a browser
    left logged in (or a login taken from it) cannot lock every other admin out; that reset is logged.
    Your own password is changed under My account, which asks for the current one, or on the server
    (app/manage.py)."""
    user = await run_in_threadpool(_user_or_404, db, user_id)
    if user.id == admin.id:
        raise HTTPException(403, "Change your own password under My account.")
    password = _new_password()

    def reset() -> dict:
        if user.is_admin:
            auth.confirm_password(
                db, request, admin.username, body.your_password if body else "", auth.REAUTH,
                "Your password is wrong, so the admin's password was not changed.",
            )
        auth.set_password(db, user, password)
        if user.is_admin:
            log.warning("Admin %s gave the admin %s a new password", admin.username, user.username)
        return {**_account(user), "password": password}

    answer = await run_in_threadpool(reset)
    # A notebook someone else had open on this account ends too. If the hub cannot be reached the
    # password is still the new one (getting back into a locked-out account must not wait for it).
    try:
        await hub_client.delete_user(answer["hub_username"])
    except httpx.HTTPError:
        answer["notice"] = ("The notebook service could not be reached, so a notebook that is open on this account "
                            "stays open until it is stopped in the JupyterHub section.")
    return answer


@router.delete("/users/{user_id}")
async def delete_user(user_id: int, admin: PlatformUser = Depends(require_admin), db: Session = Depends(get_db)):
    """Removes an account: its logins, course memberships and submissions go with it. Its notebook
    servers are stopped and its hub login ended first; if the hub cannot be reached nothing is
    removed, because the person could otherwise keep using a notebook that is still running.
    The files in their notebook home stay on the server (deploy/scripts/reset-student.sh archives them)."""
    user = await run_in_threadpool(_user_or_404, db, user_id)
    if user.id == admin.id:
        raise HTTPException(403, "You cannot remove your own account.")
    if user.is_admin:
        raise HTTPException(403, "Take away its admin rights first (Remove admin rights, in the same menu).")
    try:
        await hub_client.delete_user(PlatformUser.from_db(user).hub_username)
    except httpx.HTTPError:
        raise HTTPException(503, "The notebook service is not reachable right now, so the account was not removed. Try again in a minute.")

    def remove():
        db.delete(user)
        db.commit()

    await run_in_threadpool(remove)
    return {"deleted": True}


class AdminRights(BaseModel):
    admin: bool                 # true gives admin rights, false takes them away
    your_password: str = ""     # the acting admin's own password, typed again


@router.put("/users/{user_id}/admin")
def set_admin(
    user_id: int, body: AdminRights, request: Request,
    admin: PlatformUser = Depends(require_admin), db: Session = Depends(get_db),
):
    """Gives a teacher admin rights, so they can manage accounts too, or takes them away from another
    admin. The acting admin types their own password again first, so that a browser left logged in
    (or a login taken from it) cannot hand out admin rights or take them from everyone else. Students
    are never made admins, and nobody takes away their own rights, so an admin is always left. The
    command line (python -m app.manage set-admin) does the same on the server itself."""
    user = _user_or_404(db, user_id)
    if body.admin and user.role != "teacher":
        raise HTTPException(400, "Only a teacher can be made an admin.")
    if not body.admin and user.id == admin.id:
        raise HTTPException(403, "You cannot take away your own admin rights.")
    auth.confirm_password(
        db, request, admin.username, body.your_password, auth.REAUTH,
        "Your password is wrong, so the admin rights were not changed.",
    )
    if not body.admin:
        # The admins' rows are locked until this is saved, so two admins taking each other's rights at
        # the same moment cannot leave the site with none: the second waits, then is no admin any more.
        admins = db.scalars(select(User.id).where(User.is_admin).with_for_update()).all()
        if admin.id not in admins:
            raise HTTPException(403, "This page is for admins only.")
    user.is_admin = body.admin
    db.commit()
    log.warning("Admin %s %s %s", admin.username, "made an admin:" if body.admin else "took admin rights from", user.username)
    return _account(user)
