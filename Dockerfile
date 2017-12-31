FROM alpine:edge

# Requirements for the system and Python
COPY requirements.txt /usr/src/MusicBot/requirements.txt
RUN apk add --no-cache build-base libintl python3 python3-dev ffmpeg opus opus-dev libffi libffi-dev rtmpdump ca-certificates libsodium libsodium-dev pkgconf && \
	SODIUM_INSTALL=system pip3 install -r /usr/src/MusicBot/requirements.txt && \
	apk del build-base opus-dev libffi-dev libsodium-dev

# Setup our main environment
WORKDIR /usr/src/MusicBot
COPY . /usr/src/MusicBot

# Create volume for mapping the config
VOLUME /usr/src/MusicBot/config

CMD ["python3", "run.py"]
