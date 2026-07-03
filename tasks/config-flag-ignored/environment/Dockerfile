FROM python:3.12-slim

WORKDIR /app
COPY dispatch_app /app/dispatch_app
COPY tests /app/tests
COPY README.md /app/README.md
COPY orders.json /app/orders.json
COPY .env.nightly /app/.env.nightly

ENV PYTHONPATH=/app
