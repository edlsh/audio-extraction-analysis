# syntax=docker/dockerfile:1.7

# ============================================================
# Stage 1: Builder - Install dependencies with uv on glibc base
# ============================================================
FROM python:3.12-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first (layer caching optimization)
COPY pyproject.toml uv.lock README.md ./

# Install only production dependencies (no dev, no project yet)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Copy source code
COPY src/ ./src/

# Install the project itself
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Strip unnecessary files from venv to reduce size (~15-30MB savings)
RUN find /app/.venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true \
    && find /app/.venv -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true \
    && find /app/.venv -type d -name "test" -exec rm -rf {} + 2>/dev/null || true \
    && find /app/.venv -type f -name "*.pyc" -delete 2>/dev/null || true \
    && find /app/.venv -type f -name "*.pyo" -delete 2>/dev/null || true \
    && find /app/.venv -type f -name "*.pyi" -delete 2>/dev/null || true \
    && find /app/.venv -type d -name "*.dist-info" -exec sh -c 'rm -rf {}/*.txt {}/*.rst {}/*.md 2>/dev/null' \; 2>/dev/null || true \
    && rm -rf /app/.venv/lib/python*/site-packages/pip 2>/dev/null || true \
    && rm -rf /app/.venv/lib/python*/site-packages/setuptools 2>/dev/null || true \
    && rm -rf /app/.venv/lib/python*/site-packages/wheel 2>/dev/null || true

# ============================================================
# Stage 2: Runtime - Debian-based image with UPX-compressed static FFmpeg
# Using slim-bookworm to match builder's glibc for native wheel compatibility
# ============================================================
FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Copy UPX-compressed static FFmpeg binaries (~26% smaller than uncompressed)
# Static binaries work on both Alpine and Debian (no dependency issues)
COPY --from=ghcr.io/jim60105/static-ffmpeg-upx:7.1 /ffmpeg /usr/local/bin/ffmpeg
COPY --from=ghcr.io/jim60105/static-ffmpeg-upx:7.1 /ffprobe /usr/local/bin/ffprobe

# Create non-root user (Debian uses groupadd/useradd)
RUN groupadd -g 1000 appgroup \
    && useradd -u 1000 -g appgroup -s /bin/bash -m appuser

WORKDIR /app

# Copy virtual environment from builder
# Note: Built on glibc but pure-Python packages work; binary packages need glibc compat
COPY --from=builder --chown=appuser:appgroup /app/.venv ./.venv

# Copy source code from builder
COPY --from=builder --chown=appuser:appgroup /app/src ./src

# Fix Python path in venv (Debian uses /usr/local/bin/python, Alpine uses /usr/local/bin/python)
# Both use the same path so this should work!

# Create directories for input/output
RUN mkdir -p /app/input /app/output && chown -R appuser:appgroup /app/input /app/output

# Switch to non-root user
USER appuser

# Healthcheck to verify the application is functional
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from src.cli import main; print('healthy')" || exit 1

# Default entrypoint
ENTRYPOINT ["audio-extraction-analysis"]
CMD ["--help"]
