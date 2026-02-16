FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Runtime deps for healthcheck + Playwright install.
RUN apt-get update \
  && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
  && python -m playwright install --with-deps chromium

COPY scraper /app/scraper
COPY scripts /app/scripts
COPY config.yml /app/config.yml


FROM base AS runtime

EXPOSE 8080 9108

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -fsS http://localhost:8080/health || exit 1

CMD ["python", "-m", "scraper.app"]


FROM base AS test

COPY requirements-dev.txt /app/requirements-dev.txt
RUN pip install --no-cache-dir -r /app/requirements-dev.txt

COPY tests /app/tests
COPY pytest.ini /app/pytest.ini

CMD ["pytest", "-q"]
