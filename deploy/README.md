# Jupyter integration scaffolding

The full design, diagrams and step-by-step setup are in the "Student Jupyter Platform:
Architecture & Setup" doc. File map:

| Path | Purpose |
| --- | --- |
| `deploy/docker-compose.yml`, `Caddyfile`, `.env.example` | Whole stack on one server |
| `deploy/jupyterhub/` | Hub image + `jupyterhub_config.py` (OAuth, profiles, GPU limits, iframe CSP) |
| `deploy/images/` | CPU and GPU student notebook images (build context is `deploy/images`) |
| `grader/` (project root) | Grading service: Otter-Grader in throwaway containers; built by `docker compose` |
| `deploy/scripts/host-setup.sh` | Fresh Ubuntu server: driver, Docker, NVIDIA Container Toolkit, firewall |
| `deploy/scripts/reset-student.sh` | Archive and wipe one student's home volume |
| `deploy/scripts/gpu_usage_logger.py` | Per-minute CSV of GPU use per student container |
| `deploy/examples/nextjs/` | "Open Notebook" component and Next.js headers/rewrites |
| `api/app/jupyter/` | OAuth2 provider, hub REST client, launch/stop API |

## Database and accounts on the server

Run these from `deploy/` on the server, once `deploy/.env` exists (copy `.env.example` and fill it in):

```bash
(cd images && docker build -f cpu/Dockerfile -t cyberai/notebook-cpu . && docker build -f gpu/Dockerfile -t cyberai/notebook-gpu .)
docker compose up -d --build                                             # build and start the whole stack
docker compose exec backend alembic -c ../sql/alembic.ini upgrade head   # create or update the tables
docker compose exec backend python -m app.manage create-user admin --role teacher --admin   # first admin
```

The first line builds the student notebook images, which `docker compose` does not build. They are also
what submissions are graded in, so they include Otter-Grader.

The last command asks for the password twice. It is never written to a file; Postgres only stores its
Argon2 hash. The server's database starts empty: accounts made on a laptop are not copied, so create
them again here, and give the server's admin a long password of its own.

Then log in to the site as that admin and add students and teachers under **Admin > Accounts**.

Assignments are uploaded in the site too: **Teach > Assignments** (teachers and admins) > Upload notebook,
choose who gets it, publish. Notebooks, submissions and grades are stored in Postgres, so there
is no assignments folder to create or copy to the server, and backing up the database backs them up.
Each student gets their own copy the first time they open an assignment. The project `README.md`
describes courses, submitting and grading.

Lessons are written in the site as well: **Teach > Lessons**. Their text, questions, pictures and
what students answered are stored in Postgres too, so the same database backup covers them. Videos in
lessons are played from `www.youtube-nocookie.com`, so students' browsers must be able to reach YouTube.

### Updating a server that is already running

```bash
git pull
docker compose up -d --build                                             # rebuilds the images that changed
docker compose exec backend alembic -c ../sql/alembic.ini upgrade head   # adds new tables and columns
```

