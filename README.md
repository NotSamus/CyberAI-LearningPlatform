# cyberAI-Platform

Student coding platform: **FastAPI + uvicorn** backend in `api/` (conda env `CyberP`), **Next.js + TypeScript** frontend,
and **JupyterHub** for per-student notebook environments (CPU and GPU).
Design and server setup: see the "Student Jupyter Platform: Architecture & Setup" doc and `deploy/README.md`.

## Project structure

```
api/app/main.py                FastAPI app
api/app/config.py              settings (env vars, dev defaults)
api/app/db.py                  SQLAlchemy engine, sessions, model Base
api/app/models.py              database tables: users, login sessions, courses, assignments, submissions, announcements
api/app/auth.py                accounts, password hashing, login/logout, changing your password, limit on password guessing
api/app/admin.py               admin-only API behind Settings > Accounts (add, edit, new password, remove)
api/app/manage.py              command line tool: create accounts, grant admin, reset passwords, import a notebook
api/app/assignments.py         assignments: who sees which, who opened what, checks on uploaded notebooks
api/app/courses.py             courses (groups of students) and announcements
api/app/submissions.py         submissions and grades; has the autograder grade them in the background
api/app/grading.py             talks to the grading service; reads Otter-Grader's notebooks and results
api/app/teach.py               teacher-only API behind Settings > Assignments, Courses, Announcements and the gradebook
api/app/jupyter/               OAuth2 provider for JupyterHub, hub REST client, launch and submit API (copies notebooks to and from students)
grader/                        grading service: runs Otter-Grader in throwaway locked-down containers (its own Docker image)
sql/                           Alembic database migrations (see sql/README.md)
test/                          pytest suite: test/api (API, login attacks, assignments, courses, grading), test/sql (migrations)
frontend/                      Next.js + TypeScript app (login, home with assignments by course, notebook page with iframe and Submit, Settings)
assignments/<id>/              example notebooks to import, one of them autograded (see Assignments below)
deploy/                        production stack, hub config, notebook images, scripts
dev.sh                         start everything: Postgres (:5433), JupyterHub (:8081), grader (:8090), backend (:8000), frontend (:3000)
dev-hub.sh                     start/stop only the local JupyterHub in Docker (dev.sh calls it)
```

## Run it locally

```bash
conda activate CyberP
pip install -r api/requirements.txt
(cd frontend && npm install)

./dev.sh          # everything; needs Docker Desktop for Postgres and notebooks. First run builds the notebook image.
```

