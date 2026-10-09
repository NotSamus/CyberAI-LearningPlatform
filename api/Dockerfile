FROM python:3.12-slim
# Built from the project root (see deploy/docker-compose.yml) so the image also gets sql/.
WORKDIR /srv/api
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY api/app ./app
COPY sql /srv/sql
# One worker: the OAuth code/token stores are in memory (see app/jupyter/oauth.py)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
