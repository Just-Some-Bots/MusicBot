FROM python:3.7-alpine as build

# Prepare build environment
RUN apk add --no-cache \
  opus \
  libsodium-dev \
  gcc \
  git \
  libffi-dev \
  make \
  musl-dev

# Build dependencies
COPY ./requirements.txt ./requirements.txt
RUN pip3 wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# Build plugins that refresh more often to keep cache
COPY ./requirements-plugins.txt ./requirements-plugins.txt
RUN pip3 wheel --no-cache-dir --wheel-dir /wheels -r requirements-plugins.txt

# Install wheels in clean environment
FROM python:3.7-alpine
COPY --from=build /wheels /wheels
RUN pip install --no-cache /wheels/*

# Install opus for voice transfer, gcc is needed for ctypes access
RUN apk add --no-cache \
  ca-certificates \
  ffmpeg \
  opus \
  gcc \
  && ln -s /usr/lib/libopus.so.0 /usr/lib/libopus.so

# Set working directory
WORKDIR /musicbot

# Add project sources
COPY . ./

# Inject config folder volume
VOLUME /musicbot/config

# Override default starting point
ENV APP_ENV=docker
CMD ["python3", "dockerentry.py"]
