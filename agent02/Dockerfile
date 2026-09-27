ARG NODE_IMAGE=node:22-alpine
ARG BASE_IMAGE=python:3.12-slim
FROM ${NODE_IMAGE} AS web-builder

WORKDIR /web
COPY web/package.json ./
RUN npm install --no-audit --no-fund
COPY web ./
RUN npm run build

FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app
COPY --from=web-builder /web/dist ./web/dist
RUN pip install --no-cache-dir .

COPY alembic.ini ./
COPY migrations ./migrations
COPY eval ./eval
COPY scripts ./scripts

EXPOSE 8001

CMD ["python", "-m", "scripts.start_api"]
