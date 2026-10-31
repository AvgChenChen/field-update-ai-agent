# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install .

RUN useradd --system --uid 1001 app && mkdir -p /app/data && chown app /app/data
USER app
ENV LLM_PROVIDER=heuristic DATABASE_PATH=/app/data/agent.db
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "field_agent.api:app", "--host", "0.0.0.0", "--port", "8000"]
