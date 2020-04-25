FROM ubuntu:18.04

# Add project source
WORKDIR /usr/src/musicbot
COPY . ./
ENV DEBIAN_FRONTEND noninteractive

# Install dependencies
RUN apt-get -y update
RUN apt-get -y upgrade

RUN apt-get -y install build-essential unzip \
&& apt-get -y install software-properties-common \
&& apt-get -y update \
&& apt-get -y install git ffmpeg libopus-dev libffi-dev libsodium-dev python3-pip

RUN python3 -m pip install -U -r requirements.txt

# Create volume for mapping the config
VOLUME /usr/src/musicbot/config

ENV APP_ENV=docker

ENTRYPOINT ["python3", "run.py"]
