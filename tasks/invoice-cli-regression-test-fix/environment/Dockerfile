FROM python:3.12-slim

WORKDIR /app
COPY invoice_tool /app/invoice_tool
COPY tests /app/tests
COPY sample_invoices.csv /app/sample_invoices.csv

ENV PYTHONPATH=/app
