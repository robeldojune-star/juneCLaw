FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TRADING_PROJECT_ROOT=/app \
    TRADING_RUNNER_PORT=8765

WORKDIR /app

RUN pip install --no-cache-dir \
    requests \
    "psycopg[binary]" \
    pandas

CMD ["python", "scripts/trading_stage_http_server.py"]
