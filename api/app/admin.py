"""Admin-only API, used by the Accounts section of the Settings page.

Every route checks the account's admin flag here, on the server, for each request. What the
frontend shows or hides is only a convenience and is never what protects this data.
"""
import secrets

import httpx
from fastapi import APIRouter, Depends, HTTPException
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
    admin to hand over; only its hash is stored. Admin rights are not given here: that stays with the
    command line tool (app/manage.py), which needs access to the server itself."""
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


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: int, admin: PlatformUser = Depends(require_admin), db: Session = Depends(get_db)):
    """For someone who forgot their password: a new one is generated and returned once, and the
    account is logged out everywhere. Not for admin accounts: their passwords are only set on the
    server itself (app/manage.py), so that one admin's browser cannot take over another admin."""
    user = _user_or_404(db, user_id)
    if user.is_admin:
        raise HTTPException(403, "An admin's password is set on the server: python -m app.manage set-password " + user.username)
    password = _new_password()
    auth.set_password(db, user, password)
    return {**_account(user), "password": password}


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
        raise HTTPException(403, "Take away its admin rights on the server first: python -m app.manage set-admin " + user.username + " --remove")
    try:
        await hub_client.delete_user(PlatformUser.from_db(user).hub_username)
    except httpx.HTTPError:
        raise HTTPException(503, "The notebook service is not reachable right now, so the account was not removed. Try again in a minute.")

    def remove():
        db.delete(user)
        db.commit()

    await run_in_threadpool(remove)
    return {"deleted": True}
