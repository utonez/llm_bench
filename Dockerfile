# One image, two entry points:
#   Cloud Run Job : python -m jobs.run_bench   (default CMD)
#   Cloud Run API : added in the API milestone
#
# Supply chain: the base image is pinned by digest and every dependency is installed
# from requirements.lock with --require-hashes, so a build is reproducible and a
# tampered or unexpected package fails the build instead of entering the image.
# Regenerate the lock (in this same image) with:
#   pip-compile --generate-hashes --strip-extras --allow-unsafe -o requirements.lock pyproject.toml
FROM python:3.13-slim@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TASKS_PATH=/app/tasks \
    TARGETS_PATH=/app/config/targets.yaml

WORKDIR /app

# Dependencies first (only the lock file), so code changes don't invalidate this layer.
COPY requirements.lock ./
RUN pip install --require-hashes -r requirements.lock

COPY pyproject.toml README.md ./
COPY app/__init__.py app/__init__.py
COPY jobs/__init__.py jobs/__init__.py
RUN pip install --no-deps .

COPY app ./app
COPY jobs ./jobs
COPY tasks ./tasks
COPY config ./config
COPY frontend ./frontend

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 bench
USER bench

CMD ["python", "-m", "jobs.run_bench"]
