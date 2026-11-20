# One image, two entry points:
#   Cloud Run Job : python -m jobs.run_bench   (default CMD)
#   Cloud Run API : added in the API milestone
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TASKS_PATH=/app/tasks \
    TARGETS_PATH=/app/config/targets.yaml

WORKDIR /app

# Dependencies first so code changes don't invalidate this layer.
COPY pyproject.toml README.md ./
COPY app/__init__.py app/__init__.py
COPY jobs/__init__.py jobs/__init__.py
RUN pip install .

COPY app ./app
COPY jobs ./jobs
COPY tasks ./tasks
COPY config ./config

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 bench
USER bench

CMD ["python", "-m", "jobs.run_bench"]
