# JD Lens API. Build from backend/: docker build -t jd-lens-api .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /srv

# Dependencies first (read from pyproject.toml), so code changes don't reinstall them.
# The project itself isn't pip-installed: it runs from this folder.
COPY pyproject.toml ./
RUN python -c "import tomllib; print('\n'.join(tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']))" > requirements.txt \
    && pip install -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
RUN useradd --create-home --uid 10001 api
USER api

EXPOSE 8000

# Migrations run on every start (idempotent; one instance), then the API.
# No --forwarded-allow-ips='*': that trusts the client-supplied X-Forwarded-For. The rate
# limiter gets the real client IP from Cloudflare instead (TRUST_CF_CONNECTING_IP).
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
