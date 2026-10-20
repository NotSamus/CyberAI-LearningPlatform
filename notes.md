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
- Admin rights are given in the site after all: an admin makes a teacher an admin, or takes the rights
  from another admin, after typing their own password. Students are never made admins, and nobody takes
  away their own. This replaces the 2026-10-02 decision to keep admin rights command-line only. (2026-10-19)

## How accounts, Settings and the JupyterHub panel work (2026-10-02)

### Running it locally
- Ports 3000/8000 are often used by other projects (MaLLM's backend is on 8000). Since 2026-10-14 the
  backend starts on 8003 and `dev.sh` moves it to the next free port by itself. If 3000 is taken:
  `FRONTEND_PORT=3001 ./dev.sh` (CyberP env active), then open http://localhost:3001.
- Run `./dev.sh` with `CyberP` active, not `(base)`: `(base)` has no uvicorn or alembic, so the backend
  never starts and every page shows ECONNREFUSED errors for `/api/...`.
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
- On iqsec.cs.utep.edu only SSH (22) gets through the firewall; Docker's 8081 does too, Next.js's 3000
  does not. From my Mac (on the VPN): `./dev-tunnel.sh iqsec.cs.utep.edu` starts dev.sh there and
  shares it at my Mac's address. Stop any ./dev.sh already running on the server first. (2026-10-14)
- `FRONTEND_PORT=3001 ./dev.sh --lan`, then open the address it prints
  (on this Mac it was `http://192.168.1.9:3001`).
- Use that address on the Mac too: logging in at `localhost` is refused in this mode.
- Plain http: use test accounts only. A real password would cross the network unencrypted.
- Campus and guest Wi-Fi often block device-to-device connections, and a VPN may too.
- The site and the notebooks share one address in this mode, so it is for people I trust, not for a class.
- Normal `./dev.sh`: the site and the hub listen on this Mac only (127.0.0.1); the backend on every
  address (on Linux the hub container needs that), with secrets made new on every start. Before
  2026-10-19 the hub's 8081 was open to the network with the hub token written in the repository.

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
  password, or remove an admin. (No longer so since 2026-10-19: the site gives and takes admin rights and
  resets another admin's password, see the sections of that day. Removing an admin still needs the rights gone first.)

### Limits right now
- Every teacher manages every course and assignment.
- Only a student's newest submission is kept.
- An assignment is one notebook, no data files, and its file cannot be replaced after upload.
  (Since 2026-10-19: it can, until the first student opens it. See that day's section.)
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


## Calendar and timeline on Home (2026-10-19)
- Home has a column on the right: a calendar of this year and a timeline of what is due. The lists
  moved left of the middle of the screen to make room (the page is as much wider as the column).
- Calendar (`components/learn/Calendar.tsx`): today's date, "Day 292 of 365" with a bar, and one
  month at a time, January to December of this year only (arrows, "Back to today"). Today is a filled
  circle, the days of the year gone by are grey, and a day something is due has a dot: red overdue,
  yellow less than two days left, green handed in, blue otherwise (grey: a draft, for teachers).
  Clicking a marked day scrolls the timeline to it; the page itself does not move.
- Timeline (`components/learn/Timeline.tsx`): for a student, what is overdue and not handed in (at
  the top), then every assignment still to come, by day ("Today", "Tomorrow", "Fri, Oct 23"), with
  the time, the course and "Submitted" or the score. For a teacher: what is still to come, drafts
  marked. Only assignments have dates, so lessons are never in it.
- The day moves on by itself at midnight, and when the tab is come back to (`lib/useToday.ts`).
  Today is only worked out in the browser: the server may be in another time zone or day.
- iPad held upright (below 1024 px): the calendar and the timeline stand side by side above Up next,
  the timeline as tall as the calendar and scrolling. 1024 px and wider: the column on the right,
  staying in view while the lists scroll.
- The column is 256 px at every width, also on 1080p screens: it was tried at 320 and 384 px, but
  320 is off the spacing scale and the timeline needed no more room (at 256 only a long title wraps).
  The space left on wide screens stays empty, as "Refactoring UI" says (use the width the content needs).
- It is kept quieter than the lists, so they come first: no card and no shadow, only a thin line on
  the page; "Timeline" is a small grey label, and today's date is no larger than body text. 24 px
  between the calendar and the timeline. In Retro 95 both are small grey windows.
- Frontend only: no server or database change. On the UTEP server: `git pull`, `docker compose up -d --build`.

### Checked
- In the dev browser at 768, 1024 and 1440 px, light and dark, and in Halloween and Retro 95, with
  made-up assignments fed to the page (overdue, today, tomorrow, two on one day, handed in, a draft,
  no due date): as a student and as a teacher. The production build passes; tsc and ESLint are clean.

### Not verified
- With real accounts and real due dates (the dev database has no assignment with a due date).
- On a real iPad, and the midnight change of day (only the code that does it was read).

### Open question
- "Due soon" and the timeline now show much the same assignments. Due soon could go, or the
  timeline could leave out what Up next lists.

## Admins reset other admins' passwords (2026-10-19)
- Admin › Accounts › ⋯ › New password now works on other admins' accounts too. This replaces the
  2026-10-02 rule that admin passwords are set only on the server. (Admin rights: see the next section.)
- For an admin's account the site first asks for your own password (`auth.confirm_password`, the same
  check My account uses: 5 wrong tries from one address, then 15 minutes' wait). That way a browser
  left logged in, or a login taken through a student's notebook in `--lan` mode, cannot lock the other
  admins out. Your own account is not reset there: My account asks for your current password.
- Files: `reset_password` in `api/app/admin.py` (body `{"your_password": ...}`, only needed for an
  admin's account), `confirm_password` in `api/app/auth.py` (change_password uses it too),
  AdminPasswordDialog in `frontend/app/admin/accounts/page.tsx`, test
  `test_another_admins_new_password_needs_your_own` in `test/api/test_security.py`.
- Fixed on the way, in `components/Dialog.tsx`: no dialog ever focused its first field. A field's
  autoFocus ran before the dialog was shown, so the browser focused the Close button, and a space typed
  into "the field" closed the dialog. The contents now go in once the dialog is open.
- Checked: `./check.sh` (113 tests, ruff, tsc, ESLint). In the browser at 1024 px with answers faked in
  the page: focus in Add account, Edit and the new dialog; wrong password shows the message, right one
  shows the new password once; your own row's New password is greyed out.
- Not verified: against the real backend in a browser (no admin password at hand; the API is covered
  by the tests). On the server: `git pull`, `docker compose up -d --build` (no migration).

## Admin rights from the site (2026-10-19)
- Admin > Accounts, a teacher's ⋯ menu: **Make admin**. An admin's ⋯ menu: **Remove admin rights**
  (greyed out on my own row). Both open a small dialog that asks for my own password, then reload the list.
  Replaces the 2026-10-02 decision that admin rights are command-line only; `set-admin` still works too.
- Rules, all on the server (`set_admin` in `api/app/admin.py`, `PUT /api/admin/users/{id}/admin` with
  `{admin, your_password}`):
  - only teachers are made admins (a student: 400); nobody takes away their own rights (403);
  - the acting admin's password is checked with `auth.confirm_password` (also used by the change of an
    admin's password in the main checkout). 5 wrong guesses from one address, then 15 minutes of 429,
    shared with every other password typed again (see "After the security review" below);
  - taking rights away locks the admins' rows first, so two admins taking each other's rights at the same
    moment cannot leave the site with no admin: the second finds its own rights gone (403).
- It takes effect on the next request: the admin flag is read from the database every time, so the
  teacher does not log in again. JupyterHub decides who is a hub admin at hub login: on this branch
  teachers are hub admins anyway, but with `claude/security-fixes` only platform admins are, so there a
  change made here reaches the hub at that person's next hub login.
- An admin still cannot be removed from the site, but now the rights can be taken away first, then the
  account removed. Students made admins on the command line can lose the rights in the site too.
- Tests in `test/api/test_security.py` ("admin rights from the site"): student refused, missing or wrong
  password, guesses cut off, the teacher gets the admin pages in the login they already had, non-admins
  403, own rights refused, and the two-admins race (the test fails without the re-check).
- No database change. On the UTEP server: `git pull`, `docker compose up -d --build`.

### Checked
- In the dev browser at 768, 1024 and 1440 px, light and dark, with made-up accounts fed to the page
  (no admin password at hand): the ⋯ menu of a teacher (Make admin), of another admin (Remove admin
  rights), of my own row (greyed out) and of a student (no entry); the dialog with a wrong password (the
  message shows under it) and with the right one (the list reloads, the Admin chip comes or goes).
- Only the frontend ran from the worktree (port 3002, against the backend already running), not
  `dev.sh`: stopping `dev.sh` runs `docker compose down` on the dev Postgres, hub and grader, which
  the main checkout was using at the time.

### Not verified
- In a browser against the real backend (the route itself is covered by the tests).
- The cursor in the password field when the dialog opens, with the `Dialog.tsx` fix from the section
  above (the fix came in with the merge; it was not tried in the browser on this branch).

### After the security review (2026-10-19)
Finding 5 of the privilege-escalation review (another admin's new password), on this branch after
merging master into it:
- One guess limit for every password typed again by someone already logged in: My account, another
  admin's new password and admin rights all use `auth.REAUTH`. A stolen admin session gets 5 guesses in
  all per 15 minutes, not 5 on each of those pages.
- Any new password (a student's too) also stops that account's notebook servers and ends its hub login
  (`hub_client.delete_user`, as removing an account does; files stay, the hub account is made again at
  the next notebook). If the hub is down the password is still reset and shown, with a note that open
  notebooks stay open: getting back into a locked-out account must not wait for the hub.
- The backend logs "Admin X gave the admin Y a new password" and "Admin X made an admin: Y" / "took admin
  rights from Y" (warnings, in `docker compose logs backend`). No table for it yet.
- The tests can no longer reach a real JupyterHub: an autouse fixture in `test/conftest.py` makes every
  hub call a test has not faked fail as if the hub were down. Before, a reset in a test without the
  `no_hub` fixture would have gone to the dev hub on :8081 with the dev token.
- Checked: ruff, 120 tests, tsc, ESLint (the tests on a private Postgres on :5435, because another
  session was using the shared test one on :5434). Not tried in the browser: the hub note under the password.

### Merging
- Master (`8cc11ff`) is merged into this branch, with the conflicts in `README.md`, `notes.md` and
  `frontend/app/admin/accounts/page.tsx` resolved here. Merging this branch into master afterwards is
  then a fast-forward, if master has nothing newer.
- The "usernames-only" session changes the add and edit dialogs, `NewAccount`/`AccountChanges` and
  `manage.py`; this work does not touch them. Two comments in `test_security.py` it may edit still say admin
  rights cannot be given from the browser (`test_admin_creates_a_student_account` and the PATCH in
  `test_admin_edits_resets_and_removes_accounts`): both remain true for those routes, but read oddly now.

## Exporting students' progress and grades (2026-10-19)
- Teachers export students as Excel (.xlsx) or CSV: **Export** on a course's Students tab (that
  course), and **Export** on Teach > Courses (every student). A secondary button with a menu, so each
  page still has one filled button at most. `frontend/components/teach/ExportMenu.tsx`.
- Made on the server (`api/app/exports.py`, routes `/api/teach/students.csv|xlsx` and
  `/api/teach/courses/<id>/students.csv|xlsx`): teachers and admins get it, students 403, logged out 401.
- Decided with me: teachers may export every student, not only admins (every teacher already sees
  every course and gradebook). The layout below was agreed before it was built.
- One row per student, by username only (no real names, per the usernames-only policy). Columns:
  Course(s); Lessons completed / given; Checks answered (any try, as on a lesson's Progress tab) /
  correct / given; per assignment, soonest due first, a status (not started, opened, submitted, late =
  handed in after the due date with no grade yet, graded, graded late, could not be graded) and a score
  "(of N)"; then Assignments submitted / given, Total score, Total out of. Totals count graded work
  only, so score / out of is a running grade.
- Published lessons and assignments only. A course's file: its own lessons and assignments plus those
  for every student. Every student's file: everything; cells left empty where an assignment was not
  given to that student. Assignments given one by one are only in the file of every student.
- Excel: one sheet for a course; for every student "All students" (same as the CSV) plus a sheet per
  course. Bold header, header and usernames frozen, filters on. Names like `cs-101-students-2026-10-19.xlsx`.
- CSV is UTF-8 with a byte order mark (Excel). Cells starting with = + - @ tab or CR get a `'` in front;
  in the Excel file such text is stored as text (never a formula) and keeps no quote.
- New backend packages: `openpyxl` 3.1.5 and its `et-xmlfile` 2.0.0 (exact versions in
  `api/requirements.txt`, installed in CyberP). On the server: `git pull`, `docker compose up -d --build`;
  no migration.

### Checked
- 6 new tests (`test/api/test_exports.py`): 401/403/200 for logged out, students, a teacher and an
  admin; a course's file has only its students and what they were given; the whole platform's CSV and
  workbook row by row, opened with openpyxl; formula-looking titles and course names; sheet names.
  All 118 backend tests, ruff, tsc and ESLint pass. Both Docker images build.
- In the dev browser at 768, 1024 and 1440 px, with made-up data fed to the pages: the Students tab and
  Teach > Courses, the menu open, its two links.

### Not verified
- Downloading a real file through the site while logged in (no teacher password in the dev database
  at hand); the routes were only tried logged out through the dev site (401) and in the tests.
- Opening the files in Excel itself, and in Numbers or Google Sheets (only openpyxl read them). Excel
  may show the `'` in front of a formula-looking CSV cell instead of hiding it.
- Large classes: everything is read in a few queries, but it was only tried with a handful of students.

### Limits
- Two assignments with the same title get columns with the same names.
- In the file of every student, a published assignment given to nobody is still there, as empty columns.

## CPU and memory limits in deploy/.env (2026-10-19)
- Notebook servers and grading jobs take their limits from `deploy/.env` now, with the old values as
  defaults: `CPU_PROFILE_CPUS`/`CPU_PROFILE_MEM` (1, 2G), `GPU_PROFILE_CPUS`/`GPU_PROFILE_MEM` (4, 12G),
  `GRADER_MEMORY` (2g), `GRADER_TIMEOUT` (300 s), `GRADER_PARALLEL` (2). Read in
  `deploy/jupyterhub/jupyterhub_config.py` (PROFILES) and `grader/main.py`; passed in `deploy/docker-compose.yml`.
  A server whose `deploy/.env` has none of them keeps today's limits.
- Caps, not reservations. One person's assignments all share one CPU server, and each open notebook
  keeps its kernel until shut down, so memory runs out first. Nothing stops idle kernels yet (only the
  hub's 30-minute idle / 4-hour culler stops whole servers).
- Apply: `docker compose up -d jupyterhub grader`; running servers keep old limits until they restart.
- Checked: hub config compiles, PROFILES picks up overrides and treats empty values as defaults,
  `docker compose config` renders with and without the new lines. Not tried on a running hub.

## Security fixes from the privilege review (2026-10-19)
Review: findings 1, 2 and 4 fixed here (branch `claude/security-fixes`); 5 went to the admin-rights
session; 3 (one address for every notebook server) needs a wildcard DNS name and certificate from UTEP IT.
- `./dev.sh` makes new hub, OAuth and grader secrets on every start, not only with `--lan`. Without
  `--lan` the site and the hub listen on this Mac only (`LISTEN_ADDRESS`, default 127.0.0.1); the
  backend still listens on every address (on Linux the hub container reaches it that way).
  `dev-tunnel.sh` passes `LISTEN_ADDRESS=127.0.0.1`, so on iqsec the hub's 8081 no longer gets through
  the firewall: the tunnel reaches it on the server's own localhost.
- Teachers are no longer JupyterHub admins; platform admins still are (`jupyterhub_config.py`,
  `_hub_admins`). JupyterHub's admin role opened every notebook server to every teacher.
- Autograding: when a notebook is uploaded, Otter also grades the students' version with nothing
  answered, which gives each question's real points (`assignments.question_points`, new migration).
  A submission's results are checked against those: only those questions count, none for more than
  its points, and the gradebook says "Look at this notebook before trusting its score" when the results
  claimed other questions or points. Uploading an autograded notebook takes one more Otter run.
  Older assignments get their points when their next submission is graded.
- Checked: Otter 7.0.0 in the notebook image grades the unanswered `otter-example` students' version
  without stopping (q1 out of 2, q2 out of 3).
- On the server: `git pull`, `docker compose up -d --build`, run the migration; teachers lose hub admin
  at their next hub login (or untick it in Admin > JupyterHub). Steps in `deploy/README.md`.

## Students have only a username; made-up usernames (2026-10-19)
- **Decision: the platform stores no real name for a student, only a username.** Teachers keep their
  names (shown to their students). A student's `display_name` is their username.
- One rule for it, `auth.check_name()` in `api/app/auth.py`: a name for a student is refused when an
  account is created (site and command line) and when one is edited (`PATCH /api/admin/users/<id>`), 400
  "Students have no name here, only a username."
- Made-up usernames like Xbox gamertags: adjective + noun + 2 to 4 digits (`swiftfalcon482`), from the
  word lists in `api/app/usernames.py` (70 x 70 words). No people, bodies, skin colours, violence, or
  animals with a second meaning; joined pairs are checked against a list of rude strings (`BLOCKED`, also
  69 / 88 / 420 / 666 in the digits) by `test/api/test_usernames.py`. Never one that is already taken.
  - Site: `GET /api/admin/username-suggestion` (admins only). Admin > Accounts > Add account starts on
    Student with a suggestion filled in; the dice beside Username makes another; it can be typed over.
    Choosing Teacher takes an untouched suggestion out and shows "Full name". Role is now the first field.
  - Command line: `python -m app.manage create-user --random [--gpu]` prints the username it made.
    `--name` is refused for students.
- Edit for a student shows only "GPU notebooks". Tables (Accounts, gradebook, lesson progress), the
  student picker and My account show a student's username once instead of "name (username)".
- The gradebook CSV keeps its Name column: for students it holds the username.
- No database change: the `display_name` column stays, for teachers.

### No migration for existing students
- Not needed: there are no real students yet (said 2026-10-19), so no stored student has a real name to
  clear. Every student added from now on gets none. The dev database's one test student still has the
  name it was made with; remove it in Admin > Accounts, or leave it (it is test data).

### Checked
- `ruff`, the tests (117 pass, on the test Postgres, 5434), tsc and ESLint.
- Admin > Accounts in the dev browser at 768, 1024 and 1440 px, light and dark, with made-up accounts
  fed to the page: Add account as a student (suggestion, dice, sent without a name), switching to Teacher
  and back, the password box, Edit for a student and for a teacher.

### Not verified
- Against the real backend in the browser (the page was fed made-up answers), and on a real iPad.
- The gradebook, lesson progress, student picker and My account pages were not opened after the change
  (one-line changes, type-checked).
- When Add account opens, the focus is on the dialog's Close button, not on Username (React's autoFocus
  runs before the dialog is shown). Fixed separately in `components/Dialog.tsx` in the main checkout;
  this work leaves Dialog.tsx alone, so it is fixed once both are merged.
- The confirm boxes for New password and Remove still say "quietorca58 (quietorca58)" for a student.

## GPU notebooks turned off for now (2026-10-19)
- **Decision: GPU notebooks are off for the whole platform until we come back to them.** The options
  stay: "GPU notebooks" on accounts and "Needs a GPU" on assignments can still be set and are stored.
- One setting, `GPU_NOTEBOOKS` (`off` when not set, `on` turns them back on), read by the backend
  (`api/app/config.py`) and by the hub (`deploy/jupyterhub/jupyterhub_config.py`). Passed to both in
  `deploy/docker-compose.yml` and to the dev hub in `deploy/docker-compose.dev.yml`; in `.env.example`.
- While off:
  - A GPU assignment opens, is submitted and stopped in the standard (CPU) environment
    (`_server_for` in `api/app/jupyter/launch.py`). Both servers share one home, so students keep
    the same file when GPUs come back. Chosen over refusing to open GPU assignments; refusing would be
    a one-line change in `_server_for`.
  - The hub refuses to start any GPU server, even asked directly ("GPU notebooks are turned off for now.").
    Needed because teachers pass the hub's GPU check through the `teachers` group.
  - `/api/me` has `gpu_notebooks: false`. Students do not see "GPU" on those assignments (Home, the
    assignment page). Beside the GPU options in Accounts and in the assignment form: "turned off for now".
  - Hub groups are unchanged (the `gpu` group is still given), so turning it back on needs nothing else.
  - Grading unchanged: GPU assignments were already graded in the GPU image without a GPU.
  - In the CPU image `import torch` fails, so a GPU notebook that needs PyTorch will not run until GPUs
    are back.
- To turn them on: `GPU_NOTEBOOKS=on ./dev.sh`, or `GPU_NOTEBOOKS=on` in `deploy/.env` and
  `docker compose up -d --build` on the server (the hub's config is built into its image).

### Not verified
- The hub's refusal was not tried on a running hub (no test can load `jupyterhub_config.py`); only
  read and linted. The dev hub picks it up the next time `./dev.sh` starts it (`up --build`).
- Checked: 118 tests pass (new: a GPU assignment opens and stops on the CPU server while off, and on
  the GPU server when on), ruff, tsc, ESLint. In the dev browser (made-up data, light, one width): the
  note beside "Needs a GPU" on Upload notebook and beside "GPU notebooks" in Add account.
- Not looked at: the assignment Settings tab, Edit account, and what students see (Home, assignment page).

## Exporting and importing lessons as a .zip (2026-10-19)
- A lesson's ⋯ menu (list and editor): **Export as .zip**. Teach > Lessons: **Export** beside "Show" takes
  the lessons the list shows, in that order (choose a course to get its lessons). **Import** beside New
  lesson, and in the empty list, so a new server starts from it. Asked for so lessons can be moved (laptop
  to the UTEP server) or kept and brought back.
- In the file: `lessons.json` (order, format version 1), a folder per lesson (`lesson.json` + `images/`),
  `notebooks/<slug>/<file>.ipynb` for each linked assignment, `README.txt`. Blocks name their picture or
  notebook by its path in the .zip, never by an id. Layout is in `api/app/lesson_zip.py` and README.md.
- Decided while building (not asked):
  - The **working copy** is exported (what the editor shows, unpublished edits included), not the
    published version. Imported lessons are **drafts**, after the others, for whom the Import dialog says
    (nobody by default). Nothing students did goes in the file.
  - Linked notebooks travel with the lessons, as the teacher uploaded them: an autograded one **with its
    solutions and hidden tests**. The file is for teachers; the hint on Export and the README.txt say so.
  - On import a notebook is taken in like Upload notebook (Otter prepares an autograded one again; the
    grader must be up, otherwise 503 and nothing imported). If an assignment with the **same title and the
    same file** is already there, the lesson links to it instead of making a copy. New assignments are
    drafts for the same people as the lessons: they must be published for the links to show to students.
  - All or nothing: everything is read and checked first, then stored in one transaction. A picture or
    notebook missing from the file only empties its block, with a warning in the result.
  - At most 100 MB and 200 lessons per file; Export refuses a file that Import would not take back.
    The dev proxy limit in `frontend/next.config.ts` went from 12 MB to 101 MB for it (dev only).
- Routes: `GET /api/teach/lessons.zip?ids=3,1,2` and `POST /api/teach/lesson-imports` (form: `file`,
  `for` = none / everyone / course id), teachers only. Shared on the way: `grading.autograded_fields`
  (Upload notebook uses it too), `lessons.check_shape`, `exports.file_stem`, `assignments.create(commit=False)`.
- No database change, no new setting. On the server: `git pull`, `docker compose up -d --build`. A proxy
  UTEP puts in front must let 101 MB requests through to the import (deploy/README.md).

### Checked
- 18 new tests (`test/api/test_lesson_zip.py`): the round trip on the same platform (picture bytes, blocks,
  linked to the same assignment, no student answers in the file), "another platform" with a plain and an
  autograded notebook given to a course, grader down, who may use it, missing files, 12 kinds of refused
  file leaving no rows, size limits. Breaking the request-size entry or the assignment match makes them
  fail. All 151 backend tests, ruff, tsc and ESLint pass.
- In the dev browser against a real backend on a throwaway Postgres (port 5436, deleted afterwards),
  logged in as a test teacher: the export through the site (fetched in the page), importing it on the same
  platform for a course (linked to the existing notebook) and into an emptied platform (new draft
  assignment), the picture shown in the imported lesson, a refused export ("No such lesson." on the page)
  and a file that is not a .zip. Teach > Lessons and the dialog at 768, 1024 and 1440 px, light.
- 2026-10-20, on the main checkout's `./dev.sh` (real grader and hub, dev database), as a throwaway
  teacher `zip-teacher`; the test lessons and assignments were deleted afterwards. No bug found.
  - Autograded notebook through the real grader: `assignments/otter-example/functions.ipynb` uploaded as
    "Zip check: functions" (autograded, 5 points), linked from a lesson "TLS Basics", exported, lesson and
    assignment deleted, the .zip imported in the dialog (~15 s). Otter ran again (grader log: /prepare,
    /grade). The new assignment is autograded, 5 points (q1 2, q2 3), its master byte for byte the
    original file (md5), the students' version different (solutions out); the lesson links to it.
  - Large file through the dev proxy: a lesson with 9 random-noise pictures of 4.6 MB, exported in the
    page (39.6 MB) and imported in the dialog at :3000: 201, all 9 pictures byte for byte the same. So
    `middlewareClientMaxBodySize: "101mb"` works (before, 12 MB). The list's Export of 5 lessons made an
    84 MB file through the proxy too.
  - The three Export entries clicked in the dev browser, really saving into ~/Downloads (asked first):
    the editor's ⋯ and a lesson's ⋯ save `tls-basics-2026-10-20.zip` (2209 bytes; the second replaced
    the first, the pane does not add "(1)"), the list's Export `3-lessons-2026-10-20.zip` (1.2 MB, the
    name by design for several lessons). Each opens as a lessons export (`unzip -l`).
  - The file picker: picking `tls-basics-2026-10-20.zip` from Downloads in the OS picker (done by me
    by hand) and importing it: 201, the lesson came in linked to the same "Zip check: functions" (same
    title and file), no second assignment. Also the field's change path with a file put in from the page.
  - Teach > Lessons, a lesson's ⋯ menu and the Import dialog (a file chosen, the "not a .zip" error) in
    Standard dark, Halloween light and dark, Retro 95 light and dark at 1024 px, Retro 95 dark at 768:
    readable, nothing overlapping, no sideways scroll. Themes set on the page only.
  - Seen, not changed: during an import the drop area says "Uploading…" also while Otter runs.
  - Left behind on purpose: the test teacher `zip-teacher` (id 34) in the dev database, and the two
    files in ~/Downloads.

### Not verified
- A file close to the 100 MB limit (39.6 MB imported, 84 MB exported).
- Importing an autograded notebook that needs a GPU, and the grader being down during a real import
  (both only in the tests).

## Changing an assignment's notebook after upload (2026-10-19)
- Asked how to add the grading (Otter's cells) to a notebook already uploaded. The assignment's
  Settings tab now has "Change the notebook": Edit in JupyterLab (a copy at `editing/<slug>/<name>` in
  my own notebook files; for an autograded one the version with solutions) then Use my edits, or upload
  a new version. Otter runs as at upload: with Otter's cells it becomes autograded, without them graded
  by hand (out of 100 again unless I set the points).
- Decision: only until the first student opens it or hands one in; teachers trying it out do not count.
  After that, a corrected notebook is a new assignment, as before: the student's copy has the old
  public tests.
- Pressing Edit in JupyterLab again opens my copy with my edits in it; Start over replaces them.
- A student opening it while a new notebook is being saved waits for that (the save locks the
  assignment's row; opening records the open before copying the notebook), so nobody gets the old file
  after a replace. Tested by holding the lock with a timeout.
- My own try-out copy under `assignments/<slug>/` is not updated by a replace: delete it in JupyterLab.
- The editing copy (hidden tests included) sits in my notebook files next to opened submissions:
  one more reason never to run an opened submission there.
- The platform runs Otter Assign itself (grader service, `otter assign`), at upload and at a replace:
  the teacher never makes the autograder .zip; it is kept in the database.
- Verified: pytest, ruff, tsc, ESLint. End to end on the dev site with the real hub and grader, with
  throwaway accounts check-teacher / check-student: plain notebook replaced by the Otter example in
  12 s (5 points), editing copy out and back unchanged, the student's open, 409 after it, the student's
  submission autograded (0 of 5). The Settings tab at 768 / 1024 / 1440 px light, and 768 dark; the
  locked tab at 768.
- Not verified: the three buttons clicked in the page (the same requests were made from a script), and
  choosing a file in the drop area.

## Light and dark for every theme (2026-10-19)
- Asked for light and dark mode for the three themes. Before: Standard followed the device, Halloween
  was always dark, Retro 95 always light.
- Decision (chosen from two options): every theme follows the device by default, and My account >
  Appearance has "Light or dark": Match my device / Light / Dark, saved with the account like the theme
  (`users.color_mode`, migration `2026_10_19_1800-8d4a2f6c1b90_account_color_mode.py`, same
  `PUT /api/auth/theme` with `mode`). A `cyberai_mode` cookie draws the first paint, as for the theme.
- New versions: Halloween light (bone white page, purple ink, burnt-orange accent, the bar stays
  midnight, code stays a midnight block, the cobweb drawn in purple); Retro 95 dark (dark grey windows
  and bevels, black fields and lists, light-blue accents, deep teal desktop, a black editor). Retro's
  hard-coded whites and blacks became colours (`--field`, `--focus-line`, `--frame`, ...).
- Retro 95 light's green on grey was 3.95:1; now 4.87:1 (`--gpu` 17% instead of 20%).
- The dark colours are written twice (device dark, and chosen dark): no `light-dark()`, which needs
  iPadOS 17.5+. `test/test_themes_css.py` keeps the copies the same, checks every version sets every
  colour, and the contrast in all six versions.
- On the server: `git pull`, `docker compose up -d --build`, run the migrations (new column).
- Verified: pytest, ruff, tsc, ESLint. In the dev browser, with the theme set on the page only (my
  admin account's saved choice untouched): every theme x choice x device setting gives the right
  colours (18 cases read from the page); Home, a lesson with code, Teach > Assignments and the account
  menu in Halloween light and Retro 95 dark at 1024; Halloween light at 768, Retro 95 dark at 1440; the
  Appearance pictures following light and dark.
- Not verified: pressing Light / Dark in Appearance (it would have saved to my account; the API is
  tested); the login page in the new versions; Halloween's bats sit over "Admin" in the bar at 768,
  as before in dark.


## Data files (datasets) beside an assignment's notebook (2026-10-20)
- Asked for: upload a dataset with the notebook "so the lesson runs with it", and each student has a copy.
- Teach > Assignments > Upload notebook: **Data files (optional)**, several at once. The Settings tab's
  **Files** section lists them (download), and until the first student opens the assignment: remove (asks
  first) and **Add data files** (same name = replaces). Messages show under the list, not at the top.
- Each student gets their own copy beside the notebook (`assignments/<slug>/`) when they open the
  assignment (`copy_data_files` in `api/app/jupyter/launch.py`): only files they do not have, never
  overwriting theirs, a deleted one comes back. At most 4 copies at once, so a class opening it together
  does not fill the backend's memory. The teacher's Edit in JupyterLab copy gets them too.
- Autograded: the grading service puts the data beside the notebook for `otter assign` and adds Otter's
  `files:` list to the ASSIGNMENT CONFIG when the notebook has none, so the autograder zip carries them and
  Otter copies them beside every submission (grading has no network). Its prepare script now copies
  `<notebook>-autograder_*.zip`, not `*.zip`: Otter copies data files into dist/autograder too, so a
  dataset .zip broke the old one. Every change of data files has Otter prepare the notebook again.
- Decided (not asked): 20 files and 50 MB per assignment (every student gets a copy; the grader reads back
  at most 64 MB); names kept as they are (refused, not renamed, when not plain: letters, digits, `. _ -`,
  spaces); no folders (a .zip instead); locked once a student has it, like the notebook. Constants, not
  settings in deploy/.env, for now.
- Stored in Postgres: table `assignment_files` (migration `2026_10_20_1600-2e7c9b4d1f58`). Routes:
  `POST /api/teach/assignments` takes `data` fields; `POST|GET|DELETE /api/teach/assignments/<id>/data-files[/<name>]`.
  Command line: `import-assignment ... --data FILE`. Lesson .zip export carries them beside the notebook
  (`"data"` in each notebook entry); import matches an existing assignment only with the same data files.
- On the server: `git pull`, `docker compose up -d --build` (the grader changed), run the migration. With
  `./dev.sh --lan`, restarting it does both.

### Checked
- 13 new tests (`test/api/test_assignment_files.py`): copies for a student, never overwritten, deleted one
  back, locked after a student opened it, add/replace/remove, notebook replace keeps them, editing copy,
  Otter given the data on upload and on each change (and a refusal keeps the old set), refused names and
  limits, lesson .zip round trip, the `files:` the grader writes. Breaking the copy on launch or the data
  sent to Otter makes them fail. All 179 backend tests, ruff, tsc and ESLint pass.
- Real Otter 7.0.0 (the CyberP env, same version as the notebook image), running the grader's own steps:
  `otter assign` with ports.csv and a .zip beside the notebook put both in the autograder zip, and grading
  a filled-in student notebook in a folder with only the notebook and the autograder scored 2/2, a hidden
  test checking the .zip was there.
- In the browser (a copy of the frontend on :3013, its own backend and throwaway database): upload with two
  data files, the Files list, a refused name, adding one, removing one; Upload and Settings at 768, 1024,
  1440 px, light.

### Not verified
- A student opening it through a real JupyterHub (the tests use the stand-in hub), and a real grader
  container (the steps were run with Otter on the Mac, not in Docker). The dev stack was in use by another
  session.
- Large data (only up to 1.2 MB was tried) and many students opening at once. Dark, Halloween and Retro 95.
- The dev stack running on 2026-10-20 has the grader built before this change: an autograded notebook
  with data files fails there ("Otter could not prepare") until `./dev.sh` is restarted (it rebuilds the grader).

## Ideas (not built)

### A classroom address instead of the IP and port: `http://cyberai.local` (2026-10-19)
- The name: the machine announces `cyberai.local` by itself, no DNS server needed (Mac: System
  Settings > General > Sharing > Local hostname = `cyberai`; Ubuntu: hostname `cyberai` + `avahi-daemon`).
  iPads, Macs and Windows find it. A bare `cyberai` needs a DNS entry on a router I control, and
  students would still have to type `cyberai/`.
- Works today, with the port: `DEV_HOST=cyberai.local ./dev.sh --lan`, students open
  `http://cyberai.local:3000`. DEV_HOST in lowercase: browsers send it lowercase and the backend
  compares the origin exactly (`api/app/main.py`), so `samusMP-2.local` would refuse every login.
- Without the port, dev.sh: frontend on port 80, and dev.sh must write APP_ORIGIN without `:80`
  (browsers leave the default port out of Origin). The hub can stay on 8081: students never type it.
- Without the port, server stack: Caddy is already on 80/443. `APP_DOMAIN=http://cyberai.local` and
  `APP_ORIGIN=http://cyberai.local`, plus a second announced name for the hub under it
  (`hub.cyberai.local`), so site and hub stay same-site for the hub's cookie.
- Limits: plain http, because no certificate can be issued for a `.local` name, so passwords cross
  the room unencrypted: use a classroom router of my own, not campus Wi-Fi. Campus Wi-Fi often blocks
  `.local` names between devices anyway.
- Not verified: avahi announcing a two-part name like `hub.cyberai.local`; Caddy with `http://` inside
  `APP_DOMAIN`.
