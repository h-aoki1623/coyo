# Stage 1: Build dependencies with uv
#
# IMPORTANT: The Python image tag MUST be identical in both the builder and
# runtime stages. The builder produces a virtualenv whose internal symlinks
# (e.g., python3.12) are tied to the builder's interpreter. If the runtime
# tag drifts, those symlinks break and the container fails to start.
FROM python:3.12-slim AS builder

# Install uv from the official distroless image (digest-pinned for supply-chain safety).
# To refresh: `docker buildx imagetools inspect ghcr.io/astral-sh/uv:<version>`
COPY --from=ghcr.io/astral-sh/uv:0.7.19@sha256:2dcbc74e60ed6d842122ed538f5267c80e7cde4ff1b6e66a199b89972496f033 /uv /uvx /usr/local/bin/

WORKDIR /app

# uv settings:
#   - UV_LINK_MODE=copy: avoid hardlink warnings when /tmp and /app are on different filesystems
#   - UV_COMPILE_BYTECODE=1: precompile .pyc for faster startup
#   - UV_PYTHON_DOWNLOADS=never: use the system Python (do not let uv download a managed one)
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    VIRTUAL_ENV=/app/.venv

COPY pyproject.toml ./
COPY src/ ./src/

RUN uv venv "$VIRTUAL_ENV" \
    && uv pip install --no-cache .

# Stage 2: Runtime
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy the prebuilt virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Make the venv binaries the default
ENV PATH="/app/.venv/bin:$PATH" \
    VIRTUAL_ENV=/app/.venv

# Copy source code and alembic config
COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY src/ ./src/

# Create non-root user
RUN adduser --disabled-password --gecos "" appuser
USER appuser

EXPOSE 8080

CMD ["uvicorn", "coyo.main:app", "--host", "0.0.0.0", "--port", "8080"]
