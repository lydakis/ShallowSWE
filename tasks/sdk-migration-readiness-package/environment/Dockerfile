FROM python:3.12-slim

WORKDIR /app
COPY generate_fixture.py /tmp/generate_fixture.py
RUN python /tmp/generate_fixture.py /app

ENV PYTHONPATH=/app
