# cyberAI-Platform

Student coding platform: **FastAPI + uvicorn** backend in `api/` (conda env `CyberP`), **Next.js + TypeScript** frontend,
and **JupyterHub** for per-student notebook environments (CPU and GPU; GPU notebooks are turned off
for now, see "GPU notebooks: turned off for now" below).
Design and server setup: see the "Student Jupyter Platform: Architecture & Setup" doc and `deploy/README.md`.

## Project structure

```
api/app/main.py                FastAPI app
api/app/config.py              settings (env vars, dev defaults)
api/app/db.py                  SQLAlchemy engine, sessions, model Base
api/app/models.py              database tables: users, login sessions, courses, assignments, submissions, announcements, lessons
api/app/auth.py                accounts, password hashing, login/logout, changing your password, limit on password guessing
api/app/admin.py               admin-only API behind Admin > Accounts (add, edit, new password, admin rights, remove)
api/app/manage.py              command line tool: create accounts, grant admin, reset passwords, import a notebook
api/app/assignments.py         assignments: who sees which, who opened what, checks on uploaded notebooks and their data files
api/app/courses.py             courses (groups of students) and announcements
api/app/submissions.py         submissions and grades; has the autograder grade them in the background
api/app/grading.py             talks to the grading service; reads Otter-Grader's notebooks and results
api/app/teach.py               teacher-only API behind Teach: assignments, courses, announcements, the gradebook
api/app/lessons.py             lessons: their blocks, who sees which, knowledge checks (checked on the server), pictures
api/app/lesson_routes.py       lessons over HTTP: the teacher API behind Teach > Lessons, and reading and answering for everyone
api/app/lesson_zip.py          lessons as a .zip with their pictures and linked notebooks: export, and import here or on another platform
api/app/exports.py             students' progress and grades as CSV or Excel, for one course or every student (teachers only)
api/app/jupyter/               OAuth2 provider for JupyterHub, hub REST client, launch and submit API (copies notebooks to and from students)
grader/                        grading service: runs Otter-Grader in throwaway locked-down containers (its own Docker image)
sql/                           Alembic database migrations (see sql/README.md)
test/                          pytest suite: test/api (API, login attacks, assignments, data files, courses, grading, lessons, lesson .zip files, exports), test/sql (migrations)
frontend/                      Next.js + TypeScript app: login, Home (what to do next, lessons and assignments by course),
                               lesson page, notebook page with iframe and Submit, Teach (/teach), Admin (/admin), My account
assignments/<id>/              example notebooks to import, one of them autograded (see Assignments below)
deploy/                        production stack, hub config, notebook images, scripts
dev.sh                         start everything: Postgres (:5433), JupyterHub (:8081), grader (:8090), backend (:8003), frontend (:3000)
dev-hub.sh                     start/stop only the local JupyterHub in Docker (dev.sh calls it)
dev-tunnel.sh                  run dev.sh on a server that only lets SSH through, shared on your network through your computer
check.sh                       every check: ruff, the tests (on a Postgres of their own), tsc and ESLint
```

## Run it locally

```bash
conda activate CyberP
pip install -r api/requirements.txt
(cd frontend && npm install)

./dev.sh          # everything; needs Docker Desktop for Postgres and notebooks. First run builds the notebook image.
```

`dev.sh` starts Postgres, applies the migrations in `sql/`, then starts the rest.
The backend runs on port 8003, or on the next free port when another project has 8003; `dev.sh` prints
which one (`BACKEND_PORT=8010 ./dev.sh` starts looking at 8010 instead).
If port 3000 is taken by another project, pick another: `FRONTEND_PORT=3001 ./dev.sh`
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
./dev.sh --lan          # with another frontend port:  FRONTEND_PORT=3001 ./dev.sh --lan
```

It prints the address to open, for example `http://192.168.1.9:3000`: this computer's address on the
Wi-Fi or Ethernet network (`DEV_HOST=<address> ./dev.sh --lan` if it picks the wrong one). Use that
address on this computer too: logging in does not work at `localhost` while in this mode. macOS may ask
once whether to allow incoming connections. A VPN or a network that keeps devices apart (many guest and
campus networks do) can prevent other devices from connecting.

When the site runs on a server whose firewall lets only SSH through (port 3000 there times out from
other computers), run this on your own computer instead:

```bash
./dev-tunnel.sh iqsec.cs.utep.edu     # the server as named in ~/.ssh/config, or user@host
```

It starts `./dev.sh --lan` on the server over SSH, with your computer's address, and forwards ports 3000
and 8081 from your computer to the server. People on your network then open
`http://<your computer's address>:3000`, the address it prints; you too, not `localhost`. Stop any
`./dev.sh` already running on the server first. Your computer has to stay on and connected while people
use the site, and its address changes when it joins another network, so run the script again after
moving. Ctrl+C stops the tunnel and everything on the server.

This is for trying the site with people you trust, not for a class:

- It is plain `http`, so passwords and logins cross the network unencrypted and anyone on the same
  network can read them. Use test accounts, not real passwords.
- The site and the notebooks share one address, so a notebook server receives the visitor's platform
  login. Someone with a notebook could use that to act as a teacher who opens their notebook server.
  On the real server the two have separate addresses and HTTPS, which prevents it (`deploy/README.md`).
