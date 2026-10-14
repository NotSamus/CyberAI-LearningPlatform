psql postgresql://platform:dev-db-password@localhost:5433/platform

## Decisions
- Grading: use Otter-Grader (not nbgrader). The backend collects a student's notebook, grades it in an
  isolated container (never inside the backend, which can reach the database) and stores scores in Postgres. (2026-09-29)
- Grading runs in a separate `grader` service (grader/). It is the only service besides the hub with the
  Docker socket; the backend never has it. Each job gets a throwaway container of the student notebook
  image with no network, 2 GB, one CPU, five minutes. (2026-10-02)
- Notebooks, submissions and grades are stored in Postgres: there is no assignments folder on the server,
  and backing up the database backs them up. (2026-10-02)
- An assignment's folder in students' homes is `<title>-<id>`, so deleting an assignment and uploading a
  corrected one under the same title never hands students the old file. (2026-10-02)
- Size limits: 10 MB for an uploaded notebook, 20 MB for a submission, 1 MB for every other request. (2026-10-02)
- `./dev.sh --lan` opens the dev site to the local network. Plain http, for trusted testers and test
  accounts only; it makes new hub, OAuth and grader secrets on every start. (2026-10-02)
- Everything for teachers and admins lives under Settings (menu on the left); there is no separate Teach page. (2026-10-02)
- Lessons are written in the site as a list of blocks (text, code, callout, picture, video, notebook link,
  multiple choice, short answer), stored as JSON in Postgres with their pictures. Not a WYSIWYG editor:
  text is Markdown, as in notebook cells. (2026-10-13)
- A lesson has a working copy (saved as the teacher types) and a published copy (what students get).
  Students never see half-typed edits; "Publish changes" hands over the new version. (2026-10-13)
- Knowledge checks are checked on the server, three tries each, and are practice only: they never reach
  the gradebook. Students are never sent the answers before a question is closed. (2026-10-13)
- Videos in lessons come from YouTube only (cookie-less player); pictures are uploaded, never linked
  from other sites. (2026-10-13)
- No phone version of the site: it is made for iPad and desktop. (2026-10-13)
- Teaching tools move out of Settings into their own area again: the top bar becomes Home · Teach
  (teachers and admins) · Admin (admins), and My account moves to a menu under your name. Old
  /settings links redirect. This replaces the 2026-10-02 decision to keep teaching inside Settings. (2026-10-13)
- Brand: a navy top bar and login band with a cyan accent. Not UTEP's orange, and the UTEP name is
  not written in the site. (2026-10-13)

## How accounts, Settings and the JupyterHub panel work (2026-10-02)

### Running it locally
- Ports 3000/8000 are often used by other projects on this Mac. Run this one on other ports:
  `FRONTEND_PORT=3001 BACKEND_PORT=8001 ./dev.sh` (CyberP env active), then open http://localhost:3001.
- Ctrl+C in that terminal stops everything. Database contents and notebook files are kept.

### The JupyterHub panel (Settings > JupyterHub)
- It is JupyterHub's own admin panel. It lists one row per notebook server, and each user has up to
  three: an unnamed default one, plus `cpu` and `gpu`. Three rows with the same name are one user.
- Hub names: `s-<id>` is a student, `t-<id>` is a teacher. The Accounts table shows each account's
  hub name in the "Notebook user" column. My admin account is `t-1`.
- `s-1` is a leftover from before login existed, when everyone was one hard-coded stand-in user.
  No account maps to it now. Its old files are in the Docker volume `jupyterhub-user-s-2d1`, and
  `python-basics/lab1.ipynb` in there has my own edits (saved Sep 25). Removing the `s-1` hub entry
  does not delete those files. Not removed yet.
- Buttons to be careful with:
  - Shutdown Hub: stops every notebook for everyone.
  - Add Users: creates a hub-only user who cannot log in to the site. Do not create students there.
  - Edit User: changes get overwritten the next time that person opens a notebook.

### Creating accounts
- Students and teachers: Settings > Accounts > Add an account (username, full name, role, GPU).
- The server generates the password and shows it once. Only its hash is stored, so it cannot be
  shown again. Hand it over right away.
- Command line only (run from `api/`), because these need access to the server itself:
  - `python -m app.manage create-user admin --role teacher --admin` (the first admin)
  - `python -m app.manage set-admin <username>` (or `--remove`)
  - `python -m app.manage set-password <username>` (forgotten password; logs them out everywhere)
  - `python -m app.manage list-users`
- Editing and removing accounts, new passwords, and changing your own password are built now: see the next section.
- On the UTEP server: create the first admin with the command line once, then add everyone else
  from Settings. Steps are in `deploy/README.md`. Accounts on my laptop are not copied to the server.

