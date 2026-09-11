FROM python:3.12-slim

WORKDIR /app

# Unbuffered stdout/stderr so gunicorn and app logs appear in Railway's
# log viewer immediately rather than sitting in a pipe buffer.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# Single worker, threaded - in-memory job tracking (jobs/registry.py)
# assumes one process, so this must not be scaled to multiple workers
# or multiple Railway replicas. PORT is injected by Railway; 8080 is
# the local fallback. Access logs go to stdout so Railway captures them.
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 8 --timeout 120 --graceful-timeout 30 --access-logfile - --error-logfile - app:app"]