- The hub's API and the notebooks become reachable from the network. `dev.sh` makes new random secrets
  on every start (also without `--lan`) in place of the ones written in this repository.

Without `--lan`, the site and the hub listen on this computer only (127.0.0.1). The backend listens on
every address, because on Linux the hub container can reach it only that way; it only answers with
what a logged-in browser would get. Through `dev-tunnel.sh`, the site and the hub listen only on the
server's own localhost, where the tunnel reaches them, so the hub's port does not get through the
server's firewall (Docker's published ports otherwise do).

## Settings (environment variables)

On a server, every setting is in one file, `deploy/.env`, which `docker compose` reads from `deploy/`.
Start from this template (it is also `deploy/.env.example`): copy it, then fill in the addresses and a
new secret for each `change-me`. Never commit `deploy/.env`.

```bash
cd deploy && cp .env.example .env && openssl rand -hex 32    # once per secret
```

```bash
# Settings for the whole stack on a server (deploy/docker-compose.yml). Copy this file to
# deploy/.env and fill it in; docker compose reads it from deploy/. Every variable is described in
# README.md, "Settings (environment variables)". Never commit deploy/.env: it holds the secrets.

# --- Addresses -----------------------------------------------------------------------------------
# The site and the notebooks, each on its own name under one parent domain (both under utep.edu, say).
# APP_ORIGIN must be exactly what people type to reach the site: the backend refuses logins from anything else.
APP_DOMAIN=app.school.example
HUB_DOMAIN=hub.school.example
APP_ORIGIN=https://app.school.example
HUB_ORIGIN=https://hub.school.example

# --- Secrets: each one new, from `openssl rand -hex 32` ------------------------------------------
# The backend refuses to start with one shorter than 32 characters, containing "dev-", or "change-me".
OAUTH_CLIENT_ID=jupyterhub
OAUTH_CLIENT_SECRET=change-me
PLATFORM_HUB_API_TOKEN=change-me
JUPYTERHUB_CRYPT_KEY=change-me
POSTGRES_PASSWORD=change-me
GRADER_TOKEN=change-me

# --- Notebook images and GPUs --------------------------------------------------------------------
# GPU notebooks for everyone: off until they are taken up again. "on" turns them back on (backend and hub).
GPU_NOTEBOOKS=off
# The GPUs students may use (nvidia-smi numbers, comma separated), and how many servers share one.
GPU_IDS=0
MAX_SESSIONS_PER_GPU=4
# The images students' notebooks (and the autograder) run in: build them first, see deploy/README.md.
CPU_IMAGE=cyberai/notebook-cpu:latest
GPU_IMAGE=cyberai/notebook-gpu:latest

# --- Limits --------------------------------------------------------------------------------------
# What one person's notebook server may use (per server; caps, not reserved). Applies to servers
# started afterwards: `docker compose up -d jupyterhub`, then running servers pick it up once restarted.
CPU_PROFILE_CPUS=1
CPU_PROFILE_MEM=2G
GPU_PROFILE_CPUS=4
GPU_PROFILE_MEM=12G
# The autograder: memory and seconds per job, and how many jobs run at once (`docker compose up -d grader`).
GRADER_MEMORY=2g
GRADER_TIMEOUT=300
GRADER_PARALLEL=2
```

| Variable | Needed | Default | What it is | Read by |
| --- | --- | --- | --- | --- |
| `APP_DOMAIN` | yes | | The site's name; Caddy gets its certificate | Caddy |
| `HUB_DOMAIN` | yes | | The notebooks' name, under the same parent domain as the site | Caddy |
| `APP_ORIGIN` | yes | | Exactly the address people type, `https://` and no path. Logins and changes from anywhere else are refused | backend, hub |
| `HUB_ORIGIN` | yes | | The notebooks' address. Built into the frontend: run `docker compose up -d --build frontend` after changing it | backend, hub, frontend |
| `OAUTH_CLIENT_ID` | yes | `jupyterhub` | The hub's name when it logs people in through the platform | backend, hub |
| `OAUTH_CLIENT_SECRET` | yes, secret | | Shared by the hub and the backend for that login | backend, hub |
| `PLATFORM_HUB_API_TOKEN` | yes, secret | | The backend's key to the hub's API (starting servers, copying notebooks) | backend, hub |
| `JUPYTERHUB_CRYPT_KEY` | yes, secret | | Encrypts what the hub keeps about each login | hub |
| `POSTGRES_PASSWORD` | yes, secret | | The database password | database, backend |
| `GRADER_TOKEN` | yes, secret | | The backend's key to the grading service | backend, grader |
| `GPU_NOTEBOOKS` | no | `off` | `on` lets GPU assignments and GPU notebooks start again, for everyone | backend, hub |
| `GPU_IDS` | yes | `0` | The GPUs students may use (`nvidia-smi` numbers, comma separated) | hub |
| `MAX_SESSIONS_PER_GPU` | yes | `4` | GPU notebook servers sharing one GPU; each gets that share of its memory | hub |
| `CPU_IMAGE`, `GPU_IMAGE` | yes | `cyberai/notebook-cpu:latest`, `cyberai/notebook-gpu:latest` | The images notebooks and grading jobs run in | hub, grader |
| `CPU_PROFILE_CPUS`, `CPU_PROFILE_MEM` | no | `1`, `2G` | Most one person's CPU notebook server may use | hub |
| `GPU_PROFILE_CPUS`, `GPU_PROFILE_MEM` | no | `4`, `12G` | Most one person's GPU notebook server may use | hub |
| `GRADER_MEMORY`, `GRADER_TIMEOUT` | no | `2g`, `300` | One grading job's memory, and seconds before it is stopped | grader |
| `GRADER_PARALLEL` | no | `2` | Grading jobs at once; the others wait their turn | grader |

