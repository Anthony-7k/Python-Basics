# syntax=docker/dockerfile:1.7

ARG PYTHON_VERSION=3.11.9

FROM ghcr.io/astral-sh/uv:0.12.1 AS uv

FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY --from=uv /uv /bin/uv
COPY pyproject.toml uv.lock README.md .python-version ./

RUN uv sync --locked --no-dev --no-install-project

COPY src ./src

RUN uv sync --locked --no-dev --no-editable


FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ARG APP_UID=10001

ENV HOME=/home/agent01 \
    PATH=/app/.venv/bin:$PATH \
    PYTHONPATH=/app \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid ${APP_UID} agent01 \
    && useradd --uid ${APP_UID} --gid agent01 --create-home agent01 \
    && install -d --owner=agent01 --group=agent01 \
        /app /app/data/chroma /app/data/uploads

WORKDIR /app

COPY --from=builder --chown=agent01:agent01 /app/.venv ./.venv
COPY --chown=agent01:agent01 alembic ./alembic
COPY --chown=agent01:agent01 alembic.ini ./alembic.ini
COPY --chown=agent01:agent01 app ./app
COPY --chown=agent01:agent01 frontend ./frontend

USER agent01:agent01

EXPOSE 8000 8501

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=6 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=3)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
