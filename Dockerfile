# --- Stage 1: Python environment, installed by uv exactly from uv.lock ---------
FROM python:3.12-slim AS build
# Same uv version as local and CI.
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /src

# Dependencies first: this layer only rebuilds when uv.lock changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

# --- Stage 2: runtime image, without uv or sources -------------------------------
FROM python:3.12-slim

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Paris \
    HOME=/tmp \
    WAYPOINT_PORT=8503

WORKDIR /app
COPY --from=build /app/.venv /app/.venv

# Never root. The actual UID is set by compose (`user:`); this is the default.
RUN useradd --uid 1000 --no-create-home --home-dir /tmp waypoint
USER waypoint

EXPOSE 8503
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8503/healthz', timeout=4)"]
CMD ["waypoint"]