"Needed: yes" with a default means: keep the template's value unless you have a reason. Those are
passed as they are: an empty `MAX_SESSIONS_PER_GPU` stops the hub, an empty image name or `GPU_IDS`
leaves notebooks unable to start. The limits are caps, not reserved memory: see
`deploy/README.md` ("CPU and memory of notebook servers and grading jobs") before raising them. After
changing `deploy/.env`, `docker compose up -d` restarts what uses the changed values.

**Set by the stack itself, not in `deploy/.env`:** `DATABASE_URL` (built from `POSTGRES_PASSWORD`),
`HUB_API_URL` and `HUB_API_TOKEN` (the backend's names for the hub and `PLATFORM_HUB_API_TOKEN`),
`GRADER_URL`, `PLATFORM_INTERNAL_URL`, `DOCKER_NETWORK_NAME` and `NEXT_PUBLIC_HUB_ORIGIN` (from
`HUB_ORIGIN`, when the frontend is built), all in `deploy/docker-compose.yml`. The hub gives each
notebook server `FRAME_ANCESTORS` (only the site may show it in a frame) and `GPU_MEM_FRACTION` (its
share of a GPU).

**Running it locally (`./dev.sh`)** needs no `.env` file: everything has a development value in the
code or in `deploy/docker-compose.dev.yml`, and the secrets are made new on every start. What can be
set on the command line:

| Variable | Default | What it does |
| --- | --- | --- |
| `FRONTEND_PORT` | `3000` | The site's port: `FRONTEND_PORT=3001 ./dev.sh` when 3000 is taken |
| `BACKEND_PORT` | `8003` | Where the backend starts; it moves to the next free port by itself |
| `DEV_HOST` | `localhost` | The site's address. With `--lan`, this computer's network address (found by itself) |
| `LISTEN_ADDRESS` | `127.0.0.1` | Where the site and the hub listen; `--lan` makes it `0.0.0.0` |
| `GPU_NOTEBOOKS` | `off` | `GPU_NOTEBOOKS=on ./dev.sh` tries GPU notebooks (a pretend GPU on a laptop) |
| `REMOTE_DIR`, `CONDA_ENV` | `CyberAI-LearningPlatform`, `llm` | For `./dev-tunnel.sh`: the project's folder on the server, and the conda environment to start it in |
| `PYTHON` | `python` | The Python `./check.sh` uses |
| `TEST_DATABASE_URL` | the test Postgres on port 5434 | Where the tests make their throwaway databases; they stop if it is the platform's own |
| `BACKEND_URL` | `http://localhost:8003` | Where the frontend sends `/api` when it is run without `dev.sh` |

## Accounts

There is no public sign-up. The first admin is created from the command line, while `dev.sh` is running:

```bash
cd api
python -m app.manage create-user admin --role teacher --admin     # asks for the password twice
```

After that, an admin manages accounts in the site, under **Admin** (top bar) > **Accounts**:

- **Add account**: the server generates the password and shows it once, in a box that stays open until
  the admin presses "I have noted it".
- **Students have no name, only a username.** The form asks a teacher's name, never a student's, and the
  server refuses one (a student's name on the site is their username). For a student the username is
  filled in with a made-up one in the style of an Xbox gamertag, like `swiftfalcon482`; the dice beside
  it makes up another, and it can still be typed over. They are made on the server
  (`GET /api/admin/username-suggestion`, `api/app/usernames.py`), never one that is taken, from word
  lists checked so that no pairing spells anything rude.
- **Edit**: a teacher's name, and whether the account may use GPU notebooks. The username and the role
  are fixed (the account's notebook files are stored under a name made from its role and number).
- **New password** (in the row's ⋯ menu), for someone who forgot theirs: again generated and shown once,
  and the account is logged out everywhere, its running notebooks and JupyterHub login included (its
  files stay). For another admin's account the site first asks for your own password (guesses are
  limited like logins), so a browser left logged in cannot lock the other admins out, and the backend
  logs who did it. Your own password is changed under **My account**, not here.
- **Remove** (in the ⋯ menu): deletes the account with its submissions and grades, stops its notebook servers and ends
  its JupyterHub login. The files in its notebook home stay on the server.

Everyone changes their own password under **My account**, in the menu under their name at the top right (the current password is asked for
again, and every other device is logged out).

Admin rights are given in the site too, but only to teachers, and only after the admin types their own
password again (so a browser left logged in cannot change who is an admin; guesses are limited like logins):

- **Make admin** (in a teacher's ⋯ menu): the teacher can manage accounts as well, at once, without
  logging in again. Students are never made admins.
- **Remove admin rights** (in an admin's ⋯ menu): from another admin, never from yourself, so there is
  always an admin left. The account and its role stay.

The site removes an admin only once their admin rights are gone. On the server itself the command line
tool does all of it, for any account (also the way back in when no admin can log in):

```bash
python -m app.manage set-admin maria                               # or: set-admin maria --remove
python -m app.manage set-password maria                            # choose a password yourself; also logs that account out everywhere
python -m app.manage create-user --random                          # a student with a made-up username; add --gpu for GPU notebooks
python -m app.manage create-user msmith --role teacher --name "Mary Smith"   # --name is refused for students
python -m app.manage list-users
```

Roles are `student` and `teacher` (teachers may use GPU notebooks). `--admin` is
separate: it marks who may manage accounts. Usernames are not case sensitive. Passwords are stored only
as Argon2 hashes. A login lasts 7 days. Logging out ends it on the server and also logs the browser out
of JupyterHub.
The same commands run on the server: see `deploy/README.md`.

Who is an admin or a teacher is decided on the server for every request: the browser stores nothing
about it (no password, no role), only a session cookie that page scripts cannot read. Platform admins
are JupyterHub admins; teachers are not, because JupyterHub's admin role opens every notebook server.

## Where things are

The navy bar at the top has up to three areas, by account, and a menu under the person's name with
**My account** (change your password) and **Log out**:

| Area | Who | What |
| --- | --- | --- |
| **Home** (`/`) | everyone | what to do next, what is due, announcements, and every lesson and assignment, course by course |
| **Teach** (`/teach`) | teachers, admins | Overview · Courses · Lessons · Assignments · Announcements |
| **Admin** (`/admin`) | admins | Accounts · JupyterHub (its own admin panel: running notebook servers) |

Teachers land on **Teach > Overview** after logging in: what waits to be graded, what is due in the
coming week with how many have handed it in, what needs attention (drafts, changes not published,
assignments given to nobody), and the courses. On Home, a line at the top says the same in short and
links to Teach; their Home shows what students see, drafts marked.

Hiding a link is only tidiness. Each page's data comes from the API, which checks the account on every
request. For now every teacher sees and manages every course, lesson and assignment.
Old `/settings/...` links and bookmarks still work: they are sent on to the new pages
(`frontend/next.config.ts`), and `/settings` itself to Teach or to My account.

## Lessons

Lessons are written in the site, under **Teach > Lessons** (or on a course's page): press **New lesson**,
type a title, choose who gets it, and the editor opens. A lesson is a list of **blocks**:

| Block | What it is |
| --- | --- |
| Text | Markdown, as in a notebook's text cells: headings, lists, links, tables, inline code |
| Code | a snippet with a language label, shown in the colours of that language |
| Callout | a note, tip or warning box |
| Picture | PNG, JPEG, GIF or WebP up to 5 MB: choose a file, or paste or drop it anywhere in the lesson |
| Video | a YouTube link, shown as a player |
| Notebook | a link to a notebook assignment, shown to the students that assignment was given to |
| Multiple choice | a knowledge check with 2 to 8 options. One ticked option: students choose one. Several: they must choose exactly those. "True or false" is the same block with the two options filled in |
| Short answer | a knowledge check where the student types the answer. It is right when it equals one of the accepted answers, ignoring capital letters and extra spaces |

Code is shown in the colours of its language: in a Code block (its language label), and between ```
lines in a text block when the language is written after the first ones (```python). Python, Bash and
shell sessions, JavaScript, TypeScript, SQL, JSON, C, C++, Java, Go, Rust, HTML, CSS, YAML and about
twenty more are known; any other code is shown as it is, never guessed. The colours come from
highlight.js (through `lowlight` and `rehype-highlight`, `frontend/lib/highlight.ts`), which hands back
a tree React draws, never HTML; each theme has its own colours, all at least 4.5:1 on the code's background.

Writing is meant to be quick:

- Everything is **saved by itself** a moment after you stop typing. There is no Save button.
- Text blocks show the result, and turn into a text field when you click them, like notebook cells.
- Type `/` on an empty line of a text block for the menu of blocks (`/mu` + Enter gives a multiple-choice
  question). **Ctrl/⌘ + Enter** adds a text block below the block you are in.
- In a question, **Enter** adds the next option and starting an option with `*` ticks it as correct.
  Options left empty are ignored.
- **Write or paste a whole lesson as text** (at the bottom of the editor) turns one piece of text into
  blocks: Markdown for text (each heading starts a block), a line starting with `?? ` for a question
  followed by `- [ ]` wrong and `- [x]` correct options or `= accepted answer` lines and a `> ` explanation,
  ` ``` ` around code, and `> [!NOTE]`, `> [!TIP]` or `> [!WARNING]` for a callout. **Show an example** fills one in.

What you write is your **working copy**. Students get the lesson when you press **Publish**, and keep that
version while you go on editing, until you press **Publish changes**. Publishing is refused, with the
reasons, while a question is unfinished (no question text, fewer than two options, no correct option, no
accepted answer). **Preview** shows your working copy as a student would see it, questions included.
**For** (top of the editor) chooses who gets the lesson: all students or one course. The arrows in the
list of lessons (Teach > Lessons with one course chosen, or the course's page) set the order students see
them in. A lesson's **Progress** tab shows who has done it.

While you write, the left side of the editor lists **every lesson** in that order, each with where it
stands: Draft (an empty ring), Published (a green tick) or Changes not published (a dashed blue ring). Click one to
switch to it (what you were typing is saved first), or type a title in **New lesson…** and press Enter to
start the next one. Under the lesson you are in, the list shows its **topics**: the headings you write in
text blocks with `#`, `##` and `###`. Click a topic to jump to it.

Students see their lessons on Home, above the assignments of the same course, with a status (Not
started, In progress, Completed) and how far they are in each course. **Up next**, at the top of Home,
picks what to do now, most pressing first: a submission that could not be graded, work past its due date,
work due within a week, a lesson that only needs marking complete, a lesson in progress, the next lesson
of each course. A lesson's page shows where it is in its course ("Lesson 2 of 3"), how long it takes to
read and how many checks are done. At the end, "2 checks left: go to it" jumps to the first open check,
and **Mark as complete** (once every check is done) shows how it went and the next lesson, without
reloading the page.

Every lesson's page has a **menu on its left** (under the title on an iPad): the lessons of the same
course, each with how far the reader is (Not started, In progress with the checks done, Completed), and
under the lesson being read its topics. The topics are the same `#`, `##` and `###` headings; a `#`
inside code is not a heading. The menu follows the reader down the page, marks the topic being read, and
jumps to a topic or to another lesson when clicked. A lesson without headings still gets the menu, with
the lessons only.

**Knowledge checks are checked on the server** (`api/app/lessons.py`). What a student's browser receives
never contains which option is correct, the accepted answers or the explanation. Each check allows three
tries ("Try 2 of 3"): a wrong try is only told to be wrong; a right answer, or the third wrong one, closes
the question and shows the explanation and the right answer. They are practice and do not count towards any grade.
**Progress** (a tab of each lesson, also in the lesson's ⋯ menu) shows per student who opened and completed the lesson, and
per question how many got it right at the first try, in the end, or not at all.

When a published change alters what counts as right in a question (its options or accepted answers), or
removes the question, students' earlier answers to it are deleted and they are asked again. Fixing a typo
in the question or in an option's text keeps them.

### Exporting and importing lessons

Lessons can be taken out as a `.zip` and brought in again, on the same platform or another one (from a
laptop to the server, or to keep a copy):

- **Export**: a lesson's ⋯ menu (in the list, or in the editor) has **Export as .zip**. On Teach > Lessons,
  **Export** beside "Show" takes every lesson the list shows, in that order: choose a course there to export
  that course's lessons.
- **Import**: **Import** on Teach > Lessons (also offered while there are no lessons yet). Choose or drop the
  `.zip` and who the lessons are for; they come in as **drafts**, after the lessons already there.

The file holds each lesson's working copy (unpublished edits included), its pictures, and every notebook
assignment it links to, as the teacher uploaded it: an autograded notebook **with its solutions and hidden
tests**, and the answers to the knowledge checks. Keep it away from students. Nothing students did is in it
(answers, progress, submissions, grades).

On import, a linked notebook is taken in as if it were chosen on **Upload notebook**: it becomes a draft
assignment for the same people as the lessons, and an autograded one goes through Otter again (the grading
service must be running; it takes as long as running the notebook twice). When an assignment with the same
title and the same file is already there, the lesson links to it instead of making a second one. Every
picture and notebook is checked as an upload is. If anything in the file is refused, nothing is imported;
a picture or notebook the file lacks only leaves its block empty, and the import says so.

What is in the `.zip` (format version 1, `api/app/lesson_zip.py`):

```
lessons.json                          the lessons in order, and each notebook's title, description, points
01-tls-basics/lesson.json             a lesson: title, summary, blocks
01-tls-basics/images/1.png            its pictures
notebooks/python-basics-lab-1/lab1.ipynb   the notebooks the lessons link to, each with its data files beside it
README.txt                            what the file is
```

The blocks are as stored, except that a picture or notebook is named by its file in the `.zip`
(`"image"`, `"notebook"`) instead of an id. A file is at most 100 MB (and 200 lessons); Export refuses to
make one that Import would not take back.

## Assignments

Under **Teach > Assignments**, a teacher:

1. Presses **Upload notebook** and uploads a notebook (`.ipynb`, at most 10 MB) with a title, a description
   and an optional due date. It is stored in Postgres as a **draft** given to nobody.
2. On the assignment's **Settings** tab, chooses who gets it: the students of a course, all students
   (including accounts added later), or chosen students. The same tab edits the title, due date, points
   and environment, downloads the notebook (with or without solutions) and deletes the assignment.
3. Presses **Publish**. Students now see it on Home. **Unpublish** hides it again.

A student only ever sees, and can only open, published assignments given to them. The server checks this
on every request (`api/app/assignments.py`), so guessing another assignment's address gives "No such assignment."

The first time a student opens an assignment, the backend puts their own copy of the notebook in their
Jupyter home at `assignments/<folder>/<file>.ipynb`, through that student's running notebook server.
It is never overwritten after that: the file is the student's work. Deleting an assignment removes it
(with its submissions and grades) from the platform, not from the homes of students who already opened it.

### Data files (datasets)

An assignment can have **data files** that go with its notebook: a CSV, JSON, images, a `.zip` of many
files, anything the notebook opens. Add them under **Data files (optional)** on Upload notebook, or later in
the **Files** section of the assignment's Settings tab (where each can also be downloaded or removed).

- Each student gets **their own copy**, beside the notebook in `assignments/<folder>/`, the first time they
  open the assignment, so the notebook opens them by name: `pd.read_csv("ports.csv")`. A copy already in
  their folder is never overwritten (they may have changed it); one they deleted comes back the next time
  they open the assignment. The teacher's **Edit in JupyterLab** copy gets them too.
- An **autograded** notebook is prepared by Otter with its data files beside it, and they go into its
  autograder (Otter's `files:` list, which the grading service adds to the ASSIGNMENT CONFIG cell), so
  submissions are graded with them even though grading has no network. If your ASSIGNMENT CONFIG already has
  a `files:` list, it must name every data file. Every change of the data files has Otter prepare the
  notebook again.
- Like the notebook, they can be changed only until the first student opens the assignment.
- Limits: 20 files and 50 MB per assignment together (every student gets a copy, and the autograder carries
  them). Names are kept as they are, since the notebook uses them: letters, digits, dots, dashes, underscores
  and spaces, starting with a letter or digit; never a folder (put a folder in a `.zip`), never a `.ipynb`.
- They are stored in Postgres with the notebook (`assignment_files`), so the database backup covers them.

Home shows each student their lessons and assignments by course. Each assignment has its status:
Not started, Opened, Overdue, Submitted, Grading or the score. An assignment's page says in three steps
how it works (open, save, submit) and offers **Continue working** once the notebook has been opened.

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
  within seconds to minutes. Students see their score per question and whether each question's public
  tests passed; what a test reported they see in their notebook, with `grader.check`. The platform
  never shows them the hidden tests or Otter's report on any test. Their own code can still read the
  hidden tests while the autograder runs it (see Current limits below).
- **Graded by hand**: any other notebook. Submissions wait for the teacher.

Until the first student opens an assignment, its **Settings** tab can still change its notebook, for
instance to add Otter's cells to a notebook uploaded without them. **Edit in JupyterLab** puts a copy
(for an autograded assignment, the version with solutions and tests) into the teacher's own notebook
files, at `editing/<folder>/<notebook>`, and **Use my edits** takes it back from there; **Replace
notebook** takes another file instead. Either goes through Otter as an upload does, so the assignment
is autograded or graded by hand according to the new notebook. Once a student has opened it, it stays
as it is: their copy is theirs, and it would no longer match the tests. A student who opens it while
a new notebook is being saved gets the new one.

The **Gradebook** tab of each assignment lists every student the assignment is given to, when they
opened and submitted it, and their score. From there a teacher can open a submission in their own
notebook environment (a copy; the student's files are not touched), download it, give or change the
score, write a comment for the student, run the autograder again, and download the table as CSV.
**Save and next** saves a grade and opens the next submission waiting for one.

Read an opened submission, do not run it: it is a student's code, and in the teacher's environment it
would run with network access and with the teacher's files in reach: other students' submissions, and
the editing copies of autograded notebooks, hidden tests included. The autograder is the safe place
where submissions are run.

Student code never runs in the backend. The grading service (`grader/`) starts a new container of the
student notebook image for every job, with no network, 2 GB of memory, one CPU, a limit on processes
and five minutes, and removes it afterwards. It is the only service besides the hub with the Docker
socket, and it has no database access. GPU assignments are graded in the GPU image without a GPU.

### Courses and announcements

A course (**Teach > Courses**) is a named group of students. Its page has tabs for its **Content** (its
lessons in the order students see them, and its assignments), its **Students** and its
**Announcements**, and buttons to start a lesson or upload a notebook for that course. An assignment or
announcement given to a course reaches its students, including students added to the course later.
Deleting a course keeps its lessons and assignments, given to nobody until a teacher gives them out again.

**Teach > Announcements** posts a short message to everyone or to one course. Students see the five
newest ones meant for them on Home.

### Exporting students' progress and grades

**Export** on a course's **Students** tab downloads that course's students; **Export** on
**Teach > Courses** downloads every student on the platform. Each offers Excel (.xlsx) or CSV, named
like `cs-101-students-2026-10-19.xlsx` or `all-students-2026-10-19.csv`. The server makes the file and
checks the account first: teachers and admins get it, students get 403.

One row per student, by username (the platform records no real names), with these columns:

- **Course** (one course) or **Courses** (every student: all of theirs, separated by `;`).
- **Lessons completed** and **Lessons given**; **Checks answered** (at least one try, as on a lesson's
  Progress tab), **Checks correct** and **Checks given** (the knowledge checks in those lessons).
- For each assignment, soonest due first: **status** (`not started`, `opened`, `submitted`, `late`
  (handed in after the due date, no grade yet), `graded`, `graded late`, `could not be graded`) and
  **score**, with what it is out of in the column's name. Both are empty for a student the assignment
  was not given to.
- **Assignments submitted**, **Assignments given**, **Total score** and **Total out of**. The totals add
  up graded work only, so score / out of is a running grade: work not handed in yet does not count as 0.

Only published lessons and assignments count, as students never see drafts. A course's file has the
course's own lessons and assignments and those given to every student; assignments given to students
one by one are only in the file of every student. The Excel file of one course has one sheet; the one
of every student has an **All students** sheet (the same as the CSV) and a sheet per course. In Excel
the header row and the usernames stay in view, and each column can be filtered.

The CSV is UTF-8 with a byte order mark, so Excel shows accents right. A cell that would start with
`=`, `+`, `-`, `@`, a tab or a carriage return (a course or assignment name can) gets a `'` in front, so
a spreadsheet program never runs it as a formula; in the Excel file such text is stored as text instead.

### From the command line

The example notebooks in `assignments/` can be added from the command line instead of the page:

```bash
cd api
python -m app.manage import-assignment ../assignments/python-basics/lab1.ipynb --title "Python basics" --publish
python -m app.manage import-assignment ../assignments/hello-gpu/lab1.ipynb --title "Hello GPU" --gpu --publish
python -m app.manage import-assignment ../assignments/otter-example/functions.ipynb --title "Functions lab"   # autograded
```

`--publish` gives it to every student at once; without it the notebook is a draft. `--data FILE` (once per
file) adds a data file beside the notebook.

## Security checks

Uploads are checked on the server: the file must be a real notebook (validated with `nbformat`) and its
name is reduced to a plain file name. Requests are limited to 1 MB, except a teacher's notebook upload
(11 MB, or 61 MB with data files), data files added later (51 MB), a picture for a lesson (6 MB) and a
`.zip` of lessons to import (101 MB), which are only read after the account has been checked
(`LimitRequestSize` in `api/app/main.py`). Data file names are refused rather than changed when they are
not plain names (no folders, no `..`), and students only ever get them as copies in their own homes.

A lessons `.zip` is never unpacked to disk: only the files its `lessons.json` names are read, by plain
names (no `..`, no leading `/`), each with its own limit (a picture 5 MB, a notebook 10 MB) and 300 MB
in all, however large the file says they are, so a "zip bomb" is stopped early. Its pictures, notebooks
and blocks go through the same checks as when they are uploaded or typed.

Lessons: every block is checked on the server before it is saved (known types only, length limits, at
most 200 blocks). A picture is accepted by how the file starts, never by its name, as PNG, JPEG, GIF or
WebP only (SVG can carry scripts and is refused), and is served only to people who may see that lesson.
Markdown is rendered without running any HTML written in it, and pictures from other sites are not
loaded. Videos are only ever embedded from YouTube's cookie-less player, the one other site the pages
may show in a frame (`frontend/next.config.ts`).

After 5 wrong passwords for one username from one network address, further logins for that username from
that address are refused for 15 minutes (`MAX_LOGIN_ATTEMPTS` in `api/app/auth.py`). `test/api/test_security.py`
attacks the login and the admin API: password guessing (also of a password typed again when already
logged in: My account, another admin's new password, admin rights, which share one limit of 5),
SQL injection, forged and planted cookies, oversized input, requests sent from other websites, and a
student asking for admin data or trying to create, change or remove accounts. `test_assignments.py`,
`test_courses.py` and `test_grading.py` do the same for the teacher API: students trying to upload,
grade themselves, read other students' submissions or see hidden tests. `test_exports.py` checks that
only teachers and admins get the export, that a course's file has only its own students, and that
nothing in it runs as a formula. `test_lessons.py` checks that
students cannot write or read drafts, and that nothing they are sent gives away an answer.

The backend's JupyterHub token (`PLATFORM_HUB_API_TOKEN`) is only sent to the hub's own API, never to a
student's notebook server, where code the student runs could read it. To put a notebook into a
student's home, or take a submission out of it, the backend has the hub make a token that opens only
that one server for two minutes, and deletes it afterwards (`test/api/test_hub_client.py`).

Current limits: an assignment is one notebook file (with up to 50 MB of data files beside it), and neither
can be changed once a student has opened it. Every teacher manages every course and assignment. Only the newest submission of a student
is kept. Otter runs the student's code and the tests in one process, so a student's code can read the
hidden tests there and influence its own autograder score within the assignment's questions (the
platform counts only those questions, none for more than the points read from the teacher's tests at
upload, and tells the teacher in the gradebook when the results claimed otherwise); when a score looks
wrong, open the stored notebook from the gradebook and read it. Lessons can be given to all students or to one course, not to chosen students; two teachers
editing the same lesson at once overwrite each other; code is coloured where it is read, not while it is
written in the editor, and Markdown has no math formulas yet. Locally the "GPU" profile is simulated: same
checks, no GPU attached, and it uses the CPU image, so `import torch` fails unless you pass
`GPU_IMAGE=... ./dev-hub.sh`.

## GPU notebooks: turned off for now

GPU notebooks are off for the whole platform until they are taken up again. One setting,
`GPU_NOTEBOOKS` (`off` by default, `on` to turn them back on), read by the backend (`api/app/config.py`)
and by the hub (`deploy/jupyterhub/jupyterhub_config.py`):

- An assignment marked "Needs a GPU" opens, is submitted and stopped in the standard environment. The
  CPU and GPU servers share one home directory, so a student's file is the same one when GPUs are back.
- The hub refuses to start a GPU server for anyone ("GPU notebooks are turned off for now."), also when
  it is asked directly, without going through the platform.
- Nothing is lost: "GPU notebooks" on an account and "Needs a GPU" on an assignment can still be set, and
  are shown with "turned off for now"; students do not see "GPU" on those assignments meanwhile.
- Grading is unchanged: GPU assignments were already graded in the GPU image without a GPU.

To turn them back on: `GPU_NOTEBOOKS=on ./dev.sh` locally, or `GPU_NOTEBOOKS=on` in `deploy/.env` on
the server, then `docker compose up -d --build` (the hub's config is built into its image).

## How it looks

The site is made for **iPad and desktop** (768 px wide and up); there is no phone layout. Nothing
depends on hovering (an iPad cannot), and buttons that are only an icon grow to 48 px on touch screens.
On an iPad the lists that sit beside a lesson move above it.

The styling is in three files: `frontend/app/globals.css` (the scales and everything shared: buttons,
fields, chips, lists, tables, the top bar, page headers, dialogs, menus), `frontend/app/styles/teach.css`
(Teach, Admin, the lesson editor) and `frontend/app/styles/learn.css` (Home, a lesson, a notebook).
Sizes, colours and shadows come from a few scales at the top of `globals.css` (after the book
*Refactoring UI*): spacing 4 to 64 px, text 12 to 30 px, two font weights, one corner radius, three
shadows, and colours named by what they are for (`--card`, `--muted`, `--accent`, ...), each with a dark
version. When changing the look, pick the nearest step of a scale instead of writing a new value. Text
colours are at least 4.5:1 against what they stand on, and the outlines of fields at least 3:1, in light
and dark.

The bar is navy with a cyan spark, which is only ever used on the navy. Status is a small chip with an
icon and a word, in five tones: green (done, published), blue (in progress), grey (not started, draft),
yellow (soon, changes waiting, try again) and red (late, failed, wrong). Icons come from `lucide-react`
and are sized by the CSS. Every page starts with the same header (where you are, the title with its
status, one line about it, its actions): one filled button for its main action, other actions outlined,
and rare or destructive ones in a ⋯ menu.

**Themes.** Everyone chooses how the site looks under **My account > Appearance**: **Standard** (the
look above), **Halloween** (pumpkin orange and purple, with bats and a cobweb) or **Retro 95** (grey
windows with bevelled edges on a teal desktop), and, for any of them, **Light or dark**: Match my
device (the default), Light or Dark. Each theme has both versions: Halloween on bone white or on
midnight, Retro 95 in grey or in the dark grey of a high-contrast setting on a deep teal desktop. Both
choices belong to the account (`users.theme` and `users.color_mode`, saved with `PUT /api/auth/theme`,
which only takes the names in `THEMES` and `MODES` in `api/app/models.py`), so they follow the person
to every device. The browser also keeps them in cookies, only so that a page is drawn in them from the
first moment. A theme gives the colour roles of `globals.css` other values and redraws a few pieces
its own way, all in `frontend/app/styles/themes.css`; the choices are listed in `frontend/lib/themes.ts`.
Light or dark is `<html data-mode>`; without it the CSS asks the device. Each dark version is written
twice (for a dark device, and for an account that chose dark), and `test/test_themes_css.py` checks
that the two stay the same, that every version sets every colour, and the contrast of all six.

## Tests

```bash
pip install -r api/requirements-dev.txt     # once: pytest and ruff, into the CyberP environment
./check.sh                                  # every check: ruff, the backend's tests, the frontend's type check and ESLint
(cd frontend && npm test)                   # the frontend's type check, ESLint and the production build
```

**The tests never reach the platform's own database**, on this computer or on the server. They run
on a Postgres of their own (`deploy/docker-compose.test.yml`, port 5434, its data in memory), which
`./check.sh` starts and removes again; each run makes a throwaway database there and drops it.
`test/conftest.py` points `DATABASE_URL` at that Postgres before the app is loaded, so nothing in the
app can open another database during the tests, and it refuses to run when told to use the
platform's Postgres. To run only the tests: `docker compose -f deploy/docker-compose.test.yml up -d
--wait`, then `pytest test` (tests that need a database are skipped while it is not running). The hub
and the grader are replaced by stand-ins, so they do not need to be running.

**Lint.** Python: `ruff check api test grader deploy`, with the rules in `ruff.toml` (mistakes such
as undefined names, unused imports, blocking calls in async code; not layout). Frontend: `npm run lint`
(ESLint with Next.js's own rules, `frontend/eslint.config.mjs`); `next build` runs it too.

When you are running the thing make sure to investigate the following:
- a way to connect a sql base on to this project with all of the migrations. 
- Also make sure to connect jupyter notebook per user in this instance of code.
