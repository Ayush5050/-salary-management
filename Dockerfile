# syntax=docker/dockerfile:1
#
# One image serving both the API and the built UI from a single origin.
#
# Two services behind a reverse proxy would be the production shape, but for a
# single-user internal tool backed by SQLite there is no second thing to scale
# independently — and one origin removes CORS from the deployment entirely.
# The split becomes worthwhile at the same point the database does; see
# docs/adr/0002-sqlite-over-postgres.md.

FROM node:22-alpine AS ui

WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# Relative, because the API is served from the same origin as the page.
ENV VITE_API_BASE_URL=/api
RUN npm run build


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/pyproject.toml ./
COPY backend/app ./app
COPY backend/scripts ./scripts
RUN pip install --no-cache-dir .

COPY --from=ui /ui/dist ./static

ENV SALARY_STATIC_DIR=/app/static \
    SALARY_DATABASE_URL=sqlite:////data/salary.db

# The database lives on a volume so a restart does not discard seeded data or
# anything added through the UI.
VOLUME ["/data"]
EXPOSE 8000

# Seeded on first boot only: re-seeding every start would silently discard
# employees added through the UI, which is exactly the surprise a demo does not
# need. PORT is honoured because most managed platforms assign one.
CMD ["sh", "-c", "[ -f /data/salary.db ] || python -m app.seed; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
