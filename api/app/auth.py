"""Accounts and login: password hashing, account creation and login sessions stored in the database.

Routes:
    POST /api/auth/login      {username, password} -> sets the session cookie
    POST /api/auth/logout     ends this browser's session
    POST /api/auth/password   {current_password, new_password} -> a logged-in person changes their own password
There is no public sign-up: accounts are created by an admin (app/admin.py) or with the command
line tool in app/manage.py.

Password guessing is limited per (client address, username): see `_register_attempt`. The counters
live in memory, which is fine for one uvicorn worker (same constraint as app/jupyter/oauth.py).
"""
import hashlib
import math
import re
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import config
from app.db import get_db
from app.models import ROLES, THEMES, LoginSession, User

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Over HTTPS (production) the cookie has the "__Host-" prefix: browsers then only accept it from
# this exact host over HTTPS, so a page on a sibling address (the hub, where student code runs)
# cannot plant or overwrite it. Plain http (local development) cannot use the prefix.
COOKIE_NAME = "__Host-cyberai_session" if config.HTTPS else "cyberai_session"
SESSION_TTL = timedelta(days=7)
USERNAME_RE = re.compile(r"[a-z0-9][a-z0-9._-]{2,31}")
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 256                   # hashing a huge "password" would tie up the server

MAX_LOGIN_ATTEMPTS = 5                      # failed logins for one username from one address...
LOGIN_ATTEMPT_WINDOW = 15 * 60              # ...within this many seconds, before further ones are refused

_hasher = PasswordHasher()                  # argon2id with the library's recommended parameters
_DUMMY_HASH = _hasher.hash("unused")        # so a login for an unknown username takes as long as a real one


class AccountError(ValueError):
    """A username or password that cannot be used. The message is safe to show to the person."""


def normalize_username(username: str) -> str:
    return username.strip().lower()


def check_password(password: str) -> None:
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise AccountError(f"Passwords are {MIN_PASSWORD_LENGTH} to {MAX_PASSWORD_LENGTH} characters.")


def check_new_username(db: Session, username: str) -> str:
    """Returns the username as it will be stored."""
    username = normalize_username(username)
    if not USERNAME_RE.fullmatch(username):
        raise AccountError(
            "Usernames are 3 to 32 characters: lowercase letters, digits, '.', '_' or '-', "
            "starting with a letter or digit."
        )
    if db.scalar(select(User.id).where(User.username == username)) is not None:
        raise AccountError(f"The username '{username}' is already taken.")
    return username


