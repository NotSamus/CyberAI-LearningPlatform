"""Grading service: prepares autograded assignments and grades submissions with Otter-Grader.

Notebooks contain code written by students (and teachers), so it never runs here. Each job gets its
own container made from the student notebook image, with no network, limited memory, CPU, processes
and time, and it is thrown away afterwards. Files go in and come out through the Docker API.

    POST /prepare   a teacher's master notebook -> the students' version + the autograder package
    POST /grade     a student's notebook + the autograder package -> scores per question

Only the platform backend calls this (api/app/grading.py), with the token in GRADER_TOKEN.
"""
import base64
import hmac
import io
import json
import os
import re
import tarfile
import threading

import docker
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from requests.exceptions import ConnectionError as WaitTimeout, ReadTimeout

TOKEN = os.environ["GRADER_TOKEN"]
IMAGES = {
    "cpu": os.environ.get("CPU_IMAGE", "cyberai/notebook-cpu:latest"),
    # GPU assignments are graded in the GPU image (it has the libraries), but without a GPU attached.
    "gpu": os.environ.get("GPU_IMAGE", "cyberai/notebook-gpu:latest"),
}
TIMEOUT = int(os.environ.get("GRADER_TIMEOUT", "300"))          # seconds one job may take
MEMORY = os.environ.get("GRADER_MEMORY", "2g")
MAX_PARALLEL = int(os.environ.get("GRADER_PARALLEL", "2"))
MAX_OUTPUT_BYTES = 64 * 1024 * 1024                            # what is read back out of a container
HOME = "/home/jovyan"                                          # the notebook image's user: jovyan, uid 1000, gid 100
JOB = "job"                                                    # the job's folder inside HOME
NOTEBOOK_NAME = re.compile(r"[A-Za-z0-9._-]{1,100}\.ipynb")

app = FastAPI(title="cyberAI grader")
_slots = threading.BoundedSemaphore(MAX_PARALLEL)


class JobFailed(Exception):
    def __init__(self, reason: str, log: str = ""):
        super().__init__(reason)
        self.reason, self.log = reason, log


def authorized(authorization: str = Header("")) -> None:
    if not hmac.compare_digest(authorization.encode(), f"Bearer {TOKEN}".encode()):
        raise HTTPException(401, "wrong grader token")


