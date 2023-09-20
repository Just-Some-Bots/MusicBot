---
title: Ubuntu
category: Installing the bot
order: 1
---

<img class="doc-img" src="{{ site.baseurl }}/images/ubuntu.png" alt="Ubuntu" style="width: 75px; float: right;"/>

Installing MusicBot on Ubuntu via the command line is the **recommended way to install the bot**, though the system dependencies differ depending on what version of Ubuntu you are using. Firstly, lets install the dependencies required for your system:

## Ubuntu 20.04

~~~ bash

# Install build tools
sudo apt-get install build-essential unzip -y
sudo apt-get install software-properties-common -y

# Install system dependencies
sudo apt-get update -y
sudo apt-get install git ffmpeg libopus-dev libffi-dev libsodium-dev python3-pip 
sudo apt-get upgrade -y

# Clone the MusicBot to your home directory
git clone https://github.com/Just-Some-Bots/MusicBot.git ~/MusicBot -b master
cd ~/MusicBot

# Install Python dependencies
sudo python3 -m pip install -U pip
sudo python3 -m pip install -U -r requirements.txt
~~~


## Ubuntu 18.04

~~~ bash
# Add external repositories
sudo add-apt-repository ppa:deadsnakes/ppa

# Install build tools
sudo apt-get install build-essential unzip -y
sudo apt-get install software-properties-common -y

# Install system dependencies
sudo apt-get update -y
sudo apt-get install git ffmpeg libopus-dev libffi-dev libsodium-dev python3.8
sudo apt-get upgrade -y

# Install pip
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python3.8 get-pip.py

# Clone the MusicBot to your home directory
git clone https://github.com/Just-Some-Bots/MusicBot.git ~/MusicBot -b master
cd ~/MusicBot

# Install Python dependencies
sudo python3.8 -m pip install -U pip
sudo python3.8 -m pip install -U -r requirements.txt
~~~

## Ubuntu 16.04

~~~ bash
# Install build tools
sudo apt-get install build-essential unzip -y
sudo apt-get install software-properties-common -y

# Add external repositories
sudo add-apt-repository ppa:mc3man/xerus-media -y
sudo add-apt-repository ppa:deadsnakes/ppa -y

# Install system dependencies
sudo apt-get update -y
sudo apt-get install git ffmpeg libopus-dev libffi-dev libsodium-dev python3.8 -y
sudo apt-get upgrade -y

# Install pip
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python3.8 get-pip.py

# Clone the MusicBot to your home directory
git clone https://github.com/Just-Some-Bots/MusicBot.git ~/MusicBot -b master
cd ~/MusicBot

# Install Python dependencies
python3.8 -m pip install -U pip
python3.8 -m pip install -U -r requirements.txt 
~~~


After doing those commands, you can [configure]({{ site.baseurl }}/using/configuration) the bot and then run it using `bash ./run.sh`.
