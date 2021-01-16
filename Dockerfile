FROM ubuntu:20.04

RUN apt-get update
RUN apt-get install software-properties-common -y

# Install dependencies
RUN add-apt-repository ppa:deadsnakes/ppa
RUN apt-get update
RUN apt-get install python3.7 -y

# Install build tools
RUN apt-get install build-essential unzip -y
RUN apt-get install software-properties-common -y

# Install system dependencies
RUN apt-get update -y
RUN apt-get install git ffmpeg libopus-dev libffi-dev libsodium-dev python3-pip -y
RUN apt-get upgrade -y

# Add project source
WORKDIR /app
COPY . ./

# Install Python dependencies
RUN python3.7 -m pip install -U pip
RUN python3.7 -m pip install -U -r requirements.txt

# Create volume for mapping the config
# VOLUME /app/config

ENV APP_ENV=docker

RUN python3.7 dockerentry.py

ENTRYPOINT ["python3.7", "run.py"]
