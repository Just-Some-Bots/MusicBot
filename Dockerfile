# syntax=docker/dockerfile:1.7.0

# Build stage
FROM python:3.8-alpine3.20 AS builder

# pip env vars
ENV PIP_NO_CACHE_DIR=off
ENV PIP_DISABLE_PIP_VERSION_CHECK=on
ENV PIP_DEFAULT_TIMEOUT=100

# standardise on locale, don't generate .pyc, enable tracebacks on seg faults
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONFAULTHANDLER=1

# set locale
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Install build dependencies
RUN apk update && apk add --no-cache \
    build-base \
    libffi-dev \
    libsodium-dev \
    git \
    && rm -rf /var/cache/apk/*

WORKDIR /musicbot

# Install pip and dependencies
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.8-alpine3.20 AS runner

# pip env vars
ENV PIP_NO_CACHE_DIR=off
ENV PIP_DISABLE_PIP_VERSION_CHECK=on
ENV PIP_DEFAULT_TIMEOUT=100

# standardise on locale, don't generate .pyc, enable tracebacks on seg faults
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONFAULTHANDLER=1

# set locale
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Install runtime dependencies
RUN apk update && apk add --no-cache \
    ca-certificates \
    ffmpeg \
    git \
    libffi \
    libsodium \
    opus-dev \
    && rm -rf /var/cache/apk/*

# Copy only necessary files from builder stage
COPY --from=builder /usr/local/lib/python3.8/site-packages /usr/local/lib/python3.8/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

WORKDIR /musicbot
COPY . .
COPY ./config sample_config

# Create volumes for audio cache, config, data and logs
VOLUME ["/musicbot/audio_cache", "/musicbot/config", "/musicbot/data", "/musicbot/logs"]

ENV APP_ENV=docker

ENTRYPOINT ["/bin/sh", "docker-entrypoint.sh"]

LABEL org.opencontainers.image.title="musicbot"
