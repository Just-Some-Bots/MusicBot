FROM ubuntu:disco

WORKDIR /usr/src/musicbot
COPY . ./

# Install dependencies
RUN apt-get -y update \
&& apt-get -y upgrade \
&& apt-get -y install build-essential unzip \
&& apt-get -y install software-properties-common \
&& apt-get -y update \
&& apt-get -y install git ffmpeg libopus-dev libffi-dev libsodium-dev python3-pip \
&& python3 -m pip install -U -r requirements.txt

# Create volume for mapping the config
VOLUME /usr/src/musicbot/config

ENV APP_ENV=docker

ENTRYPOINT ["python3", "run.py"]
