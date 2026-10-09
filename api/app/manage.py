"""Accounts and assignments from the command line. Run from api/ (production: `docker compose exec backend ...`).

    python -m app.manage create-user USERNAME [--name "Full Name"] [--role student|teacher] [--admin] [--gpu]
    python -m app.manage set-admin USERNAME [--remove]
    python -m app.manage set-password USERNAME
    python -m app.manage list-users
    python -m app.manage import-assignment FILE.ipynb --title "Title" [--description "..."] [--gpu] [--publish]

`import-assignment` does what the upload in Settings > Assignments does, for a notebook file on this
machine (an Otter Assign notebook becomes an autograded assignment; the grading service must be
running); with --publish every student gets it straight away.

Passwords are asked for twice at the prompt. When standard input is not a terminal (scripts, tests),
its first line is the password.
"""
import argparse
import asyncio
import getpass
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import assignments, auth, grading
from app.db import SessionLocal
from app.models import ROLES, User


def read_password() -> str:
    if not sys.stdin.isatty():
        return sys.stdin.readline().rstrip("\n")
    password = getpass.getpass("Password: ")
    if getpass.getpass("Repeat the password: ") != password:
        sys.exit("The passwords do not match.")
    return password


def find_user(db: Session, username: str) -> User:
    user = db.scalar(select(User).where(User.username == auth.normalize_username(username)))
    if user is None:
        sys.exit(f"There is no account named '{username}'.")
    return user


def describe(user: User) -> str:
    flags = [user.role] + (["admin"] if user.is_admin else []) + (["gpu"] if user.gpu_enabled else [])
    return f"{user.username} (id {user.id}; {', '.join(flags)})"


def run(args: argparse.Namespace, db: Session) -> None:
    if args.command == "create-user":
        auth.check_new_username(db, args.username)          # before asking for a password
        user = auth.create_user(
            db, args.username, read_password(),
            display_name=args.name, role=args.role, is_admin=args.admin, gpu_enabled=args.gpu,
        )
        print(f"Created {describe(user)}")
    elif args.command == "set-admin":
        user = find_user(db, args.username)
        user.is_admin = not args.remove
        db.commit()
        print(f"Updated {describe(user)}")
    elif args.command == "set-password":
        user = find_user(db, args.username)
        auth.set_password(db, user, read_password())
        print(f"New password set for {user.username}. Their other sessions were logged out.")
    elif args.command == "list-users":
        for user in db.scalars(select(User).order_by(User.id)):
            print(describe(user))
    elif args.command == "import-assignment":
        try:
            notebook = Path(args.file).read_bytes()
        except OSError as e:
            sys.exit(f"Cannot read {args.file}: {e.strerror}.")
        name = assignments.safe_notebook_name(Path(args.file).name)
        assignments.check_notebook(notebook)
        autograding = {}
        if grading.is_otter_master(notebook):       # as the upload in the site does: Otter makes the students' version
            student, autograder = asyncio.run(grading.prepare(notebook, name, args.gpu))
            autograding = dict(master=notebook, autograder=autograder, points=grading.total_points(student))
            notebook = student
        assignment = assignments.create(
            db, title=args.title, description=args.description, requires_gpu=args.gpu,
            filename=name, notebook=notebook, published=args.publish, for_everyone=args.publish, **autograding,
        )
        state = "published to every student" if assignment.published else "a draft: publish it in Settings > Assignments"
        kind = "autograded" if assignment.autograded else "graded by hand"
        print(f"Imported '{assignment.title}' (id {assignment.id}; {kind}; {state})")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.manage", description="Manage platform accounts and assignments.")
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser("create-user", help="create an account (asks for its password)")
    create.add_argument("username")
    create.add_argument("--name", help="display name (default: the username)")
    create.add_argument("--role", choices=ROLES, default="student")
    create.add_argument("--admin", action="store_true", help="may manage accounts")
    create.add_argument("--gpu", action="store_true", help="may use GPU notebooks (teachers always may)")

    admin = commands.add_parser("set-admin", help="give an existing account admin rights")
    admin.add_argument("username")
    admin.add_argument("--remove", action="store_true", help="take admin rights away instead")

    password = commands.add_parser("set-password", help="set a new password (logs the account out everywhere)")
    password.add_argument("username")

    commands.add_parser("list-users", help="show every account")

    imported = commands.add_parser("import-assignment", help="add a notebook file as an assignment")
    imported.add_argument("file", help="path to the .ipynb file")
    imported.add_argument("--title", required=True)
    imported.add_argument("--description", default="")
    imported.add_argument("--gpu", action="store_true", help="opens in the GPU environment")
    imported.add_argument("--publish", action="store_true", help="give it to every student now (default: a draft)")

    args = parser.parse_args(argv)
    try:
        with SessionLocal() as db:
            run(args, db)
    except (auth.AccountError, assignments.AssignmentError) as e:
        sys.exit(str(e))
    except grading.GradingError as e:
        sys.exit(f"Otter could not prepare this notebook. {e}")
    except OperationalError:
        sys.exit("Cannot reach the database. Is it running? (./dev.sh starts it locally.)")


if __name__ == "__main__":
    main()