def _archive(files: dict[str, bytes]) -> bytes:
    """A tar of the job folder, owned by the notebook user so the job can write next to the files."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        folder = tarfile.TarInfo(JOB)
        folder.type, folder.mode, folder.uid, folder.gid = tarfile.DIRTYPE, 0o775, 1000, 100
        tar.addfile(folder)
        for name, content in files.items():
            info = tarfile.TarInfo(f"{JOB}/{name}")
            info.size, info.mode, info.uid, info.gid = len(content), 0o664, 1000, 100
            tar.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


def _read_file(container, path: str) -> bytes | None:
    """One file out of the (stopped) container, or None when the job did not produce it."""
    try:
        stream, _ = container.get_archive(f"{HOME}/{JOB}/{path}")
    except docker.errors.NotFound:
        return None
    buffer = io.BytesIO()
    for chunk in stream:
        buffer.write(chunk)
        if buffer.tell() > MAX_OUTPUT_BYTES:
            raise JobFailed("The job produced a file that is too large.")
    buffer.seek(0)
    with tarfile.open(fileobj=buffer) as tar:
        member = tar.next()
        return tar.extractfile(member).read() if member and member.isfile() else None


def run_job(image: str, script: str, notebook: str, files: dict[str, bytes], outputs: list[str]) -> tuple[dict[str, bytes], str]:
    """Runs `script` (bash, in the job folder, with $NOTEBOOK set) in a new container and returns
    the output files it produced and the tail of what it printed."""
    client = docker.from_env()
    with _slots:
        try:
            client.images.get(image)
        except docker.errors.ImageNotFound:
            raise HTTPException(503, {"reason": f"The notebook image {image} is not built on this server.", "log": ""})
        container = client.containers.create(
            image,
            ["bash", "-c", f"cd {HOME}/{JOB} && {script}"],
            environment={"NOTEBOOK": notebook},
            network_mode="none",                        # only the container's own loopback: student code cannot reach anything
            mem_limit=MEMORY, memswap_limit=MEMORY,
            nano_cpus=1_000_000_000,                    # one CPU
            pids_limit=256,                             # fork-bomb protection
            cap_drop=["ALL"],
            security_opt=["no-new-privileges"],
            labels={"cyberai": "grading-job"},
        )
        try:
            container.put_archive(HOME, _archive(files))
            container.start()
            try:
                exit_code = container.wait(timeout=TIMEOUT)["StatusCode"]
            except (ReadTimeout, WaitTimeout):
                limit = f"{TIMEOUT // 60} minutes" if TIMEOUT >= 120 else f"{TIMEOUT} seconds"
                raise JobFailed(f"It ran for more than {limit} and was stopped. Look for a loop that never ends.")
            log = container.logs(tail=200).decode(errors="replace")
            log = "\n".join(     # without the image's start-up chatter and a warning Jupyter prints on every run
                line for line in log.splitlines() if not line.startswith("INFO[") and "IPKernelApp] WARNING" not in line
            )
            if exit_code == 137:
                raise JobFailed(f"It needed more than {MEMORY.upper()} of memory and was stopped.", log)
            if exit_code != 0:
                raise JobFailed("Otter stopped with an error.", log)
            return {path: content for path in outputs if (content := _read_file(container, path)) is not None}, log
        finally:
            container.remove(force=True)


def _checked(name: str, image: str) -> str:
    if not NOTEBOOK_NAME.fullmatch(name) or image not in IMAGES:
        raise HTTPException(422, "bad notebook name or image")
    return IMAGES[image]


def _with_autograder_package(master: bytes) -> bytes:
    """Otter only builds the autograder package when the notebook's ASSIGNMENT CONFIG cell says
    `generate`. Teachers should not have to know that: it is added when missing."""
    notebook = json.loads(master)
    for cell in notebook.get("cells", []):
        source = cell.get("source", "")
        text = "".join(source) if isinstance(source, list) else source
        if cell.get("cell_type") == "raw" and text.lstrip().startswith("# ASSIGNMENT CONFIG"):
            if not re.search(r"^generate\s*:", text, re.MULTILINE):
                cell["source"] = text.rstrip("\n") + "\ngenerate: true"
            return json.dumps(notebook).encode()
    raise HTTPException(400, "This notebook has no '# ASSIGNMENT CONFIG' cell, so Otter cannot prepare it.")


def _failure(e: JobFailed) -> HTTPException:
    return HTTPException(400, {"reason": e.reason, "log": e.log[-4000:]})


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/prepare", dependencies=[Depends(authorized)])
def prepare(name: str = Form(), image: str = Form("cpu"), notebook: UploadFile = File()):
    """`otter assign`: from the teacher's notebook (with solutions and tests) to the version students
    get and the autograder package. Otter runs the solutions against the tests while doing so, so a
    notebook whose own solutions fail its tests is refused here."""
    image = _checked(name, image)
    master = _with_autograder_package(notebook.file.read())
    script = 'otter assign --no-pdfs "$NOTEBOOK" dist && cp dist/autograder/*.zip autograder.zip && cp "dist/student/$NOTEBOOK" student.ipynb'
    try:
        files, log = run_job(image, script, name, {name: master}, ["student.ipynb", "autograder.zip"])
    except JobFailed as e:
        raise _failure(e)
    if set(files) != {"student.ipynb", "autograder.zip"}:
        raise HTTPException(400, {"reason": "Otter did not produce a student notebook and an autograder package.", "log": log[-4000:]})
    return {
        "student": base64.b64encode(files["student.ipynb"]).decode(),
        "autograder": base64.b64encode(files["autograder.zip"]).decode(),
        "log": log[-4000:],
    }


@app.post("/grade", dependencies=[Depends(authorized)])
def grade(name: str = Form(), image: str = Form("cpu"), notebook: UploadFile = File(), autograder: UploadFile = File()):
    """`otter run`: executes the student's notebook and runs every test, hidden ones included."""
    image = _checked(name, image)
    script = 'mkdir out && otter run --no-logo -a autograder.zip -o out "$NOTEBOOK"'
    try:
        files, log = run_job(image, script, name, {name: notebook.file.read(), "autograder.zip": autograder.file.read()}, ["out/results.json"])
    except JobFailed as e:
        raise _failure(e)
    try:
        return {"results": json.loads(files["out/results.json"]), "log": log[-4000:]}
    except (KeyError, ValueError):
        raise HTTPException(400, {"reason": "Otter did not produce results.", "log": log[-4000:]})