### Settings button
- Shown in the top bar for everyone; the page is `/settings`, with a menu of the sections that account has.
- The server checks the admin and teacher flags from the database on every request. The browser is
  never trusted for it: a student calling the API directly gets 403 with no data.

### Security that is in place
- Passwords stored only as Argon2 hashes. Session cookie cannot be read by page scripts, HTTPS-only on the server.
- 5 wrong passwords for a username from one network address, then a 15-minute lockout. The counters
  are in the backend's memory, so restarting the backend clears them.
- Any change (login, logout, creating accounts, starting notebooks) must come from the site's own
  pages. Requests from another address, including the hub's (where student notebook code runs), get 403.
- On the server the session cookie has a prefix so it can only be set by the exact site address.
- Logging in or out also ends the browser's JupyterHub session, so the next person on a shared
  computer does not get the previous person's notebooks. People still need to log out on shared machines.

### Things to get right on the server
- `APP_ORIGIN` in `deploy/.env` must be exactly the address people type to reach the site, or every login is refused.
- The site and the hub addresses must share a parent domain (for example both under `utep.edu`).
- Use a long, unique admin password on the server, not the local one.
- If UTEP puts its own proxy in front of the server, see the lockout note in `deploy/README.md`.

## Settings menu, upload limit, network mode and the learning features (2026-10-02)

### Settings menu
- One Settings button for everyone; the Teach button is gone. The menu on the left shows only the
  sections that account has:
  - Assignments, Courses, Announcements: teachers and admins
  - Accounts, JupyterHub: admins
  - My account: everyone
- The menu only hides links. Every section's data comes from the API, which checks the account each time.

### Upload limit
- A notebook upload is at most 10 MB. A submission is at most 20 MB. Every other request is capped at 1 MB.
- An upload is only read after the account has been checked, so a non-teacher cannot push a big file at the server.

### Letting other devices on my network use it
- `FRONTEND_PORT=3001 BACKEND_PORT=8001 ./dev.sh --lan`, then open the address it prints
  (on this Mac it was `http://192.168.1.9:3001`).
- Use that address on the Mac too: logging in at `localhost` is refused in this mode.
- Plain http: use test accounts only. A real password would cross the network unencrypted.
- Campus and guest Wi-Fi often block device-to-device connections, and a VPN may too.
- The site and the notebooks share one address in this mode, so it is for people I trust, not for a class.
- Normal `./dev.sh` is localhost only and exposes nothing.

### What students see
- Home page: announcements on top, then assignments grouped by course. Each assignment shows its status:
  Not started, Opened, Overdue, Submitted, Grading, or the score.
- Submit takes the notebook as it is saved at that moment (JupyterLab saves every 30 seconds here; the
  button reminds them to save). Submitting again replaces the earlier submission and its grade.
- A submission after the due date is accepted and marked late.

### Grading
- A notebook written in Otter's "Otter Assign" format is autograded. Otter makes the students' version
  (no solutions, public tests only) at upload, and refuses the upload if my own solutions fail my tests.
  Example to start from: `assignments/otter-example/functions.ipynb`. Run every test cell before
  uploading: the value a test cell shows is what Otter expects.
- Any other notebook is graded by hand.
- Students see their score per question and whether each question's public tests passed (the details
  are in their notebook, with grader.check). The platform never shows them the hidden tests or Otter's
  report, but Otter runs their code next to the tests, so their code could read the hidden tests and
  sway its own score: open the notebook when a score looks wrong.
- A live run graded in about five seconds, and a hidden test caught a bug the public tests missed.
- Gradebook: "Progress and grades" on each assignment. Per student: opened, submitted, score. I can
  open or download a submission, set a score, leave a comment, rerun the autograder, export CSV.
- Opening a submission puts a copy in my own notebook environment. Read it, do not run it: it is
  student code and would run with my files in reach. The autograder is the safe place to run it.

### Courses, announcements, accounts
- Courses group students. An assignment or announcement given to a course reaches its students,
  including ones added later. Deleting a course keeps its assignments, given to nobody.
- Accounts (admins): edit name and GPU, issue a new password (shown once), remove an account.
  Removing stops that person's notebook servers and deletes their submissions; their notebook files stay.
- Everyone changes their own password under Settings > My account.
- Admin accounts stay command-line only: the site cannot give admin rights, reset an admin's
  password, or remove an admin.

### Limits right now
- Every teacher manages every course and assignment.
- Only a student's newest submission is kept.
- An assignment is one notebook, no data files, and its file cannot be replaced after upload.
- GPU assignments are graded without a GPU.

### Not verified yet
- The embedded notebook view in network mode (opening the notebook directly at the network address worked).
- The 30-second autosave and the removed "Jupyter news" pop-up in a fresh student server.

