# syntax=docker/dockerfile:1
# BioNodulo v2 — Multi-stage container image
# Stage 1 builds the frontend. Stage 2 installs the Python app into a venv (pip).
# Stage 3 is the minimal runtime image with non-root user.

# ------------------------------------------------------------------------------
# Stage 1: Frontend builder
# ------------------------------------------------------------------------------
FROM node:24-slim AS frontend-builder
WORKDIR /build
COPY web/package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm install
COPY web/ ./
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 2: Python dependency build
# Installs the bionodulo package + its dependencies into an isolated venv using
# pip against pyproject.toml (same source of truth as CI: `pip install -e .`).
# ------------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV PATH="/opt/venv/bin:$PATH"

# Files hatchling needs to build the wheel metadata (readme + license) plus the
# package source. Root entrypoints (main.py/server.py/lambda_handler.py) are not
# installed — they run from the working dir at runtime.
COPY pyproject.toml README.md LICENSE ./
COPY bionodulo ./bionodulo
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m venv /opt/venv \
    && pip install --upgrade pip \
    && pip install .

# ------------------------------------------------------------------------------
# Stage 3: Runtime
# ------------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    git wget curl ca-certificates \
    r-base r-base-dev \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy the pre-built virtualenv from the deps stage
COPY --from=deps /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY . .

# Copy built frontend from stage 1
COPY --from=frontend-builder /build/dist ./web/dist

# Create runtime directories and set permissions
RUN mkdir -p workspace runs cache environments custom_nodes \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1
CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "8000"]
