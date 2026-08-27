# Production image for wecarwpm (:8090) — Python 3.12 multi-stage, non-root (agent.md)
FROM python:3.12-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=run.py \
    APP_UID=10001 \
    APP_GID=10001

WORKDIR /app

LABEL org.opencontainers.image.source="https://github.com/JTY9410/wecar_wpm"

RUN apt-get update && apt-get install -y --no-install-recommends \
    gosu \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid ${APP_GID} appuser \
    && useradd --uid ${APP_UID} --gid ${APP_GID} --create-home --shell /usr/sbin/nologin appuser

COPY --from=builder /install /usr/local
COPY . .
RUN chmod +x entrypoint.sh \
    && mkdir -p /app/instance \
    && chown -R appuser:appuser /app

# Entrypoint starts as root to chown bind-mounted ./instance, then gosu → appuser
USER root
EXPOSE 5000
ENTRYPOINT ["./entrypoint.sh"]
