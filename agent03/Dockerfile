FROM node:22-alpine AS web-build
WORKDIR /web
COPY web/package.json ./
RUN corepack enable && pnpm install --no-frozen-lockfile
COPY web/ ./
RUN pnpm build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY app ./app
COPY migrations ./migrations
COPY scripts ./scripts
COPY alembic.ini ./
COPY --from=web-build /web/dist ./web/dist
RUN pip install --no-cache-dir .
EXPOSE 8003
CMD ["sh", "-c", "python scripts/migrate.py && python -m app.main"]

