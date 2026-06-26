# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app

# Install production dependencies cleanly using cache mounts
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Final Runtime Stage (Super lean, optimized for cold starts)
FROM python:3.11-slim-bookworm
WORKDIR /app

# Stream logs instantly to Google Cloud Logging
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

# Copy ONLY what is strictly needed for production
COPY --from=builder /app/.venv /app/.venv
COPY story_refiner /app/story_refiner

EXPOSE 8080

# Exec form prevents /bin/sh overhead for faster, cleaner execution
CMD ["python", "-m", "uvicorn", "story_refiner.main:api", "--host", "0.0.0.0", "--port", "8080"]