FROM python:3.15-alpine AS builder

WORKDIR /microservice

COPY requirements.txt .

RUN python3 -m venv .venv \
    && .venv/bin/pip install --no-cache-dir --upgrade pip \
    && .venv/bin/pip install --no-cache-dir -r requirements.txt

FROM python:3.15-alpine AS runner

RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /microservice

COPY --from=builder --chown=appuser:appgroup /microservice/.venv /microservice/.venv
COPY --chown=appuser:appgroup *.py .

USER appuser
ENV PORT=8000
CMD [ ".venv/bin/fastapi", "run" ]