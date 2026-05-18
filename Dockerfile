# syntax=docker/dockerfile:1.7
#
# One image, six container roles (web / worker / beat / bot / migrate / one-off).
# Roles differ only by command, not by code or deps — keeps the build cache hot
# and the compose file readable.
#
# uv handles the Python env. Playwright Chromium is baked in for the detail
# enricher; `--with-deps` pulls in the apt packages the browser needs.

FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:/root/.local/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# --- uv (pinned base image is reproducible enough; uv self-updates rarely break) ---
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /usr/local/bin/

WORKDIR /app

# --- Dependency layer (cached on pyproject + lockfile only) ---
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Playwright browser + system deps. Heavy (~300 MB), keep as its own layer so it
# doesn't re-run when only Python code changes.
RUN uv run playwright install --with-deps chromium && \
    rm -rf /var/lib/apt/lists/*

# --- App code ---
COPY . .

# Final sync to install the project itself (now that the code is present).
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Django expects to be run from webapp/.
WORKDIR /app/webapp

EXPOSE 8000

# Default command runs the web server; compose overrides per service.
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
