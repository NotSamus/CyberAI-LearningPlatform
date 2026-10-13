import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app import admin, assignments, auth, config, lesson_routes, lessons, submissions, teach
from app.jupyter import launch, oauth

# How large a request may be. Nearly everything sent here is a few lines of JSON; the exceptions
# are a teacher uploading a notebook, or a picture for a lesson. Anything bigger is cut off while it
# arrives, logged in or not, so nobody can fill the server's memory or disk with one request.
MAX_REQUEST_BYTES = 1024 * 1024
MAX_UPLOAD_REQUEST_BYTES = assignments.MAX_NOTEBOOK_BYTES + 1024 * 1024
LARGER_REQUESTS = {
    ("POST", "/api/teach/assignments"): MAX_UPLOAD_REQUEST_BYTES,
    ("POST", "/api/teach/lesson-images"): lessons.MAX_IMAGE_BYTES + 1024 * 1024,
}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Submissions that were waiting for the autograder when the backend last stopped go back to it.
    try:
        waiting = await run_in_threadpool(submissions.waiting_for_the_autograder)
    except SQLAlchemyError:
        waiting = []                    # the database is not up (yet): nothing to pick up
    tasks = [asyncio.create_task(submissions.grade_submission(*one)) for one in waiting]
    yield
    for task in tasks:
        task.cancel()


app = FastAPI(
    title="cyberAI-Platform API",
    version="0.3.0",
    lifespan=lifespan,
)

# No CORS middleware on purpose: the browser only talks to the frontend origin, which forwards
# /api and /oauth here (Next.js rewrites in dev, Caddy in production).

app.include_router(auth.router)      # /api/auth/login, /api/auth/logout
app.include_router(admin.router)     # /api/admin/users  (admins only)
app.include_router(teach.router)     # /api/teach/...  (teachers and admins only)
app.include_router(lesson_routes.teach_router)   # /api/teach/lessons/...  (teachers and admins only)
app.include_router(lesson_routes.router)         # /api/lessons: read a lesson, answer its knowledge checks
app.include_router(oauth.router)     # /oauth/authorize, /oauth/token, /oauth/userinfo  (JupyterHub login)
app.include_router(launch.router)    # /api/me, /api/assignments (the ones this person may see), launch + stop


@app.middleware("http")
async def refuse_cross_site_writes(request: Request, call_next):
    """Only this site's own pages may change anything here. Browsers send an Origin header with every
    write that comes from another address, including the hub's, where students' notebook code runs
    with the visitor's cookies in reach. Server-to-server calls (the hub's /oauth/token) send none."""
    origin = request.headers.get("origin")
    if request.method not in ("GET", "HEAD", "OPTIONS") and origin and origin != config.APP_ORIGIN.rstrip("/"):
        return JSONResponse({"detail": f"This request did not come from {config.APP_ORIGIN}."}, status_code=403)
    return await call_next(request)


class LimitRequestSize:
    """Refuses requests larger than `max_bytes` (or the larger limit given for that method and path):
    at once when the Content-Length header says so, and otherwise while the body arrives (a sender
    can leave that header out). The app is then told the sender went away, so it stops reading, and
    whatever it answers after that is dropped."""

    def __init__(self, app, max_bytes: int, larger: dict[tuple[str, str], int] | None = None):
        self.app, self.max_bytes, self.larger = app, max_bytes, larger or {}

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        max_bytes = self.larger.get((scope["method"], scope["path"].rstrip("/")), self.max_bytes)
        megabytes = max_bytes // (1024 * 1024)
        too_large = JSONResponse({"detail": f"This request is larger than {megabytes} MB."}, status_code=413)
        declared = dict(scope["headers"]).get(b"content-length", b"0")
        if declared.isdigit() and int(declared) > max_bytes:
            return await too_large(scope, receive, send)
        received, answering, refused = 0, False, False

        async def counting_receive():
            nonlocal received, refused
            message = {"type": "http.disconnect"} if refused else await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > max_bytes:
                    refused = True
                    if not answering:
                        await too_large(scope, receive, send)
                    return {"type": "http.disconnect"}
            return message

        async def send_unless_refused(message):
            nonlocal answering
            if not refused:
                answering = True
                await send(message)

        await self.app(scope, counting_receive, send_unless_refused)


app.add_middleware(LimitRequestSize, max_bytes=MAX_REQUEST_BYTES, larger=LARGER_REQUESTS)


@app.exception_handler(OperationalError)
async def database_unreachable(request: Request, exc: OperationalError):
    return JSONResponse({"detail": "The database is not reachable right now. Try again in a minute."}, status_code=503)


@app.get("/")
def root():
    return {"name": "cyberAI-Platform API", "status": "ok", "docs": "/docs"}


@app.get("/api/health")
def health():
    return {"status": "healthy"}
