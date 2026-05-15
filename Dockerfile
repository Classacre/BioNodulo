# syntax=docker/dockerfile:1
# BioNodulo v2 — Multi-stage container image with pixi
# Stage 1 builds the frontend. Stage 2 installs pixi environments.
# Stage 3 is the minimal runtime image with non-root user.

# ------------------------------------------------------------------------------
# Stage 1: Frontend builder
# ------------------------------------------------------------------------------
FROM node:20-slim AS frontend-builder
WORKDIR /build
COPY web/package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm install
COPY web/ ./
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 2: Pixi environment setup
# ------------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS pixi-envs
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates build-essential \
    r-base r-base-dev \
    && rm -rf /var/lib/apt/lists/*

# Install pixi
RUN curl -fsSL https://pixi.sh/install.sh | bash
ENV PATH="/root/.pixi/bin:$PATH"

WORKDIR /app
COPY pixi.toml pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/rattler \
    pixi install

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

# Copy pixi binary and environments from deps stage
COPY --from=pixi-envs /root/.pixi/bin/pixi /usr/local/bin/pixi
COPY --from=pixi-envs /app/.pixi ./.pixi
ENV PATH="/app/.pixi/envs/default/bin:/usr/local/bin:$PATH"

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
