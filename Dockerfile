FROM python:3.15-slim AS builder

RUN apt-get update

WORKDIR /microservice

COPY requirements.txt .

RUN python3 -m venv .venv \
    && .venv/bin/pip install --no-cache-dir --upgrade pip \
    && .venv/bin/pip install --no-cache-dir -r requirements.txt

FROM python:3.15-slim AS runner

RUN apt-get update && apt-get install -y ffmpeg

RUN groupadd -g 10001 appgroup && \
    useradd -r -u 10001 -g appgroup -m -s /bin/bash appuser

WORKDIR /microservice

COPY --from=builder --chown=appuser:appgroup /microservice/.venv /microservice/.venv
COPY --chown=appuser:appgroup *.py .

USER appuser
ENV PORT=8000
CMD [ ".venv/bin/fastapi", "run" ]