Run the migration every time: a new version may need tables the old one did not have (lessons were
added this way, and the column that keeps each account's theme), and until they exist the pages that use them answer with an error.

**Once, when updating to the version that stopped sending the hub token to notebook servers**, replace
`PLATFORM_HUB_API_TOKEN`: earlier versions sent it to every student's running notebook server, where
code the student ran could have copied it. Put a new value in `deploy/.env` (from `openssl rand -hex 32`),
then run `docker compose up -d`: the backend and the hub both restart with it, and the hub forgets the
old token as it starts. The same update changes the hub's permissions in `jupyterhub/jupyterhub_config.py`,
which is built into the hub's image: the `--build` above applies it. Until both the hub and the backend
run the new version, opening and submitting notebooks fail with "The notebook service returned an error".
`PLATFORM_SESSION_SECRET` is no longer used: a value left in `deploy/.env` is simply ignored.

Every secret in `deploy/.env` must be set, or `docker compose` stops and names the missing one. The
backend also refuses to start when `PLATFORM_HUB_API_TOKEN`, `OAUTH_CLIENT_SECRET` or `GRADER_TOKEN` is
shorter than 32 characters, contains `dev-` or is still `change-me` (`api/app/config.py`): generate them
with `openssl rand -hex 32`.

### The grading service

`grader` runs Otter-Grader for autograded assignments. Student code is executed there, so it is kept
apart from everything else:

- Every job runs in a new container of the notebook image (`CPU_IMAGE`, or `GPU_IMAGE` for GPU
  assignments, without a GPU) with no network, 2 GB of memory, one CPU, at most 256 processes and five
  minutes (`GRADER_MEMORY`, `GRADER_TIMEOUT` in seconds, `GRADER_PARALLEL` jobs at once, default 2). The
  container is removed afterwards.
- The service has the Docker socket, which is root on the server, like the hub's. It has no database
  access and no published port, and sits on a network (`grading`) that only the backend is on. The
  backend authenticates with `GRADER_TOKEN` from `deploy/.env`: generate it like the other secrets.
- If it is down, uploading an autograded notebook is refused with a message, and submissions are marked
  "could not be graded"; a teacher presses **Run the autograder again** on them once it is back.
  Submissions that were waiting when the backend restarts are picked up again by themselves.

`APP_ORIGIN` in `deploy/.env` must be exactly the address people type to reach the site (for example
`https://cyberai.utep.edu`, no path). The backend refuses logins and every other change that does not
come from a page at that address.

`APP_DOMAIN` and `HUB_DOMAIN` must share a parent domain (for example both under `utep.edu`). Two
things depend on the browser sending the hub's cookie to the hub from a platform page:

- Logging in or out of the platform also ends the browser's JupyterHub session, so the next person on
  a shared computer cannot reach the previous person's notebooks. Without a shared parent domain the
  hub session stays open until it expires.
- **Admin > JupyterHub** shows JupyterHub's admin panel in a frame.

Teachers and platform admins (`--admin`) are JupyterHub admins. The hub decides this when that person's
hub session starts, so after `set-admin` they log out of the platform and in again.

Password guessing is limited: 5 wrong passwords for one username from one address, then 15 minutes of
refusals. The counters are in the backend's memory (keep one uvicorn worker, as `api/Dockerfile` does;
restarting the backend clears them), and "address" is the visitor's address as passed on by Caddy.
This relies on two things staying as they are:

- The backend is only reachable through Caddy (it has no published port in `docker-compose.yml`). It
  believes the `X-Forwarded-For` header, so anyone who could reach it directly could fake their address.
- The `Caddyfile` has no `trusted_proxies`. By default Caddy ignores an `X-Forwarded-For` sent by the
  visitor and sets the real address. If the university puts its own proxy or load balancer in front of
  this server, every visitor arrives from that proxy's address and shares one lockout counter: in that
  case add `trusted_proxies` with exactly that proxy's address, and nothing wider.

People behind one shared address (a campus network) count as one visitor per username: five wrong
guesses at a classmate's username from the same network lock that username out there for 15 minutes.

After every code update, run the first two commands again (the second does nothing when there are no
new migrations).

When `deploy/images/` changes, rebuild the student notebook images too (the first command above).
Notebook servers that are already running keep the old image until they are restarted.

How a notebook reaches a student, and a submission the backend: the backend calls that student's
running notebook server through the hub. For each of these operations it first has the hub make a
token of that student's own, which opens only that one notebook server, expires after two minutes and
is deleted as soon as the operation is done; that token is the only one the notebook server sees.
`PLATFORM_HUB_API_TOKEN` never goes to a notebook server, where code a student runs could read it.
With it the backend creates and removes hub users, starts and stops their servers, sets their groups
and makes those tokens (`platform-role` in `jupyterhub/jupyterhub_config.py`). It cannot open a notebook
server itself, but because it can make a token for any user it still reaches every notebook home in
the end: keep it only in `deploy/.env`. To replace it, change it in `deploy/.env` and run
`docker compose up -d`: the hub forgets the old token when it starts.

More account commands (same tool, `api/app/manage.py`):

```bash
docker compose exec backend python -m app.manage set-admin maria          # or: set-admin maria --remove
docker compose exec backend python -m app.manage set-password maria       # choose a password; logs the account out everywhere
docker compose exec backend python -m app.manage create-user maria --name "Maria Lopez"   # same as Add account in the site
docker compose exec backend python -m app.manage list-users
```

From a script, pass the password on standard input and add `-T`:
`printf '%s\n' "$PASSWORD" | docker compose exec -T backend python -m app.manage create-user maria`
