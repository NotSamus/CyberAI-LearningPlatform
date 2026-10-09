# Grading service: runs Otter-Grader on notebooks, each time in a new locked-down container of the
# student notebook image. It needs the Docker socket for that (root-equivalent, like the hub's), so
# it has no database access and no published port: only the backend talks to it.
FROM python:3.12-slim
WORKDIR /srv/grader
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
