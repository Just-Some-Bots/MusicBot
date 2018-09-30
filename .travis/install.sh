#!/bin/bash

if [[ $TRAVIS_OS_NAME == 'osx' ]]; then
    brew install git
    brew install ffmpeg
    brew install opus
    brew install libffi
    brew install libsodium  
else
    sudo apt-get install build-essential unzip -y
    sudo apt-get install software-properties-common -y
    sudo add-apt-repository ppa:deadsnakes -y
    sudo add-apt-repository ppa:mc3man/trusty-media -y
    sudo add-apt-repository ppa:chris-lea/libsodium -y
    sudo apt-get update -y
    sudo apt-get install git libav-tools libopus-dev libffi-dev libsodium-dev -y
fi