### On the UTEP server, in this order (details in `deploy/README.md`)
1. Build both notebook images; they now include Otter.
2. Add `GRADER_TOKEN` to `deploy/.env` (`openssl rand -hex 32`).
3. `docker compose up -d --build`
4. Run the migrations.
- The grader service holds the Docker socket (root on the server). It has no database access and only
  the backend can reach it.
- JupyterHub used to keep accepting an old API token after a new one was set. It now forgets old ones
  when it starts, so changing the token in `deploy/.env` really replaces it.

### Trying it locally
- Log in as `admin` at http://localhost:3001. Under Teach > Assignments there is a draft
  "Functions lab (autograded example)": publish it, open it, submit.

## Lessons (2026-10-13)

### Where things are
- The project folder is now `~/Desktop/CyberAI-LearningPlatform` (a git repository, on GitHub).
- Teach > Lessons: list, "New lesson", order arrows, a Progress tab per lesson. The editor is at
  `/teach/lessons/<id>`, the page students read at `/lessons/<id>`.
- Backend: `api/app/lessons.py` (rules), `api/app/lesson_routes.py` (routes), migration
  `sql/versions/2026_10_13_1301-96f8b8967047_lessons.py` (tables `lessons`, `lesson_images`,
  `lesson_progress`, `lesson_answers`). Frontend: `components/LessonEditor.tsx`, `LessonBlocks.tsx`,
  `LessonReader.tsx`, `Markdown.tsx`, `lib/lessons.ts`.
- New frontend packages: `react-markdown` 10.1.0 and `remark-gfm` 4.0.1 (exact versions).

### Writing fast
- Autosave, no Save button. `/` on an empty line of a text block opens the block menu.
  Ctrl/Cmd+Enter adds a text block below. Enter adds a quiz option, `*` in front ticks it as correct.
- Paste or drop a picture anywhere. "Write or paste a whole lesson as text" turns text into blocks
  (`?? question`, `- [x]` correct, `- [ ]` wrong, `= accepted answer`, `> explanation`).

### The list of lessons and the index of topics (2026-10-13)
- Beside the editor: every lesson with its status, click to switch, "New lesson…" to start one.
  `components/LessonRail.tsx`. It asks the server again when the window is come back to.
- Headings written with `#`, `##`, `###` in text blocks are the lesson's topics. They show under the
  current lesson in that list, and as "In this lesson" on the page students read
  (`components/Outline.tsx`, `outline()` in `lib/lessons.ts`). No change on the server.
- The page students read has the same kind of menu on its left: the lessons of that course with the
  reader's progress, and the topics of the lesson being read (`components/LessonMenu.tsx`,
  `LessonList.tsx`). It is there even when a lesson has no headings.
- On an iPad the lists move above the editor (below 1360 px wide) and under the lesson's title (below 1100 px).

### The look of the site (2026-10-13)
- All styling is in `frontend/app/globals.css`, rewritten on scales after "Refactoring UI": spacing,
  text sizes, two weights, one radius, three shadows, colours by role with a dark version. New values
  are not invented: the nearest step is used.
- Cards stand out by a shadow instead of an outline; fields have a darker outline (3:1); badges are
  filled tints; deleting is a quiet red word; numbers in tables are right-aligned; lesson text is kept
  to about 75 characters a line.
- Fixed on the way: form tick boxes had picked up the knowledge check's card style (both used the
  class `check`; the knowledge check is now `quiz`), and text typed into fields was bold.

### Limits right now
- A lesson goes to all students or to one course, not to chosen students.
- Two teachers editing the same lesson at once overwrite each other (last save wins).
- Headings written inside a quote or a list, or underlined with `===`, are not in the index.
- No math formulas in Markdown. Code is coloured where it is read, not while it is typed in the editor.
- Pictures taken out of a lesson are deleted from the database at the next Publish (after an hour).

### Not verified
- Dropping a picture file and choosing one with the file button, in a real browser (pasting was tested).
- The frontend's production build was only run in Docker on the Mac, not on the server.

### Still to do in the repository (2026-10-13)
- `.gitignore` had `lib/` (from the Python template), which also ignored `frontend/lib/`: `api.ts`,
  `dates.ts`, `errors.ts`, `useMe.ts` and `lessons.ts` were never on GitHub, so a fresh
  clone could not build the frontend. `.gitignore` now has `!frontend/lib/`. Still to do: commit that
  folder and push.
- `notes.md` got committed in this repository (it was ignored in the old folder). `.gitignore` ignores
  it again, but git keeps following a file it already has: `git rm --cached notes.md` and commit.
  The copies already pushed stay in the GitHub history (nothing secret is in them).

