# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install .

# Run as an unprivileged user. USER is numeric so Kubernetes' runAsNonRoot can verify it.
RUN groupadd --system --gid 1001 app \
 && useradd --system --uid 1001 --gid 1001 --no-create-home --shell /usr/sbin/nologin app \
 && mkdir -p /app/data && chown 1001:1001 /app/data
USER 1001:1001
ENV LLM_PROVIDER=heuristic DATABASE_PATH=/app/data/agent.db
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
CMD ["uvicorn", "field_agent.api:app", "--host", "0.0.0.0", "--port", "8000"]
