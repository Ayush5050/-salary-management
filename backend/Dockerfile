# syntax=docker/dockerfile:1

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Source is copied before the install rather than after, so that `pip install .`
# builds the real package. This does mean a code change re-resolves
# dependencies; splitting them into a cached layer needs a placeholder package
# that the real source later shadows, and that indirection is not worth the
# rebuild seconds on an image this small.
COPY pyproject.toml ./
COPY app ./app
COPY scripts ./scripts

RUN pip install --no-cache-dir .

# The database lives on a volume so a container restart does not discard the
# seeded data.
ENV SALARY_DATABASE_URL=sqlite:////data/salary.db
VOLUME ["/data"]

EXPOSE 8000

# Seed on first start only. Re-seeding on every boot would silently discard any
# employee added through the UI — exactly the surprise a demo does not need.
CMD ["sh", "-c", "[ -f /data/salary.db ] || python -m app.seed; exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
