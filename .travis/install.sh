#!/bin/bash

if [[ $TRAVIS_OS_NAME == 'osx' ]]; then
    brew install git
    brew install ffmpeg
    brew install opus
    brew install libffi
    brew install libsodium  
    python3 -m pip install -U pip
    python3 -m pip install -U -r requirements.txt
else
    sudo apt-get install build-essential unzip -y
    sudo apt-get install software-properties-common -y
    sudo add-apt-repository ppa:deadsnakes -y
    sudo add-apt-repository ppa:mc3man/trusty-media -y
    sudo add-apt-repository ppa:chris-lea/libsodium -y
    sudo apt-get update -y
    sudo apt-get install git python3.5-dev libav-tools libopus-dev libffi-dev libsodium-dev python3-pip -y
    sudo apt-get upgrade -y
    sudo python3 -m pip install -U pip
    sudo python3 -m pip install -U -r requirements.txt
fi