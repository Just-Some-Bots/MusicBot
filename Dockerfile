FROM python:3.5

MAINTAINER Sidesplitter, https://github.com/SexualRhinoceros/MusicBot

#Install and update dependencies
RUN sudo echo "deb http://httpredir.debian.org/debian jessie-backports main contrib non-free" >> /etc/apt/sources.list \
    && sudo apt-get update -y \
    && sudo apt-get install software-properties-common -y \
    && sudo apt-get install build-essential unzip -y \
    && sudo apt-get install ffmpeg -y \
    && sudo apt-get install libopus-dev -y \
    && sudo apt-get install libffi-dev -y

#Add musicBot
ADD . /musicBot
WORKDIR /musicBot

#Install PIP dependencies
RUN sudo pip install -r requirements.txt

#Add volume for configuration
VOLUME /musicBot/config

CMD ["python", "run.py"]
