"""Glue between platform accounts (app/auth.py) and the Jupyter integration.

Everything else in this package only depends on the PlatformUser shape below.
"""
from dataclasses import dataclass, field

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app import auth
from app.db import get_db
from app.models import User


@dataclass
class PlatformUser:
    id: int
    username: str
    display_name: str
    role: str                              # "student" | "teacher"
    is_admin: bool = False                 # may manage accounts on the platform
    gpu_enabled: bool = False              # set by a teacher / by enrolment in a GPU course
    theme: str = "standard"                # how the site looks for them (app.models.THEMES)
    extra_groups: list[str] = field(default_factory=list)

    @classmethod
    def from_db(cls, user: User) -> "PlatformUser":
        return cls(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            role=user.role,
            is_admin=user.is_admin,
            gpu_enabled=user.gpu_enabled,
            theme=user.theme,
        )

    @property
    def can_teach(self) -> bool:
        """May upload assignments and give them to students (app/teach.py), and sees every assignment."""
        return self.role == "teacher" or self.is_admin

    @property
    def hub_username(self) -> str:
        # Stable, lowercase, safe in Docker container and volume names. Never use emails.
        return f"{'t' if self.role == 'teacher' else 's'}-{self.id}"

    @property
    def hub_groups(self) -> list[str]:
        groups = ["teachers" if self.role == "teacher" else "students", *self.extra_groups]
        if self.gpu_enabled or self.role == "teacher":
            groups.append("gpu")
        return groups


def get_current_user_optional(request: Request, db: Session = Depends(get_db)) -> PlatformUser | None:
    """The user whose session cookie came with this request, or None when not logged in."""
    token = request.cookies.get(auth.COOKIE_NAME)
    user = auth.user_for_session(db, token) if token else None
    return PlatformUser.from_db(user) if user else None
