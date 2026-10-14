# cyberAI-Platform

Student coding platform: **FastAPI + uvicorn** backend in `api/` (conda env `CyberP`), **Next.js + TypeScript** frontend,
and **JupyterHub** for per-student notebook environments (CPU and GPU).
Design and server setup: see the "Student Jupyter Platform: Architecture & Setup" doc and `deploy/README.md`.

## Project structure

```
api/app/main.py                FastAPI app
api/app/config.py              settings (env vars, dev defaults)
api/app/db.py                  SQLAlchemy engine, sessions, model Base
api/app/models.py              database tables: users, login sessions, courses, assignments, submissions, announcements, lessons
api/app/auth.py                accounts, password hashing, login/logout, changing your password, limit on password guessing
api/app/admin.py               admin-only API behind Admin > Accounts (add, edit, new password, remove)
api/app/manage.py              command line tool: create accounts, grant admin, reset passwords, import a notebook
api/app/assignments.py         assignments: who sees which, who opened what, checks on uploaded notebooks
api/app/courses.py             courses (groups of students) and announcements
api/app/submissions.py         submissions and grades; has the autograder grade them in the background
api/app/grading.py             talks to the grading service; reads Otter-Grader's notebooks and results
api/app/teach.py               teacher-only API behind Teach: assignments, courses, announcements, the gradebook
api/app/lessons.py             lessons: their blocks, who sees which, knowledge checks (checked on the server), pictures
api/app/lesson_routes.py       lessons over HTTP: the teacher API behind Teach > Lessons, and reading and answering for everyone
api/app/jupyter/               OAuth2 provider for JupyterHub, hub REST client, launch and submit API (copies notebooks to and from students)
grader/                        grading service: runs Otter-Grader in throwaway locked-down containers (its own Docker image)
sql/                           Alembic database migrations (see sql/README.md)
test/                          pytest suite: test/api (API, login attacks, assignments, courses, grading, lessons), test/sql (migrations)
frontend/                      Next.js + TypeScript app: login, Home (what to do next, lessons and assignments by course),
                               lesson page, notebook page with iframe and Submit, Teach (/teach), Admin (/admin), My account
assignments/<id>/              example notebooks to import, one of them autograded (see Assignments below)
deploy/                        production stack, hub config, notebook images, scripts
dev.sh                         start everything: Postgres (:5433), JupyterHub (:8081), grader (:8090), backend (:8000), frontend (:3000)
dev-hub.sh                     start/stop only the local JupyterHub in Docker (dev.sh calls it)
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

After that, an admin manages accounts in the site, under **Admin** (top bar) > **Accounts**:

- **Add account**: the server generates the password and shows it once, in a box that stays open until
  the admin presses "I have noted it".
- **Edit**: the name and whether the account may use GPU notebooks. The username and the role are fixed
  (the account's notebook files are stored under a name made from its role and number).
- **New password** (in the row's ⋯ menu), for someone who forgot theirs: again generated and shown once,
  and the account is logged out everywhere.
- **Remove** (in the ⋯ menu): deletes the account with its submissions and grades, stops its notebook servers and ends
  its JupyterHub login. The files in its notebook home stay on the server.

Everyone changes their own password under **My account**, in the menu under their name at the top right (the current password is asked for
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

The **Gradebook** tab of each assignment lists every student the assignment is given to, when they
opened and submitted it, and their score. From there a teacher can open a submission in their own
notebook environment (a copy; the student's files are not touched), download it, give or change the
score, write a comment for the student, run the autograder again, and download the table as CSV.
**Save and next** saves a grade and opens the next submission waiting for one.

Read an opened submission, do not run it: it is a student's code, and in the teacher's environment it
would run with network access and with the teacher's files (other students' submissions among them) in
reach. The autograder is the safe place where submissions are run.

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
(11 MB) and a picture for a lesson (6 MB), which are only read after the account has been checked
(`LimitRequestSize` in `api/app/main.py`).

Lessons: every block is checked on the server before it is saved (known types only, length limits, at
most 200 blocks). A picture is accepted by how the file starts, never by its name, as PNG, JPEG, GIF or
WebP only (SVG can carry scripts and is refused), and is served only to people who may see that lesson.
Markdown is rendered without running any HTML written in it, and pictures from other sites are not
loaded. Videos are only ever embedded from YouTube's cookie-less player, the one other site the pages
may show in a frame (`frontend/next.config.ts`).

After 5 wrong passwords for one username from one network address, further logins for that username from
that address are refused for 15 minutes (`MAX_LOGIN_ATTEMPTS` in `api/app/auth.py`). `test/api/test_security.py`
attacks the login and the admin API: password guessing (also of the current password when changing it),
SQL injection, forged and planted cookies, oversized input, requests sent from other websites, and a
student asking for admin data or trying to create, change or remove accounts. `test_assignments.py`,
`test_courses.py` and `test_grading.py` do the same for the teacher API: students trying to upload,
grade themselves, read other students' submissions or see hidden tests. `test_lessons.py` checks that
students cannot write or read drafts, and that nothing they are sent gives away an answer.

The backend's JupyterHub token (`PLATFORM_HUB_API_TOKEN`) is only sent to the hub's own API, never to a
student's notebook server, where code the student runs could read it. To put a notebook into a
student's home, or take a submission out of it, the backend has the hub make a token that opens only
that one server for two minutes, and deletes it afterwards (`test/api/test_hub_client.py`).

Current limits: an assignment is one notebook file (no extra data files) and its file cannot be replaced
after upload. Every teacher manages every course and assignment. Only the newest submission of a student
is kept. Otter runs the student's code and the tests in one process, so a student's code can read the
hidden tests there and influence its own autograder score (the platform counts no question for more
than its points); when a score looks wrong, open the stored notebook from the gradebook and read it. Lessons can be given to all students or to one course, not to chosen students; two teachers
editing the same lesson at once overwrite each other; code is coloured where it is read, not while it is
written in the editor, and Markdown has no math formulas yet. Locally the "GPU" profile is simulated: same
checks, no GPU attached, and it uses the CPU image, so `import torch` fails unless you pass
`GPU_IMAGE=... ./dev-hub.sh`.

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
look above, light or dark as the device is set), **Halloween** (midnight purple and pumpkin orange,
with bats and a cobweb) or **Retro 95** (grey windows with bevelled edges on a teal desktop). The
choice belongs to the account (`users.theme`, saved with `PUT /api/auth/theme`, which only takes the
names in `THEMES` in `api/app/models.py`), so it follows the person to every device. The browser also
keeps it in a cookie, only so that a page is drawn in it from the first moment. A theme gives the
colour roles of `globals.css` other values and redraws a few pieces its own way, all in
`frontend/app/styles/themes.css`; the choices are listed in `frontend/lib/themes.ts`.

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