### On the UTEP server
- `git pull`, `docker compose up -d --build`, then run the migrations (new tables).

### Running it locally
- `conda activate CyberP` first: `dev.sh` needs `alembic` and `uvicorn`, which are not in the base environment.

## The redesign: Teach and Admin areas, and the polish (2026-10-13)

### Where things are now
- Top bar: Home · Teach (teachers, admins) · Admin (admins), and a menu under my name with My account
  and Log out. Teachers land on Teach > Overview after logging in.
- Teach: Overview (to grade, due soon with counts, needs attention, courses) · Courses (each with
  Content, Students and Announcements tabs) · Lessons (editor with Write | Progress tabs) · Assignments
  (Upload notebook page; each assignment has Gradebook | Settings tabs) · Announcements.
- Admin: Accounts · JupyterHub. My account: `/account`.
- Old `/settings/...` links are sent on to the new pages (temporary redirects in `frontend/next.config.ts`).
- The overview's counts come from the server: `counts` on each item of `GET /api/teach/assignments`
  (`assignments.counts()` in `api/app/assignments.py`); only students the assignment is given to count.

### How it looks
- Navy bar with a cyan spark (only on the navy), the same navy band behind the login card.
- Status chips with an icon and a word in five tones (green, blue, grey, yellow, red). Yellow is new:
  due soon, changes not published, "try again". Red is only late, failed, wrong and deleting.
- One page header everywhere; one filled button per page; rare or destructive actions in a ⋯ menu.
- Icons: `lucide-react` 1.48.0 (exact version), sized by the CSS.
- Styles in three files: `globals.css` (shared), `styles/teach.css`, `styles/learn.css`.
- Student Home: Up next (the one thing to do now, then three more), Due soon, announcements, each
  course with one progress bar. Lessons: header with "Lesson 2 of 3", reading time, checks progress,
  dark code blocks with Copy, callouts with icons, knowledge checks as option cards with "Try 2 of 3",
  and a completion panel without reloading.
- Gradebook: "Save and next", the score says what it is out of. Dates leave out the year when it is this year.

### Checked
- In the dev browser at 768, 1024 and 1440 px wide, light and dark: every page of Home, a lesson,
  an assignment, Teach, Admin, My account and login.
- Tried: answering checks (wrong, out of tries, right), completing a lesson, grading with "Save and
  next", posting an announcement, adding an account (the password box stays open through Escape),
  uploading a notebook by dropping it, a failed lesson save (the corner notice and Try again), and the
  old /settings links. The production build (`frontend/Dockerfile`) passes; 104 backend tests pass.

### Not verified
- Not on a real iPad. The 48 px touch size of icon buttons was not seen (the dev browser only acts as
  a touch screen below 768 px).
- Choosing a picture or notebook with the file picker in the new drop areas (dropping was tested).
- A knowledge check with several right answers (check boxes) in its new look.
- If `/api/me` fails with an error other than "not logged in", Home, Teach and Admin stay on
  "Loading…" or blank, with no message.

## Themes (2026-10-14)
- My account > Appearance: Standard, Halloween, Retro 95. Saved per account on the server
  (`users.theme`, migration `2026_10_14_0010-3b7e5c1d9a24_account_theme.py`, `PUT /api/auth/theme`),
  mirrored in a `cyberai_theme` cookie so the first paint is right (`app/layout.tsx`).
- Colours and the retro bevels are in `frontend/app/styles/themes.css`; the list in `frontend/lib/themes.ts`.
- On the server: `git pull`, `docker compose up -d --build`, then run the migrations (new column).
- Checked in the dev browser at 1024 px: account page, Home, a lesson, the editor, assignments,
  gradebook, a menu, a dialog and login, in both themes.

## Tests, lint and code colours (2026-10-14)
- **Remember: the test suite must never get to the platform's database** (said 2026-10-14). The tests
  run on their own Postgres (`deploy/docker-compose.test.yml`, port 5434, in memory); `test/conftest.py`
  sets `DATABASE_URL` to it before the app is imported and stops if it is the platform's Postgres.
- `./check.sh` (CyberP active, Docker running): ruff, the tests on that Postgres, tsc, ESLint.
- Lint: ruff 0.16.10 (in CyberP, listed in `api/requirements-dev.txt`, rules in `ruff.toml`); ESLint 9.39.5
  with eslint-config-next 15.5.25 (`frontend/eslint.config.mjs`, `npm run lint`). Both found almost
  nothing: two unused imports in tests.
- Code colours: `lowlight` 3.3.0 and `rehype-highlight` 7.0.2 (exact versions), `frontend/lib/highlight.ts`;
  colours per theme in `learn.css` / `themes.css`.

