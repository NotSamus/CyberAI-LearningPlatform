# Graph Report - CyberAI-LearningPlatform  (2026-10-28)

## Corpus Check
- 159 files · ~112,087 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 29 file(s) not represented in the graph (top: (none) 16, .css 4, .ipynb 3)

## Summary
- 1986 nodes · 5415 edges · 87 communities (74 shown, 13 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 449 edges (avg confidence: 0.91)
- Token cost: 302,084 input · 0 output

## Community Hubs (Navigation)
- Lesson Editor UI
- Teacher Dashboard UI
- Project Decisions (notes.md)
- Admin & Announcement Pages
- Grader Service & Lesson Tests
- Assignments API
- Auth & Login Sessions
- Lesson Routes API
- Page Shell & Error Handling
- Lesson Zip Import/Export
- Users, Admin & DB Deps
- Submissions API
- Course Exports (Excel)
- Courses & Announcements API
- Grading Pipeline
- Security Tests
- Student Home & Lesson Reader
- Grading Tests
- Frontend API Client & Hooks
- Notebook Launch & Submit
- Assignment & Course Tests
- Auth & Theme Tests
- Top Bar, Themes & Account
- Notebook Editing Copies
- Lesson Progress Models
- Lesson Answers & Checks
- Database Migrations
- Test Fixtures (conftest)
- API & Hub Tests
- Assignment Data File Tests
- Lesson Zip Tests
- Prod Backend Env Vars
- Lesson Blocks Rendering
- TypeScript Config
- App Entry & Middleware
- dev.sh Local Runner
- Progress Page & Empty States
- JupyterHub File Client
- Frontend Dev Dependencies
- Test Database Compose
- Assignments & Grading Docs
- Markdown Rendering Deps
- Migration Env & Account Tests
- Python Requirements
- Local Dev Stack Docs
- Dev Backend Env Vars
- Database Models
- Prod Networks & Volumes
- Prod Frontend/Backend Services
- OAuth Provider
- Prod Grader Env Vars
- Lessons Feature Docs
- Code Highlighting
- Hub User & Server Control
- JupyterHub Integration Docs
- Security Hardening Docs
- Fake Hub Test Double
- Username Tests
- Accounts & Admin Docs
- Prod Caddy Service
- Prod Postgres Service
- Dev Compose Structure
- Deployment Setup Docs
- Testing Docs
- Dev Postgres Service
- Dev Grader Service
- Hub Client Tests
- Username Suggestions
- Dev JupyterHub Service
- Settings & GPU Docs
- Frontend npm Scripts
- Config & Weak Secrets
- Lesson Pictures
- Dev DB Healthcheck
- Prod JupyterHub Service
- ESLint Config
- Fake Grader Fixture
- Next.js Embed Example
- dev-tunnel.sh
- check.sh
- Next.js Config
- host-setup.sh
- reset-student.sh

## God Nodes (most connected - your core abstractions)
1. `message()` - 103 edges
2. `PlatformUser` - 97 edges
3. `api()` - 96 edges
4. `Assignment` - 57 edges
5. `lucide-react` - 54 edges
6. `notes.md (project decisions, how-tos and status log)` - 53 edges
7. `react` - 52 edges
8. `User` - 44 edges
9. `LessonEditor()` - 41 edges
10. `next` - 40 edges

## Surprising Connections (you probably didn't know these)
- `Dialog focus fix (autoFocus ran before the dialog opened)` --references--> `Dialog()`  [EXTRACTED]
  notes.md → frontend/components/Dialog.tsx
- `Production migration (docker compose exec backend alembic upgrade head)` --semantically_similar_to--> `Updating a running server (git pull, build, migrate)`  [INFERRED] [semantically similar]
  sql/README.md → deploy/README.md
- `Admins reset other admins' passwords` --references--> `reset_password()`  [EXTRACTED]
  notes.md → api/app/admin.py
- `Admin rights given from the site` --references--> `set_admin()`  [EXTRACTED]
  notes.md → api/app/admin.py
- `Top bar Home / Teach / Admin areas` --references--> `counts()`  [EXTRACTED]
  notes.md → api/app/assignments.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Local dev stack started by dev.sh** — readme_dev_sh, readme_postgres_database, readme_jupyterhub, readme_grading_service, readme_fastapi_backend, readme_nextjs_frontend [EXTRACTED 1.00]
- **Hub token least-privilege model** — deploy_readme_scoped_hub_tokens, deploy_readme_platform_role, deploy_readme_hub_token_rotation, deploy_readme_jupyter_api, readme_scoped_hub_tokens [INFERRED 0.85]
- **Autograding pipeline (submit, isolated Otter run, gradebook)** — readme_submissions, readme_grading_service, readme_otter_grader, deploy_readme_notebook_images, readme_gradebook, readme_data_files [INFERRED 0.85]
- **Admin actions guarded by re-typing your own password** — notes_admin_rights_from_site, notes_admin_password_reset, notes_reauth_guess_limit, api_app_auth_confirm_password [EXTRACTED 1.00]
- **Otter autograding pipeline (assign, isolated grading, points check)** — notes_otter_grader, notes_grader_service, notes_otter_assign_format, notes_question_points_check, notes_assignment_data_files [INFERRED 0.85]
- **Lesson authoring and delivery** — notes_lesson_block_editor, notes_lesson_working_vs_published, notes_knowledge_checks, notes_picture_questions, notes_lesson_topic_index, notes_lesson_zip [INFERRED 0.85]

## Communities (87 total, 13 thin omitted)

### Community 0 - "Lesson Editor UI"
Cohesion: 0.05
Nodes (65): save(), LessonEditorPage(), AddHere(), ChoiceEditor(), addOption(), Growing(), ImportText(), add() (+57 more)

### Community 1 - "Teacher Dashboard UI"
Cohesion: 0.11
Nodes (49): AssignmentPage(), Grade, GradeForm(), Row(), statusOf(), AssignmentsPage(), CourseContent(), Attention (+41 more)

### Community 2 - "Project Decisions (notes.md)"
Cohesion: 0.05
Nodes (24): _active_gpu_spawners(), _forget_stored_service_tokens(), _hub_admins(), pre_spawn_hook(), App Icon (favicon, Next.js app/icon.svg), Brand Blue Gradient (hsl 226/82/40 to hsl 215/89/14), Shield Emblem with Cyan Core (cybersecurity brand mark), nextConfig (+16 more)

### Community 3 - "Admin & Announcement Pages"
Cohesion: 0.07
Nodes (58): MyAccount(), submit(), AccountsPage(), remove(), resetPassword(), AddAccountDialog(), AddAccountForm(), submit() (+50 more)

### Community 4 - "Grader Service & Lesson Tests"
Cohesion: 0.07
Nodes (36): counting_receive(), send_unless_refused(), _archive(), authorized(), _checked(), _failure(), grade(), health() (+28 more)

### Community 5 - "Assignments API"
Cohesion: 0.07
Nodes (30): a_student_has_it(), AssignmentError, audience(), check_data_files(), check_description(), check_due_at(), check_notebook(), check_points() (+22 more)

### Community 6 - "Auth & Login Sessions"
Cohesion: 0.08
Nodes (29): reset(), AccountError, authenticate(), change_password(), check_name(), check_new_username(), check_password(), choose_theme() (+21 more)

### Community 7 - "Lesson Routes API"
Cohesion: 0.08
Nodes (27): Answer, answer_question(), change_lesson(), Changes, complete_lesson(), create_lesson(), delete_lesson(), _details() (+19 more)

### Community 8 - "Page Shell & Error Handling"
Cohesion: 0.13
Nodes (34): HubPage(), CourseLayout(), RenameDialog(), CoursesPage(), NewCourseDialog(), create(), Filter, LessonsPage() (+26 more)

### Community 9 - "Lesson Zip Import/Export"
Cohesion: 0.07
Nodes (26): file_stem(), export_lessons(), _Contents, export(), _Files, Found, _json(), _lesson() (+18 more)

### Community 10 - "Users, Admin & DB Deps"
Cohesion: 0.08
Nodes (18): _account(), AccountChanges, AdminRights, change_user(), create_user(), delete_user(), list_users(), _new_password() (+10 more)

### Community 11 - "Submissions API"
Cohesion: 0.09
Nodes (27): Submission, details(), get(), grade_by_hand(), _iso(), notebook_bytes(), of_assignment(), of_user() (+19 more)

### Community 12 - "Course Exports (Excel)"
Cohesion: 0.08
Nodes (23): _download(), export_course(), export_everyone(), load(), _number(), _out_of(), plain_text(), Platform (+15 more)

### Community 13 - "Courses & Announcements API"
Cohesion: 0.09
Nodes (26): announcement(), announcements_for(), check_announcement(), check_name(), CourseError, save(), set_students(), student_ids() (+18 more)

### Community 14 - "Grading Pipeline"
Cohesion: 0.07
Nodes (21): _ask_grader(), autograded_fields(), _cell_text(), checked(), grade(), GraderUnreachable, GradingError, is_otter_master() (+13 more)

### Community 15 - "Security Tests"
Cohesion: 0.07
Nodes (32): client(), client_at(), login(), no_hub(), set_admin(), test_a_new_password_ends_the_notebook_login_and_an_admins_is_logged(), test_a_new_password_is_given_while_the_hub_is_unreachable(), test_a_planted_cookie_is_not_adopted_at_login() (+24 more)

### Community 16 - "Student Home & Lesson Reader"
Cohesion: 0.10
Nodes (33): LessonPage(), Home(), Announcements(), Row(), byCourse(), CourseGroup, courseName(), FOR_EVERYONE (+25 more)

### Community 17 - "Grading Tests"
Cohesion: 0.07
Nodes (26): lab(), otter(), grade(), otter_master(), prepare(), otter_results(), replace(), solve() (+18 more)

### Community 18 - "Frontend API Client & Hooks"
Cohesion: 0.10
Nodes (32): SettingsIndex(), AddDataFiles(), add(), Audience, EditAssignment(), submit(), NewAssignmentPage(), submit() (+24 more)

### Community 19 - "Notebook Launch & Submit"
Cohesion: 0.10
Nodes (22): counts(), get_visible(), list_visible(), summary(), _visible_to(), names(), copy_data_files(), get_assignment() (+14 more)

### Community 20 - "Assignment & Course Tests"
Cohesion: 0.09
Nodes (28): test_a_copy_that_cannot_be_made_is_reported(), test_a_corrected_notebook_under_the_same_title_reaches_students(), test_an_admin_can_teach_whatever_their_role(), test_an_upload_from_someone_who_may_not_teach_is_refused_unread(), test_download_and_delete(), test_import_assignment_from_the_command_line(), test_only_student_accounts_can_be_given_an_assignment(), test_opening_gives_each_student_their_own_copy_once() (+20 more)

### Community 21 - "Auth & Theme Tests"
Cohesion: 0.09
Nodes (22): data_file_name(), container_for_pid(), sh(), client(), login(), manage(), test_account_rules(), test_command_line_tool() (+14 more)

### Community 22 - "Top Bar, Themes & Account"
Cohesion: 0.13
Nodes (28): Appearance(), choose(), isDeviceDark(), watchDeviceDark(), metadata, RootLayout(), landing(), LoginPage() (+20 more)

### Community 23 - "Notebook Editing Copies"
Cohesion: 0.10
Nodes (19): PlatformUser, put_file(), me(), notebook_url(), running_server(), put(), add_data_files(), _changeable_or_409() (+11 more)

### Community 24 - "Lesson Progress Models"
Cohesion: 0.10
Nodes (21): visible_lesson(), add_image(), answers_of(), audience(), closed_counts(), complete(), content(), get_visible() (+13 more)

### Community 25 - "Lesson Answers & Checks"
Cohesion: 0.11
Nodes (21): _accepted(), answer(), _answer_key(), AssignmentLink, Callout, Code, _correct_ids(), Image (+13 more)

### Community 26 - "Database Migrations"
Cohesion: 0.11
Nodes (9): upgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade(), upgrade() (+1 more)

### Community 27 - "Test Fixtures (conftest)"
Cohesion: 0.08
Nodes (11): manage(), alembic(), db(), empty_db_url(), hub(), migrated_db_url(), no_leftover_login_attempts(), no_real_hub() (+3 more)

### Community 28 - "API & Hub Tests"
Cohesion: 0.08
Nodes (11): fake_hub(), logged_in(), test_database_down_is_reported(), test_environment_still_starting(), test_gpu_notebooks_turned_off(), test_hub_error_response_is_not_called_unreachable(), test_hub_refusal_is_passed_to_student(), test_launch_cpu_and_gpu() (+3 more)

### Community 29 - "Assignment Data File Tests"
Cohesion: 0.12
Nodes (14): add(), otter(), otter_master(), prepare(), stored(), test_an_autograded_notebook_is_prepared_with_its_data(), test_data_file_names_that_are_refused(), test_data_files_are_added_and_removed_until_a_student_has_it() (+6 more)

### Community 30 - "Lesson Zip Tests"
Cohesion: 0.23
Nodes (16): blocks(), bring_in(), export(), opened(), otter_master(), stored(), test_a_lesson_goes_out_as_a_zip_and_comes_back_in(), test_files_that_are_refused_leave_nothing_behind() (+8 more)

### Community 31 - "Prod Backend Env Vars"
Cohesion: 0.11
Nodes (21): environment, APP_ORIGIN, CPU_PROFILE_CPUS, CPU_PROFILE_MEM, DATABASE_URL, DOCKER_NETWORK_NAME, GPU_IDS, GPU_NOTEBOOKS (+13 more)

### Community 32 - "Lesson Blocks Rendering"
Cohesion: 0.18
Nodes (18): Answered, checkAnchor(), CheckHead(), Choice, ChoiceCheck(), LessonBlocks(), Outcome(), tone() (+10 more)

### Community 33 - "TypeScript Config"
Cohesion: 0.11
Nodes (18): compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules, jsx, lib, module (+10 more)

### Community 34 - "App Entry & Middleware"
Cohesion: 0.12
Nodes (6): database_unreachable(), health(), LimitRequestSize, refuse_cross_site_writes(), root(), test_size_limits_by_route()

### Community 35 - "dev.sh Local Runner"
Cohesion: 0.14
Nodes (16): APP_ORIGIN, BACKEND_URL, cleanup(), compose_dev(), DEV_HOST, GRADER_TOKEN, HUB_API_TOKEN, HUB_ORIGIN (+8 more)

### Community 36 - "Progress Page & Empty States"
Cohesion: 0.27
Nodes (10): AdminLayout(), TeachLayout(), LessonProgressPage(), EmptyState(), Person(), ProgressBar(), Tab, Tabs() (+2 more)

### Community 37 - "JupyterHub File Client"
Cohesion: 0.19
Nodes (7): _contents_url(), file_names(), FileTooLarge, get_file(), has_file(), HubError, _notebook_server()

### Community 38 - "Frontend Dev Dependencies"
Cohesion: 0.16
Nodes (16): devDependencies, eslint@9.39.5, eslint-config-next@15.5.25, @types/node@^22.10.0, @types/react@^19.0.0, @types/react-dom@^19.0.0, typescript@^5.7.0, name (+8 more)

### Community 39 - "Test Database Compose"
Cohesion: 0.12
Nodes (15): environment, healthcheck, image, ports, tmpfs, POSTGRES_DB, POSTGRES_PASSWORD, POSTGRES_USER (+7 more)

### Community 40 - "Assignments & Grading Docs"
Cohesion: 0.18
Nodes (16): Grading service isolation (server), Moving lessons between platforms via .zip, CPU and memory caps for notebook servers and grading jobs, Edit in JupyterLab / Replace notebook (before first open), Assignments, Autograded vs hand-graded assignments, Courses and announcements, Current limits (known limitations) (+8 more)

### Community 41 - "Markdown Rendering Deps"
Cohesion: 0.12
Nodes (16): dependencies, hast-util-to-jsx-runtime@2.3.6, lowlight@3.3.0, lucide-react@1.48.0, next@^15.1.0, react@^19.0.0, react-dom@^19.0.0, react-markdown@10.1.0 (+8 more)

### Community 42 - "Migration Env & Account Tests"
Cohesion: 0.15
Nodes (5): run_migrations_offline(), test_choosing_a_theme(), test_choosing_light_or_dark(), test_only_teachers_and_admins_export(), browser()

### Community 43 - "Python Requirements"
Cohesion: 0.17
Nodes (14): api/requirements.txt (backend dependencies), et-xmlfile 2.0.0, fastapi 0.115.6, openpyxl 3.1.5, pydantic 2.10.4, python-multipart 0.0.20, uvicorn[standard] 0.34.0, grader/requirements.txt (grading service dependencies) (+6 more)

### Community 44 - "Local Dev Stack Docs"
Cohesion: 0.19
Nodes (14): alembic 1.20.0, psycopg[binary] 3.3.6, sqlalchemy 2.1.1, Alembic database migrations (sql/), Assignment data files (datasets), dev-hub.sh (local JupyterHub in Docker), dev.sh (start everything locally), dev-tunnel.sh (SSH tunnel to a server) (+6 more)

### Community 45 - "Dev Backend Env Vars"
Cohesion: 0.14
Nodes (14): APP_ORIGIN, CLEANUP_SERVERS, DEV_FAKE_GPU, DOCKER_NETWORK_NAME, GPU_NOTEBOOKS, GPU_PROFILE_MEM, HUB_ORIGIN, JUPYTERHUB_CRYPT_KEY (+6 more)

### Community 46 - "Database Models"
Cohesion: 0.21
Nodes (5): Base, AssignmentOpen, AssignmentStudent, CourseStudent, LessonImage

### Community 47 - "Prod Networks & Volumes"
Cohesion: 0.15
Nodes (12): internal, internal, name, networks, data, grading, jupyter-users, web (+4 more)

### Community 48 - "Prod Frontend/Backend Services"
Cohesion: 0.17
Nodes (13): NEXT_PUBLIC_HUB_ORIGIN, build, networks, restart, args, context, dockerfile, build (+5 more)

### Community 49 - "OAuth Provider"
Cohesion: 0.32
Nodes (5): authorize(), _check_client(), _purge(), token(), userinfo()

### Community 50 - "Prod Grader Env Vars"
Cohesion: 0.17
Nodes (12): CPU_IMAGE, GPU_IMAGE, GRADER_MEMORY, GRADER_PARALLEL, GRADER_TIMEOUT, GRADER_TOKEN, build, environment (+4 more)

### Community 51 - "Lessons Feature Docs"
Cohesion: 0.20
Nodes (10): deploy/examples/nextjs Open Notebook component, Code syntax highlighting (highlight.js via lowlight/rehype-highlight), Lesson blocks (text, code, callout, picture, video, notebook, questions), Lesson working copy and Publish, Write or paste a whole lesson as text, Lessons, Next.js + TypeScript frontend, Refactoring UI (book) (+2 more)

### Community 52 - "Code Highlighting"
Cohesion: 0.23
Nodes (8): CodeBlock(), HeadingProps, HIGHLIGHT, ALIASES, highlighted(), LANGUAGES, lowlight, Code colouring (lowlight + rehype-highlight)

### Community 53 - "Hub User & Server Control"
Cohesion: 0.20
Nodes (5): _client(), delete_user(), ensure_user(), start_server(), stop_server()

### Community 54 - "JupyterHub Integration Docs"
Cohesion: 0.22
Nodes (8): httpx 0.28.1, One-time PLATFORM_HUB_API_TOKEN rotation, api/app/jupyter (OAuth2 provider, hub REST client, launch/stop API), jupyterhub_config.py (OAuth, profiles, GPU limits, iframe CSP), platform-role hub permissions, Teachers stop being JupyterHub admins (2026-10-19), Updating a running server (git pull, build, migrate), Roles: student, teacher, admin flag

### Community 55 - "Security Hardening Docs"
Cohesion: 0.24
Nodes (6): nbformat 5.11.1, Caddy reverse proxy, Password-guessing lockout behind Caddy (in-memory, one uvicorn worker), Caddy trusted_proxies (university proxy), Upload security checks, Security test suite (test_security.py and teacher-API tests)

### Community 57 - "Username Tests"
Cohesion: 0.24
Nodes (4): client(), login(), test_only_admins_get_suggestions(), test_students_are_known_by_their_username_only()

### Community 58 - "Accounts & Admin Docs"
Cohesion: 0.22
Nodes (8): argon2-cffi 25.1.0, Admin action log (docker compose logs backend), Accounts (no public sign-up), Admin > Accounts management, Admin area (/admin), Argon2 password hashing, app.manage command line tool, Gamertag-style username suggestions (api/app/usernames.py)

### Community 59 - "Prod Caddy Service"
Cohesion: 0.22
Nodes (9): environment, image, networks, ports, restart, volumes, APP_DOMAIN, HUB_DOMAIN (+1 more)

### Community 60 - "Prod Postgres Service"
Cohesion: 0.22
Nodes (9): environment, image, networks, restart, volumes, POSTGRES_DB, POSTGRES_PASSWORD, POSTGRES_USER (+1 more)

### Community 61 - "Dev Compose Structure"
Cohesion: 0.22
Nodes (8): name, networks, users, services, name, volumes, hub-data, pg-data

### Community 62 - "Deployment Setup Docs"
Cohesion: 0.33
Nodes (9): Jupyter integration scaffolding (deploy README), Production docker-compose stack (docker-compose.yml, Caddyfile, .env.example), host-setup.sh (fresh Ubuntu server setup), CPU and GPU student notebook images, reset-student.sh (archive and wipe a student's home volume), First server setup: images, stack, migration, first admin, cyberAI-Platform README, Student Jupyter Platform: Architecture & Setup (doc) (+1 more)

### Community 63 - "Testing Docs"
Cohesion: 0.36
Nodes (7): api/requirements-dev.txt (test and lint tools), pytest 9.1.1, ruff 0.16.10, check.sh (all checks), Lint: ruff and ESLint, pytest suite (test/), Migration tests (apply, roll back, match models)

### Community 64 - "Dev Postgres Service"
Cohesion: 0.25
Nodes (8): environment, image, ports, volumes, POSTGRES_DB, POSTGRES_PASSWORD, POSTGRES_USER, db

### Community 65 - "Dev Grader Service"
Cohesion: 0.25
Nodes (8): CPU_IMAGE, GPU_IMAGE, GRADER_TOKEN, build, environment, ports, volumes, grader

### Community 66 - "Hub Client Tests"
Cohesion: 0.39
Nodes (5): test_a_large_file_goes_in_pieces_with_one_token(), test_a_refused_token_stops_before_the_notebook_server(), test_file_operations_never_send_the_service_token_to_a_notebook_server(), test_hub_api_calls_carry_the_service_token(), test_the_token_is_deleted_also_when_the_operation_fails()

### Community 68 - "Dev JupyterHub Service"
Cohesion: 0.29
Nodes (7): build, extra_hosts, networks, ports, stop_grace_period, volumes, jupyterhub

### Community 69 - "Settings & GPU Docs"
Cohesion: 0.29
Nodes (7): APP_ORIGIN origin check, GPU notebooks turned off (server), gpu_usage_logger.py (per-minute GPU use CSV), APP_DOMAIN and HUB_DOMAIN share a parent domain, Settings (environment variables, deploy/.env), GPU_NOTEBOOKS toggle (GPU notebooks turned off), DATABASE_URL target database

### Community 70 - "Frontend npm Scripts"
Cohesion: 0.29
Nodes (7): scripts, build, dev, lint, start, test, typecheck

### Community 72 - "Lesson Pictures"
Cohesion: 0.40
Nodes (3): lesson_image(), get_image(), picture_ids()

### Community 73 - "Dev DB Healthcheck"
Cohesion: 0.40
Nodes (5): healthcheck, interval, retries, test, timeout

### Community 74 - "Prod JupyterHub Service"
Cohesion: 0.40
Nodes (5): build, networks, restart, volumes, jupyterhub

### Community 75 - "ESLint Config"
Cohesion: 0.40
Nodes (4): compat, config, @eslint/eslintrc@3.3.7, @eslint/eslintrc

### Community 79 - "dev-tunnel.sh"
Cohesion: 0.83
Nodes (3): lan_address(), port_in_use(), dev-tunnel.sh script

## Ambiguous Edges - Review These
- `Tests use their own throwaway Postgres (port 5434)` → `Migration tests (apply, roll back, match models)`  [AMBIGUOUS]
  sql/README.md · relation: conceptually_related_to

## Knowledge Gaps
- **22 isolated node(s):** `DEV_HOST`, `LISTEN_ADDRESS`, `HUB_API_TOKEN`, `OAUTH_CLIENT_SECRET`, `GRADER_TOKEN` (+17 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 630 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Lessons as a list of blocks (Markdown, not WYSIWYG)` connect `Project Decisions (notes.md)` to `Lesson Blocks Rendering`, `Lesson Editor UI`, `Lesson Routes API`, `Student Home & Lesson Reader`, `Code Highlighting`, `Lesson Answers & Checks`?**
  _High betweenness centrality (0.215) - this node is a cross-community bridge._
- **Are the 82 inferred relationships involving `PlatformUser` (e.g. with `_account()` and `change_user()`) actually correct?**
  _`PlatformUser` has 82 INFERRED edges - model-reasoned connections that need verification._
- **What connects `DEV_HOST`, `LISTEN_ADDRESS`, `HUB_API_TOKEN` to the rest of the system?**
  _22 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Lesson Editor UI` be split into smaller, more focused modules?**
  _Cohesion score 0.04841772151898734 - nodes in this community are weakly interconnected._
- **Why does `notes.md (project decisions, how-tos and status log)` connect `Project Decisions (notes.md)` to `Lesson Editor UI`, `Teacher Dashboard UI`, `Code Highlighting`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Are the 47 inferred relationships involving `Assignment` (e.g. with `audience()` and `counts()`) actually correct?**
  _`Assignment` has 47 INFERRED edges - model-reasoned connections that need verification._

### Low-confidence Hints
_AMBIGUOUS edges — the extractor was unsure. Verify before acting on these._

- **What is the exact relationship between `Tests use their own throwaway Postgres (port 5434)` and `Migration tests (apply, roll back, match models)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._