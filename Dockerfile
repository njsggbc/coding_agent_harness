FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY harness/ harness/
COPY config.yaml .

RUN pip install --no-cache-dir -e .

ENTRYPOINT ["harness"]