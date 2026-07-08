FROM python:3.12-slim

WORKDIR /app
COPY dispatch_app /app/dispatch_app
COPY tests /app/tests
COPY README.md /app/README.md
COPY orders.json /app/orders.json
COPY .env.nightly /app/.env.nightly
COPY .env.legacy /app/.env.legacy
COPY .env.preview /app/.env.preview
COPY .env.backfill /app/.env.backfill

ENV PYTHONPATH=/app
