# syntax=docker/dockerfile:1.7.0

FROM python:3.8-alpine3.20

# Add project source
WORKDIR /musicbot
COPY . ./
COPY ./config sample_config

# Install build dependencies
RUN apk update && apk add --no-cache --virtual .build-deps \
    build-base \
    libffi-dev \
    libsodium-dev \
    && rm -rf /var/cache/apk/*

# Install dependencies
RUN apk update && apk add --no-cache \
    ca-certificates \
    ffmpeg \
    gcc \
    git \
    libffi \
    libsodium \
    opus-dev \
    && rm -rf /var/cache/apk/*

# pip env vars
ENV PIP_NO_CACHE_DIR=off
ENV PIP_DISABLE_PIP_VERSION_CHECK=on
ENV PIP_DEFAULT_TIMEOUT=100

# don't generate .pyc, enable tracebacks on seg faults
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONFAULTHANDLER=1

# Install pip dependencies
RUN python -m pip install --no-cache-dir -r requirements.txt

# Clean up build dependencies
RUN apk del .build-deps

# Create volumes for audio cache, config, data and logs
VOLUME ["/musicbot/audio_cache", "/musicbot/config", "/musicbot/data", "/musicbot/logs"]

ENV APP_ENV=docker

ENTRYPOINT ["/bin/sh", "docker-entrypoint.sh"]

LABEL org.opencontainers.image.title="musicbot"