def create_user(
    db: Session,
    username: str,
    password: str,
    *,
    display_name: str | None = None,
    role: str = "student",
    is_admin: bool = False,
    gpu_enabled: bool = False,
) -> User:
    username = check_new_username(db, username)
    if role not in ROLES:
        raise AccountError(f"The role must be one of: {', '.join(ROLES)}.")
    check_password(password)
    user = User(
        username=username,
        password_hash=_hasher.hash(password),
        display_name=(display_name or "").strip() or username,
        role=role,
        is_admin=is_admin,
        gpu_enabled=gpu_enabled,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:                  # the same username was created a moment ago by someone else
        db.rollback()
        raise AccountError(f"The username '{username}' is already taken.")
    return user


def set_password(db: Session, user: User, password: str) -> None:
    check_password(password)
    user.password_hash = _hasher.hash(password)
    db.execute(delete(LoginSession).where(LoginSession.user_id == user.id))   # log out everywhere
    db.commit()


def authenticate(db: Session, username: str, password: str) -> User | None:
    if len(password) > MAX_PASSWORD_LENGTH:
        return None
    username = normalize_username(username)
    # A name that could never be an account (odd characters, a megabyte long) is not sent to the database.
    user = db.scalar(select(User).where(User.username == username)) if USERNAME_RE.fullmatch(username) else None
    try:
        _hasher.verify(user.password_hash if user else _DUMMY_HASH, password)
    except (VerificationError, InvalidHashError):
        return None
    if user is None:
        return None
    if _hasher.check_needs_rehash(user.password_hash):     # hashing parameters were raised since
        user.password_hash = _hasher.hash(password)
        db.commit()
    return user


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def start_session(db: Session, user: User) -> str:
    """Returns the token for the cookie. The database only keeps its hash."""
    now = datetime.now(timezone.utc)
    db.execute(delete(LoginSession).where(LoginSession.expires_at < now))    # tidy up expired ones
    token = secrets.token_urlsafe(32)
    db.add(LoginSession(token_hash=_token_hash(token), user_id=user.id, expires_at=now + SESSION_TTL))
    db.commit()
    return token


def user_for_session(db: Session, token: str) -> User | None:
    return db.scalar(
        select(User)
        .join(LoginSession, LoginSession.user_id == User.id)
        .where(LoginSession.token_hash == _token_hash(token), LoginSession.expires_at > datetime.now(timezone.utc))
    )


def end_session(db: Session, token: str) -> None:
    db.execute(delete(LoginSession).where(LoginSession.token_hash == _token_hash(token)))
    db.commit()


_attempts: dict[tuple[str, str], list[float]] = {}     # (client address, username) -> times of recent attempts
_attempts_lock = threading.Lock()


def _register_attempt(key: tuple[str, str]) -> None:
    """Counts a login attempt, or refuses it (429) after too many recent ones for this key.

    The attempt is counted before the password is checked, so parallel guesses cannot slip past the
    limit; a successful login clears the count. Unknown usernames are counted exactly like real ones,
    so the limit does not reveal which usernames exist.
    """
    now = time.monotonic()
    with _attempts_lock:
        if len(_attempts) > 10_000:             # keep memory bounded under a flood of made-up usernames
            for k in [k for k, times in _attempts.items() if now - times[-1] >= LOGIN_ATTEMPT_WINDOW]:
                del _attempts[k]
        recent = [t for t in _attempts.get(key, []) if now - t < LOGIN_ATTEMPT_WINDOW]
        if len(recent) >= MAX_LOGIN_ATTEMPTS:
            minutes = math.ceil((LOGIN_ATTEMPT_WINDOW - (now - recent[0])) / 60)
            raise HTTPException(429, f"Too many failed login attempts. Try again in {minutes} minutes.")
        _attempts[key] = [*recent, now]


class LoginRequest(BaseModel):
    username: str
    password: str


def _cookie_options() -> dict:
    return {"path": "/", "httponly": True, "samesite": "lax", "secure": config.HTTPS}


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    attempt = (request.client.host if request.client else "", normalize_username(body.username)[:64])
    _register_attempt(attempt)
    user = authenticate(db, body.username, body.password)
    if user is None:
        raise HTTPException(401, "Wrong username or password.")
    with _attempts_lock:
        _attempts.pop(attempt, None)
    previous = request.cookies.get(COOKIE_NAME)
    if previous:
        end_session(db, previous)       # logging in over another login: that one is finished, not left behind
    token = start_session(db, user)
    response.set_cookie(COOKIE_NAME, token, max_age=int(SESSION_TTL.total_seconds()), **_cookie_options())
    return {"username": user.username}


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        end_session(db, token)
    response.delete_cookie(COOKIE_NAME, **_cookie_options())
    return {"logged_out": True}


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


@router.post("/password")
def change_password(body: PasswordChange, request: Request, response: Response, db: Session = Depends(get_db)):
    """A logged-in person sets a new password for their own account. The current password is asked
    for again, so that someone who finds a logged-in browser cannot take the account over, and
    guesses at it are limited like logins are. Every session of the account ends, on all devices;
    this browser gets a new one."""
    token = request.cookies.get(COOKIE_NAME)
    user = user_for_session(db, token) if token else None
    if user is None:
        raise HTTPException(401, "not logged in")
    attempt = (request.client.host if request.client else "", f"password-change:{user.username}")
    _register_attempt(attempt)
    if authenticate(db, user.username, body.current_password) is None:
        raise HTTPException(400, "The current password is wrong.")
    with _attempts_lock:
        _attempts.pop(attempt, None)
    try:
        set_password(db, user, body.new_password)
    except AccountError as e:
        raise HTTPException(400, str(e))
    response.set_cookie(COOKIE_NAME, start_session(db, user), max_age=int(SESSION_TTL.total_seconds()), **_cookie_options())
    return {"changed": True}


class ThemeChoice(BaseModel):
    theme: str


@router.put("/theme")
def choose_theme(body: ThemeChoice, request: Request, db: Session = Depends(get_db)):
    """A logged-in person chooses how the site looks for their own account (My account >
    Appearance). Only the names in THEMES are taken."""
    token = request.cookies.get(COOKIE_NAME)
    user = user_for_session(db, token) if token else None
    if user is None:
        raise HTTPException(401, "not logged in")
    if body.theme not in THEMES:
        raise HTTPException(400, "There is no such theme.")
    user.theme = body.theme
    db.commit()
    return {"theme": user.theme}