`dev.sh` starts Postgres, applies the migrations in `sql/`, then starts the rest.
If port 3000 or 8000 is taken by another project, pick others: `FRONTEND_PORT=3001 BACKEND_PORT=8001 ./dev.sh`
(then open http://localhost:3001).
Ctrl+C (or closing the terminal) stops everything, including every student notebook container.
Student files are kept in Docker volumes (`jupyterhub-user-*`) and the database in `cyberai-dev_pg-data`,
so they are there next time.

The dev database is Postgres 16 (the same as production) on `localhost:5433`, not 5432, so it does not
clash with a Postgres installed on the Mac. Connect with
`psql postgresql://platform:dev-db-password@localhost:5433/platform` while `dev.sh` is running.

Open http://localhost:3000, log in, pick an assignment, click **Open Notebook**.
If Docker is not running, nobody can log in (the accounts are in Postgres).

### Letting other devices on your network use it

```bash
./dev.sh --lan          # with other ports:  FRONTEND_PORT=3001 BACKEND_PORT=8001 ./dev.sh --lan
```

It prints the address to open, for example `http://192.168.1.9:3000`: this computer's address on the
Wi-Fi or Ethernet network (`DEV_HOST=<address> ./dev.sh --lan` if it picks the wrong one). Use that
address on this computer too: logging in does not work at `localhost` while in this mode. macOS may ask
once whether to allow incoming connections. A VPN or a network that keeps devices apart (many guest and
campus networks do) can prevent other devices from connecting.

This is for trying the site with people you trust, not for a class:

- It is plain `http`, so passwords and logins cross the network unencrypted and anyone on the same
  network can read them. Use test accounts, not real passwords.
- The site and the notebooks share one address, so a notebook server receives the visitor's platform
  login. Someone with a notebook could use that to act as a teacher who opens their notebook server.
  On the real server the two have separate addresses and HTTPS, which prevents it (`deploy/README.md`).
- The hub's API and the notebooks become reachable from the network, so `--lan` makes new random
  secrets on every start in place of the ones written in this repository.

## Accounts

There is no public sign-up. The first admin is created from the command line, while `dev.sh` is running:

```bash
cd api
python -m app.manage create-user admin --role teacher --admin     # asks for the password twice
```

After that, an admin manages accounts in the site, under **Settings** (top bar) > **Accounts**:

- **Add an account**: the server generates the password and shows it once, for the admin to hand over.
- **Edit**: the name and whether the account may use GPU notebooks. The username and the role are fixed
  (the account's notebook files are stored under a name made from its role and number).
- **New password**, for someone who forgot theirs: again generated and shown once, and the account is
  logged out everywhere.
- **Remove**: deletes the account with its submissions and grades, stops its notebook servers and ends
  its JupyterHub login. The files in its notebook home stay on the server.

Everyone changes their own password under **Settings > My account** (the current password is asked for
again, and every other device is logged out).

Admin accounts are different on purpose: the site cannot give or take admin rights, and cannot set an
admin's password or remove an admin. That needs access to the server itself, with the command line tool:

```bash
python -m app.manage set-admin maria                               # or: set-admin maria --remove
python -m app.manage set-password maria                            # choose a password yourself; also logs that account out everywhere
python -m app.manage create-user maria --name "Maria Lopez"        # same as the form; add --gpu for GPU notebooks
python -m app.manage list-users
```

Roles are `student` and `teacher` (teachers get GPU notebooks and are JupyterHub admins). `--admin` is
separate: it marks who may manage accounts. Usernames are not case sensitive. Passwords are stored only
as Argon2 hashes. A login lasts 7 days. Logging out ends it on the server and also logs the browser out
of JupyterHub.
The same commands run on the server: see `deploy/README.md`.

Who is an admin or a teacher is decided on the server for every request: the browser stores nothing
about it (no password, no role), only a session cookie that page scripts cannot read. Platform admins
and teachers are JupyterHub admins.

## Settings

Everyone has a **Settings** button in the top bar. The menu on the left shows the sections that account has:

| Section | Who | What |
| --- | --- | --- |
| Assignments | teachers, admins | upload notebooks, give them to students, publish; per assignment: progress and grades |
| Courses | teachers, admins | groups of students |
| Announcements | teachers, admins | short messages on students' home page |
| Accounts | admins | add, edit and remove accounts, new passwords |
| JupyterHub | admins | JupyterHub's own admin panel (running notebook servers) |
| My account | everyone | change your password |

The menu only hides links. Each section's data comes from the API, which checks the account on every request.
For now every teacher sees and manages every course and assignment.

## Assignments

Under **Settings > Assignments**, a teacher:

1. Uploads a notebook (`.ipynb`, at most 10 MB) with a title, a description and an optional due date. It is
   stored in Postgres as a **draft** given to nobody.
2. Presses **Edit** and chooses who gets it: the students of a course, all students (including accounts
   added later), or chosen students.
3. Presses **Publish**. Students now see it on their home page. **Unpublish** hides it again.

A student only ever sees, and can only open, published assignments given to them. The server checks this
on every request (`api/app/assignments.py`), so guessing another assignment's address gives "No such assignment."

The first time a student opens an assignment, the backend puts their own copy of the notebook in their
Jupyter home at `assignments/<folder>/<file>.ipynb`, through that student's running notebook server.
It is never overwritten after that: the file is the student's work. Deleting an assignment removes it
(with its submissions and grades) from the platform, not from the homes of students who already opened it.

The home page shows each student their assignments by course, each with its status: Not started, Opened,
Overdue, Submitted, Grading or the score.

### Submitting and grading

A student presses **Submit** (on the assignment's page or above the notebook). The backend takes the
notebook as it is saved in their Jupyter home at that moment and stores it. JupyterLab saves every 30
seconds here, and the Submit button reminds the student to save first. Submitting again replaces the
earlier submission and its grade. A submission after the due date is accepted and marked late.

There are two kinds of assignment, decided by the notebook that was uploaded:

- **Autograded**: the notebook is written in [Otter-Grader](https://otter-grader.readthedocs.io)'s
  Otter Assign format: questions with their solutions and tests, some of them hidden.
  `assignments/otter-example/functions.ipynb` is a small example to start from. On upload, Otter makes
  the version students get (no solutions, public tests only) and checks that your own solutions pass
  your tests; a notebook that fails that is refused with Otter's report. Each submission is graded
  within seconds to minutes. Students see their score per question and what the public tests reported,
  never the hidden tests.
- **Graded by hand**: any other notebook. Submissions wait for the teacher.

**Progress and grades** (a link on each assignment) is the gradebook: every student the assignment is
given to, when they opened and submitted it, and their score. From there a teacher can open a
submission in their own notebook environment (a copy; the student's files are not touched), download
it, give or change the score, write a comment for the student, run the autograder again, and download
the table as CSV.

Read an opened submission, do not run it: it is a student's code, and in the teacher's environment it
would run with network access and with the teacher's files (other students' submissions among them) in
reach. The autograder is the safe place where submissions are run.

Student code never runs in the backend. The grading service (`grader/`) starts a new container of the
student notebook image for every job, with no network, 2 GB of memory, one CPU, a limit on processes
and five minutes, and removes it afterwards. It is the only service besides the hub with the Docker
socket, and it has no database access. GPU assignments are graded in the GPU image without a GPU.

### Courses and announcements

A course (**Settings > Courses**) is a named group of students. An assignment or announcement given to a
course reaches its students, including students added to the course later. Deleting a course keeps its
assignments, given to nobody until a teacher gives them out again.

**Settings > Announcements** posts a short message to everyone or to one course. Students see the five
newest ones meant for them at the top of their home page.

### From the command line

The example notebooks in `assignments/` can be added from the command line instead of the page:

```bash
cd api
python -m app.manage import-assignment ../assignments/python-basics/lab1.ipynb --title "Python basics" --publish
python -m app.manage import-assignment ../assignments/hello-gpu/lab1.ipynb --title "Hello GPU" --gpu --publish
python -m app.manage import-assignment ../assignments/otter-example/functions.ipynb --title "Functions lab"   # autograded
```

`--publish` gives it to every student at once; without it the notebook is a draft.

## Security checks

Uploads are checked on the server: the file must be a real notebook (validated with `nbformat`) and its
name is reduced to a plain file name. Requests are limited to 1 MB, except a teacher's notebook upload
(11 MB), which is only read after the account has been checked (`LimitRequestSize` in `api/app/main.py`).

After 5 wrong passwords for one username from one network address, further logins for that username from
that address are refused for 15 minutes (`MAX_LOGIN_ATTEMPTS` in `api/app/auth.py`). `test/api/test_security.py`
attacks the login and the admin API: password guessing (also of the current password when changing it),
SQL injection, forged and planted cookies, oversized input, requests sent from other websites, and a
student asking for admin data or trying to create, change or remove accounts. `test_assignments.py`,
`test_courses.py` and `test_grading.py` do the same for the teacher API: students trying to upload,
grade themselves, read other students' submissions or see hidden tests.

Current limits: an assignment is one notebook file (no extra data files) and its file cannot be replaced
after upload. Every teacher manages every course and assignment. Only the newest submission of a student
is kept. Locally the "GPU" profile is simulated: same
checks, no GPU attached, and it uses the CPU image, so `import torch` fails unless you pass
`GPU_IMAGE=... ./dev-hub.sh`.

## Tests

```bash
pip install pytest && pytest test     # from the project root: API + migrations (needs dev.sh running for Postgres)
                                      # the hub and the grader are replaced by stand-ins: Docker is not needed for these
(cd frontend && npm test)             # TypeScript typecheck + production build
```

When you are running the thing make sure to investigate the following:
- a way to connect a sql base on to this project with all of the migrations. 
- Also make sure to connect jupyter notebook per user in this instance of code.
