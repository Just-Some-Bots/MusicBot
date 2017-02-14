FROM ubuntu:14.04

MAINTAINER Sidesplitter, https://github.com/SexualRhinoceros/MusicBot

#Install dependencies
RUN sudo apt-get update \
    && sudo apt-get install software-properties-common -y \
    && sudo add-apt-repository ppa:fkrull/deadsnakes -y \
    && sudo add-apt-repository ppa:mc3man/trusty-media -y \
    && sudo apt-get update -y \
    && sudo apt-get install build-essential unzip -y \
    && sudo apt-get install python3.5 python3.5-dev -y \
    && sudo apt-get install ffmpeg -y \
    && sudo apt-get install libopus-dev -y \
    && sudo apt-get install libffi-dev -y

#Install Pip
RUN sudo apt-get install wget \
    && wget https://bootstrap.pypa.io/get-pip.py \
    && sudo python3.5 get-pip.py

#Add musicBot
ADD . /musicBot
WORKDIR /musicBot

#Install PIP dependencies
RUN sudo pip install -r requirements.txt

#Add volume for configuration
VOLUME /musicBot/config

CMD python3.5 run.py
