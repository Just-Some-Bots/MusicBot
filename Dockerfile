FROM alpine:3.4

MAINTAINER Parkervcp, https://github.com/parkervcp/MusicBot

#Install dependencies
RUN apk update \
 && apk --no-cache add python3 python3-dev git ffmpeg opus libffi-dev libsodium-dev musl-dev gcc make \
 && cd /srv/ \
 && pip3 install --upgrade pip

#Add musicBot
ADD . /musicBot
WORKDIR /musicBot

#Install PIP dependencies
RUN pip install -r requirements.txt

#Add volume for configuration
VOLUME /musicBot/config

CMD python3.5 run.py
